"""Phone-facing SMS endpoints (mounted under /api/v1/device/). Device-token auth only; every query is scoped to
`request.auth.device`, so a phone can only read or write its own data."""

import time

from django.conf import settings
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from common.errors import ApiError
from modules.devices.api.base import DeviceAPIView
from modules.platforms.services import is_platform_enabled

from ..models import Message, MessagePart, QuickReply
from ..services import media, outbound, sync
from ..services.store import from_millis


class SmsDeviceAPIView(DeviceAPIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not is_platform_enabled("sms"):
            raise ApiError("platform_disabled", "SMS is switched off on the server. Messages stay on the phone and upload later.", status.HTTP_403_FORBIDDEN)


class ConfigResponseSerializer(serializers.Serializer):
    device = serializers.DictField()
    options = serializers.DictField()
    sims = serializers.ListField(child=serializers.DictField())
    quick_replies = serializers.ListField(child=serializers.DictField())
    poll_seconds = serializers.IntegerField()
    show_admin_name = serializers.BooleanField()
    outbound_ttl_hours = serializers.IntegerField()
    acked_seq = serializers.IntegerField()
    resync_requested = serializers.BooleanField()
    server_time = serializers.IntegerField()


class ConfigView(SmsDeviceAPIView):
    @extend_schema(responses=ConfigResponseSerializer, operation_id="device_sms_config")
    def get(self, request):
        device = self.device
        replies = QuickReply.objects.filter(Q(device__isnull=True) | Q(device=device)).order_by("title")[:100]
        return Response({
            "device": {"id": str(device.pk), "code": device.code, "name": device.name, "office": device.office.name},
            "options": device.options,
            "sims": [{"subscription_id": s.subscription_id, "label": s.label, "colour": s.colour} for s in device.sim_lines.filter(is_active=True)],
            "quick_replies": [{"id": r.pk, "title": r.title, "body": r.body} for r in replies],
            "poll_seconds": settings.SMS_DEVICE_POLL_SECONDS,
            "show_admin_name": settings.SMS_SHOW_ADMIN_NAME_ON_PHONE,
            "outbound_ttl_hours": settings.SMS_OUTBOUND_TTL_HOURS,
            "acked_seq": int(device.sync_state.get("last_seq", 0)),
            "resync_requested": False,
            "server_time": int(time.time()),
        })


class SyncResultSerializer(serializers.Serializer):
    acked_seq = serializers.IntegerField()
    processed = serializers.IntegerField()
    skipped = serializers.IntegerField()
    rejected = serializers.ListField(child=serializers.DictField())


class SyncEventsView(SmsDeviceAPIView):
    @extend_schema(request=sync.BatchSerializer, responses=SyncResultSerializer, operation_id="device_sync_events")
    def post(self, request):
        if len(request.body) > sync.MAX_BATCH_BYTES:
            raise ApiError("batch_too_large", "Send at most 1 MB per batch.", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        data = sync.BatchSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(sync.process(self.device, data.validated_data["events"]))


class MediaChunkSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["mms"], default="mms")
    provider_id = serializers.IntegerField(min_value=0)
    date = serializers.IntegerField()
    seq = serializers.IntegerField(min_value=0, max_value=50)
    offset = serializers.IntegerField(min_value=0)
    chunk = serializers.FileField()


class MediaChunkResultSerializer(serializers.Serializer):
    received_bytes = serializers.IntegerField()
    complete = serializers.BooleanField()


class MediaUploadView(SmsDeviceAPIView):
    parser_classes = [MultiPartParser]

    @extend_schema(request={"multipart/form-data": MediaChunkSerializer}, responses=MediaChunkResultSerializer, operation_id="device_sync_media")
    def post(self, request):
        data = MediaChunkSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        part = MessagePart.objects.filter(
            message__device=self.device, message__kind=Message.MMS, message__provider_id=values["provider_id"],
            message__provider_date=from_millis(values["date"]), seq=values["seq"],
        ).first()
        if not part:
            raise ApiError("not_found", "Declare the message and its parts in a sync event first.", status.HTTP_404_NOT_FOUND)
        chunk = values["chunk"].read(media.MAX_CHUNK + 1)
        try:
            media.receive_chunk(part, values["offset"], chunk)
        except media.MediaError as exc:
            raise ApiError(exc.code, exc.message, exc.status, errors={"received_bytes": [str(part.received_bytes)]}) from None
        return Response({"received_bytes": part.received_bytes, "complete": bool(part.uploaded_at)})


class ClaimSerializer(serializers.Serializer):
    limit = serializers.IntegerField(min_value=1, max_value=outbound.CLAIM_LIMIT, required=False, default=outbound.CLAIM_LIMIT)


class ClaimResultSerializer(serializers.Serializer):
    messages = serializers.ListField(child=serializers.DictField())
    commands = serializers.ListField(child=serializers.DictField())
    lease_seconds = serializers.IntegerField()


class ClaimView(SmsDeviceAPIView):
    @extend_schema(request=ClaimSerializer, responses=ClaimResultSerializer, operation_id="device_outbox_claim")
    def post(self, request):
        data = ClaimSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(outbound.claim(self.device, data.validated_data["limit"]))


class StatusReportSerializer(serializers.Serializer):
    client_uuid = serializers.UUIDField()
    status = serializers.ChoiceField(choices=sorted(outbound.ALLOWED_REPORTS))
    at = serializers.IntegerField(required=False, allow_null=True, default=None)
    error_code = serializers.IntegerField(required=False, allow_null=True, default=None)
    parts = serializers.IntegerField(min_value=1, max_value=50, required=False, allow_null=True, default=None)

    def validate_at(self, value):
        if value is not None:
            sync._check_date(value)
        return value


class CommandAckSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    ok = serializers.BooleanField(default=True)


class StatusBatchSerializer(serializers.Serializer):
    reports = StatusReportSerializer(many=True, max_length=200, required=False, default=list)
    command_acks = CommandAckSerializer(many=True, max_length=200, required=False, default=list)


class StatusResultSerializer(serializers.Serializer):
    results = serializers.ListField(child=serializers.DictField())


class StatusView(SmsDeviceAPIView):
    @extend_schema(request=StatusBatchSerializer, responses=StatusResultSerializer, operation_id="device_outbox_status")
    def post(self, request):
        data = StatusBatchSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        outbound.ack_commands(self.device, data.validated_data["command_acks"])
        return Response(outbound.report(self.device, data.validated_data["reports"]))
