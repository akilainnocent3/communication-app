import re
from collections import defaultdict

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.errors import ApiError
from common.pagination import decode_cursor, encode_cursor
from modules.audit.services import record

from ..models import Contact, Label, Mailbox, Message, Thread, ThreadNote, TrustedSender
from ..providers import get_provider
from ..providers.base import ProviderError
from ..services import access, actions, search, store
from ..services.threads import open_thread, trusted_senders
from .permissions import CanUseMail
from .serializers import (
    ActionRequestSerializer,
    ActionResultSerializer,
    AssigneeSerializer,
    ContactSuggestionSerializer,
    LabelSerializer,
    LabelWriteSerializer,
    NoteSerializer,
    ThreadDetailSerializer,
    ThreadPageSerializer,
    ThreadSummarySerializer,
    UndoRequestSerializer,
)

PAGE_SIZE = 50
CATEGORIES = {"primary": "CATEGORY_PERSONAL", "social": "CATEGORY_SOCIAL", "promotions": "CATEGORY_PROMOTIONS", "updates": "CATEGORY_UPDATES", "forums": "CATEGORY_FORUMS"}
SUMMARY_RELATED = ("mailbox", "mailbox__office", "assignment__assignee", "snooze")


def label_context(threads) -> dict:
    """{mailbox_id: {label_id: chip}} for user labels on these threads."""
    mailbox_ids = {t.mailbox_id for t in threads}
    result: dict[int, dict] = defaultdict(dict)
    for label in Label.objects.filter(mailbox_id__in=mailbox_ids, type=Label.USER):
        result[label.mailbox_id][label.provider_label_id] = {"id": label.provider_label_id, "name": label.name, "colour": label.colour, "text_colour": label.text_colour}
    return result


def summaries(request, threads) -> list:
    threads = list(threads)
    return ThreadSummarySerializer(threads, many=True, context={"request": request, "labels": label_context(threads)}).data


def _bool(value):
    if value in (None, ""):
        return None
    return str(value).lower() in ("1", "true", "yes")


def filtered_threads(user, params) -> tuple:
    """The thread queryset for list filters. Used by the list view and 'select all matching'."""
    mailbox_param = str(params.get("mailbox") or "all")
    if mailbox_param == "all":
        qs = access.accessible_threads(user)
    else:
        mailbox = access.get_mailbox(user, mailbox_param)
        qs = Thread.objects.filter(mailbox=mailbox)
    label = (params.get("label") or "").strip()
    q = (params.get("q") or "").strip()
    upper = label.upper()
    if upper == "SNOOZED":
        qs = qs.filter(snooze__isnull=False)
    elif upper == "ASSIGNED":
        qs = qs.filter(assignment__assignee=user, assignment__status="open")
    elif upper == "ALL" or (not upper and not q):
        # "All mail": everything except spam, trash and draft-only conversations.
        qs = qs.exclude(Q(label_ids__overlap=["SPAM", "TRASH"]) | Q(label_ids=["DRAFT"]))
    elif upper:
        qs = qs.filter(label_ids__contains=[label])
    category = (params.get("category") or "").lower()
    if category in CATEGORIES:
        if category == "primary":
            others = [v for k, v in CATEGORIES.items() if k != "primary"]
            qs = qs.exclude(label_ids__overlap=others)
        else:
            qs = qs.filter(label_ids__contains=[CATEGORIES[category]])
    if q:
        qs = search.apply(qs, q, include_spam_trash=upper in ("SPAM", "TRASH"))
    for key, field in (("unread", "is_unread"), ("starred", "is_starred")):
        value = _bool(params.get(key))
        if value is not None:
            qs = qs.filter(**{field: value})
    if _bool(params.get("has_attachment")):
        qs = qs.filter(has_attachments=True)
    if params.get("from"):
        qs = search.apply(qs, f'from:"{params["from"]}"')
    after, before = params.get("after"), params.get("before")
    if after:
        qs = search.apply(qs, f"after:{after}")
    if before:
        qs = search.apply(qs, f"before:{before}")
    if params.get("assigned_to"):
        assignee = user.pk if params["assigned_to"] == "me" else params["assigned_to"]
        qs = qs.filter(assignment__assignee_id=assignee)
    return qs


