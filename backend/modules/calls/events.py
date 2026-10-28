"""Calls sync events (phone → server), registered with the shared pipeline (modules/devices/services/events.py).

Event types: call.upsert, call.event, call.annotation, callback.state, call_log.backfill. Strict validation: plausible
timestamps (2000 … now + 1 day), ordered times, durations ≤ 24 h, number characters only, short text fields.
"""

import time

from rest_framework import serializers

from modules.devices.services import events

from .models import CallEvent, CallRecord, Result
from .services import ingest

EARLIEST_MS = 946684800000  # 2000-01-01
MAX_SECONDS = 24 * 3600


def check_millis(value):
    if value is None:
        return value
    if value < EARLIEST_MS or value > (time.time() + 86400) * 1000:
        raise serializers.ValidationError("bad_date")
    return value


class NumberField(serializers.CharField):
    """Digits and dialling characters only. USSD/MMI characters pass validation so the server can refuse them with a
    reason code (ingest.refuse_private) instead of a generic error."""

    def __init__(self, **kwargs):
        super().__init__(max_length=64, allow_blank=True, required=False, default="", **kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data).strip()
        if value and not all(c.isdigit() or c in "+*#,;() .-" for c in value):
            raise serializers.ValidationError("bad_number")
        return value


class CallUpsertSerializer(serializers.Serializer):
    call_key = serializers.RegexField(r"^[A-Za-z0-9_-]{8,64}$", required=False, allow_null=True, default=None)
    call_log_id = serializers.IntegerField(min_value=0, required=False, allow_null=True, default=None)
    direction = serializers.ChoiceField(choices=["in", "out"])
    result = serializers.ChoiceField(choices=Result.values)
    number = NumberField()
    presentation = serializers.ChoiceField(choices=[c for c, _ in CallRecord.PRESENTATION], required=False, default="allowed")
    contact_name = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    started_at = serializers.IntegerField()
    answered_at = serializers.IntegerField(required=False, allow_null=True, default=None)
    ended_at = serializers.IntegerField(required=False, allow_null=True, default=None)
    duration = serializers.IntegerField(min_value=0, max_value=MAX_SECONDS, required=False, allow_null=True, default=None)
    disconnect_code = serializers.IntegerField(min_value=-1, max_value=1000, required=False, allow_null=True, default=None)
    disconnect_label = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    ended_by = serializers.ChoiceField(choices=["local", "remote", "system", ""], required=False, default="")
    is_conference = serializers.BooleanField(required=False, default=False)
    conference_size = serializers.IntegerField(min_value=0, max_value=20, required=False, default=0)
    is_video = serializers.BooleanField(required=False, default=False)
    network = serializers.ChoiceField(choices=[c for c, _ in CallRecord.NETWORK], required=False, default="unknown")
    hold_seconds = serializers.IntegerField(min_value=0, max_value=MAX_SECONDS, required=False, default=0)
    sub_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    origin = serializers.ChoiceField(choices=["manual", "callback_task", "from_sms", "redial"], required=False, allow_null=True, default=None)
    callback_task = serializers.UUIDField(required=False, allow_null=True, default=None)
    deleted = serializers.BooleanField(required=False, default=False)

    def validate_started_at(self, value):
        return check_millis(value)

    def validate_answered_at(self, value):
        return check_millis(value)

    def validate_ended_at(self, value):
        return check_millis(value)

    def validate(self, data):
        if not data.get("call_key") and data.get("call_log_id") is None:
            raise serializers.ValidationError({"call_key": "call_key or call_log_id is required"})
        start, answered, ended = data["started_at"], data.get("answered_at"), data.get("ended_at")
        if answered is not None and answered < start - 1000:
            raise serializers.ValidationError({"answered_at": "before_start"})
        if ended is not None and (ended < start - 1000 or ended - start > MAX_SECONDS * 1000):
            raise serializers.ValidationError({"ended_at": "implausible"})
        return data


class CallEventSerializer(serializers.Serializer):
    call_key = serializers.RegexField(r"^[A-Za-z0-9_-]{8,64}$")
    kind = serializers.ChoiceField(choices=CallEvent.KINDS)
    at = serializers.IntegerField()
    size = serializers.IntegerField(min_value=0, max_value=20, required=False, allow_null=True, default=None)

    def validate_at(self, value):
        return check_millis(value)


class CallAnnotationSerializer(serializers.Serializer):
    client_uuid = serializers.UUIDField()
    call_key = serializers.RegexField(r"^[A-Za-z0-9_-]{8,64}$", required=False, allow_null=True, default=None)
    call_log_id = serializers.IntegerField(min_value=0, required=False, allow_null=True, default=None)
    outcome_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    tags = serializers.ListField(child=serializers.CharField(max_length=40), max_length=10, required=False, default=list)


class CallbackStateSerializer(serializers.Serializer):
    task = serializers.UUIDField()
    state = serializers.ChoiceField(choices=["notified", "dialed", "done", "snoozed"])
    at = serializers.IntegerField()
    snoozed_until = serializers.IntegerField(required=False, allow_null=True, default=None)

    def validate_at(self, value):
        return check_millis(value)


class CallBackfillSerializer(serializers.Serializer):
    phase = serializers.ChoiceField(choices=["running", "done", "failed"])
    done = serializers.IntegerField(min_value=0)
    total = serializers.IntegerField(min_value=0)


def _upsert(device, data, context):
    _, created = ingest.upsert_call(device, data, context)
    return "created" if created else "updated"


for _name, _serializer, _apply in (
    ("call.upsert", CallUpsertSerializer, _upsert),
    ("call.event", CallEventSerializer, lambda device, data, context: ingest.add_event(device, data)),
    ("call.annotation", CallAnnotationSerializer, lambda device, data, context: ingest.annotate_from_phone(device, data)),
    ("callback.state", CallbackStateSerializer, lambda device, data, context: ingest.callback_state(device, data)),
    ("call_log.backfill", CallBackfillSerializer, lambda device, data, context: ingest.backfill_progress(device, data)),
):
    events.register(events.EventType(name=_name, platform="calls", serializer=_serializer, apply=_apply))
events.register_finisher("calls", ingest.finish)
