"""Admin endpoints for Calls (/api/v1/calls/…): call log, call detail, notes, call-backs, live board, dashboard,
export, customers (the shared directory), outcomes, settings, office hours, tariffs and Calls phones."""

import re
from datetime import datetime, time

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.devicecrypto import decrypt_text, encrypt_text
from common.errors import ApiError
from common.pagination import decode_cursor, encode_cursor
from modules.audit.services import record
from modules.devices.models import Device, DeviceStatus
from modules.devices.services.health import attention_for
from modules.devices.services.phone import mask
from modules.directory.models import Customer
from modules.directory.services import customers as directory
from modules.identity.models import Office
from modules.sms.api import devices as sms_device_views

from ..models import (
    MISSED_RESULTS, CallAnnotation, CallbackTask, CallOutcome, CallRecord, CallSettings, CarrierTariff, DeviceAccess, Direction, OfficeHours,
)
from ..services import access, callbacks, export, hours, stats
from ..services.retention import retention_days
from . import serializers as s

User = get_user_model()
PAGE_SIZE = 50
FOLDERS = ("all", "missed", "unreturned", "incoming", "outgoing", "after_hours")


class CanUseCalls(BasePermission):
    """`calls.access` and the Calls platform switched on (a disabled platform refuses its whole API)."""

    message = "You don't have access to the Calls platform."

    def has_permission(self, request, view):
        return access.can_use_calls(request.user)


class CanManageCalls(BasePermission):
    message = "You don't have permission to change Calls settings."

    def has_permission(self, request, view):
        return access.can_use_calls(request.user) and request.user.has_perm("calls.manage_settings")


class CallsView(APIView):
    permission_classes = [IsAuthenticated, CanUseCalls]


def _bool(value):
    if value in (None, ""):
        return None
    return str(value).lower() in ("1", "true", "yes")


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def scoped_devices(user, params):
    device_param = str(params.get("device") or "all")
    devices = access.accessible_devices(user)
    if device_param != "all":
        devices = devices.filter(pk=access.get_device(user, device_param).pk)
    return devices


def filtered_calls(user, params):
    """The call log with the dashboard's filters. Dates are whole days in the viewer's time zone (as the dashboard)."""
    devices = scoped_devices(user, params)
    qs = CallRecord.objects.filter(device__in=devices.values("pk"))
    folder = (params.get("folder") or "all").lower()
    if folder == "missed":
        qs = qs.filter(direction=Direction.IN, result__in=MISSED_RESULTS)
    elif folder == "unreturned":
        qs = qs.filter(direction=Direction.IN, result__in=MISSED_RESULTS, is_final=True, returned_at__isnull=True)
    elif folder == "incoming":
        qs = qs.filter(direction=Direction.IN)
    elif folder == "outgoing":
        qs = qs.filter(direction=Direction.OUT)
    elif folder == "after_hours":
        qs = qs.filter(is_after_hours=True)
    if params.get("direction") in ("in", "out"):
        qs = qs.filter(direction=params["direction"])
    if params.get("result"):
        results = [r for r in str(params["result"]).split(",") if r in s.RESULT_CHOICES]
        qs = qs.filter(result__in=results) if results else qs.none()
    if (sim := _int(params.get("sim"))) is not None:
        qs = qs.filter(sim_line_id=sim)
    tz = stats.tz_for(user)
    if (after := parse_date(params.get("after") or "")):
        qs = qs.filter(started_at__gte=datetime.combine(after, time.min, tzinfo=tz))
    if (before := parse_date(params.get("before") or "")):
        from datetime import timedelta

        qs = qs.filter(started_at__lt=datetime.combine(before + timedelta(days=1), time.min, tzinfo=tz))
    if (low := _int(params.get("min_duration"))) is not None:
        qs = qs.filter(talk_seconds__gte=low)
    if (high := _int(params.get("max_duration"))) is not None:
        qs = qs.filter(talk_seconds__lte=high)
    if (outcome := _int(params.get("outcome"))) is not None:
        qs = qs.filter(annotations__outcome_id=outcome).distinct()
    if _bool(params.get("after_hours")) is not None:
        qs = qs.filter(is_after_hours=_bool(params["after_hours"]))
    if _bool(params.get("unreturned")):
        qs = qs.filter(direction=Direction.IN, result__in=MISSED_RESULTS, is_final=True, returned_at__isnull=True)
    if (customer := _int(params.get("customer"))) is not None:
        qs = qs.filter(customer_id=customer)
    if (staff := _int(params.get("staff"))) is not None:
        qs = qs.filter(device__assigned_to_id=staff)
    if params.get("q"):
        q = params["q"].strip()[:60]
        digits = re.sub(r"\D", "", q)
        condition = Q(contact_name_on_phone__icontains=q) | Q(customer__display_name__icontains=q)
        if len(digits) >= 3:
            condition |= Q(number_e164__contains=digits) | (Q(number_e164__contains=digits[1:]) if digits.startswith("0") else Q())
        qs = qs.filter(condition)
    return qs