LIST_PARAMS = [
    OpenApiParameter("mailbox", str, description="Mailbox id or 'all' (unified inbox)"),
    OpenApiParameter("label", str, description="Label id, or ALL / SNOOZED / ASSIGNED"),
    OpenApiParameter("category", str, enum=list(CATEGORIES)),
    OpenApiParameter("q", str, description="Search with Gmail operators"),
    OpenApiParameter("unread", bool), OpenApiParameter("starred", bool), OpenApiParameter("has_attachment", bool),
    OpenApiParameter("from", str), OpenApiParameter("after", str), OpenApiParameter("before", str),
    OpenApiParameter("assigned_to", str), OpenApiParameter("cursor", str),
]


class ThreadListView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(parameters=LIST_PARAMS, responses=ThreadPageSerializer, operation_id="mail_threads_list")
    def get(self, request):
        qs = filtered_threads(request.user, request.query_params)
        cursor = decode_cursor(request.query_params.get("cursor"))
        total = None if cursor else qs.count()
        if cursor and "t" in cursor and "id" in cursor:
            qs = qs.filter(Q(last_message_at__lt=cursor["t"]) | Q(last_message_at=cursor["t"], id__lt=cursor["id"]))
        rows = list(qs.select_related(*SUMMARY_RELATED).order_by("-last_message_at", "-id")[: PAGE_SIZE + 1])
        more = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]
        next_cursor = encode_cursor({"t": rows[-1].last_message_at.isoformat(), "id": rows[-1].pk}) if more and rows else None
        return Response({"results": summaries(request, rows), "next_cursor": next_cursor, "total": total})


class ServerSearchView(APIView):
    """'Search full message bodies in Gmail': asks the provider, indexes what it finds, returns summaries."""

    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(parameters=[OpenApiParameter("mailbox", int, required=True), OpenApiParameter("q", str, required=True), OpenApiParameter("page_token", str)],
                   responses=ThreadPageSerializer, operation_id="mail_threads_server_search")
    def get(self, request):
        mailbox = access.get_mailbox(request.user, request.query_params.get("mailbox"))
        query = (request.query_params.get("q") or "").strip()
        if not query:
            raise ApiError("validation_error", "Type something to search for.")
        provider = get_provider(mailbox)
        try:
            ids, next_token = provider.list_threads(query=query, page_token=request.query_params.get("page_token") or None, max_results=25)
            known = set(Thread.objects.filter(mailbox=mailbox, provider_thread_id__in=ids).values_list("provider_thread_id", flat=True))
            missing = [t for t in ids if t not in known]
            if missing:
                found, _ = provider.get_threads(missing)
                for pthread in found:
                    store.apply_thread(mailbox, pthread)
        except ProviderError as exc:
            raise ApiError(exc.code, str(exc), status.HTTP_503_SERVICE_UNAVAILABLE if exc.retryable else status.HTTP_400_BAD_REQUEST) from None
        rows = {t.provider_thread_id: t for t in Thread.objects.filter(mailbox=mailbox, provider_thread_id__in=ids).select_related(*SUMMARY_RELATED)}
        ordered = [rows[t] for t in ids if t in rows]
        return Response({"results": summaries(request, ordered), "next_cursor": next_token, "total": None})


class ThreadDetailView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(parameters=[OpenApiParameter("peek", bool), OpenApiParameter("images", bool)], responses=ThreadDetailSerializer, operation_id="mail_threads_retrieve")
    def get(self, request, pk):
        thread = access.accessible_threads(request.user).select_related(*SUMMARY_RELATED).filter(pk=pk).first()
        if not thread:
            raise ApiError("not_found", "This conversation was not found. It may have been deleted.", status.HTTP_404_NOT_FOUND)
        thread, messages = open_thread(request.user, thread, peek=_bool(request.query_params.get("peek")) or False, request=request)
        thread = Thread.objects.select_related(*SUMMARY_RELATED).get(pk=thread.pk)
        context = {
            "request": request, "messages": messages, "labels": label_context([thread]),
            "show_images": bool(_bool(request.query_params.get("images"))), "trusted": trusted_senders(request.user),
        }
        return Response(ThreadDetailSerializer(thread, context=context).data)


class ActionView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(request=ActionRequestSerializer, responses=ActionResultSerializer, operation_id="mail_actions")
    def post(self, request):
        data = ActionRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        ids = list(values["thread_ids"])
        if values.get("select_all"):
            ids = list(filtered_threads(request.user, values["select_all"]).values_list("pk", flat=True)[:5000])
        result = actions.perform(
            request.user, values["action"], ids, label_ids=values["label_ids"], until=values.get("until"),
            assignee_id=values.get("assignee"), request=request, undoable=len(ids) <= 500,
        )
        return Response({"threads": summaries(request, result["threads"]), "deleted_ids": result["deleted_ids"], "undo_token": result["undo_token"]})


