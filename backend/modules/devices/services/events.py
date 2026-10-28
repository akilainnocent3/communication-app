"""Phone → server sync: one idempotent event pipeline for every phone platform (SMS, Calls).

Every event carries a monotonically increasing `seq` from the phone's durable outbox. The server processes events in
order, each in its own savepoint, and answers with the highest sequence it has dealt with (`acked_seq`); the phone then
deletes those events. Events at or below the stored high-water mark are skipped, so retries are harmless. Malformed
events are rejected *and* acknowledged, so one bad event can never block the queue.

Platforms register their event types (`register`) and an optional end-of-batch hook (`register_finisher`, e.g. SMS
refreshes the conversations a batch touched). Two platform rules:

- an event of a platform that is switched off on the server stops the batch *before* that event (nothing after it is
  acknowledged): the phone keeps it and uploads it once the platform is back. If nothing could be processed the
  request answers 403 `platform_disabled`.
- an event of a platform that is not enabled for this phone (`Device.capabilities`) is rejected and acknowledged
  (`platform_not_enabled`): a phone not enrolled for Calls never gets call data stored.

Everything a phone sends is untrusted: strict serializers, length caps, timestamp sanity and per-device scoping.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from rest_framework import serializers

from ..models import Device

log = logging.getLogger(__name__)

MAX_EVENTS = 200
MAX_BATCH_BYTES = 1024 * 1024


class EventRejected(Exception):
    """An event that is well-formed but cannot be applied (rejected and acknowledged)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class EventType:
    name: str
    platform: str
    serializer: type[serializers.Serializer]
    # (device, validated data, batch context) -> "created" | "updated" | "ignored"
    apply: Callable[[Device, dict, dict], str]


_TYPES: dict[str, EventType] = {}
_FINISHERS: dict[str, Callable[[Device, dict], None]] = {}


def register(event_type: EventType) -> None:
    existing = _TYPES.get(event_type.name)
    if existing and existing != event_type:
        raise ValueError(f"Sync event type '{event_type.name}' is already registered.")
    _TYPES[event_type.name] = event_type


def register_finisher(platform: str, finish: Callable[[Device, dict], None]) -> None:
    _FINISHERS[platform] = finish


def types() -> dict[str, EventType]:
    return dict(_TYPES)


class EventSerializer(serializers.Serializer):
    seq = serializers.IntegerField(min_value=1)
    type = serializers.CharField(max_length=40, help_text="message.upsert, call.upsert, … (see docs/sms-mobile.md and docs/calls-mobile.md)")
    payload = serializers.DictField()

    def validate_type(self, value):
        if value not in _TYPES:
            raise serializers.ValidationError("Unknown event type.")
        return value


class BatchSerializer(serializers.Serializer):
    events = EventSerializer(many=True, max_length=MAX_EVENTS, allow_empty=True)


def process(device: Device, events: list[dict]) -> dict:
    """Apply a validated batch. Returns {acked_seq, processed, skipped, rejected: [{seq, code}]} plus
    `disabled_platform` when the batch stopped at an event of a switched-off platform."""
    from modules.platforms.services import is_platform_enabled

    enabled: dict[str, bool] = {}
    with transaction.atomic():
        locked = Device.objects.select_for_update().get(pk=device.pk)
        high = int(locked.sync_state.get("last_seq", 0))
        contexts: dict[str, dict[str, Any]] = {}
        rejected, processed, skipped, disabled = [], 0, 0, None
        for event in sorted(events, key=lambda item: item["seq"]):
            seq = event["seq"]
            if seq <= high:
                skipped += 1
                continue
            kind = _TYPES[event["type"]]
            if kind.platform not in enabled:
                enabled[kind.platform] = is_platform_enabled(kind.platform)
            if not enabled[kind.platform]:
                disabled = kind.platform
                break  # keep it (and everything after it) on the phone
            if not locked.has(kind.platform):
                rejected.append({"seq": seq, "code": "platform_not_enabled"})
                high = seq
                continue
            serializer = kind.serializer(data=event["payload"])
            if not serializer.is_valid():
                code = next(iter(serializer.errors), "invalid")
                rejected.append({"seq": seq, "code": f"invalid_{code}"})
            else:
                context = contexts.setdefault(kind.platform, {})
                try:
                    with transaction.atomic():
                        kind.apply(locked, dict(serializer.validated_data), context)
                    processed += 1
                except EventRejected as exc:
                    rejected.append({"seq": seq, "code": exc.code})
            high = seq
        for platform, context in contexts.items():
            if platform in _FINISHERS:
                _FINISHERS[platform](locked, context)
        state = dict(locked.sync_state)
        state["last_seq"] = high
        Device.objects.filter(pk=locked.pk).update(sync_state=state, last_sync_at=_now())
    if rejected:
        log.info("device %s: %d sync events rejected (%s)", device.code, len(rejected), ",".join(sorted({r["code"] for r in rejected})))
    result = {"acked_seq": high, "processed": processed, "skipped": skipped, "rejected": rejected}
    if disabled:
        result["disabled_platform"] = disabled
    return result


def _now():
    from django.utils import timezone

    return timezone.now()