LIST_PARAMS = [
    OpenApiParameter("device", str, description="Device id or 'all'"), OpenApiParameter("folder", str, enum=list(FOLDERS)),
    OpenApiParameter("direction", str, enum=["in", "out"]), OpenApiParameter("result", str, description="Comma separated results"),
    OpenApiParameter("sim", int), OpenApiParameter("after", str, description="YYYY-MM-DD"), OpenApiParameter("before", str, description="YYYY-MM-DD"),
    OpenApiParameter("min_duration", int), OpenApiParameter("max_duration", int), OpenApiParameter("outcome", int),
    OpenApiParameter("after_hours", bool), OpenApiParameter("unreturned", bool), OpenApiParameter("customer", int), OpenApiParameter("staff", int),
    OpenApiParameter("q", str, description="Number or name"), OpenApiParameter("cursor", str),
]


def _with_related(qs):
    return qs.select_related("device", "device__office", "sim_line", "customer").prefetch_related(
        Prefetch("annotations", queryset=CallAnnotation.objects.select_related("outcome").order_by("created_at", "id"), to_attr="prefetched_annotations"))


class CallListView(CallsView):
    @extend_schema(parameters=LIST_PARAMS, responses=s.CallPageSerializer, operation_id="calls_list")
    def get(self, request):
        qs = filtered_calls(request.user, request.query_params).order_by("-started_at", "-id")
        cursor = decode_cursor(request.query_params.get("cursor"))
        if cursor and "t" in cursor and "id" in cursor:
            qs = qs.filter(Q(started_at__lt=cursor["t"]) | Q(started_at=cursor["t"], id__lt=cursor["id"]))
        rows = list(_with_related(qs)[: PAGE_SIZE + 1])
        next_cursor = encode_cursor({"t": rows[PAGE_SIZE - 1].started_at.isoformat(), "id": rows[PAGE_SIZE - 1].pk}) if len(rows) > PAGE_SIZE else None
        return Response({"results": s.CallSummarySerializer(rows[:PAGE_SIZE], many=True).data, "next_cursor": next_cursor})


def customer_history(user, call: CallRecord, limit: int = 30) -> list[dict]:
    """The customer's other calls and SMS on phones the user can read, newest first."""
    numbers = [call.number_e164] if call.number_e164 else []
    if call.customer_id:
        numbers = directory.numbers_of(call.customer)
    if not numbers:
        return []
    items = []
    for other in (access.accessible_calls(user).filter(number_e164__in=numbers).exclude(pk=call.pk).select_related("device").order_by("-started_at")[:limit]):
        items.append({"kind": "call", "at": other.started_at, "direction": other.direction, "result": other.result, "talk_seconds": other.talk_seconds,
                      "device": other.device.name, "call_id": other.pk, "conversation_id": None, "snippet": ""})
    from modules.sms.services.access import accessible_conversations

    for conversation in accessible_conversations(user).filter(Q(customer_id=call.customer_id) if call.customer_id else Q(participants_key__in=numbers)).select_related("device")[:10]:
        snippet = decrypt_text(conversation.encrypted_snippet)
        items.append({"kind": "sms", "at": conversation.last_message_at, "direction": conversation.last_direction, "result": "", "talk_seconds": None,
                      "device": conversation.device.name, "call_id": None, "conversation_id": conversation.pk, "snippet": snippet[:120]})
    return sorted(items, key=lambda item: item["at"], reverse=True)[:limit]


def detail_payload(user, call: CallRecord) -> dict:
    call = _with_related(CallRecord.objects.filter(pk=call.pk)).get()
    config = CallSettings.load()
    data = s.CallSummarySerializer(call).data
    data.update({
        "disconnect_cause_label": call.disconnect_cause_label, "ended_by": call.ended_by, "network": call.network, "conference_size": call.conference_size,
        "was_on_hold_seconds": call.was_on_hold_seconds, "returns_call_id": call.returns_call_id, "returned_by_id": call.returned_by_id,
        "callback_task_id": call.callback_task_id,
        "events": s.CallEventSerializer(call.events.all(), many=True).data,
        "annotations": s.CallAnnotationSerializer(call.prefetched_annotations, many=True).data,
        "history": customer_history(user, call),
        "permissions": access.permissions_for(user, call.device),
        "outcome_required": bool(config.outcome_required_after_seconds and call.talk_seconds >= config.outcome_required_after_seconds),
    })
    return data


class CallDetailView(CallsView):
    @extend_schema(parameters=[OpenApiParameter("peek", bool)], responses=s.CallDetailSerializer, operation_id="calls_retrieve")
    def get(self, request, pk):
        call = access.get_call(request.user, pk)
        if not _bool(request.query_params.get("peek")):
            record("calls.call_open", request=request, target_type="call", target_id=call.pk, metadata={"device": call.device.code, "number": mask(call.number_e164)})
        return Response(detail_payload(request.user, call))


def _outcome(value):
    if value in (None, ""):
        return None
    outcome = CallOutcome.objects.filter(pk=value, is_active=True).first()
    if not outcome:
        raise ApiError("validation_error", "Choose an outcome.", errors={"outcome": ["Unknown outcome."]})
    return outcome