class UndoView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(request=UndoRequestSerializer, responses=ActionResultSerializer, operation_id="mail_actions_undo")
    def post(self, request):
        data = UndoRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = actions.undo(request.user, data.validated_data["undo_token"], request=request)
        return Response({"threads": summaries(request, result["threads"]), "deleted_ids": [], "undo_token": None})


# --- Labels -----------------------------------------------------------------------------------------------


class LabelListView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(parameters=[OpenApiParameter("mailbox", int, required=True)], responses=LabelSerializer(many=True), operation_id="mail_labels_list")
    def get(self, request):
        mailbox = access.get_mailbox(request.user, request.query_params.get("mailbox"))
        return Response(LabelSerializer(Label.objects.filter(mailbox=mailbox).order_by("type", "name"), many=True).data)

    @extend_schema(request=LabelWriteSerializer, responses={201: LabelSerializer}, operation_id="mail_labels_create")
    def post(self, request):
        data = LabelWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        mailbox = access.get_mailbox(request.user, data.validated_data.get("mailbox"), access.SEND)
        values = data.validated_data
        try:
            created = get_provider(mailbox).create_label(values["name"], values["colour"], values["text_colour"])
        except ProviderError as exc:
            raise ApiError(exc.code, str(exc)) from None
        label, _ = Label.objects.update_or_create(mailbox=mailbox, provider_label_id=created.id, defaults={"name": created.name, "type": Label.USER, "colour": created.colour, "text_colour": created.text_colour})
        record("mail.label_create", request=request, mailbox=mailbox, target_type="label", target_id=label.provider_label_id, metadata={"name": label.name})
        return Response(LabelSerializer(label).data, status=status.HTTP_201_CREATED)


class LabelDetailView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    def _label(self, request, pk) -> Label:
        label = Label.objects.select_related("mailbox").filter(pk=pk, mailbox__in=access.accessible_mailboxes(request.user)).first()
        if not label:
            raise ApiError("not_found", "This label was not found.", status.HTTP_404_NOT_FOUND)
        if label.type != Label.USER:
            raise ApiError("validation_error", "System labels cannot be changed.")
        access.get_mailbox(request.user, label.mailbox_id, access.SEND)
        return label

    @extend_schema(request=LabelWriteSerializer, responses=LabelSerializer, operation_id="mail_labels_update")
    def patch(self, request, pk):
        label = self._label(request, pk)
        data = LabelWriteSerializer(data={"name": label.name, **request.data})
        data.is_valid(raise_exception=True)
        values = data.validated_data
        try:
            updated = get_provider(label.mailbox).update_label(label.provider_label_id, name=values["name"], colour=values.get("colour") or None, text_colour=values.get("text_colour") or None)
        except ProviderError as exc:
            raise ApiError(exc.code, str(exc)) from None
        label.name, label.colour, label.text_colour = updated.name, updated.colour or label.colour, updated.text_colour or label.text_colour
        label.save()
        record("mail.label_update", request=request, mailbox=label.mailbox, target_type="label", target_id=label.provider_label_id, metadata={"name": label.name})
        return Response(LabelSerializer(label).data)

    @extend_schema(responses={204: None}, operation_id="mail_labels_destroy")
    def delete(self, request, pk):
        label = self._label(request, pk)
        try:
            get_provider(label.mailbox).delete_label(label.provider_label_id)
        except ProviderError as exc:
            raise ApiError(exc.code, str(exc)) from None
        threads = list(Thread.objects.filter(mailbox=label.mailbox, label_ids__contains=[label.provider_label_id]))
        store.apply_label_change_locally(threads, [], [label.provider_label_id])
        record("mail.label_delete", request=request, mailbox=label.mailbox, target_type="label", target_id=label.provider_label_id, metadata={"name": label.name})
        label.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Messages ---------------------------------------------------------------------------------------------


def _message(request, pk) -> Message:
    message = Message.objects.select_related("mailbox", "thread").filter(pk=pk, thread__in=access.accessible_threads(request.user)).first()
    if not message:
        raise ApiError("not_found", "This message was not found.", status.HTTP_404_NOT_FOUND)
    return message


