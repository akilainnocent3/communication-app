"""Retention (CALLS_RETENTION_DAYS, or CallSettings.retention_days when set; 0 = keep forever).

Calls older than the window are deleted with their timeline and notes, and so are the per-number rollups
(CallerDaily, which holds numbers). The hourly counts (CallStatHourly) carry no personal data and are kept, so long-term
volume charts survive. Deleting a call on the phone never deletes the server copy (it shows "Deleted on phone").
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from modules.audit.services import record

from ..models import CallerDaily, CallRecord, CallSettings


def retention_days() -> int:
    override = CallSettings.load().retention_days
    return settings.CALLS_RETENTION_DAYS if override is None else override


def purge(now=None, batch: int = 2000) -> int:
    days = retention_days()
    if days <= 0:
        return 0
    cutoff = (now or timezone.now()) - timedelta(days=days)
    total = 0
    while True:
        ids = list(CallRecord.objects.filter(started_at__lt=cutoff).values_list("pk", flat=True)[:batch])
        if not ids:
            break
        CallRecord.objects.filter(pk__in=ids).delete()
        total += len(ids)
    callers = CallerDaily.objects.filter(day__lt=cutoff.date()).delete()[0]
    if total or callers:
        record("calls.retention_purge", metadata={"calls": total, "caller_days": callers, "cutoff": cutoff.isoformat(), "days": days})
    return total