class CallAnnotationListView(CallsView):
    @extend_schema(request=s.CallAnnotationWriteSerializer, responses={201: s.CallAnnotationSerializer}, operation_id="calls_annotations_create")
    def post(self, request, pk):
        call = access.get_call(request.user, pk, access.ANNOTATE)
        data = s.CallAnnotationWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        if values["outcome"] is None and not values["note"].strip():
            raise ApiError("validation_error", "Choose an outcome or write a note.")
        annotation = CallAnnotation.objects.create(call=call, outcome=_outcome(values["outcome"]), encrypted_note=encrypt_text(values["note"].strip()),
                                                   tags=[t.strip()[:40] for t in values["tags"] if t.strip()], author=request.user)
        record("calls.annotation_create", request=request, target_type="call", target_id=call.pk, metadata={"annotation": annotation.pk, "outcome": annotation.outcome_id})
        return Response(s.CallAnnotationSerializer(annotation).data, status=status.HTTP_201_CREATED)


class CallAnnotationDetailView(CallsView):
    def _annotation(self, request, pk):
        annotation = CallAnnotation.objects.select_related("call", "call__device", "outcome", "author").filter(pk=_int(pk) or 0).first()
        if not annotation or annotation.call.device_id not in set(access.accessible_devices(request.user).values_list("pk", flat=True)):
            raise ApiError("not_found", "This note was not found.", status.HTTP_404_NOT_FOUND)
        if not access.permissions_for(request.user, annotation.call.device)[access.ANNOTATE]:
            raise ApiError("permission_denied", access.PERM_MESSAGES[access.ANNOTATE], status.HTTP_403_FORBIDDEN)
        if annotation.from_phone or (annotation.author_id != request.user.pk and not access.is_calls_admin(request.user)):
            raise ApiError("permission_denied", "Only the author or an admin can change this note.", status.HTTP_403_FORBIDDEN)
        return annotation

    @extend_schema(request=s.CallAnnotationWriteSerializer, responses=s.CallAnnotationSerializer, operation_id="calls_annotations_update")
    def patch(self, request, pk):
        annotation = self._annotation(request, pk)
        data = s.CallAnnotationWriteSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        if "outcome" in request.data:
            annotation.outcome = _outcome(values.get("outcome"))
        if "note" in request.data:
            annotation.encrypted_note = encrypt_text(values.get("note", "").strip())
        if "tags" in request.data:
            annotation.tags = [t.strip()[:40] for t in values.get("tags", []) if t.strip()]
        annotation.save()
        record("calls.annotation_update", request=request, target_type="call", target_id=annotation.call_id, metadata={"annotation": annotation.pk})
        return Response(s.CallAnnotationSerializer(annotation).data)

    @extend_schema(responses={204: None}, operation_id="calls_annotations_delete")
    def delete(self, request, pk):
        annotation = self._annotation(request, pk)
        record("calls.annotation_delete", request=request, target_type="call", target_id=annotation.call_id, metadata={"annotation": annotation.pk})
        annotation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Call-backs --------------------------------------------------------------------------------------------------

CALLBACK_VIEWS = {"open": CallbackTask.ACTIVE_STATES, "mine": CallbackTask.ACTIVE_STATES, "done": (CallbackTask.DONE,),
                  "closed": (CallbackTask.CANCELLED, CallbackTask.EXPIRED), "all": None}


def _callbacks_qs(user, params):
    qs = access.accessible_callbacks(user).select_related("device", "device__office", "customer", "assigned_by", "assignee")
    view = params.get("view") or "open"
    if view not in CALLBACK_VIEWS:
        view = "open"
    if CALLBACK_VIEWS[view]:
        qs = qs.filter(state__in=CALLBACK_VIEWS[view])
    if view == "mine":
        qs = qs.filter(Q(assignee=user) | Q(assigned_by=user))
    if params.get("device") not in (None, "", "all"):
        qs = qs.filter(device=access.get_device(user, params["device"]))
    return qs.order_by("due_at", "id") if view in ("open", "mine") else qs.order_by("-updated_at", "-id")


class CallbackListView(CallsView):
    @extend_schema(parameters=[OpenApiParameter("view", str, enum=list(CALLBACK_VIEWS)), OpenApiParameter("device", str)],
                   responses=s.CallbackSerializer(many=True), operation_id="calls_callbacks_list")
    def get(self, request):
        return Response(s.CallbackSerializer(_callbacks_qs(request.user, request.query_params)[:500], many=True).data)

    @extend_schema(request=s.CallbackCreateSerializer, responses={201: s.CallbackSerializer}, operation_id="calls_callbacks_create")
    def post(self, request):
        data = s.CallbackCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        task = callbacks.create(request.user, device_id=v["device"], number=v["number"], call_id=v["call"], customer_id=v["customer"], due_at=v["due_at"],
                                priority=v["priority"], reason_text=v["reason"], request=request)
        return Response(s.CallbackSerializer(task).data, status=status.HTTP_201_CREATED)


