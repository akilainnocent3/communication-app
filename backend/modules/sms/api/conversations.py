"""Admin endpoints for conversations, messages, media, contacts, blocks, notes and the dashboard."""

import re
from datetime import datetime, time
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.errors import ApiError
from common.pagination import decode_cursor, encode_cursor
from modules.audit.services import record
from modules.devices.services.manage import queue_command
from modules.devices.services.phone import address_kind, display_number, mask

from ..models import Contact, Conversation, ConversationNote, Message, MessagePart
from ..services import access, actions, media, store
from ..services.crypto import decrypt_text
from .permissions import CanUseSms
from .serializers import (
    SmsActionRequestSerializer,
    SmsActionResultSerializer,
    SmsAssigneeSerializer,
    BlockRequestSerializer,
    ContactPageSerializer,
    ConversationDetailSerializer,
    ConversationPageSerializer,
    ConversationSummarySerializer,
    SmsMessagePageSerializer,
    SmsMessageSerializer,
    SmsNoteSerializer,
    RevealSerializer,
    StarSerializer,
    contact_map,
)

PAGE_SIZE = 50
MESSAGE_PAGE = 60
SEARCH_SCAN_LIMIT = 5000
SUMMARY_RELATED = ("device", "device__office", "assigned_to", "sim_line")
FOLDERS = ("inbox", "unread", "awaiting", "assigned", "starred", "archived", "spam", "all")


def _bool(value):
    if value in (None, ""):
        return None
    return str(value).lower() in ("1", "true", "yes")


def summaries(request, rows) -> list:
    rows = list(rows)
    return ConversationSummarySerializer(rows, many=True, context={"request": request, "contacts": contact_map(rows)}).data


def search_conversations(qs, device_ids, q: str):
    """Search by contact name (plaintext) or number. Message text is encrypted and not searchable here."""
    q = q.strip()[:60]
    if not q:
        return qs
    names = Contact.objects.filter(device_id__in=device_ids, display_name__icontains=q).values_list("address", flat=True)[:200]
    condition = Q(participants_key__icontains=q)
    digits = re.sub(r"\D", "", q)
    if len(digits) >= 3:
        condition |= Q(participants_key__contains=digits)
        if digits.startswith("0"):
            condition |= Q(participants_key__contains=digits[1:])  # 0712… typed, +255712… stored
    for address in names:
        condition |= Q(participants_key__contains=address)
    return qs.filter(condition)


def filtered_conversations(user, params):
    device_param = str(params.get("device") or "all")
    if device_param == "all":
        devices = access.accessible_devices(user)
    else:
        devices = access.accessible_devices(user).filter(pk=access.get_device(user, device_param).pk)
    device_ids = list(devices.values_list("pk", flat=True))
    qs = Conversation.objects.filter(device_id__in=device_ids)
    folder = (params.get("folder") or "inbox").lower()
    if folder not in FOLDERS:
        folder = "inbox"
    if folder == "inbox":
        qs = qs.filter(is_archived=False, is_spam=False)
    elif folder == "unread":
        qs = qs.filter(is_spam=False, unread_count__gt=0)
    elif folder == "awaiting":
        qs = qs.filter(is_spam=False, is_archived=False, state=Conversation.OPEN, awaiting_since__isnull=False)
    elif folder == "assigned":
        qs = qs.filter(assigned_to=user, is_spam=False)
    elif folder == "starred":
        qs = qs.filter(Q(is_starred=True) | Q(messages__is_starred=True)).distinct()
    elif folder == "archived":
        qs = qs.filter(is_archived=True, is_spam=False)
    elif folder == "spam":
        qs = qs.filter(is_spam=True)
    if params.get("q"):
        qs = search_conversations(qs, device_ids, params["q"])
    unread = _bool(params.get("unread"))
    if unread is not None:
        qs = qs.filter(unread_count__gt=0) if unread else qs.filter(unread_count=0)
    if params.get("direction") in ("in", "out"):
        qs = qs.filter(last_direction=params["direction"])
    if params.get("sim"):
        qs = qs.filter(sim_line_id=params["sim"]) if str(params["sim"]).isdigit() else qs.none()
    if _bool(params.get("has_mms")):
        qs = qs.filter(has_mms=True)
    if params.get("assigned_to"):
        assignee = user.pk if params["assigned_to"] == "me" else params["assigned_to"]
        qs = qs.filter(assigned_to_id=assignee) if str(assignee).isdigit() else qs.none()
    if params.get("state") in (Conversation.OPEN, Conversation.DONE):
        qs = qs.filter(state=params["state"])
    if (after := parse_date(params.get("after") or "")):
        qs = qs.filter(last_message_at__gte=timezone.make_aware(datetime.combine(after, time.min)))
    if (before := parse_date(params.get("before") or "")):
        qs = qs.filter(last_message_at__lt=timezone.make_aware(datetime.combine(before, time.max)))
    return qs, folder