SAFE_INLINE = {"image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf", "text/plain"}


class AttachmentView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(parameters=[OpenApiParameter("download", bool), OpenApiParameter("preview", bool)], responses={(200, "application/octet-stream"): bytes}, operation_id="mail_attachments_retrieve")
    def get(self, request, pk, attachment_id):
        message = _message(request, pk)
        meta = next((a for a in message.attachments if a["id"] == attachment_id), None)
        if not meta:
            raise ApiError("not_found", "This attachment was not found.", status.HTTP_404_NOT_FOUND)
        try:
            data = get_provider(message.mailbox).get_attachment(message.provider_message_id, attachment_id)
        except ProviderError as exc:
            raise ApiError(exc.code, str(exc), status.HTTP_503_SERVICE_UNAVAILABLE if exc.retryable else status.HTTP_404_NOT_FOUND) from None
        content_type = meta.get("mime_type") or "application/octet-stream"
        inline = content_type in SAFE_INLINE and not _bool(request.query_params.get("download"))
        response = HttpResponse(data, content_type=content_type if inline else "application/octet-stream")
        filename = re.sub(r'[\r\n"\\]', "_", meta.get("filename") or "attachment")
        from urllib.parse import quote

        response["Content-Disposition"] = f"{'inline' if inline else 'attachment'}; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}"
        response["X-Content-Type-Options"] = "nosniff"
        # Every response is sandboxed by default. Chrome refuses to render PDFs inside a CSP sandbox, so only an
        # explicit in-app PDF preview (`?preview=1`) drops `sandbox`; it still allows no scripts (`default-src 'none'`).
        pdf_preview = content_type == "application/pdf" and inline and _bool(request.query_params.get("preview"))
        sandbox = "" if pdf_preview else "; sandbox"
        response["Content-Security-Policy"] = f"default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; frame-ancestors 'self'{sandbox}"
        response["Cache-Control"] = "private, max-age=300"
        record("mail.attachment_download", request=request, mailbox=message.mailbox, target_type="message", target_id=message.pk, metadata={"filename": meta.get("filename", "")[:120]})
        return response


class RawMessageView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(responses={(200, "text/plain"): str}, operation_id="mail_messages_raw")
    def get(self, request, pk):
        message = _message(request, pk)
        try:
            raw = get_provider(message.mailbox).get_raw(message.provider_message_id)
        except ProviderError as exc:
            raise ApiError(exc.code, str(exc), status.HTTP_503_SERVICE_UNAVAILABLE) from None
        record("mail.show_original", request=request, mailbox=message.mailbox, target_type="message", target_id=message.pk)
        response = HttpResponse(raw, content_type="text/plain; charset=utf-8")
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response


class UnsubscribeView(APIView):
    """One-click unsubscribe (RFC 8058) when offered, else returns the link/mailto for the user to open."""

    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(request=None, responses={200: OpenApiTypes.OBJECT}, operation_id="mail_messages_unsubscribe")
    def post(self, request, pk):
        message = _message(request, pk)
        access.get_mailbox(request.user, message.mailbox_id, access.SEND)
        targets = re.findall(r"<([^>]+)>", message.list_unsubscribe or "")
        https = next((t for t in targets if t.lower().startswith("https://")), None)
        mailto = next((t for t in targets if t.lower().startswith("mailto:")), None)
        record("mail.unsubscribe", request=request, mailbox=message.mailbox, target_type="message", target_id=message.pk)
        if https and "one-click" in (message.list_unsubscribe_post or "").lower():
            import requests

            try:
                response = requests.post(https, data={"List-Unsubscribe": "One-Click"}, timeout=10, allow_redirects=False)
                if response.status_code < 400:
                    return Response({"method": "one_click", "done": True})
            except requests.RequestException:
                pass
        if mailto:
            return Response({"method": "mailto", "done": False, "target": mailto})
        if https:
            return Response({"method": "link", "done": False, "target": https})
        raise ApiError("validation_error", "This sender did not provide a way to unsubscribe.")


class TrustedSenderView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(request=ContactSuggestionSerializer, responses={201: None}, operation_id="mail_trusted_senders_create")
    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        if "@" not in email:
            raise ApiError("validation_error", "Enter an email address.")
        TrustedSender.objects.get_or_create(user=request.user, email=email)
        return Response(status=status.HTTP_201_CREATED)