class CallbackDetailView(CallsView):
    @extend_schema(responses=s.CallbackSerializer, operation_id="calls_callbacks_retrieve")
    def get(self, request, pk):
        return Response(s.CallbackSerializer(access.get_callback(request.user, pk)).data)

    @extend_schema(request=s.CallbackUpdateSerializer, responses=s.CallbackSerializer, operation_id="calls_callbacks_update")
    def patch(self, request, pk):
        task = access.get_callback(request.user, pk)
        data = s.CallbackUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        return Response(s.CallbackSerializer(callbacks.update(request.user, task, dict(data.validated_data), request=request)).data)


class CallbackCancelView(CallsView):
    @extend_schema(request=None, responses=s.CallbackSerializer, operation_id="calls_callbacks_cancel")
    def post(self, request, pk):
        return Response(s.CallbackSerializer(callbacks.cancel(request.user, access.get_callback(request.user, pk), request=request)).data)


class CallbackBulkView(CallsView):
    @extend_schema(request=s.CallbackBulkSerializer, responses=s.CallbackSerializer(many=True), operation_id="calls_callbacks_bulk")
    def post(self, request):
        data = s.CallbackBulkSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        if v["action"] == "assign" and not v.get("device"):
            raise ApiError("validation_error", "Choose a phone.", errors={"device": ["Required."]})
        values = {"device": v.get("device"), "due_at": v.get("due_at")} if v["action"] == "assign" else {"state": CallbackTask.DONE} if v["action"] == "done" else {}
        with transaction.atomic():
            tasks = callbacks.bulk(request.user, v["ids"], "cancel" if v["action"] == "cancel" else "update", values, request=request)
        return Response(s.CallbackSerializer(tasks, many=True).data)


# --- Live board, dashboard, badges, export -------------------------------------------------------------------------


class LiveView(CallsView):
    @extend_schema(responses=s.CallLiveSerializer, operation_id="calls_live")
    def get(self, request):
        return Response(stats.live_board(request.user, access.accessible_devices(request.user).exclude(status=DeviceStatus.REVOKED)))


class StatsView(CallsView):
    @extend_schema(parameters=[OpenApiParameter("range", int, enum=[1, 7, 30, 90, 365]), OpenApiParameter("device", str), OpenApiParameter("sim", int)],
                   responses=s.CallStatsSerializer, operation_id="calls_stats")
    def get(self, request):
        days = _int(request.query_params.get("range")) or 30
        if days not in (1, 7, 30, 90, 365):
            days = 30
        return Response(stats.dashboard(request.user, scoped_devices(request.user, request.query_params), days, _int(request.query_params.get("sim"))))


class BadgesView(CallsView):
    @extend_schema(parameters=[OpenApiParameter("device", str)], responses=s.CallBadgesSerializer, operation_id="calls_badges")
    def get(self, request):
        devices = scoped_devices(request.user, request.query_params)
        unreturned = CallRecord.objects.filter(device__in=devices.values("pk"), direction=Direction.IN, result__in=MISSED_RESULTS, is_final=True,
                                               returned_at__isnull=True).count()
        tasks = CallbackTask.objects.filter(device__in=devices.values("pk"), state__in=CallbackTask.ACTIVE_STATES)
        return Response({"unreturned": unreturned, "open_callbacks": tasks.count(),
                         "my_callbacks": tasks.filter(Q(assignee=request.user) | Q(assigned_by=request.user)).count(),
                         "attention": devices.exclude(attention=[]).exclude(status=DeviceStatus.REVOKED).count()})


