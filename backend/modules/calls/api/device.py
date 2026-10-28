"""Phone-facing Calls endpoints (mounted under /api/v1/device/calls/). Device-token auth only; every query is scoped
to the authenticated phone. Calls events themselves go through the shared sync/events pipeline."""

import time

from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response

from common.devicecrypto import decrypt_text
from common.errors import ApiError
from common.pagination import decode_cursor, encode_cursor
from modules.devices.api.base import DeviceAPIView
from modules.platforms.services import is_platform_enabled

from ..models import CallOutcome, CallSettings
from ..services import callbacks

DIRECTORY_PAGE = 500


class CallsDeviceAPIView(DeviceAPIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not is_platform_enabled("calls"):
            raise ApiError("platform_disabled", "Calls is switched off on the server. Calls stay in the phone's history and upload later.", status.HTTP_403_FORBIDDEN)
        if not request.user.device.has("calls"):
            raise ApiError("calls_not_enabled", "Calls is not enabled for this phone.", status.HTTP_403_FORBIDDEN)


class CallsConfigSerializer(serializers.Serializer):
    outcomes = serializers.ListField(child=serializers.DictField())
    post_call_card = serializers.BooleanField()
    outcome_required_after_seconds = serializers.IntegerField()
    sims = serializers.ListField(child=serializers.DictField())
    server_time = serializers.IntegerField()


class CallsConfigView(CallsDeviceAPIView):
    @extend_schema(responses=CallsConfigSerializer, operation_id="device_calls_config")
    def get(self, request):
        config = CallSettings.load()
        return Response({
            "outcomes": [{"id": o.pk, "name": o.name, "colour": o.colour} for o in CallOutcome.objects.filter(is_active=True)],
            "post_call_card": config.post_call_card, "outcome_required_after_seconds": config.outcome_required_after_seconds,
            "sims": [{"subscription_id": s.subscription_id, "label": s.label, "colour": s.colour} for s in self.device.sim_lines.filter(is_active=True)],
            "server_time": int(time.time()),
        })


class PhoneCallbackSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    number = serializers.CharField()
    name = serializers.CharField()
    reason = serializers.CharField()
    requested_by = serializers.CharField()
    priority = serializers.CharField()
    due_at = serializers.IntegerField()
    state = serializers.CharField()
    snoozed_until = serializers.IntegerField(allow_null=True)


class CallbacksView(CallsDeviceAPIView):
    @extend_schema(responses=PhoneCallbackSerializer(many=True), operation_id="device_calls_callbacks")
    def get(self, request):
        return Response([{
            "id": str(t.uuid), "number": t.number_e164, "name": t.customer.display_name if t.customer_id else "", "reason": callbacks.reason(t),
            "requested_by": t.assigned_by.display_name if t.assigned_by_id else "", "priority": t.priority, "due_at": int(t.due_at.timestamp() * 1000),
            "state": t.state, "snoozed_until": int(t.snoozed_until.timestamp() * 1000) if t.snoozed_until else None,
        } for t in callbacks.for_phone(self.device)])


class DirectoryEntrySerializer(serializers.Serializer):
    number = serializers.CharField()
    name = serializers.CharField(allow_blank=True)
    organisation = serializers.CharField(allow_blank=True)
    removed = serializers.BooleanField()


class DirectoryPageSerializer(serializers.Serializer):
    entries = DirectoryEntrySerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)
    complete = serializers.BooleanField()


class DirectoryView(CallsDeviceAPIView):
    """Caller ID from the company directory: names and numbers only, and only of customers this phone has been in
    contact with (or flagged for every phone). A delta by `updated_at`; the phone keeps the result in its encrypted
    database and wipes it on revoke. An entry that lost its name or was merged comes back as removed."""

    @extend_schema(parameters=[OpenApiParameter("cursor", str)], responses=DirectoryPageSerializer, operation_id="device_calls_directory")
    def get(self, request):
        from modules.directory.models import Customer

        qs = Customer.objects.filter(Q(device_links__device=self.device) | Q(caller_id_all_phones=True)).distinct().order_by("updated_at", "id")
        cursor = decode_cursor(request.query_params.get("cursor"))
        if cursor and "t" in cursor and "id" in cursor:
            qs = qs.filter(Q(updated_at__gt=cursor["t"]) | Q(updated_at=cursor["t"], id__gt=cursor["id"]))
        rows = list(qs.only("pk", "key", "display_name", "organisation", "merged_into_id", "updated_at")[:DIRECTORY_PAGE])
        entries = [{"number": c.key, "name": c.display_name if not c.merged_into_id else "", "organisation": c.organisation if not c.merged_into_id else "",
                    "removed": bool(c.merged_into_id) or not c.display_name} for c in rows]
        next_cursor = encode_cursor({"t": rows[-1].updated_at.isoformat(), "id": rows[-1].pk}) if rows else request.query_params.get("cursor")
        return Response({"entries": entries, "next_cursor": next_cursor, "complete": len(rows) < DIRECTORY_PAGE})


__all__ = ["decrypt_text"]