LIST_PARAMS = [
    OpenApiParameter("device", str, description="Device id or 'all' (every phone you can open)"),
    OpenApiParameter("folder", str, enum=list(FOLDERS)),
    OpenApiParameter("q", str, description="Contact name or number"),
    OpenApiParameter("unread", bool), OpenApiParameter("direction", str, enum=["in", "out"]), OpenApiParameter("sim", int),
    OpenApiParameter("has_mms", bool), OpenApiParameter("assigned_to", str), OpenApiParameter("state", str, enum=["open", "done"]),
    OpenApiParameter("after", str, description="YYYY-MM-DD"), OpenApiParameter("before", str, description="YYYY-MM-DD"),
    OpenApiParameter("cursor", str),
]


class ConversationListView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(parameters=LIST_PARAMS, responses=ConversationPageSerializer, operation_id="sms_conversations_list")
    def get(self, request):
        qs, folder = filtered_conversations(request.user, request.query_params)
        cursor = decode_cursor(request.query_params.get("cursor"))
        total = None if cursor else qs.count()
        pinned_first = folder == "inbox"
        if cursor and "t" in cursor and "id" in cursor:
            older = Q(last_message_at__lt=cursor["t"]) | Q(last_message_at=cursor["t"], id__lt=cursor["id"])
            if pinned_first:
                # Order is (pinned desc, time desc, id desc): after a pinned row come older pinned rows, then all others.
                qs = qs.filter((Q(is_pinned=True) & older) | Q(is_pinned=False)) if cursor.get("p") else qs.filter(Q(is_pinned=False) & older)
            else:
                qs = qs.filter(older)
        order = ("-is_pinned", "-last_message_at", "-id") if pinned_first else ("-last_message_at", "-id")
        rows = list(qs.select_related(*SUMMARY_RELATED).order_by(*order)[: PAGE_SIZE + 1])
        more = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]
        next_cursor = encode_cursor({"t": rows[-1].last_message_at.isoformat(), "id": rows[-1].pk, "p": rows[-1].is_pinned}) if more and rows else None
        return Response({"results": summaries(request, rows), "next_cursor": next_cursor, "total": total})


def conversation_stats(conversation) -> dict:
    counts = conversation.messages.aggregate(inbound=Count("id", filter=Q(direction=Message.IN)), outbound=Count("id", filter=Q(direction=Message.OUT) & ~Q(status__in=["cancelled", "expired"])))
    gaps, waiting = [], None
    for direction, date in conversation.messages.exclude(status__in=["cancelled", "expired", "queued"]).order_by("provider_date").values_list("direction", "provider_date")[:5000]:
        if direction == Message.IN:
            waiting = waiting or date
        elif waiting:
            gaps.append((date - waiting).total_seconds() / 60)
            waiting = None
    return {"first_contact_at": conversation.first_message_at, **counts, "avg_response_minutes": round(sum(gaps) / len(gaps)) if gaps else None}


def detail_payload(request, conversation):
    conversation = Conversation.objects.select_related(*SUMMARY_RELATED).get(pk=conversation.pk)
    context = {"request": request, "contacts": contact_map([conversation]), "stats": conversation_stats(conversation)}
    return ConversationDetailSerializer(conversation, context=context).data


