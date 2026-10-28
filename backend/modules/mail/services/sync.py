"""Sync engine. Runs in Celery; API requests only enqueue it (never block on a long sync).

* Full sync: metadata only, newest first, limited to MAIL_INITIAL_SYNC_DAYS / MAIL_INITIAL_SYNC_MAX_THREADS,
  with progress saved on the mailbox ("Syncing 1,240 / 3,000").
* Incremental sync: from the stored cursor (Gmail historyId). An expired cursor falls back to a full resync.
* Credential failures mark the mailbox `needs_reconnect`.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from common.stores import security_store

from ..models import Draft, Mailbox, MailboxStatus, Thread
from ..providers import get_provider
from ..providers.base import AuthError, CursorExpired, ProviderError
from . import store
from .ratelimit import with_backoff

log = logging.getLogger(__name__)



class SyncLock:
    """One sync per mailbox at a time (across workers)."""

    def __init__(self, mailbox_id: int, ttl: int = 15 * 60):
        self.key = f"mail-sync-lock:{mailbox_id}"
        self.ttl = ttl
        self.acquired = False

    def __enter__(self):
        # The security store never evicts, so a held lock cannot vanish under memory pressure.
        self.acquired = security_store().add(self.key, 1, self.ttl)
        return self.acquired

    def __exit__(self, *exc):
        if self.acquired:
            security_store().delete(self.key)


def _set(mailbox: Mailbox, **fields) -> None:
    for key, value in fields.items():
        setattr(mailbox, key, value)
    Mailbox.objects.filter(pk=mailbox.pk).update(**fields)


def mark_needs_reconnect(mailbox: Mailbox, reason: str = "") -> None:
    if mailbox.status != MailboxStatus.NEEDS_RECONNECT:
        from modules.audit.services import record

        record("mailbox.needs_reconnect", mailbox=mailbox, target_type="mailbox", target_id=mailbox.pk, metadata={"reason": reason[:200]})
    _set(mailbox, status=MailboxStatus.NEEDS_RECONNECT, sync_error=reason or "Access was revoked or expired. Send a reconnect link.")


def handle_provider_error(mailbox: Mailbox, exc: ProviderError) -> None:
    if isinstance(exc, AuthError):
        mark_needs_reconnect(mailbox, str(exc))


def full_sync(mailbox: Mailbox) -> int:
    provider = get_provider(mailbox)
    _set(mailbox, status=MailboxStatus.SYNCING, sync_error="", sync_progress={"done": 0, "total": 0, "phase": "starting"})
    store.sync_labels(mailbox, with_backoff(provider.list_labels))
    since = timezone.now() - timedelta(days=settings.MAIL_INITIAL_SYNC_DAYS)

    def progress(done: int, total: int) -> None:
        _set(mailbox, sync_progress={"done": done, "total": total, "phase": "threads"})

    threads, cursor = provider.sync_full(since, settings.MAIL_INITIAL_SYNC_MAX_THREADS, progress)
    seen = set()
    for pthread in threads:
        seen.add(pthread.id)
        store.apply_thread(mailbox, pthread)
    # Anything we indexed before that the server no longer has (within the window) is gone.
    Thread.objects.filter(mailbox=mailbox, last_message_at__gte=since).exclude(provider_thread_id__in=seen).delete()
    sync_drafts(mailbox, provider)
    store.refresh_label_counts(mailbox)
    _set(mailbox, history_id=cursor, status=MailboxStatus.CONNECTED, last_synced_at=timezone.now(), sync_progress={}, sync_error="")
    return len(seen)


def incremental_sync(mailbox: Mailbox) -> int:
    if not mailbox.history_id:
        return full_sync(mailbox)
    provider = get_provider(mailbox)
    try:
        changes = with_backoff(lambda: provider.sync_incremental(mailbox.history_id))
    except CursorExpired:
        log.info("sync cursor expired for mailbox %s: full resync", mailbox.pk)
        return full_sync(mailbox)
    muted = []
    for pthread in changes.threads:
        thread = store.apply_thread(mailbox, pthread)
        if thread and thread.is_muted and "INBOX" in thread.label_ids:
            muted.append(thread)
    if muted:  # muted conversations skip the inbox when new replies arrive
        provider.modify_threads([t.provider_thread_id for t in muted], remove=["INBOX"])
        store.apply_label_change_locally(muted, [], ["INBOX"])
    if changes.deleted_thread_ids:
        store.delete_threads(mailbox, changes.deleted_thread_ids)
    if changes.deleted_message_ids:
        store.delete_messages(mailbox, changes.deleted_message_ids)
    if changes.drafts_changed:
        sync_drafts(mailbox, provider)
    if changes.threads or changes.deleted_thread_ids or changes.deleted_message_ids:
        store.refresh_label_counts(mailbox)
    fields = {"history_id": changes.cursor or mailbox.history_id, "last_synced_at": timezone.now()}
    if mailbox.status != MailboxStatus.CONNECTED:
        fields.update(status=MailboxStatus.CONNECTED, sync_error="")
    _set(mailbox, **fields)
    return len(changes.threads)


def sync_drafts(mailbox: Mailbox, provider) -> None:
    """Keep Draft rows pointing at live provider drafts (drafts created elsewhere show up too)."""
    try:
        drafts = provider.drafts_list()
    except ProviderError:
        return
    live = {d.id: d for d in drafts}
    Draft.objects.filter(mailbox=mailbox).exclude(provider_draft_id__in=live).delete()
    from ..models import Message

    known = set(Draft.objects.filter(mailbox=mailbox).values_list("provider_draft_id", flat=True))
    for draft in drafts:
        message = Message.objects.filter(mailbox=mailbox, provider_message_id=draft.message_id).select_related("thread").first()
        if draft.id in known:
            Draft.objects.filter(mailbox=mailbox, provider_draft_id=draft.id).update(provider_message_id=draft.message_id)
            continue
        Draft.objects.create(
            mailbox=mailbox,
            provider_draft_id=draft.id,
            provider_message_id=draft.message_id,
            thread=message.thread if message and message.thread.message_count > 0 and not _draft_only(message.thread) else None,
            to=message.to if message else [],
            cc=message.cc if message else [],
            bcc=message.bcc if message else [],
            subject=message.subject if message else "",
            snippet=message.snippet if message else "",
            mode="reply" if message and message.in_reply_to else "new",
        )


def _draft_only(thread: Thread) -> bool:
    return all("DRAFT" in labels for labels in thread.messages.values_list("label_ids", flat=True))


def sync_mailbox(mailbox_id: int, full: bool = False) -> str:
    """Entry point used by tasks. Returns a short outcome string (for logs and tests)."""
    mailbox = Mailbox.objects.select_related("office").filter(pk=mailbox_id).first()
    if not mailbox:
        return "missing"
    if mailbox.status in (MailboxStatus.DISABLED, MailboxStatus.NEEDS_RECONNECT):
        return f"skipped:{mailbox.status}"
    if mailbox.status == MailboxStatus.PENDING and not mailbox.encrypted_credentials and mailbox.provider != "fake":
        return "skipped:pending"
    with SyncLock(mailbox.pk) as acquired:
        if not acquired:
            return "locked"
        try:
            count = full_sync(mailbox) if full else incremental_sync(mailbox)
            return f"ok:{count}"
        except AuthError as exc:
            mark_needs_reconnect(mailbox, str(exc))
            return "needs_reconnect"
        except ProviderError as exc:
            log.warning("sync failed for mailbox %s: %s", mailbox.pk, exc.code)
            _set(mailbox, status=MailboxStatus.ERROR, sync_error=str(exc)[:500], sync_progress={})
            return f"error:{exc.code}"
