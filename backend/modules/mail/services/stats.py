"""Dashboard numbers from the local index (fast; no provider calls)."""

from __future__ import annotations

import zoneinfo
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta

from django.db.models import Count, Max, Q
from django.utils import timezone

from ..models import Mailbox, MailboxStatus, Message, Thread


def _tz(user):
    try:
        return zoneinfo.ZoneInfo(user.timezone or "Africa/Dar_es_Salaam")
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return zoneinfo.ZoneInfo("Africa/Dar_es_Salaam")


def dashboard(user, mailboxes, days: int = 30) -> dict:
    tz = _tz(user)
    now = timezone.now()
    today = now.astimezone(tz).date()
    start_day = today - timedelta(days=days - 1)
    start = datetime.combine(start_day, time.min, tzinfo=tz)
    today_start = datetime.combine(today, time.min, tzinfo=tz)
    mailbox_ids = list(mailboxes.values_list("pk", flat=True))

    messages = Message.objects.filter(mailbox_id__in=mailbox_ids, date__gte=start).exclude(label_ids__overlap=["DRAFT", "SPAM"])
    series = defaultdict(lambda: {"received": 0, "sent": 0})
    received_today = sent_today = 0
    senders: Counter = Counter()
    names: dict[str, str] = {}
    for date, outgoing, sender in messages.values_list("date", "is_outgoing", "from_addr").iterator(chunk_size=2000):
        day = date.astimezone(tz).date().isoformat()
        key = "sent" if outgoing else "received"
        series[day][key] += 1
        if date >= today_start:
            if outgoing:
                sent_today += 1
            else:
                received_today += 1
        if not outgoing and sender and sender.get("email"):
            email = sender["email"].lower()
            senders[email] += 1
            names.setdefault(email, sender.get("name") or "")

    points = []
    for offset in range(days):
        day = (start_day + timedelta(days=offset)).isoformat()
        points.append({"date": day, **series[day]})

    unread = Thread.objects.filter(mailbox_id__in=mailbox_ids, is_unread=True, label_ids__contains=["INBOX"]).count()
    per_mailbox = []
    activity = dict(Message.objects.filter(mailbox_id__in=mailbox_ids).values_list("mailbox_id").annotate(last=Max("date")).values_list("mailbox_id", "last"))
    counts = dict(
        Mailbox.objects.filter(pk__in=mailbox_ids)
        .annotate(unread=Count("threads", filter=Q(threads__is_unread=True, threads__label_ids__contains=["INBOX"])))
        .values_list("pk", "unread")
    )
    for mailbox in mailboxes.select_related("office"):
        per_mailbox.append({
            "id": mailbox.pk, "email": mailbox.email, "name": mailbox.name, "office": mailbox.office.name, "colour": mailbox.colour,
            "provider": mailbox.provider, "status": mailbox.status, "unread": counts.get(mailbox.pk, 0),
            "last_synced_at": mailbox.last_synced_at, "last_activity_at": activity.get(mailbox.pk), "sync_progress": mailbox.sync_progress,
        })

    return {
        "range_days": days,
        "kpis": {
            "unread": unread,
            "received_today": received_today,
            "sent_today": sent_today,
            "avg_first_response_minutes": first_response_minutes(mailbox_ids, start),
            "needs_reconnect": sum(1 for m in per_mailbox if m["status"] == MailboxStatus.NEEDS_RECONNECT),
        },
        "series": points,
        "mailboxes": per_mailbox,
        "top_senders": [{"email": email, "name": names.get(email, ""), "count": count} for email, count in senders.most_common(8)],
        "unanswered": unanswered(mailbox_ids, now),
    }


def first_response_minutes(mailbox_ids: list[int], since: datetime) -> int | None:
    """Average time from the first incoming message of a thread to our first reply, over threads in range."""
    rows = Message.objects.filter(mailbox_id__in=mailbox_ids, thread__last_message_at__gte=since).exclude(label_ids__overlap=["DRAFT", "SPAM"]).order_by("thread_id", "date").values_list("thread_id", "date", "is_outgoing")
    gaps = []
    current, first_in, answered = None, None, False
    for thread_id, date, outgoing in rows.iterator(chunk_size=5000):
        if thread_id != current:
            current, first_in, answered = thread_id, None, False
        if not outgoing and first_in is None:
            first_in = date
        elif outgoing and first_in is not None and not answered:
            gaps.append((date - first_in).total_seconds() / 60)
            answered = True
    return round(sum(gaps) / len(gaps)) if gaps else None


def unanswered(mailbox_ids: list[int], now: datetime, limit: int = 8) -> list[dict]:
    """Inbox threads whose latest message is incoming and older than 24 hours."""
    cutoff = now - timedelta(hours=24)
    candidates = (
        Thread.objects.filter(mailbox_id__in=mailbox_ids, label_ids__contains=["INBOX", "CATEGORY_PERSONAL"], last_message_at__lt=cutoff, last_message_at__gte=now - timedelta(days=30))
        .select_related("mailbox")
        .order_by("last_message_at")[:200]
    )
    result = []
    for thread in candidates:
        last = thread.messages.exclude(label_ids__contains=["DRAFT"]).order_by("-date").first()
        if last and not last.is_outgoing:
            result.append({
                "id": thread.pk, "subject": thread.subject, "mailbox_id": thread.mailbox_id, "mailbox": thread.mailbox.name, "colour": thread.mailbox.colour,
                "from": last.from_addr, "waiting_hours": int((now - last.date).total_seconds() // 3600),
            })
        if len(result) >= limit:
            break
    return result