class ConversationDetailView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(parameters=[OpenApiParameter("peek", bool)], responses=ConversationDetailSerializer, operation_id="sms_conversations_retrieve")
    def get(self, request, pk):
        conversation = access.get_conversation(request.user, pk)
        if not _bool(request.query_params.get("peek")):
            # Who read which phone's conversation, and when. Opening marks it read here and (optionally) on the phone.
            record("sms.conversation_open", request=request, target_type="sms_conversation", target_id=conversation.pk,
                   metadata={"device": conversation.device.code, "participants": [mask(a) for a in conversation.addresses]})
            if conversation.unread_count:
                conversation.messages.filter(direction=Message.IN, is_read=False).update(is_read=True)
                actions.mark_read_on_phone(conversation, request.user)
                store.refresh_conversation(conversation.pk)
        return Response(detail_payload(request, conversation))


def message_queryset():
    return Message.objects.select_related("sent_by", "sim_line").prefetch_related("parts")


class MessageListView(APIView):
    """Messages of one conversation, newest first (the UI reverses them). `q` searches inside this conversation only:
    the text is decrypted for this request and never stored decrypted."""

    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(parameters=[OpenApiParameter("cursor", str), OpenApiParameter("q", str), OpenApiParameter("after", int, description="Only messages with id greater than this (polling)")],
                   responses=SmsMessagePageSerializer, operation_id="sms_messages_list")
    def get(self, request, pk):
        conversation = access.get_conversation(request.user, pk)
        qs = message_queryset().filter(conversation=conversation)
        q = (request.query_params.get("q") or "").strip().lower()
        if q:
            matches = []
            for message in qs.order_by("-provider_date", "-id")[:SEARCH_SCAN_LIMIT]:
                if q in decrypt_text(message.encrypted_body).lower() and not message.is_sensitive:
                    matches.append(message)
                if len(matches) >= 100:
                    break
            return Response({"results": SmsMessageSerializer(matches, many=True).data, "next_cursor": None})
        cursor = decode_cursor(request.query_params.get("cursor"))
        if cursor and "t" in cursor and "id" in cursor:
            qs = qs.filter(Q(provider_date__lt=cursor["t"]) | Q(provider_date=cursor["t"], id__lt=cursor["id"]))
        rows = list(qs.order_by("-provider_date", "-id")[: MESSAGE_PAGE + 1])
        more = len(rows) > MESSAGE_PAGE
        rows = rows[:MESSAGE_PAGE]
        next_cursor = encode_cursor({"t": rows[-1].provider_date.isoformat(), "id": rows[-1].pk}) if more and rows else None
        return Response({"results": SmsMessageSerializer(rows, many=True).data, "next_cursor": next_cursor})


class ActionView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(request=SmsActionRequestSerializer, responses=SmsActionResultSerializer, operation_id="sms_conversations_actions")
    def post(self, request):
        data = SmsActionRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        rows = actions.perform(request.user, values["action"], values["conversation_ids"], assignee_id=values.get("assignee"), request=request)
        rows = Conversation.objects.filter(pk__in=[r.pk for r in rows]).select_related(*SUMMARY_RELATED)
        return Response({"conversations": summaries(request, rows)})


class RevealView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(request=None, responses=RevealSerializer, operation_id="sms_messages_reveal")
    def post(self, request, pk):
        message = access.get_message(request.user, pk, access.REVEAL)
        record("sms.reveal_sensitive", request=request, target_type="sms_message", target_id=message.pk,
               metadata={"device": message.device.code, "kind": message.sensitive_kind, "conversation": message.conversation_id})
        return Response({"body": decrypt_text(message.encrypted_body)})


class StarView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(request=StarSerializer, responses=SmsMessageSerializer, operation_id="sms_messages_star")
    def post(self, request, pk):
        message = access.get_message(request.user, pk)
        data = StarSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        message.is_starred = data.validated_data["starred"]
        message.save(update_fields=["is_starred"])
        return Response(SmsMessageSerializer(message_queryset().get(pk=message.pk)).data)


