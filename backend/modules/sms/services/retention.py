"""Retention (SMS_RETENTION_DAYS, 0 = keep forever).

Tanzania's PDPA asks that personal data is kept no longer than needed for its purpose. Messages older than the
retention window are deleted from the server (with their MMS files); the phone keeps its own copy. Deletions
made on the phone do not delete the server copy unless SMS_MIRROR_DEVICE_DELETES is on: the company copy is
an accountability record, and the admin shows "Deleted on phone" instead.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from modules.audit.services import record

from ..models import Message
from .media import delete_files
from .store import refresh_conversation


def purge(now=None, batch: int = 2000) -> int:
    if settings.SMS_RETENTION_DAYS <= 0:
        return 0
    cutoff = (now or timezone.now()) - timedelta(days=settings.SMS_RETENTION_DAYS)
    old = Message.objects.filter(provider_date__lt=cutoff).exclude(status__in=Message.PENDING_STATUSES)
    total, touched = 0, set()
    while True:
        rows = list(old.values_list("pk", "conversation_id", "kind")[:batch])
        if not rows:
            break
        for message in Message.objects.filter(pk__in=[pk for pk, _, kind in rows if kind == Message.MMS]):
            delete_files(message)
        Message.objects.filter(pk__in=[pk for pk, _, _ in rows]).delete()
        touched.update(conversation for _, conversation, _ in rows)
        total += len(rows)
    for conversation_id in touched:
        refresh_conversation(conversation_id)
    if total:
        record("sms.retention_purge", metadata={"messages": total, "cutoff": cutoff.isoformat(), "days": settings.SMS_RETENTION_DAYS})
    return total
