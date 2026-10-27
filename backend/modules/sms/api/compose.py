"""Compose and the outbound queue, quick replies, sensitive-message rules and platform settings."""

from django.conf import settings
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.errors import ApiError
from modules.audit.services import record

from ..models import Contact, Message, MessageStatus, QuickReply, SensitiveRule, SmsSettings
from ..services import access, outbound
from ..services.text import segment_info
from .conversations import message_queryset
from .permissions import CanManageDevices, CanUseSms
from .serializers import (
    SmsComposeResultSerializer,
    SmsComposeSerializer,
    SmsMessageSerializer,
    OutboxItemSerializer,
    QuickReplySerializer,
    SegmentInfoSerializer,
    SensitiveRuleSerializer,
    SmsSettingsSerializer,
)

OUTBOX_STATUSES = {
    "pending": Message.PENDING_STATUSES,
    "problems": (MessageStatus.FAILED, MessageStatus.EXPIRED, MessageStatus.UNKNOWN),
}


class SendView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(request=SmsComposeSerializer, responses={202: SmsComposeResultSerializer}, operation_id="sms_send")
    def post(self, request):
        data = SmsComposeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        message = outbound.compose(request.user, data.validated_data, request=request)
        message = message_queryset().get(pk=message.pk)
        return Response({"message": SmsMessageSerializer(message).data, "conversation": message.conversation_id}, status=status.HTTP_202_ACCEPTED)


class SegmentsView(APIView):
    """The composer counts segments locally; this endpoint exists so the phone and admin agree on the rules."""

    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(parameters=[OpenApiParameter("text", str)], responses=SegmentInfoSerializer, operation_id="sms_segments")
    def get(self, request):
        info = segment_info((request.query_params.get("text") or "")[:5000])
        return Response(info.__dict__)


class CancelView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(request=None, responses=SmsMessageSerializer, operation_id="sms_messages_cancel")
    def post(self, request, pk):
        message = outbound.cancel(request.user, pk, request=request)
        payload = SmsMessageSerializer(message_queryset().get(pk=message.pk)).data
        return Response(payload)


class RetryView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(request=None, responses={202: SmsComposeResultSerializer}, operation_id="sms_messages_retry")
    def post(self, request, pk):
        message = outbound.retry(request.user, pk, request=request)
        message = message_queryset().get(pk=message.pk)
        return Response({"message": SmsMessageSerializer(message).data, "conversation": message.conversation_id}, status=status.HTTP_202_ACCEPTED)


class OutboxView(APIView):
    """Admin messages still on their way (queued, at the phone, sending) or that need a decision."""

    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(parameters=[OpenApiParameter("device", str), OpenApiParameter("view", str, enum=["pending", "problems", "scheduled"])],
                   responses=OutboxItemSerializer(many=True), operation_id="sms_outbox_list")
    def get(self, request):
        devices = access.accessible_devices(request.user)
        device = request.query_params.get("device")
        if device and device != "all":
            devices = devices.filter(pk=access.get_device(request.user, device).pk)
        qs = message_queryset().select_related("device", "device__office", "conversation").filter(device__in=devices, origin=Message.ORIGIN_ADMIN)
        view = request.query_params.get("view") or "pending"
        if view == "scheduled":
            qs = qs.filter(status=MessageStatus.QUEUED, is_scheduled=True).order_by("send_at")
        elif view == "problems":
            qs = qs.filter(status__in=OUTBOX_STATUSES["problems"]).order_by("-provider_date")
        else:
            qs = qs.filter(status__in=OUTBOX_STATUSES["pending"]).filter(Q(is_scheduled=False) | ~Q(status=MessageStatus.QUEUED)).order_by("send_at")
        rows = list(qs[:200])
        addresses = {a for m in rows for a in m.conversation.addresses[:3]}
        names = {(c.device_id, c.address): c.display_name for c in Contact.objects.filter(device__in={m.device_id for m in rows}, address__in=addresses) if c.display_name}
        return Response(OutboxItemSerializer(rows, many=True, context={"names": names}).data)


# --- Quick replies ----------------------------------------------------------------------------------------------


def _can_edit_reply(user, device_id) -> None:
    if device_id:
        access.get_device(user, device_id, access.MANAGE)
    elif not user.has_perm("sms.manage_devices"):
        raise ApiError("permission_denied", "Only admins can change quick replies for every phone.", status.HTTP_403_FORBIDDEN)


class QuickReplyListView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(parameters=[OpenApiParameter("device", str)], responses=QuickReplySerializer(many=True), operation_id="sms_quick_replies_list")
    def get(self, request):
        devices = access.accessible_devices(request.user)
        qs = QuickReply.objects.filter(Q(device__isnull=True) | Q(device__in=devices))
        device = request.query_params.get("device")
        if device and device != "all":
            qs = qs.filter(Q(device__isnull=True) | Q(device=access.get_device(request.user, device)))
        return Response(QuickReplySerializer(qs, many=True).data)

    @extend_schema(request=QuickReplySerializer, responses={201: QuickReplySerializer}, operation_id="sms_quick_replies_create")
    def post(self, request):
        data = QuickReplySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        device_id = data.validated_data.pop("device_id", None)
        _can_edit_reply(request.user, device_id)
        reply = QuickReply.objects.create(**data.validated_data, device_id=device_id, created_by=request.user)
        record("sms.quick_reply_create", request=request, target_type="quick_reply", target_id=reply.pk, metadata={"title": reply.title})
        return Response(QuickReplySerializer(reply).data, status=status.HTTP_201_CREATED)


