"""SMS sync events: their serializers and how each is applied. The batch pipeline (ordering, idempotency, savepoints,
platform checks) is shared with Calls: modules/devices/services/events.py.

Everything a phone sends is untrusted: strict serializers, length caps, timestamp sanity and per-device scoping.
"""

from __future__ import annotations

import logging
import time

from rest_framework import serializers

from modules.devices.models import Device
from modules.devices.services import events

from . import store

log = logging.getLogger(__name__)

MAX_EVENTS = events.MAX_EVENTS
MAX_BATCH_BYTES = events.MAX_BATCH_BYTES
EARLIEST_MS = 946684800000  # 2000-01-01


class AddressField(serializers.CharField):
    def __init__(self, **kwargs):
        super().__init__(max_length=64, **kwargs)


class PartSerializer(serializers.Serializer):
    seq = serializers.IntegerField(min_value=0, max_value=50)
    content_type = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    filename = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    size = serializers.IntegerField(min_value=1)
    sha256 = serializers.RegexField(r"^[0-9a-fA-F]{64}$")

    def validate_size(self, value):
        from django.conf import settings

        if value > settings.SMS_MAX_MMS_BYTES:
            raise serializers.ValidationError("too_large")
        return value


def _check_date(value: int) -> int:
    if value < EARLIEST_MS or value > (time.time() + 86400) * 1000:
        raise serializers.ValidationError("bad_date")
    return value


class MessageUpsertSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["sms", "mms"])
    provider_id = serializers.IntegerField(min_value=0)
    date = serializers.IntegerField()
    thread_id = serializers.IntegerField(min_value=0, required=False, allow_null=True, default=None)
    addresses = serializers.ListField(child=AddressField(), min_length=1, max_length=20)
    direction = serializers.ChoiceField(choices=["in", "out"])
    body = serializers.CharField(max_length=5000, required=False, allow_blank=True, trim_whitespace=False, default="")
    subject = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    is_read = serializers.BooleanField(required=False, default=True)
    starred = serializers.BooleanField(required=False, default=False)
    status = serializers.ChoiceField(choices=sorted(store.PHONE_STATUSES), required=False, allow_blank=True, default="")
    sub_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    client_uuid = serializers.UUIDField(required=False, allow_null=True, default=None)
    error_code = serializers.IntegerField(required=False, allow_null=True, default=None)
    parts = PartSerializer(many=True, required=False, default=list, max_length=20)

    def validate_date(self, value):
        return _check_date(value)


class MessageRefSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["sms", "mms"])
    provider_id = serializers.IntegerField(min_value=0)
    date = serializers.IntegerField()

    def validate_date(self, value):
        return _check_date(value)


class MessageReadSerializer(MessageRefSerializer):
    is_read = serializers.BooleanField()


class ThreadRefSerializer(serializers.Serializer):
    thread_id = serializers.IntegerField(min_value=0)


class ContactSerializer(serializers.Serializer):
    address = AddressField()
    display_name = serializers.CharField(max_length=120, allow_blank=True)
    photo_hash = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")


class BlockSerializer(serializers.Serializer):
    address = AddressField()


class BackfillSerializer(serializers.Serializer):
    phase = serializers.ChoiceField(choices=["running", "done", "failed"])
    done = serializers.IntegerField(min_value=0)
    total = serializers.IntegerField(min_value=0)


EVENT_TYPES = {
    "message.upsert": MessageUpsertSerializer,
    "message.delete": MessageRefSerializer,
    "message.read": MessageReadSerializer,
    "thread.delete": ThreadRefSerializer,
    "thread.read": ThreadRefSerializer,
    "contact.upsert": ContactSerializer,
    "block.add": BlockSerializer,
    "block.remove": BlockSerializer,
    "backfill.progress": BackfillSerializer,
}


def _apply(device: Device, kind: str, data: dict, touched: set[int]) -> str:
    if kind == "message.upsert":
        _, created, conversation_id = store.upsert_message(device, data)
        touched.add(conversation_id)
        return "created" if created else "updated"
    if kind == "message.delete":
        conversation_id = store.delete_message(device, data)
    elif kind == "message.read":
        conversation_id = store.set_read(device, data)
    elif kind == "thread.delete":
        conversation_id = store.delete_thread(device, data["thread_id"])
    elif kind == "thread.read":
        conversation_id = store.set_thread_read(device, data["thread_id"])
    elif kind == "contact.upsert":
        return "updated" if store.upsert_contact(device, data) else "ignored"
    elif kind in ("block.add", "block.remove"):
        store.set_blocked(device, data["address"], kind == "block.add")
        return "updated"
    elif kind == "backfill.progress":
        Device.objects.filter(pk=device.pk).update(sync_progress=dict(data))
        return "updated"
    else:  # pragma: no cover - guarded by the registry
        return "ignored"
    if conversation_id:
        touched.add(conversation_id)
        return "updated"
    return "ignored"


def _finish(device: Device, context: dict) -> None:
    for conversation_id in context.get("touched", ()):
        store.refresh_conversation(conversation_id)


def _handler(kind: str):
    return lambda device, data, context: _apply(device, kind, data, context.setdefault("touched", set()))


for _kind, _serializer in EVENT_TYPES.items():
    events.register(events.EventType(name=_kind, platform="sms", serializer=_serializer, apply=_handler(_kind)))
events.register_finisher("sms", _finish)

# The batch pipeline itself is shared by every phone platform (modules/devices/services/events.py).
BatchSerializer = events.BatchSerializer


def process(device: Device, batch: list[dict]) -> dict:
    return events.process(device, batch)