SAFE_INLINE = media.SAFE_INLINE


class MediaView(APIView):
    """MMS media: permission-checked, audited, never a public URL, and sandboxed like mail attachments."""

    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(parameters=[OpenApiParameter("download", bool)], responses={(200, "application/octet-stream"): bytes}, operation_id="sms_media_retrieve")
    def get(self, request, pk, part_id):
        message = access.get_message(request.user, pk)
        part = MessagePart.objects.filter(message=message, pk=part_id).first()
        if not part:
            raise ApiError("not_found", "This attachment was not found.", status.HTTP_404_NOT_FOUND)
        try:
            data = media.read(part)
        except media.MediaError as exc:
            raise ApiError(exc.code, exc.message, exc.status) from None
        content_type = part.content_type or "application/octet-stream"
        inline = content_type in SAFE_INLINE and not _bool(request.query_params.get("download"))
        response = HttpResponse(data, content_type=content_type if inline else "application/octet-stream")
        filename = re.sub(r'[\r\n"\\/]', "_", part.filename or f"attachment-{part.seq}")
        response["Content-Disposition"] = f"{'inline' if inline else 'attachment'}; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; img-src 'self' data:; media-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'self'; sandbox"
        response["Cache-Control"] = "private, max-age=300"
        record("sms.media_download", request=request, target_type="sms_message", target_id=message.pk, metadata={"device": message.device.code, "part": part.pk, "type": content_type})
        return response


# --- Notes ----------------------------------------------------------------------------------------------------


class NoteListView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(responses=SmsNoteSerializer(many=True), operation_id="sms_notes_list")
    def get(self, request, pk):
        conversation = access.get_conversation(request.user, pk)
        return Response(SmsNoteSerializer(conversation.notes.select_related("author"), many=True).data)

    @extend_schema(request=SmsNoteSerializer, responses={201: SmsNoteSerializer}, operation_id="sms_notes_create")
    def post(self, request, pk):
        conversation = access.get_conversation(request.user, pk)
        data = SmsNoteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        body = data.validated_data["body"].strip()[:5000]
        if not body:
            raise ApiError("validation_error", "Write a note first.")
        note = ConversationNote.objects.create(conversation=conversation, author=request.user, body=body)
        record("sms.note_create", request=request, target_type="sms_conversation", target_id=conversation.pk, metadata={"device": conversation.device.code})
        return Response(SmsNoteSerializer(note).data, status=status.HTTP_201_CREATED)


class NoteDetailView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(responses={204: None}, operation_id="sms_notes_destroy")
    def delete(self, request, pk, note_id):
        conversation = access.get_conversation(request.user, pk)
        note = ConversationNote.objects.filter(pk=note_id, conversation=conversation).first()
        if not note:
            raise ApiError("not_found", "This note was not found.", status.HTTP_404_NOT_FOUND)
        if note.author_id != request.user.pk and not access.is_sms_admin(request.user):
            raise ApiError("permission_denied", "You can only delete your own notes.", status.HTTP_403_FORBIDDEN)
        note.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Contacts and blocks --------------------------------------------------------------------------------------


