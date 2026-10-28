"""Calls dashboard numbers, from the rollups (CallStatHourly, CallerDaily), never from a scan of the call log.

Two families of numbers read call rows, through an index and only for a small subset: the unreturned-missed metrics
(they depend on later calls, which a rollup written at ingest cannot know) and the medians (a median is not additive).
Both read only missed or answered calls of the selected phones and period (indexes call_unreturned, call_device_recent).

Every count reconciles with the call log: "missed" here is exactly the Missed folder (incoming, result in
MISSED_RESULTS) with the same phones and dates; tests/test_calls_stats.py checks rollups == raw aggregation.
Day and hour buckets use the viewer's time zone; rollup hours are UTC, so zones with a non-whole-hour offset shift
by the remainder (decision 68).
"""

from __future__ import annotations

import math
import statistics
import zoneinfo
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from modules.devices.services.health import is_online
from modules.devices.services.phone import display_number

from ..models import MISSED_RESULTS, CallAnnotation, CallerDaily, CallRecord, CallSettings, CallStatHourly, CarrierTariff, Direction, Result


def tz_for(user):
    try:
        return zoneinfo.ZoneInfo(user.timezone or "Africa/Dar_es_Salaam")
    except (zoneinfo.ZoneInfoNotFoundError, ValueError, AttributeError):
        return zoneinfo.ZoneInfo("Africa/Dar_es_Salaam")


def period(user, days: int, now=None) -> tuple[datetime, datetime, zoneinfo.ZoneInfo]:
    tz = tz_for(user)
    now = now or timezone.now()
    today = now.astimezone(tz).date()
    start = datetime.combine(today - timedelta(days=days - 1), time.min, tzinfo=tz)
    end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=tz)
    return start, end, tz