# --- Notes, contacts, assignees ---------------------------------------------------------------------------


class NoteListView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    def _thread(self, request, pk) -> Thread:
        thread = access.accessible_threads(request.user).filter(pk=pk).select_related("mailbox").first()
        if not thread:
            raise ApiError("not_found", "This conversation was not found.", status.HTTP_404_NOT_FOUND)
        return thread

    @extend_schema(responses=NoteSerializer(many=True), operation_id="mail_notes_list")
    def get(self, request, pk):
        thread = self._thread(request, pk)
        return Response(NoteSerializer(thread.notes.select_related("author"), many=True).data)

    @extend_schema(request=NoteSerializer, responses={201: NoteSerializer}, operation_id="mail_notes_create")
    def post(self, request, pk):
        thread = self._thread(request, pk)
        data = NoteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        body = data.validated_data["body"].strip()[:5000]
        if not body:
            raise ApiError("validation_error", "Write a note first.")
        note = ThreadNote.objects.create(thread=thread, author=request.user, body=body)
        record("mail.note_create", request=request, mailbox=thread.mailbox, target_type="thread", target_id=thread.pk)
        return Response(NoteSerializer(note).data, status=status.HTTP_201_CREATED)


class NoteDetailView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(responses={204: None}, operation_id="mail_notes_destroy")
    def delete(self, request, pk, note_id):
        note = ThreadNote.objects.filter(pk=note_id, thread_id=pk, thread__in=access.accessible_threads(request.user)).first()
        if not note:
            raise ApiError("not_found", "This note was not found.", status.HTTP_404_NOT_FOUND)
        if note.author_id != request.user.pk and not access.is_mail_admin(request.user):
            raise ApiError("permission_denied", "You can only delete your own notes.", status.HTTP_403_FORBIDDEN)
        note.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContactSuggestView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(parameters=[OpenApiParameter("q", str), OpenApiParameter("mailbox", int)], responses=ContactSuggestionSerializer(many=True), operation_id="mail_contacts_suggest")
    def get(self, request):
        q = (request.query_params.get("q") or "").strip().lower()
        mailboxes = access.accessible_mailboxes(request.user)
        if request.query_params.get("mailbox"):
            mailboxes = mailboxes.filter(pk=request.query_params["mailbox"])
        qs = Contact.objects.filter(mailbox__in=mailboxes)
        if q:
            qs = qs.filter(Q(email__icontains=q) | Q(name__icontains=q))
        seen, result = set(), []
        for contact in qs.order_by("-frequency", "-last_seen")[:40]:
            if contact.email not in seen:
                seen.add(contact.email)
                result.append({"email": contact.email, "name": contact.name})
        # Our own mailboxes are contacts too (internal mail between offices).
        for mailbox in Mailbox.objects.filter(Q(email__icontains=q) | Q(display_name__icontains=q) | Q(office__name__icontains=q)).select_related("office")[:5] if q else []:
            if mailbox.email not in seen:
                result.append({"email": mailbox.email, "name": mailbox.name})
        return Response(result[:10])


class AssigneeListView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(parameters=[OpenApiParameter("mailbox", int, required=True)], responses=AssigneeSerializer(many=True), operation_id="mail_assignees_list")
    def get(self, request):
        from django.contrib.auth import get_user_model

        mailbox = access.get_mailbox(request.user, request.query_params.get("mailbox"))
        users = get_user_model().objects.filter(is_active=True).select_related("role").order_by("full_name", "email")
        result = [{"id": u.pk, "email": u.email, "display_name": u.display_name} for u in users if access.permissions_for(u, mailbox)["read"]]
        return Response(result)


class StatsView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(parameters=[OpenApiParameter("range", int, enum=[7, 30, 90]), OpenApiParameter("mailbox", str)], responses={200: OpenApiTypes.OBJECT}, operation_id="mail_stats")
    def get(self, request):
        from ..services.stats import dashboard

        days = int(request.query_params.get("range") or 30)
        if days not in (7, 30, 90):
            days = 30
        mailboxes = access.accessible_mailboxes(request.user)
        mailbox = request.query_params.get("mailbox")
        if mailbox and mailbox != "all":
            mailboxes = mailboxes.filter(pk=access.get_mailbox(request.user, mailbox).pk)
        return Response({**dashboard(request.user, mailboxes, days), "generated_at": timezone.now()})