class ContactListView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(parameters=[OpenApiParameter("device", str), OpenApiParameter("q", str), OpenApiParameter("blocked", bool), OpenApiParameter("cursor", str)],
                   responses=ContactPageSerializer, operation_id="sms_contacts_list")
    def get(self, request):
        devices = access.accessible_devices(request.user)
        device = request.query_params.get("device")
        if device and device != "all":
            devices = devices.filter(pk=access.get_device(request.user, device).pk)
        qs = Contact.objects.filter(device__in=devices).select_related("device", "device__office")
        q = (request.query_params.get("q") or "").strip()[:60]
        if q:
            digits = re.sub(r"\D", "", q)
            condition = Q(display_name__icontains=q) | Q(address__icontains=q)
            if len(digits) >= 3:
                condition |= Q(address__contains=digits.lstrip("0"))
            qs = qs.filter(condition)
        blocked = _bool(request.query_params.get("blocked"))
        if blocked is not None:
            qs = qs.filter(is_blocked=blocked)
        cursor = decode_cursor(request.query_params.get("cursor"))
        if cursor and "id" in cursor:
            qs = qs.filter(id__lt=cursor["id"])
        rows = list(qs.order_by("-id")[:101])
        more = len(rows) > 100
        rows = rows[:100]
        stats = {
            (row["device_id"], row["address"]): row
            for row in Message.objects.filter(device__in={r.device_id for r in rows}, address__in={r.address for r in rows})
            .values("device_id", "address").annotate(count=Count("id"), last=Max("provider_date"))
        }
        conversations = {}
        for conv in Conversation.objects.filter(device__in={r.device_id for r in rows}, participants_key__in={r.address for r in rows}).values("device_id", "participants_key", "pk"):
            conversations[(conv["device_id"], conv["participants_key"])] = conv["pk"]
        results = []
        for row in rows:
            stat = stats.get((row.device_id, row.address), {})
            results.append({
                "id": row.pk, "device": {"id": row.device_id, "code": row.device.code, "name": row.device.name, "colour": row.device.office.colour},
                "address": row.address, "display": display_number(row.address), "name": row.display_name, "kind": address_kind(row.address),
                "is_blocked": row.is_blocked, "messages": stat.get("count", 0), "last_contact_at": stat.get("last"), "conversation": conversations.get((row.device_id, row.address)),
            })
        return Response({"results": results, "next_cursor": encode_cursor({"id": rows[-1].pk}) if more and rows else None})


class BlockView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(request=BlockRequestSerializer, responses={204: None}, operation_id="sms_blocked_create")
    def post(self, request):
        data = BlockRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        device = access.get_device(request.user, data.validated_data["device"], access.MANAGE)
        address = data.validated_data["address"]
        store.set_blocked(device, address, True)
        queue_command(device, "block", {"address": address}, request.user)
        record("sms.block", request=request, target_type="device", target_id=device.pk, metadata={"device": device.code, "address": mask(address)})
        return Response(status=status.HTTP_204_NO_CONTENT)


class UnblockView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(request=None, responses={204: None}, operation_id="sms_blocked_destroy")
    def delete(self, request, pk):
        contact = Contact.objects.filter(pk=pk, device__in=access.accessible_devices(request.user)).select_related("device").first()
        if not contact:
            raise ApiError("not_found", "This contact was not found.", status.HTTP_404_NOT_FOUND)
        access.get_device(request.user, contact.device_id, access.MANAGE)
        store.set_blocked(contact.device, contact.address, False)
        queue_command(contact.device, "unblock", {"address": contact.address}, request.user)
        record("sms.unblock", request=request, target_type="device", target_id=contact.device_id, metadata={"device": contact.device.code, "address": mask(contact.address)})
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssigneeListView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(parameters=[OpenApiParameter("device", str, required=True)], responses=SmsAssigneeSerializer(many=True), operation_id="sms_assignees_list")
    def get(self, request):
        device = access.get_device(request.user, request.query_params.get("device"))
        users = get_user_model().objects.filter(is_active=True).select_related("role").order_by("full_name", "email")
        return Response([{"id": u.pk, "email": u.email, "display_name": u.display_name} for u in users if access.permissions_for(u, device)["read"]])


class StatsView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(parameters=[OpenApiParameter("range", int, enum=[7, 30, 90]), OpenApiParameter("device", str), OpenApiParameter("sim", int)],
                   responses={200: OpenApiTypes.OBJECT}, operation_id="sms_stats")
    def get(self, request):
        from ..services.stats import dashboard

        days = int(request.query_params.get("range") or 30) if str(request.query_params.get("range") or "30").isdigit() else 30
        if days not in (7, 30, 90):
            days = 30
        devices = access.accessible_devices(request.user)
        device = request.query_params.get("device")
        if device and device != "all":
            devices = devices.filter(pk=access.get_device(request.user, device).pk)
        sim = request.query_params.get("sim")
        return Response({**dashboard(request.user, devices, days, int(sim) if sim and sim.isdigit() else None), "generated_at": timezone.now()})
