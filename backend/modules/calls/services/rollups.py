"""Call rollups: CallStatHourly (counts and sums per UTC hour and dimension) and CallerDaily (per number per day).

Maintained incrementally: when a call becomes final, or a final call's counted fields change (a late call-log row
refines the result), the old contribution is subtracted and the new one added, in the same transaction as the call.
Ingest runs under the phone's row lock, and every rollup key contains the phone, so two batches never race on a row.
`rebuild(start, end)` recomputes a window from the raw rows; the nightly task runs it for recent days, and the tests
assert rollups == raw aggregation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone

from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate, TruncHour

from ..models import MISSED_RESULTS, CallerDaily, CallRecord, CallStatHourly, Direction

UTC = dt_timezone.utc


def hour_of(at: datetime) -> datetime:
    return at.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def snapshot(call: CallRecord) -> dict | None:
    """What a call contributes to the rollups (None until it is final)."""
    if not call.is_final:
        return None
    return {
        "hour": hour_of(call.started_at), "day": call.started_at.astimezone(UTC).date(), "device_id": call.device_id,
        "sim_line_id": call.sim_line_id, "office_id": call.office_id, "direction": call.direction, "result": call.result,
        "after_hours": call.is_after_hours, "talk": call.talk_seconds, "ring": call.ring_seconds, "number": call.number_e164,
    }


def _hour_key(snap: dict) -> dict:
    return {k: snap[k] for k in ("hour", "device_id", "sim_line_id", "office_id", "direction", "result", "after_hours")}


def _caller_deltas(snap: dict, sign: int) -> dict:
    missed = snap["direction"] == Direction.IN and snap["result"] in MISSED_RESULTS
    return {
        "incoming": sign if snap["direction"] == Direction.IN else 0,
        "outgoing": sign if snap["direction"] == Direction.OUT else 0,
        "missed": sign if missed else 0,
    }


def _add(snap: dict, sign: int) -> None:
    key = _hour_key(snap)
    updated = CallStatHourly.objects.filter(**key).update(calls=F("calls") + sign, talk_seconds=F("talk_seconds") + sign * snap["talk"],
                                                           ring_seconds=F("ring_seconds") + sign * snap["ring"])
    if not updated and sign > 0:
        CallStatHourly.objects.create(**key, calls=1, talk_seconds=snap["talk"], ring_seconds=snap["ring"])
    if sign < 0:
        CallStatHourly.objects.filter(**key, calls__lte=0).delete()
    if snap["number"]:
        deltas = _caller_deltas(snap, sign)
        caller = {"day": snap["day"], "device_id": snap["device_id"], "number_e164": snap["number"]}
        updated = CallerDaily.objects.filter(**caller).update(**{k: F(k) + v for k, v in deltas.items()})
        if not updated and sign > 0:
            CallerDaily.objects.create(**caller, **deltas)


@transaction.atomic
def apply(before: dict | None, after: dict | None) -> None:
    if before == after:
        return
    if before:
        _add(before, -1)
    if after:
        _add(after, +1)


@transaction.atomic
def rebuild(start: datetime, end: datetime, device_ids: list | None = None) -> int:
    """Recompute the rollups of [start, end) (whole UTC hours and days) from the raw rows. Returns the hour rows written."""
    start, end = hour_of(start), hour_of(end) + timedelta(hours=1)
    calls = CallRecord.objects.filter(is_final=True, started_at__gte=start, started_at__lt=end)
    hours = CallStatHourly.objects.filter(hour__gte=start, hour__lt=end)
    if device_ids is not None:
        calls, hours = calls.filter(device_id__in=device_ids), hours.filter(device_id__in=device_ids)
    hours.delete()
    rows = (calls.annotate(bucket=TruncHour("started_at", tzinfo=UTC))
            .values("bucket", "device_id", "sim_line_id", "office_id", "direction", "result", "is_after_hours")
            .annotate(n=Count("id"), talk=Sum("talk_seconds"), ring=Sum("ring_seconds")))
    CallStatHourly.objects.bulk_create([
        CallStatHourly(hour=r["bucket"], device_id=r["device_id"], sim_line_id=r["sim_line_id"], office_id=r["office_id"], direction=r["direction"],
                       result=r["result"], after_hours=r["is_after_hours"], calls=r["n"], talk_seconds=r["talk"] or 0, ring_seconds=r["ring"] or 0)
        for r in rows
    ], batch_size=1000)
    # Caller days: whole UTC days covering the window.
    day_start = datetime.combine(start.date(), datetime.min.time(), tzinfo=UTC)
    day_end = datetime.combine((end - timedelta(microseconds=1)).date() + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    day_calls = CallRecord.objects.filter(is_final=True, started_at__gte=day_start, started_at__lt=day_end).exclude(number_e164="")
    callers = CallerDaily.objects.filter(day__gte=day_start.date(), day__lt=day_end.date())
    if device_ids is not None:
        day_calls, callers = day_calls.filter(device_id__in=device_ids), callers.filter(device_id__in=device_ids)
    callers.delete()
    caller_rows = (day_calls.annotate(d=TruncDate("started_at", tzinfo=UTC)).values("d", "device_id", "number_e164")
                   .annotate(incoming=Count("id", filter=Q(direction=Direction.IN)), outgoing=Count("id", filter=Q(direction=Direction.OUT)),
                             missed=Count("id", filter=Q(direction=Direction.IN, result__in=MISSED_RESULTS))))
    CallerDaily.objects.bulk_create([
        CallerDaily(day=r["d"], device_id=r["device_id"], number_e164=r["number_e164"], incoming=r["incoming"], outgoing=r["outgoing"], missed=r["missed"])
        for r in caller_rows
    ], batch_size=1000)
    return len(rows)


def repair_recent(days: int = 3, now: datetime | None = None) -> int:
    """Nightly: rebuild the last `days` days (late call-log rows, retention purges and manual fixes land here)."""
    from django.utils import timezone

    now = now or timezone.now()
    return rebuild(now - timedelta(days=days), now)