def _rate(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def dashboard(user, devices, days: int = 30, sim_id: int | None = None, now=None) -> dict:
    now = now or timezone.now()
    start, end, tz = period(user, days, now)
    device_list = list(devices.select_related("office", "assigned_to").prefetch_related("sim_lines"))
    device_ids = [d.pk for d in device_list]
    hours = CallStatHourly.objects.filter(device_id__in=device_ids, hour__gte=start, hour__lt=end)
    if sim_id:
        hours = hours.filter(sim_line_id=sim_id)
    config = CallSettings.load()

    totals = Counter()
    series = defaultdict(lambda: {"incoming": 0, "outgoing": 0, "missed": 0})
    heatmap = [[0] * 24 for _ in range(7)]
    per_device = defaultdict(Counter)
    per_office = defaultdict(Counter)
    per_sim = defaultdict(Counter)
    outgoing_seconds_by_sim = Counter()
    by_result = Counter()
    for row in hours.values("hour", "device_id", "sim_line_id", "office_id", "direction", "result", "after_hours", "calls", "talk_seconds", "ring_seconds").iterator(chunk_size=5000):
        local = row["hour"].astimezone(tz)
        day = local.date().isoformat()
        n, incoming = row["calls"], row["direction"] == Direction.IN
        missed = incoming and row["result"] in MISSED_RESULTS
        answered_in = incoming and row["result"] == Result.ANSWERED
        answered_out = not incoming and row["result"] == Result.ANSWERED
        values = {
            "calls": n, "incoming": n if incoming else 0, "outgoing": 0 if incoming else n, "missed": n if missed else 0,
            "answered_in": n if answered_in else 0, "answered_out": n if answered_out else 0,
            "blocked": n if incoming and row["result"] == Result.BLOCKED else 0,
            "abandoned": n if incoming and row["result"] == Result.MISSED else 0,
            "rejected": n if incoming and row["result"] == Result.REJECTED else 0,
            "talk_seconds": row["talk_seconds"], "ring_answered_seconds": row["ring_seconds"] if answered_in else 0,
            "after_hours": n if row["after_hours"] else 0, "after_hours_missed": n if row["after_hours"] and missed else 0,
        }
        totals.update(values)
        by_result[(row["direction"], row["result"])] += n
        series[day]["incoming"] += values["incoming"]
        series[day]["outgoing"] += values["outgoing"]
        series[day]["missed"] += values["missed"]
        if incoming:
            heatmap[local.weekday()][local.hour] += n
        per_device[row["device_id"]].update(values)
        per_office[row["office_id"]].update(values)
        per_sim[row["sim_line_id"]].update(values)
        if answered_out:
            outgoing_seconds_by_sim[row["sim_line_id"]] += row["talk_seconds"]

    answerable = totals["incoming"] - totals["blocked"]
    answered = totals["answered_in"] + totals["answered_out"]
    unreturned = unreturned_summary(device_ids, start, end, config.unreturned_hours, now, sim_id)
    sims = {s.pk: s for d in device_list for s in d.sim_lines.all()}
    offices = {d.office_id: d.office for d in device_list}
    staff = defaultdict(Counter)
    for d in device_list:
        if d.assigned_to_id:
            staff[(d.assigned_to_id, d.assigned_to.display_name)].update(per_device[d.pk])

    points = []
    cursor = start.date()
    while cursor < end.date():
        points.append({"date": cursor.isoformat(), **series[cursor.isoformat()]})
        cursor += timedelta(days=1)

    return {
        "range_days": days,
        "start": start, "end": end,
        "unreturned_hours": config.unreturned_hours,
        "kpis": {
            "total": totals["calls"], "incoming": totals["incoming"], "outgoing": totals["outgoing"], "missed": totals["missed"],
            "answered_incoming": totals["answered_in"], "answered_outgoing": totals["answered_out"],
            "answer_rate": _rate(totals["answered_in"], answerable), "missed_rate": _rate(totals["missed"], answerable),
            "unreturned": unreturned["unreturned"], "unreturned_open": unreturned["open"], "returned_in_time": unreturned["returned_in_time"],
            "median_callback_minutes": unreturned["median_minutes"],
            "avg_talk_seconds": round(totals["talk_seconds"] / answered) if answered else None,
            "median_talk_seconds": median_talk(device_ids, start, end, sim_id),
            "avg_ring_seconds": round(totals["ring_answered_seconds"] / totals["answered_in"]) if totals["answered_in"] else None,
            "abandoned": totals["abandoned"], "rejected": totals["rejected"], "blocked": totals["blocked"],
            "after_hours": totals["after_hours"], "after_hours_missed": totals["after_hours_missed"],
            "talk_minutes": round(totals["talk_seconds"] / 60),
            "estimated_cost": estimate_cost(outgoing_seconds_by_sim, sims),
        },
        "series": points,
        "heatmap": heatmap,
        "by_result": [{"direction": k[0], "result": k[1], "count": v} for k, v in sorted(by_result.items())],
        "per_device": sorted(
            [{"id": str(d.pk), "code": d.code, "name": d.name, "office": d.office.name, "colour": d.office.colour, "online": is_online(d, now),
              "call_state": d.call_state or "idle", **_row(per_device[d.pk])} for d in device_list],
            key=lambda r: -r["calls"]),
        "per_office": sorted([{"id": oid, "name": offices[oid].name if oid in offices else "—", "colour": offices[oid].colour if oid in offices else "#888",
                               **_row(values)} for oid, values in per_office.items()], key=lambda r: -r["calls"]),
        "per_sim": sorted([{"sim_id": sid, "label": sims[sid].label if sid in sims else "Unknown SIM", "carrier": sims[sid].carrier if sid in sims else "",
                            **_row(values)} for sid, values in per_sim.items()], key=lambda r: -r["calls"]),
        "staff": sorted([{"user_id": uid, "name": name, **_row(values)} for (uid, name), values in staff.items()], key=lambda r: -r["answered"]),
        **callers(device_ids, start, end),
        "outcomes": outcomes(device_ids, start, end, sim_id),
        "unreturned_list": unreturned["latest"],
    }


def _row(values: Counter) -> dict:
    answerable = values["incoming"] - values["blocked"]
    answered = values["answered_in"] + values["answered_out"]
    return {
        "calls": values["calls"], "incoming": values["incoming"], "outgoing": values["outgoing"], "missed": values["missed"],
        "answered": answered, "answer_rate": _rate(values["answered_in"], answerable), "talk_minutes": round(values["talk_seconds"] / 60),
        "avg_talk_seconds": round(values["talk_seconds"] / answered) if answered else None,
    }


def missed_calls(device_ids, start, end, sim_id=None):
    qs = CallRecord.objects.filter(device_id__in=device_ids, direction=Direction.IN, result__in=MISSED_RESULTS, is_final=True, started_at__gte=start, started_at__lt=end)
    return qs.filter(sim_line_id=sim_id) if sim_id else qs


def unreturned_summary(device_ids, start, end, hours: int, now, sim_id=None) -> dict:
    """Missed calls of the period: returned in time, unreturned (nobody reached the number within `hours`), still open
    (inside the window, not yet returned). The management metric is `unreturned`."""
    window = timedelta(hours=hours)
    rows = list(missed_calls(device_ids, start, end, sim_id).values_list("pk", "started_at", "returned_at"))
    returned_in_time = unreturned = open_ = 0
    gaps = []
    for _, started, returned in rows:
        if returned is not None:
            gaps.append((returned - started).total_seconds() / 60)
            if returned - started <= window:
                returned_in_time += 1
                continue
            unreturned += 1
        elif now - started > window:
            unreturned += 1
        else:
            open_ += 1
    latest = (missed_calls(device_ids, start, end, sim_id).filter(returned_at__isnull=True).select_related("device", "customer")
              .order_by("-started_at")[:10])
    return {
        "returned_in_time": returned_in_time, "unreturned": unreturned, "open": open_,
        "median_minutes": round(statistics.median(gaps)) if gaps else None,
        "latest": [{"id": c.pk, "number": c.number_e164, "display": display_number(c.number_e164),
                    "name": (c.customer.display_name if c.customer_id else "") or c.contact_name_on_phone, "device": c.device.name,
                    "device_id": str(c.device_id), "started_at": c.started_at, "customer_id": c.customer_id} for c in latest],
    }


def median_talk(device_ids, start, end, sim_id=None) -> int | None:
    qs = CallRecord.objects.filter(device_id__in=device_ids, result=Result.ANSWERED, is_final=True, started_at__gte=start, started_at__lt=end)
    if sim_id:
        qs = qs.filter(sim_line_id=sim_id)
    values = list(qs.values_list("talk_seconds", flat=True)[:50000])
    return round(statistics.median(values)) if values else None


def callers(device_ids, start, end) -> dict:
    """Top callers, unique callers, repeat-caller rate and first-time vs returning, from CallerDaily (UTC days)."""
    from modules.directory.models import Customer

    rows = (CallerDaily.objects.filter(device_id__in=device_ids, day__gte=start.date(), day__lt=end.date())
            .values("number_e164").annotate(incoming=Sum("incoming"), outgoing=Sum("outgoing"), missed=Sum("missed")))
    numbers = {r["number_e164"]: r for r in rows}
    incoming = {n: r for n, r in numbers.items() if r["incoming"]}
    repeat = sum(1 for r in incoming.values() if r["incoming"] >= 2)
    customers = {c.key: c for c in Customer.objects.filter(key__in=list(incoming)[:5000])}
    first_time = sum(1 for n in incoming if n in customers and customers[n].first_seen_call and customers[n].first_seen_call >= start)
    top = sorted(incoming.values(), key=lambda r: -r["incoming"])[:10]
    both = Customer.objects.filter(device_links__device_id__in=device_ids, merged_into__isnull=True, last_seen_call__gte=start, last_seen_sms__gte=start).distinct().count()
    return {
        "callers": {
            "unique": len(incoming), "repeat_rate": _rate(repeat, len(incoming)), "first_time": first_time, "returning": len(incoming) - first_time,
            "called_and_texted": both,
        },
        "top_callers": [{"number": r["number_e164"], "display": display_number(r["number_e164"]),
                         "name": customers[r["number_e164"]].display_name if r["number_e164"] in customers else "",
                         "customer_id": customers[r["number_e164"]].pk if r["number_e164"] in customers else None,
                         "incoming": r["incoming"], "missed": r["missed"], "outgoing": r["outgoing"]} for r in top],
    }


def outcomes(device_ids, start, end, sim_id=None) -> list[dict]:
    qs = CallAnnotation.objects.filter(call__device_id__in=device_ids, call__started_at__gte=start, call__started_at__lt=end, outcome__isnull=False)
    if sim_id:
        qs = qs.filter(call__sim_line_id=sim_id)
    rows = qs.values("outcome_id", "outcome__name", "outcome__colour").annotate(count=Count("call_id", distinct=True)).order_by("-count")
    return [{"id": r["outcome_id"], "name": r["outcome__name"], "colour": r["outcome__colour"], "count": r["count"]} for r in rows]


def estimate_cost(seconds_by_sim: Counter, sims: dict) -> list[dict]:
    """Outgoing answered minutes × the carrier's tariff. An estimate: rollups hold sums, so per-call rounding to the
    billing increment is applied to the total, not to each call."""
    tariffs = {t.carrier.lower(): t for t in CarrierTariff.objects.all()}
    by_carrier = Counter()
    for sim_id, seconds in seconds_by_sim.items():
        carrier = sims[sim_id].carrier if sim_id in sims else ""
        by_carrier[carrier] += seconds
    result = []
    for carrier, seconds in sorted(by_carrier.items(), key=lambda item: -item[1]):
        tariff = tariffs.get(carrier.lower())
        if not tariff:
            result.append({"carrier": carrier or "Unknown", "minutes": round(seconds / 60), "amount": None, "currency": None})
            continue
        units = math.ceil(seconds / tariff.billing_increment_seconds) if seconds else 0
        amount = (Decimal(units * tariff.billing_increment_seconds) / Decimal(60) * tariff.per_minute).quantize(Decimal("0.01"))
        result.append({"carrier": carrier, "minutes": round(seconds / 60), "amount": str(amount), "currency": tariff.currency})
    return result


def raw_totals(device_ids, start, end) -> dict:
    """The same totals straight from the call log (tests: rollups == raw)."""
    qs = CallRecord.objects.filter(device_id__in=device_ids, is_final=True, started_at__gte=start, started_at__lt=end)
    return qs.aggregate(
        total=Count("id"), incoming=Count("id", filter=Q(direction=Direction.IN)), outgoing=Count("id", filter=Q(direction=Direction.OUT)),
        missed=Count("id", filter=Q(direction=Direction.IN, result__in=MISSED_RESULTS)), talk=Sum("talk_seconds"),
        answered_in=Count("id", filter=Q(direction=Direction.IN, result=Result.ANSWERED)),
        after_hours=Count("id", filter=Q(is_after_hours=True)),
    )


def live_board(user, devices, now=None) -> dict:
    """Phones and what they are doing, plus today's counters per phone (rollups, the viewer's "today")."""
    now = now or timezone.now()
    device_list = list(devices.select_related("office", "assigned_to"))
    start, _, _ = period(user, 1, now)
    counts = defaultdict(Counter)
    for row in CallStatHourly.objects.filter(device_id__in=[d.pk for d in device_list], hour__gte=start).values("device_id", "direction", "result", "calls"):
        counts[row["device_id"]]["calls"] += row["calls"]
        if row["direction"] == Direction.IN and row["result"] in MISSED_RESULTS:
            counts[row["device_id"]]["missed"] += row["calls"]
    phones = []
    for d in device_list:
        online = is_online(d, now)
        state = (d.call_state or "idle") if online else "offline"
        phones.append({"id": str(d.pk), "code": d.code, "name": d.name, "office": d.office.name, "colour": d.office.colour,
                       "holder": d.assigned_to.display_name if d.assigned_to_id else "", "state": state,
                       "since": d.call_state_since if state in ("ringing", "active", "held") else None, "last_seen_at": d.last_seen_at,
                       "today_calls": counts[d.pk]["calls"], "today_missed": counts[d.pk]["missed"]})
    return {"server_time": now, "phones": phones,
            "totals": {"on_call": sum(1 for p in phones if p["state"] in ("active", "held")), "ringing": sum(1 for p in phones if p["state"] == "ringing"),
                       "offline": sum(1 for p in phones if p["state"] == "offline"), "calls_today": sum(p["today_calls"] for p in phones),
                       "missed_today": sum(p["today_missed"] for p in phones)}}
