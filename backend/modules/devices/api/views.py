import time

from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response

from common.errors import ApiError
from common.http import ClientIpScopedThrottle

from ..services import enrollment, events
from ..services.auth import DeviceAuthError, mint
from ..services.health import record_heartbeat
from .base import DeviceAPIView, PublicDeviceAPIView
from .serializers import (
    EnrollInfoSerializer,
    EnrollRequestSerializer,
    EnrollResponseSerializer,
    HeartbeatResponseSerializer,
    HeartbeatSerializer,
    PushTokenSerializer,
    ShortCodeRequestSerializer,
    ShortCodeResponseSerializer,
    TokenRequestSerializer,
    TokenResponseSerializer,
)


class EnrollInfoView(PublicDeviceAPIView):
    """What the app shows before enrolling: company, device name and the monitoring notice to accept."""

    throttle_scope = "device_enroll"

    @extend_schema(parameters=[OpenApiParameter("token", str, required=True)], responses=EnrollInfoSerializer, operation_id="device_enroll_info")
    def get(self, request):
        invite = enrollment.invite_for_token(request.query_params.get("token", ""))
        if not invite:
            raise ApiError("invalid_token", "This enrollment code is not valid. Ask your administrator for a new one.", status.HTTP_404_NOT_FOUND)
        platform = enrollment.invite_platform(invite)
        if platform == "calls":
            from modules.calls.models import CallSettings

            notice = CallSettings.load().monitoring_notice
        else:
            from modules.sms.models import SmsSettings

            notice = SmsSettings.load().monitoring_notice
        return Response({
            "state": invite.state, "company_name": settings.COMPANY_NAME, "device_name": invite.name, "office": invite.office.name,
            "notice": notice, "platform": platform, "expires_at": invite.expires_at, "server_time": int(time.time()),
        })


class ShortCodeHourlyThrottle(ClientIpScopedThrottle):
    """The second, hourly per-IP limit on short codes (ScopedRateThrottle reads one scope per class)."""

    scope_attr = "throttle_scope_hourly"


class EnrollResolveView(PublicDeviceAPIView):
    """Short code (XXXX-XXXX) → a token for its invite. 5 per minute and 20 per hour per IP, a global breaker, audited."""

    throttle_scope = "device_short_code"
    throttle_scope_hourly = "device_short_code_hour"
    throttle_classes = [ClientIpScopedThrottle, ShortCodeHourlyThrottle]

    @extend_schema(request=ShortCodeRequestSerializer, responses=ShortCodeResponseSerializer, operation_id="device_enroll_resolve")
    def post(self, request):
        data = ShortCodeRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            token, ttl = enrollment.resolve_short_code(data.validated_data["code"], request=request)
        except enrollment.EnrollmentError as exc:
            raise ApiError(exc.code, exc.message, exc.status) from None
        return Response({"token": token, "expires_in": ttl})


class EnrollView(PublicDeviceAPIView):
    throttle_scope = "device_enroll"

    @extend_schema(request=EnrollRequestSerializer, responses={201: EnrollResponseSerializer}, operation_id="device_enroll")
    def post(self, request):
        data = EnrollRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            device, token, ttl = enrollment.enroll(data.validated_data, request=request)
        except enrollment.EnrollmentError as exc:
            raise ApiError(exc.code, exc.message, exc.status) from None
        return Response({
            "device_id": device.pk, "device_code": device.code, "name": device.name, "office": device.office.name, "options": device.options,
            "hardware_backed": device.hardware_backed, "access_token": token, "token_type": "Bearer", "expires_in": ttl,
        }, status=status.HTTP_201_CREATED)


class TokenView(PublicDeviceAPIView):
    throttle_scope = "device_auth"

    @extend_schema(request=TokenRequestSerializer, responses=TokenResponseSerializer, operation_id="device_auth_token")
    def post(self, request):
        data = TokenRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            _, token, ttl = mint(data.validated_data, request=request)
        except DeviceAuthError as exc:
            raise ApiError(exc.code, exc.message, exc.status) from None
        return Response({"access_token": token, "token_type": "Bearer", "expires_in": ttl})


class HeartbeatView(DeviceAPIView):
    @extend_schema(request=HeartbeatSerializer, responses=HeartbeatResponseSerializer, operation_id="device_heartbeat")
    def post(self, request):
        data = HeartbeatSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        device = record_heartbeat(self.device, data.validated_data)
        return Response({"status": device.status, "capabilities": {p: device.has(p) for p in ("sms", "calls")}, "attention": device.attention, "server_time": int(time.time()), "poll_seconds": settings.SMS_DEVICE_POLL_SECONDS})


class PushTokenView(DeviceAPIView):
    @extend_schema(request=PushTokenSerializer, responses={204: None}, operation_id="device_push_token")
    def post(self, request):
        data = PushTokenSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        device = self.device
        device.push_token = data.validated_data["token"].strip()
        device.save(update_fields=["push_token"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class SyncResultSerializer(serializers.Serializer):
    acked_seq = serializers.IntegerField()
    processed = serializers.IntegerField()
    skipped = serializers.IntegerField()
    rejected = serializers.ListField(child=serializers.DictField())
    disabled_platform = serializers.CharField(required=False, help_text="Set when the batch stopped at an event of a switched-off platform.")


class SyncEventsView(DeviceAPIView):
    """The phone's outbox, for every phone platform (events.py). Ordered, idempotent, per-event savepoints."""

    @extend_schema(request=events.BatchSerializer, responses=SyncResultSerializer, operation_id="device_sync_events")
    def post(self, request):
        if len(request.body) > events.MAX_BATCH_BYTES:
            raise ApiError("batch_too_large", "Send at most 1 MB per batch.", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        data = events.BatchSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = events.process(self.device, data.validated_data["events"])
        if result.get("disabled_platform") and not result["processed"] and not result["rejected"] and not result["skipped"]:
            name = {"sms": "SMS", "calls": "Calls"}.get(result["disabled_platform"], result["disabled_platform"])
            raise ApiError("platform_disabled", f"{name} is switched off on the server. Everything stays on the phone and uploads later.", status.HTTP_403_FORBIDDEN)
        return Response(result)
