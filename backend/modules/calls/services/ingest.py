"""Apply what a phone reports about calls. Everything here is idempotent and scoped to the reporting phone.

Two sources describe one call, and are merged into one CallRecord:

- **live** events from the dialer's InCallService (`call_key`: the dialer's id for the call). Precise: ring start, the
  moment it was answered, who hung up, hold, conference, the disconnect cause, the SIM.
- **log** rows from the system call log (`call_log_id`: CallLog.Calls._ID). Written by Android for every call, also
  calls the dialer did not see (before the app was the default dialer, backfill, a crash). Coarser.

A row is found by its call_key or call_log_id; failing that, a row from the *other* source with the same number,
direction and SIM that started within MATCH_WINDOW is the same call. Live values win; log values only fill gaps, except
that a log result which is more specific than "missed" (voicemail, answered elsewhere, blocked) refines it.

Privacy (docs/security.md): USSD/MMI codes and emergency calls are never stored — the phone never sends them, and the
server refuses them anyway (rejected and acknowledged, nothing written, nothing logged but the reason code).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from modules.devices.models import Device, SimLine
from modules.devices.services.events import EventRejected
from modules.devices.services.health import set_call_state
from modules.devices.services.phone import address_key

from ..models import CONNECTED_RESULTS, MISSED_RESULTS, CallAnnotation, CallbackTask, CallEvent, CallOutcome, CallRecord, Direction, Result
from . import hours, rollups

log = logging.getLogger(__name__)

MATCH_WINDOW = timedelta(seconds=90)
LIVE_STATE_WINDOW = timedelta(minutes=5)
MMI = re.compile(r"[*#]")
REFINING_LOG_RESULTS = (Result.VOICEMAIL, Result.ANSWERED_ELSEWHERE, Result.BLOCKED, Result.REJECTED)
LIVE_FIELDS = {
    "result": "result", "disconnect_cause_code": "disconnect_code", "disconnect_cause_label": "disconnect_label", "ended_by": "ended_by",
    "is_conference": "is_conference", "conference_size": "conference_size", "is_video": "is_video", "network": "network",
    "was_on_hold_seconds": "hold_seconds",
}


def from_millis(value) -> datetime | None:
    if value in (None, ""):
        return None
    return datetime.fromtimestamp(int(value) / 1000, tz=dt_timezone.utc)


def _sim(device: Device, sub_id) -> SimLine | None:
    if sub_id in (None, "", -1):
        return None
    cache = device.__dict__.setdefault("_sim_cache", {})
    if sub_id not in cache:
        cache[sub_id] = SimLine.objects.filter(device=device, subscription_id=sub_id).first()
    return cache[sub_id]


def region_for(sim: SimLine | None) -> str:
    return (sim.country_iso if sim and sim.country_iso else settings.SMS_DEFAULT_REGION).upper()


def is_emergency(raw: str, region: str) -> bool:
    digits = re.sub(r"[^\d+]", "", raw or "")
    if not digits:
        return False
    from phonenumbers import shortnumberinfo

    try:
        return digits in ("112", "911") or shortnumberinfo.is_emergency_number(digits, region)
    except Exception:  # noqa: BLE001 - unparseable numbers are not emergency numbers
        return False


def refuse_private(raw: str, region: str) -> None:
    """USSD/MMI sessions and emergency calls are never stored (the phone does not send them; this is the backstop)."""
    if MMI.search(raw or ""):
        raise EventRejected("mmi_not_stored")
    if is_emergency(raw, region):
        raise EventRejected("emergency_not_stored")


# --- call.upsert --------------------------------------------------------------------------------------------------


def _find(device: Device, data: dict, number: str, started: datetime, sim: SimLine | None) -> CallRecord | None:
    if data.get("call_key"):
        row = CallRecord.objects.filter(device=device, android_call_key=data["call_key"]).first()
        if row:
            return row
    if data.get("call_log_id") is not None:
        row = CallRecord.objects.filter(device=device, provider_call_log_id=data["call_log_id"]).first()
        if row:
            return row
    # The other source of the same call: same number, direction and SIM, a close start, not carrying our kind of id.
    candidates = CallRecord.objects.filter(device=device, direction=data["direction"], number_e164=number,
                                           started_at__gte=started - MATCH_WINDOW, started_at__lte=started + MATCH_WINDOW)
    if data.get("call_log_id") is not None:
        candidates = candidates.filter(provider_call_log_id__isnull=True)
    else:
        candidates = candidates.filter(android_call_key__isnull=True)
    if sim:
        candidates = candidates.filter(Q(sim_line=sim) | Q(sim_line__isnull=True))
    rows = list(candidates[:5])
    return min(rows, key=lambda r: abs((r.started_at - started).total_seconds())) if rows else None


def _durations(call: CallRecord, log_duration: int | None) -> None:
    end = call.ended_at
    if call.result not in CONNECTED_RESULTS:
        call.talk_seconds = 0
    elif call.answered_at and end:
        call.talk_seconds = max(0, int((end - call.answered_at).total_seconds()))
    elif log_duration is not None:
        call.talk_seconds = log_duration
    ring_end = call.answered_at or end
    call.ring_seconds = max(0, int((ring_end - call.started_at).total_seconds())) if ring_end else 0
    if call.result in CONNECTED_RESULTS and not call.answered_at and end:
        # Call log only: it knows the talk time, not when ringing stopped.
        call.ring_seconds = max(0, int((end - call.started_at).total_seconds()) - call.talk_seconds)


def upsert_call(device: Device, data: dict, context: dict | None = None) -> tuple[CallRecord, bool]:
    sim = _sim(device, data.get("sub_id"))
    region = region_for(sim)
    raw = (data.get("number") or "").strip()
    refuse_private(raw, region)
    presentation = data.get("presentation") or "allowed"
    number = address_key(raw, region) if raw and presentation == "allowed" else ""
    started = from_millis(data["started_at"])
    live = bool(data.get("call_key"))
    call = _find(device, data, number, started, sim)
    created = call is None
    before = rollups.snapshot(call) if call else None
    if created:
        call = CallRecord(device=device, office_id=device.office_id, sim_line=sim, direction=data["direction"], number_e164=number,
                          raw_number=raw[:64] if number else "", presentation=presentation, started_at=started, result=data["result"],
                          origin="incoming" if data["direction"] == Direction.IN else "manual")
    if data.get("call_key") and not call.android_call_key:
        call.android_call_key = data["call_key"]
    if data.get("call_log_id") is not None and call.provider_call_log_id is None:
        call.provider_call_log_id = data["call_log_id"]
    if sim and not call.sim_line_id:
        call.sim_line = sim
    if data.get("contact_name") and number:
        call.contact_name_on_phone = data["contact_name"][:120]
    answered, ended = from_millis(data.get("answered_at")), from_millis(data.get("ended_at"))
    if live or created:
        call.started_at = started
        call.answered_at = answered or call.answered_at
        call.ended_at = ended or call.ended_at
        for field, source in LIVE_FIELDS.items():
            if data.get(source) not in (None, ""):
                value = data[source]
                setattr(call, field, value[:80] if isinstance(value, str) else value)
        if data.get("origin") and call.direction == Direction.OUT:
            call.origin = data["origin"]
    else:
        # A log row for a call the dialer already reported: fill gaps, refine a generic "missed".
        call.answered_at = call.answered_at or answered
        call.ended_at = call.ended_at or ended
        if call.result == Result.MISSED and data["result"] in REFINING_LOG_RESULTS:
            call.result = data["result"]
    duration = data.get("duration")
    if call.ended_at is None and data.get("call_log_id") is not None:
        # Call-log rows exist only for finished calls: start (+ talk time) is the end.
        call.ended_at = (call.answered_at or started) + timedelta(seconds=int(duration or 0))
    _durations(call, duration)
    call.is_final = call.ended_at is not None
    call.is_after_hours = hours.is_after_hours(call.started_at, call.office_id)
    if data.get("deleted"):
        call.deleted_on_device_at = call.deleted_on_device_at or timezone.now()
    if created and number:
        from modules.directory.services.customers import touch

        call.customer = touch(raw, channel="call", at=started, device=device, region=region)
    task = CallbackTask.objects.filter(device=device, uuid=data["callback_task"]).first() if data.get("callback_task") else None
    if task and not call.callback_task_id:
        call.callback_task, call.origin = task, "callback_task"
    call.save()
    if task:
        _link_task(task, call)
    after = rollups.snapshot(call)
    if before != after:
        rollups.apply(before, after)
        if call.is_final and before is None:
            link_returns(call)
            if context is not None:
                context.setdefault("finished", []).append(call.pk)
    return call, created


def _link_task(task: CallbackTask, call: CallRecord) -> None:
    updates = {}
    if task.call_id is None:
        updates["call"] = call
    if task.state in (CallbackTask.OPEN, CallbackTask.NOTIFIED):
        updates.update(state=CallbackTask.DIALED, dialed_at=call.started_at, attempts=task.attempts + 1)
    if call.is_final and call.result in CONNECTED_RESULTS and task.state in CallbackTask.ACTIVE_STATES:
        updates.update(state=CallbackTask.DONE, done_at=call.ended_at)
    if updates:
        CallbackTask.objects.filter(pk=task.pk).update(**updates)


def is_contact(call: CallRecord) -> bool:
    """Reaching the customer: any answered call with the number, in either direction (decision 67)."""
    return call.is_final and call.result in CONNECTED_RESULTS and bool(call.number_e164)


def link_returns(call: CallRecord) -> None:
    """Company-wide (any phone): a contact returns every earlier open missed call from that number; a missed call that
    arrives late (the call-log backfill is newest first) is returned by the first stored contact after it."""
    if not call.number_e164:
        return
    if is_contact(call):
        reached = call.answered_at or call.started_at
        missed = CallRecord.objects.filter(number_e164=call.number_e164, direction=Direction.IN, result__in=MISSED_RESULTS, is_final=True,
                                           returned_at__isnull=True, started_at__lt=call.started_at)
        latest = missed.order_by("-started_at").first()
        if latest:
            missed.update(returned_at=reached, returned_by=call)
            CallRecord.objects.filter(pk=call.pk).update(returns_call=latest)
            call.returns_call = latest
    elif call.is_missed and call.returned_at is None:
        contact = (CallRecord.objects.filter(number_e164=call.number_e164, is_final=True, result__in=CONNECTED_RESULTS, started_at__gt=call.started_at)
                   .order_by("started_at").first())
        if contact:
            call.returned_at, call.returned_by = contact.answered_at or contact.started_at, contact
            CallRecord.objects.filter(pk=call.pk).update(returned_at=call.returned_at, returned_by=contact)
            if contact.returns_call_id is None:
                CallRecord.objects.filter(pk=contact.pk).update(returns_call=call)


# --- call.event, call.annotation, callback.state, backfill ------------------------------------------------------------

LIVE_STATES = {"ringing": "ringing", "dialing": "active", "active": "active", "hold": "held", "unhold": "active", "conference_add": "active", "ended": "idle"}


def add_event(device: Device, data: dict) -> str:
    call = CallRecord.objects.filter(device=device, android_call_key=data["call_key"]).first()
    if not call:
        raise EventRejected("unknown_call")
    at = from_millis(data["at"])
    extra = {"size": data["size"]} if data.get("size") is not None else {}
    _, created = CallEvent.objects.get_or_create(call=call, kind=data["kind"], at=at, defaults={"data": extra})
    if at >= timezone.now() - LIVE_STATE_WINDOW:
        set_call_state(device, LIVE_STATES[data["kind"]], at)
    return "created" if created else "ignored"


def call_ref(device: Device, data: dict) -> CallRecord | None:
    if data.get("call_key"):
        call = CallRecord.objects.filter(device=device, android_call_key=data["call_key"]).first()
        if call:
            return call
    if data.get("call_log_id") is not None:
        return CallRecord.objects.filter(device=device, provider_call_log_id=data["call_log_id"]).first()
    return None


def annotate_from_phone(device: Device, data: dict) -> str:
    """The post-call card: outcome chips and an optional note, written by the staff member on the phone."""
    from common.devicecrypto import encrypt_text

    call = call_ref(device, data)
    if not call:
        raise EventRejected("unknown_call")
    outcome = None
    if data.get("outcome_id"):
        outcome = CallOutcome.objects.filter(pk=data["outcome_id"], is_active=True).first()
        if not outcome:
            raise EventRejected("unknown_outcome")
    existing = CallAnnotation.objects.select_related("call").filter(client_uuid=data["client_uuid"]).first()
    if existing and existing.call.device_id != device.pk:
        raise EventRejected("foreign_annotation")
    values = {"outcome": outcome, "encrypted_note": encrypt_text((data.get("note") or "").strip()), "tags": [str(t)[:40] for t in data.get("tags") or []][:10]}
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
        existing.save()
        return "updated"
    CallAnnotation.objects.create(call=call, from_phone=True, client_uuid=data["client_uuid"], **values)
    return "created"


CALLBACK_FLOW = {
    "notified": (CallbackTask.OPEN,),
    "dialed": (CallbackTask.OPEN, CallbackTask.NOTIFIED, CallbackTask.DIALED),
    "done": (CallbackTask.OPEN, CallbackTask.NOTIFIED, CallbackTask.DIALED),
    "snoozed": (CallbackTask.OPEN, CallbackTask.NOTIFIED, CallbackTask.DIALED),
}


def callback_state(device: Device, data: dict) -> str:
    task = CallbackTask.objects.filter(device=device, uuid=data["task"]).first()
    if not task:
        raise EventRejected("unknown_task")
    state, at = data["state"], from_millis(data["at"])
    if task.state not in CALLBACK_FLOW[state]:
        return "ignored"  # cancelled, expired or already done on the server
    if state == "notified":
        task.state, task.notified_at = CallbackTask.NOTIFIED, at
    elif state == "dialed":
        task.state, task.dialed_at, task.attempts = CallbackTask.DIALED, at, task.attempts + 1
    elif state == "done":
        task.state, task.done_at = CallbackTask.DONE, at
    else:
        task.snoozed_until = from_millis(data.get("snoozed_until")) or at + timedelta(hours=1)
    task.save()
    return "updated"


def backfill_progress(device: Device, data: dict) -> str:
    progress = dict(Device.objects.filter(pk=device.pk).values_list("sync_progress", flat=True).first() or {})
    progress["calls"] = dict(data)
    Device.objects.filter(pk=device.pk).update(sync_progress=progress)
    return "updated"


def finish(device: Device, context: dict) -> None:
    """End of a sync batch: the automatic missed-call SMS, for missed calls that just happened (never for history)."""
    from .autosms import maybe_send

    for call in CallRecord.objects.filter(pk__in=context.get("finished", []), direction=Direction.IN, result__in=MISSED_RESULTS):
        maybe_send(call)
