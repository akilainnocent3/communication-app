"""SMS dashboard numbers. Metadata only (directions, statuses, times, numbers): no message text is decrypted,
except the masked snippets of the latest conversations, which the inbox shows anyway."""

from __future__ import annotations

import statistics
import zoneinfo
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from modules.devices.services.health import ATTENTION_LABELS, is_online
from modules.devices.services.phone import display_number

from ..models import Contact, Conversation, Message, MessageStatus
from .crypto import decrypt_text
from .outbound import reason_for

SUCCESS = (MessageStatus.SENT, MessageStatus.DELIVERED)
FAILED = (MessageStatus.FAILED, MessageStatus.EXPIRED, MessageStatus.UNKNOWN)


def _tz(user):
    try:
        return zoneinfo.ZoneInfo(user.timezone or "Africa/Dar_es_Salaam")
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return zoneinfo.ZoneInfo("Africa/Dar_es_Salaam")


def dashboard(user, devices, days: int = 30, sim_id: int | None = None) -> dict:
    tz = _tz(user)
    now = timezone.now()
    today = now.astimezone(tz).date()
    start_day = today - timedelta(days=days - 1)
    start = datetime.combine(start_day, time.min, tzinfo=tz)
    device_list = list(devices.prefetch_related("sim_lines"))
    device_ids = [d.pk for d in device_list]

    messages = Message.objects.filter(device_id__in=device_ids, provider_date__gte=start).exclude(status=MessageStatus.CANCELLED)
    if sim_id:
        messages = messages.filter(sim_line_id=sim_id)
    series = defaultdict(lambda: {"received": 0, "sent": 0})
    heatmap = [[0] * 24 for _ in range(7)]
    senders: Counter = Counter()
    per_sim: dict = defaultdict(lambda: {"received": 0, "sent": 0})
    per_device: dict = defaultdict(lambda: {"received": 0, "sent": 0})
    failures: Counter = Counter()
    received = sent = failed = succeeded = 0
    rows = messages.values_list("provider_date", "direction", "address", "status", "sim_line_id", "device_id", "error_code", "origin")
    for date, direction, address, status, sim, device_id, error_code, origin in rows.iterator(chunk_size=5000):
        local = date.astimezone(tz)
        day = local.date().isoformat()
        if direction == Message.IN:
            received += 1
            series[day]["received"] += 1
            heatmap[local.weekday()][local.hour] += 1
            senders[(device_id, address)] += 1
            per_sim[sim]["received"] += 1
            per_device[device_id]["received"] += 1
        else:
            if status in SUCCESS:
                sent += 1
                succeeded += 1
                series[day]["sent"] += 1
                per_sim[sim]["sent"] += 1
                per_device[device_id]["sent"] += 1
            elif status in FAILED:
                failed += 1
                failures[(status, error_code)] += 1

    names = {(c.device_id, c.address): c.display_name for c in Contact.objects.filter(device_id__in=device_ids, address__in={a for _, a in senders}).only("device_id", "address", "display_name")}
    conversations = Conversation.objects.filter(device_id__in=device_ids)
    active = conversations.filter(is_archived=False, is_spam=False)
    sims = {s.pk: s for d in device_list for s in d.sim_lines.all()}
    points = [{"date": (start_day + timedelta(days=offset)).isoformat(), **series[(start_day + timedelta(days=offset)).isoformat()]} for offset in range(days)]

    return {
        "range_days": days,
        "kpis": {
            "received": received,
            "sent": sent,
            "unread": active.aggregate(total=Sum("unread_count"))["total"] or 0,
            "awaiting_reply": active.filter(state=Conversation.OPEN, awaiting_since__lt=now - timedelta(hours=1)).count(),
            "median_first_response_minutes": median_first_response(device_ids, start),
            "delivery_success_rate": round(100 * succeeded / (succeeded + failed), 1) if succeeded + failed else None,
            "failed": failed,
            "queued": Message.objects.filter(device_id__in=device_ids, status__in=Message.PENDING_STATUSES).count(),
        },
        "series": points,
        "heatmap": heatmap,
        "top_senders": [
            {"address": address, "display": display_number(address), "name": names.get((device_id, address), ""), "device_id": str(device_id), "count": count}
            for (device_id, address), count in senders.most_common(8)
        ],
        "per_sim": [
            {"sim_id": sim, "label": sims[sim].label if sim in sims else "Unknown SIM", "device": sims[sim].device_id if sim in sims else None, **values}
            for sim, values in sorted(per_sim.items(), key=lambda item: -(item[1]["received"] + item[1]["sent"]))
        ],
        "per_device": [
            {"id": str(d.pk), "code": d.code, "name": d.name, "office": d.office.name, "colour": d.office.colour, "status": d.status,
             "online": is_online(d, now), "last_seen_at": d.last_seen_at, **per_device[d.pk]}
            for d in device_list
        ],
        "failure_reasons": [
            {"status": status, "code": code, "reason": reason_for(code) if status == MessageStatus.FAILED else ("Expired before the phone came online" if status == MessageStatus.EXPIRED else "Delivery unknown"), "count": count}
            for (status, code), count in failures.most_common(6)
        ],
        "latest": latest_conversations(device_ids),
        "attention": [
            {"id": str(d.pk), "code": d.code, "name": d.name, "alerts": [{"code": c, "label": ATTENTION_LABELS.get(c, c)} for c in d.attention or []]}
            for d in device_list if d.attention
        ],
    }


def median_first_response(device_ids: list, since: datetime) -> int | None:
    """Median minutes from a customer's first unanswered message to the next reply, over conversations in range."""
    rows = (
        Message.objects.filter(device_id__in=device_ids, provider_date__gte=since)
        .filter(Q(direction=Message.IN) | Q(status__in=SUCCESS) | Q(status__in=Message.PENDING_STATUSES))
        .order_by("conversation_id", "provider_date").values_list("conversation_id", "provider_date", "direction")
    )
    gaps, current, waiting_since = [], None, None
    for conversation_id, date, direction in rows.iterator(chunk_size=5000):
        if conversation_id != current:
            current, waiting_since = conversation_id, None
        if direction == Message.IN:
            waiting_since = waiting_since or date
        elif waiting_since is not None:
            gaps.append((date - waiting_since).total_seconds() / 60)
            waiting_since = None
    return round(statistics.median(gaps)) if gaps else None


def latest_conversations(device_ids: list, limit: int = 8) -> list[dict]:
    rows = Conversation.objects.filter(device_id__in=device_ids, is_spam=False).select_related("device").order_by("-last_message_at")[:limit]
    names = {(c.device_id, c.address): c.display_name for c in Contact.objects.filter(device_id__in=device_ids, address__in={a for r in rows for a in r.addresses[:1]})}
    return [{
        "id": row.pk, "device": row.device.name, "title": names.get((row.device_id, row.addresses[0]), "") or display_number(row.addresses[0]),
        "snippet": decrypt_text(row.encrypted_snippet), "last_message_at": row.last_message_at, "unread": row.unread_count, "direction": row.last_direction,
    } for row in rows]