class QuickReplyDetailView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    def _reply(self, request, pk) -> QuickReply:
        reply = QuickReply.objects.filter(pk=pk).filter(Q(device__isnull=True) | Q(device__in=access.accessible_devices(request.user))).first()
        if not reply:
            raise ApiError("not_found", "This quick reply was not found.", status.HTTP_404_NOT_FOUND)
        _can_edit_reply(request.user, reply.device_id)
        return reply

    @extend_schema(request=QuickReplySerializer, responses=QuickReplySerializer, operation_id="sms_quick_replies_update")
    def patch(self, request, pk):
        reply = self._reply(request, pk)
        data = QuickReplySerializer(reply, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        data.validated_data.pop("device_id", None)
        for key, value in data.validated_data.items():
            setattr(reply, key, value)
        reply.save()
        record("sms.quick_reply_update", request=request, target_type="quick_reply", target_id=reply.pk, metadata={"title": reply.title})
        return Response(QuickReplySerializer(reply).data)

    @extend_schema(responses={204: None}, operation_id="sms_quick_replies_destroy")
    def delete(self, request, pk):
        reply = self._reply(request, pk)
        record("sms.quick_reply_delete", request=request, target_type="quick_reply", target_id=reply.pk, metadata={"title": reply.title})
        reply.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Sensitive-message rules ------------------------------------------------------------------------------------


class SensitiveRuleListView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(responses=SensitiveRuleSerializer(many=True), operation_id="sms_rules_list")
    def get(self, request):
        return Response(SensitiveRuleSerializer(SensitiveRule.objects.all(), many=True).data)

    @extend_schema(request=SensitiveRuleSerializer, responses={201: SensitiveRuleSerializer}, operation_id="sms_rules_create")
    def post(self, request):
        if not request.user.has_perm("sms.manage_devices"):
            raise ApiError("permission_denied", "Only admins can change sensitive-message rules.", status.HTTP_403_FORBIDDEN)
        data = SensitiveRuleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        rule = data.save()
        record("sms.rule_create", request=request, target_type="sensitive_rule", target_id=rule.pk, metadata={"name": rule.name, "kind": rule.kind})
        return Response(SensitiveRuleSerializer(rule).data, status=status.HTTP_201_CREATED)


class SensitiveRuleDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageDevices]

    def _rule(self, pk):
        rule = SensitiveRule.objects.filter(pk=pk).first()
        if not rule:
            raise ApiError("not_found", "This rule was not found.", status.HTTP_404_NOT_FOUND)
        return rule

    @extend_schema(request=SensitiveRuleSerializer, responses=SensitiveRuleSerializer, operation_id="sms_rules_update")
    def patch(self, request, pk):
        rule = self._rule(pk)
        data = SensitiveRuleSerializer(rule, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        rule = data.save()
        record("sms.rule_update", request=request, target_type="sensitive_rule", target_id=rule.pk, metadata={"name": rule.name, "enabled": rule.is_enabled})
        return Response(SensitiveRuleSerializer(rule).data)

    @extend_schema(responses={204: None}, operation_id="sms_rules_destroy")
    def delete(self, request, pk):
        rule = self._rule(pk)
        record("sms.rule_delete", request=request, target_type="sensitive_rule", target_id=rule.pk, metadata={"name": rule.name})
        rule.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Settings -------------------------------------------------------------------------------------------------


def settings_payload() -> dict:
    from modules.devices.services.push import configured

    row = SmsSettings.load()
    return {
        "monitoring_notice": row.monitoring_notice, "default_signature": row.default_signature, "retention_days": settings.SMS_RETENTION_DAYS,
        "mirror_device_deletes": settings.SMS_MIRROR_DEVICE_DELETES, "outbound_ttl_hours": settings.SMS_OUTBOUND_TTL_HOURS,
        "daily_cap": settings.SMS_DEVICE_DAILY_CAP, "allow_short_codes": settings.SMS_ALLOW_SHORT_CODES, "push_configured": configured(),
        "simulator_enabled": settings.SMS_ENABLE_SIMULATOR,
    }


class SmsSettingsView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(responses=SmsSettingsSerializer, operation_id="sms_settings_get")
    def get(self, request):
        return Response(settings_payload())

    @extend_schema(request=SmsSettingsSerializer, responses=SmsSettingsSerializer, operation_id="sms_settings_update")
    def put(self, request):
        if not request.user.has_perm("sms.manage_devices"):
            raise ApiError("permission_denied", "Only admins can change SMS settings.", status.HTTP_403_FORBIDDEN)
        data = SmsSettingsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = SmsSettings.load()
        row.monitoring_notice = data.validated_data["monitoring_notice"].strip()
        row.default_signature = data.validated_data["default_signature"].strip()
        row.save()
        record("settings.sms_update", request=request, metadata={"notice_length": len(row.monitoring_notice)})
        return Response(settings_payload())