class ExportView(CallsView):
    # `file_format`, not `format`: DRF reserves ?format= for renderer negotiation.
    @extend_schema(parameters=[*LIST_PARAMS, OpenApiParameter("file_format", str, enum=["csv", "xlsx"])], responses={(200, "text/csv"): OpenApiTypes.BINARY},
                   operation_id="calls_export")
    def get(self, request):
        if not request.user.has_perm("calls.export"):
            raise ApiError("permission_denied", "You don't have permission to export calls.", status.HTTP_403_FORBIDDEN)
        fmt = "xlsx" if request.query_params.get("file_format") == "xlsx" else "csv"
        filters = {k: v for k, v in request.query_params.items() if k != "file_format"}
        calls = filtered_calls(request.user, request.query_params).order_by("-started_at", "-id")
        body, content_type, name = export.export(request.user, calls, stats.tz_for(request.user), fmt, filters, request=request)
        response = HttpResponse(body, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{name}"'
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "no-store"
        return response


# --- Calls phones ----------------------------------------------------------------------------------------------------


def device_payload(device: Device) -> dict:
    return s.CallDeviceSerializer(device).data


class CallDeviceListView(CallsView):
    @extend_schema(parameters=[OpenApiParameter("candidates", bool, description="SMS phones (OCM Messages) a new OCM Phone code can be linked to: same handset")],
                   responses=s.CallDeviceSerializer(many=True), operation_id="calls_devices_list")
    def get(self, request):
        if _bool(request.query_params.get("candidates")):
            if not request.user.has_perm("calls.manage_settings"):
                return Response([])
            from modules.sms.services.access import accessible_devices as sms_devices

            rows = sms_devices(request.user).filter(app="sms", status=DeviceStatus.ACTIVE)
        else:
            rows = access.accessible_devices(request.user).exclude(status=DeviceStatus.REVOKED)
        return Response([device_payload(d) for d in rows.select_related("office", "assigned_to", "companion")])


class CallDeviceEnableView(APIView):
    """Switch Calls on or off for an OCM Phone device (the dialer app). The phone learns it from its next heartbeat (and a
    push); switching off stops the upload and keeps the history. OCM Messages devices cannot take calls (decision 80)."""

    permission_classes = [IsAuthenticated, CanManageCalls]

    @extend_schema(request=s.CallEnableSerializer, responses=s.CallDeviceSerializer, operation_id="calls_devices_enable")
    def post(self, request, pk):
        from modules.sms.services.access import accessible_devices as sms_devices

        device = (sms_devices(request.user) | access.accessible_devices(request.user)).filter(pk=access._uuid(pk)).select_related("office", "assigned_to").first()
        if not device:
            raise ApiError("not_found", "This phone was not found.", status.HTTP_404_NOT_FOUND)
        if device.app != "calls":
            raise ApiError("wrong_app", "This phone runs OCM Messages. Install OCM Phone on it and enroll it with an OCM Phone code.", status.HTTP_409_CONFLICT)
        data = s.CallEnableSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        enabled = data.validated_data["enabled"]
        if enabled and device.status != DeviceStatus.ACTIVE:
            raise ApiError("device_inactive", "This phone is suspended or removed.", status.HTTP_409_CONFLICT)
        with transaction.atomic():
            locked = Device.objects.select_for_update().get(pk=device.pk)
            locked.capabilities = {**(locked.capabilities or {}), "calls": enabled}
            locked.attention = attention_for(locked)
            locked.save(update_fields=["capabilities", "attention"])
            record("calls.device_enable" if enabled else "calls.device_disable", request=request, target_type="device", target_id=device.pk, metadata={"device": device.code})
            from modules.devices.tasks import push_task

            transaction.on_commit(lambda: push_task.delay(str(device.pk), "config"))
        locked.refresh_from_db()
        return Response(device_payload(locked))


# --- OCM Phone enrollment (the dialer app enrolls on its own; decision 80) ---------------------------------------------

class CallEnrollmentListView(sms_device_views.EnrollmentListView):
    """Codes for OCM Phone. Optionally linked to the SMS phone on the same handset, so the missed-call SMS and the admin
    know the two apps belong together."""

    permission_classes = [IsAuthenticated, CanManageCalls]
    platform = "calls"
    create_serializer = s.CallEnrollmentCreateSerializer

    @extend_schema(responses=sms_device_views.EnrollmentSerializer(many=True), operation_id="calls_enrollments_list")
    def get(self, request):
        return super().get(request)

    @extend_schema(request=s.CallEnrollmentCreateSerializer, responses={201: sms_device_views.EnrollmentCreatedSerializer}, operation_id="calls_enrollments_create")
    def post(self, request):
        return super().post(request)

    def options_for(self, values) -> dict:
        return {"backfill_days": values.get("backfill_days")}

    def companion_for(self, request, values):
        if not values.get("companion"):
            return None
        from modules.sms.services.access import accessible_devices as sms_devices

        companion = sms_devices(request.user).filter(pk=values["companion"], app="sms", status=DeviceStatus.ACTIVE).first()
        if not companion:
            raise ApiError("validation_error", "Choose an active SMS phone.", errors={"companion": ["Unknown SMS phone."]})
        return companion


class CallEnrollmentDetailView(sms_device_views.EnrollmentDetailView):
    permission_classes = [IsAuthenticated, CanManageCalls]
    platform = "calls"

    @extend_schema(responses=sms_device_views.EnrollmentSerializer, operation_id="calls_enrollments_retrieve")
    def get(self, request, pk):
        return super().get(request, pk)


class CallEnrollmentShortCodeView(sms_device_views.EnrollmentShortCodeView):
    permission_classes = [IsAuthenticated, CanManageCalls]
    platform = "calls"

    @extend_schema(request=None, responses=sms_device_views.EnrollmentShortCodeSerializer, operation_id="calls_enrollments_short_code")
    def post(self, request, pk):
        return super().post(request, pk)


class CallEnrollmentRevokeView(sms_device_views.EnrollmentRevokeView):
    permission_classes = [IsAuthenticated, CanManageCalls]
    platform = "calls"

    @extend_schema(request=None, responses=sms_device_views.EnrollmentSerializer, operation_id="calls_enrollments_revoke")
    def post(self, request, pk):
        return super().post(request, pk)


class CallDeviceAccessView(APIView):
    permission_classes = [IsAuthenticated, CanManageCalls]

    def _rows(self, device):
        rows = DeviceAccess.objects.filter(device=device).select_related("user").order_by("user__full_name", "user__email")
        return [{"user": r.user_id, "name": r.user.display_name, "email": r.user.email, "can_read": r.can_read, "can_assign_callbacks": r.can_assign_callbacks,
                 "can_annotate": r.can_annotate, "can_export": r.can_export} for r in rows]

    @extend_schema(responses=s.CallDeviceAccessSerializer(many=True), operation_id="calls_device_access_list")
    def get(self, request, pk):
        return Response(self._rows(access.get_device(request.user, pk)))

    @extend_schema(request=s.CallDeviceAccessSerializer(many=True), responses=s.CallDeviceAccessSerializer(many=True), operation_id="calls_device_access_update")
    def put(self, request, pk):
        device = access.get_device(request.user, pk)
        data = s.CallDeviceAccessSerializer(data=request.data, many=True)
        data.is_valid(raise_exception=True)
        entries = [dict(e) for e in data.validated_data]
        ids = {e["user"] for e in entries}
        if User.objects.filter(pk__in=ids, is_active=True).count() != len(ids):
            raise ApiError("validation_error", "One of the users does not exist or is inactive.")
        flags = ("can_read", "can_assign_callbacks", "can_annotate", "can_export")
        with transaction.atomic():
            DeviceAccess.objects.filter(device=device).exclude(user_id__in=ids).delete()
            for entry in entries:
                if any(entry.get(f) for f in flags[1:]):
                    entry["can_read"] = True
                DeviceAccess.objects.update_or_create(user_id=entry["user"], device=device, defaults={f: entry[f] for f in flags})
            record("calls.access_update", request=request, target_type="device", target_id=device.pk,
                   metadata={"device": device.code, "entries": [{k: e[k] for k in ("user", *flags)} for e in entries]})
        return Response(self._rows(device))


# --- Customers (company directory) -------------------------------------------------------------------------------------


def customer_payload(user, customer: Customer, detail: bool = False) -> dict:
    data = s.CustomerSerializer(customer).data
    if detail:
        visible_calls = access.accessible_calls(user).filter(customer=customer)
        data.update({
            "notes": directory.notes(customer), "can_edit": directory.can_edit(user, customer),
            "aliases": list(Customer.objects.filter(merged_into=customer).values_list("key", flat=True)),
            "stats": {"calls": visible_calls.count(), "missed": visible_calls.filter(direction=Direction.IN, result__in=MISSED_RESULTS).count(),
                      "unreturned": visible_calls.filter(direction=Direction.IN, result__in=MISSED_RESULTS, is_final=True, returned_at__isnull=True).count()},
        })
    return data


def _owner(values):
    if "owner" in values and values["owner"] is not None:
        owner = User.objects.filter(pk=values["owner"], is_active=True).first()
        if not owner:
            raise ApiError("validation_error", "Choose an active user.", errors={"owner": ["Unknown user."]})
        values["owner"] = owner
    return values


class CustomerListView(CallsView):
    @extend_schema(parameters=[OpenApiParameter("q", str), OpenApiParameter("tag", str), OpenApiParameter("cursor", str)],
                   responses=s.CustomerPageSerializer, operation_id="calls_customers_list")
    def get(self, request):
        qs = directory.accessible_customers(request.user).select_related("owner")
        q = (request.query_params.get("q") or "").strip()[:60]
        if q:
            digits = re.sub(r"\D", "", q)
            condition = Q(display_name__icontains=q) | Q(organisation__icontains=q) | Q(key__icontains=q)
            if len(digits) >= 3:
                condition |= Q(key__contains=digits) | (Q(key__contains=digits[1:]) if digits.startswith("0") else Q())
            qs = qs.filter(condition)
        if request.query_params.get("tag"):
            qs = qs.filter(tags__contains=[request.query_params["tag"]])
        qs = qs.order_by("-updated_at", "-id")
        cursor = decode_cursor(request.query_params.get("cursor"))
        if cursor and "t" in cursor and "id" in cursor:
            qs = qs.filter(Q(updated_at__lt=cursor["t"]) | Q(updated_at=cursor["t"], id__lt=cursor["id"]))
        rows = list(qs[: PAGE_SIZE + 1])
        next_cursor = encode_cursor({"t": rows[PAGE_SIZE - 1].updated_at.isoformat(), "id": rows[PAGE_SIZE - 1].pk}) if len(rows) > PAGE_SIZE else None
        return Response({"results": s.CustomerSerializer(rows[:PAGE_SIZE], many=True).data, "next_cursor": next_cursor})

    @extend_schema(request=s.CustomerWriteSerializer, responses={201: s.CustomerDetailSerializer}, operation_id="calls_customers_create")
    def post(self, request):
        data = s.CustomerWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        customer = directory.create(request.user, _owner(dict(data.validated_data)), request=request)
        return Response(customer_payload(request.user, customer, detail=True), status=status.HTTP_201_CREATED)


class CustomerDetailView(CallsView):
    @extend_schema(responses=s.CustomerDetailSerializer, operation_id="calls_customers_retrieve")
    def get(self, request, pk):
        return Response(customer_payload(request.user, directory.get_customer(request.user, pk), detail=True))

    @extend_schema(request=s.CustomerWriteSerializer, responses=s.CustomerDetailSerializer, operation_id="calls_customers_update")
    def patch(self, request, pk):
        customer = directory.get_customer(request.user, pk)
        data = s.CustomerWriteSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = _owner(dict(data.validated_data))
        values.pop("number", None)
        directory.update(request.user, customer, values, request=request)
        return Response(customer_payload(request.user, customer, detail=True))

    @extend_schema(responses={204: None}, operation_id="calls_customers_delete")
    def delete(self, request, pk):
        directory.delete(request.user, directory.get_customer(request.user, pk), request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerTimelineView(CallsView):
    @extend_schema(responses=s.CallHistoryItemSerializer(many=True), operation_id="calls_customers_timeline")
    def get(self, request, pk):
        customer = directory.get_customer(request.user, pk)
        numbers = directory.numbers_of(customer)
        items = [{"kind": "call", "at": c.started_at, "direction": c.direction, "result": c.result, "talk_seconds": c.talk_seconds, "device": c.device.name,
                  "call_id": c.pk, "conversation_id": None, "snippet": ""}
                 for c in access.accessible_calls(request.user).filter(Q(customer=customer) | Q(number_e164__in=numbers)).select_related("device").order_by("-started_at")[:100]]
        from modules.sms.models import Message
        from modules.sms.services.access import accessible_conversations

        conversations = accessible_conversations(request.user).filter(Q(customer=customer) | Q(participants_key__in=numbers))
        for message in (Message.objects.filter(conversation__in=conversations).select_related("device", "conversation").order_by("-provider_date")[:100]):
            snippet = "" if message.is_sensitive else decrypt_text(message.encrypted_body)[:160]
            items.append({"kind": "sms", "at": message.provider_date, "direction": message.direction, "result": message.status, "talk_seconds": None,
                          "device": message.device.name, "call_id": None, "conversation_id": message.conversation_id, "snippet": snippet})
        return Response(sorted(items, key=lambda item: item["at"], reverse=True)[:150])


class CustomerMergeView(CallsView):
    @extend_schema(request=s.CustomerMergeSerializer, responses=s.CustomerDetailSerializer, operation_id="calls_customers_merge")
    def post(self, request):
        data = s.CustomerMergeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        target = directory.get_customer(request.user, data.validated_data["target"])
        sources = [directory.get_customer(request.user, pk) for pk in data.validated_data["sources"]]
        return Response(customer_payload(request.user, directory.merge(request.user, target, sources, request=request), detail=True))


# --- Tools: outcomes, settings, office hours, tariffs -----------------------------------------------------------------


class OutcomeListView(CallsView):
    @extend_schema(responses=s.CallOutcomeSerializer(many=True), operation_id="calls_outcomes_list")
    def get(self, request):
        return Response(s.CallOutcomeSerializer(CallOutcome.objects.all(), many=True).data)

    @extend_schema(request=s.CallOutcomeSerializer, responses={201: s.CallOutcomeSerializer}, operation_id="calls_outcomes_create")
    def post(self, request):
        _require_manage(request)
        data = s.CallOutcomeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        outcome = data.save()
        record("calls.outcome_create", request=request, target_type="call_outcome", target_id=outcome.pk, metadata={"name": outcome.name})
        return Response(s.CallOutcomeSerializer(outcome).data, status=status.HTTP_201_CREATED)


class OutcomeDetailView(CallsView):
    @extend_schema(request=s.CallOutcomeSerializer, responses=s.CallOutcomeSerializer, operation_id="calls_outcomes_update")
    def patch(self, request, pk):
        _require_manage(request)
        outcome = CallOutcome.objects.filter(pk=pk).first()
        if not outcome:
            raise ApiError("not_found", "This outcome was not found.", status.HTTP_404_NOT_FOUND)
        data = s.CallOutcomeSerializer(outcome, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        data.save()
        record("calls.outcome_update", request=request, target_type="call_outcome", target_id=outcome.pk, metadata={"fields": sorted(request.data)})
        return Response(data.data)

    @extend_schema(responses={204: None}, operation_id="calls_outcomes_delete")
    def delete(self, request, pk):
        _require_manage(request)
        outcome = CallOutcome.objects.filter(pk=pk).first()
        if not outcome:
            raise ApiError("not_found", "This outcome was not found.", status.HTTP_404_NOT_FOUND)
        # Outcomes already used on calls are retired, not deleted, so past notes keep their label.
        if outcome.annotations.exists():
            outcome.is_active = False
            outcome.save(update_fields=["is_active", "updated_at"])
        else:
            outcome.delete()
        record("calls.outcome_delete", request=request, target_type="call_outcome", target_id=pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _require_manage(request):
    if not request.user.has_perm("calls.manage_settings"):
        raise ApiError("permission_denied", "You don't have permission to change Calls settings.", status.HTTP_403_FORBIDDEN)


SETTING_FIELDS = ("unreturned_hours", "outcome_required_after_seconds", "post_call_card", "auto_sms_enabled", "auto_sms_template", "auto_sms_after_hours_only",
                  "auto_sms_per_number_per_day", "auto_sms_cooldown_hours", "callback_expiry_hours", "retention_days")


class SettingsView(CallsView):
    def _payload(self):
        config = CallSettings.load()
        return {**{f: getattr(config, f) for f in SETTING_FIELDS}, "effective_retention_days": retention_days()}

    @extend_schema(responses=s.CallSettingsSerializer, operation_id="calls_settings_retrieve")
    def get(self, request):
        return Response(self._payload())

    @extend_schema(request=s.CallSettingsSerializer, responses=s.CallSettingsSerializer, operation_id="calls_settings_update")
    def patch(self, request):
        _require_manage(request)
        data = s.CallSettingsSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        config = CallSettings.load()
        changed = {k: v for k, v in data.validated_data.items() if k in SETTING_FIELDS and getattr(config, k) != v}
        for key, value in changed.items():
            setattr(config, key, value)
        if changed:
            config.save()
            record("calls.settings_update", request=request, target_type="calls_settings", metadata={"changed": {k: (v if k != "auto_sms_template" else "changed") for k, v in changed.items()}})
        return Response(self._payload())


class OfficeHoursListView(CallsView):
    @extend_schema(responses=s.OfficeHoursSerializer(many=True), operation_id="calls_office_hours_list")
    def get(self, request):
        rows = {row.office_id: row for row in OfficeHours.objects.all()}
        return Response([s.office_hours_payload(office, rows.get(office.pk)) for office in Office.objects.order_by("name")])


class OfficeHoursDetailView(CallsView):
    @extend_schema(request=s.OfficeHoursSerializer, responses=s.OfficeHoursSerializer, operation_id="calls_office_hours_update")
    def put(self, request, office_id):
        _require_manage(request)
        office = Office.objects.filter(pk=office_id).first()
        if not office:
            raise ApiError("not_found", "This office was not found.", status.HTTP_404_NOT_FOUND)
        data = s.OfficeHoursSerializer(data={**request.data, "office": office.pk})
        data.is_valid(raise_exception=True)
        v = data.validated_data
        try:
            week, holidays = hours.clean_week(v["week"]), hours.clean_holidays(v["holidays"])
        except hours.HoursError as exc:
            raise ApiError("validation_error", str(exc), errors={"week": [str(exc)]}) from None
        import zoneinfo

        if v["timezone"] not in zoneinfo.available_timezones():
            raise ApiError("validation_error", "Choose a time zone.", errors={"timezone": ["Unknown time zone."]})
        row, _ = OfficeHours.objects.update_or_create(office=office, defaults={"timezone": v["timezone"], "week": week, "holidays": holidays})
        record("calls.office_hours_update", request=request, target_type="office", target_id=office.pk, metadata={"timezone": row.timezone, "holidays": len(holidays)})
        return Response(s.office_hours_payload(office, row))


class TariffListView(CallsView):
    @extend_schema(responses=s.CarrierTariffSerializer(many=True), operation_id="calls_tariffs_list")
    def get(self, request):
        return Response(s.CarrierTariffSerializer(CarrierTariff.objects.all(), many=True).data)

    @extend_schema(request=s.CarrierTariffSerializer, responses={201: s.CarrierTariffSerializer}, operation_id="calls_tariffs_create")
    def post(self, request):
        _require_manage(request)
        data = s.CarrierTariffSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        tariff = data.save()
        record("calls.tariff_create", request=request, target_type="tariff", target_id=tariff.pk, metadata={"carrier": tariff.carrier, "per_minute": str(tariff.per_minute)})
        return Response(s.CarrierTariffSerializer(tariff).data, status=status.HTTP_201_CREATED)


class TariffDetailView(CallsView):
    @extend_schema(request=s.CarrierTariffSerializer, responses=s.CarrierTariffSerializer, operation_id="calls_tariffs_update")
    def patch(self, request, pk):
        _require_manage(request)
        tariff = CarrierTariff.objects.filter(pk=pk).first()
        if not tariff:
            raise ApiError("not_found", "This tariff was not found.", status.HTTP_404_NOT_FOUND)
        data = s.CarrierTariffSerializer(tariff, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        data.save()
        record("calls.tariff_update", request=request, target_type="tariff", target_id=tariff.pk, metadata={"carrier": tariff.carrier, "per_minute": str(tariff.per_minute)})
        return Response(data.data)

    @extend_schema(responses={204: None}, operation_id="calls_tariffs_delete")
    def delete(self, request, pk):
        _require_manage(request)
        deleted = CarrierTariff.objects.filter(pk=pk).delete()[0]
        if not deleted:
            raise ApiError("not_found", "This tariff was not found.", status.HTTP_404_NOT_FOUND)
        record("calls.tariff_delete", request=request, target_type="tariff", target_id=pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CallSimulatorView(APIView):
    """Demo phones only (SMS_ENABLE_SIMULATOR, refused in production): ring an incoming call, a missed one, or run a tick."""

    permission_classes = [IsAuthenticated, CanUseCalls]

    @extend_schema(request=s.CallSimulatorActionSerializer, responses={204: None}, operation_id="calls_devices_simulator")
    def post(self, request, pk):
        from django.conf import settings

        if not settings.SMS_ENABLE_SIMULATOR:
            raise ApiError("not_found", "Not found.", status.HTTP_404_NOT_FOUND)
        device = access.get_device(request.user, pk, access.ASSIGN)
        if not device.is_simulated:
            raise ApiError("validation_error", "This is a real phone.")
        data = s.CallSimulatorActionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        from ..services import simulator

        simulator.control(device, data.validated_data["action"])
        return Response(status=status.HTTP_204_NO_CONTENT)
