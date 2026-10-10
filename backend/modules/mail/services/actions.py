"""Bulk thread actions. Works across mailboxes (unified inbox): threads are grouped per mailbox and each group
goes to its provider. The local index is updated right away and an incremental sync is queued to confirm.

Permissions: marking read/unread/starred/important needs read access; organising (archive, labels, spam,
snooze, mute, assign) needs "send & organise"; trash and delete forever need delete.
"""

from __future__ import annotations

import secrets
from collections import defaultdict
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import status

from common.errors import ApiError
from modules.audit.services import record

from ..models import Label, Mailbox, SnoozedThread, Thread, ThreadAssignment, UndoToken
from ..providers import get_provider
from ..providers.base import AuthError, ProviderError
from . import access, store
from .ratelimit import with_backoff

LABEL_CHANGES: dict[str, tuple[list[str], list[str]]] = {
    "read": ([], ["UNREAD"]),
    "unread": (["UNREAD"], []),
    "star": (["STARRED"], []),
    "unstar": ([], ["STARRED"]),
    "important": (["IMPORTANT"], []),
    "not_important": ([], ["IMPORTANT"]),
    "archive": ([], ["INBOX"]),
    "move_to_inbox": (["INBOX"], ["SPAM", "TRASH"]),
    "trash": (["TRASH"], ["INBOX", "SPAM"]),
    "untrash": (["INBOX"], ["TRASH"]),
    "spam": (["SPAM"], ["INBOX"]),
    "not_spam": (["INBOX"], ["SPAM"]),
}
ACTIONS = [
    *LABEL_CHANGES, "delete_forever", "add_labels", "remove_labels", "move_to_label", "snooze", "unsnooze",
    "mute", "unmute", "assign", "unassign",
]
READ_ACTIONS = {"read", "unread", "star", "unstar", "important", "not_important"}
DELETE_ACTIONS = {"trash", "untrash", "delete_forever"}
UNDOABLE = {"read", "unread", "archive", "move_to_inbox", "trash", "untrash", "spam", "not_spam", "add_labels", "remove_labels", "move_to_label", "snooze", "mute", "star", "unstar", "important", "not_important"}
AUDITED = {"trash", "untrash", "delete_forever", "spam", "not_spam", "add_labels", "remove_labels", "move_to_label", "assign", "unassign"}
UNDO_TTL = timedelta(minutes=10)


def required_permission(action: str) -> str:
    if action in READ_ACTIONS:
        return access.READ
    if action in DELETE_ACTIONS:
        return access.DELETE
    return access.SEND


def _check_labels(mailbox: Mailbox, label_ids: list[str]) -> None:
    known = set(Label.objects.filter(mailbox=mailbox, provider_label_id__in=label_ids, type=Label.USER).values_list("provider_label_id", flat=True))
    missing = [label for label in label_ids if label not in known]
    if missing:
        raise ApiError("unknown_label", "One of the labels does not exist in this mailbox.", status.HTTP_400_BAD_REQUEST)


def _provider_call(mailbox: Mailbox, fn):
    try:
        return with_backoff(fn)
    except AuthError as exc:
        from .sync import mark_needs_reconnect

        mark_needs_reconnect(mailbox, str(exc))
        raise ApiError("needs_reconnect", f"{mailbox.email} needs to be reconnected before you can change its mail.", status.HTTP_409_CONFLICT) from exc
    except ProviderError as exc:
        code = status.HTTP_503_SERVICE_UNAVAILABLE if exc.retryable else status.HTTP_400_BAD_REQUEST
        raise ApiError(exc.code, str(exc), code) from exc


def perform(user, action: str, thread_ids: list[int], *, label_ids: list[str] | None = None, until: datetime | None = None, assignee_id: int | None = None, request=None, undoable: bool = True) -> dict:
    if action not in ACTIONS:
        raise ApiError("unknown_action", "This action is not supported.")
    if not thread_ids:
        return {"threads": [], "deleted_ids": [], "undo_token": None}
    threads = access.get_threads(user, thread_ids, required_permission(action))
    label_ids = list(label_ids or [])
    before = {t.pk: list(t.label_ids) for t in threads}
    snoozed_before = {s.thread_id: s.until for s in SnoozedThread.objects.filter(thread__in=threads)}

    by_mailbox: dict[int, list[Thread]] = defaultdict(list)
    for thread in threads:
        by_mailbox[thread.mailbox_id].append(thread)

    deleted_ids: list[int] = []
    for group in by_mailbox.values():
        mailbox = group[0].mailbox
        provider = get_provider(mailbox)
        ids = [t.provider_thread_id for t in group]
        if action in LABEL_CHANGES:
            add, remove = LABEL_CHANGES[action]
            if action == "trash":
                _provider_call(mailbox, lambda: provider.trash_threads(ids))
            elif action == "untrash":
                _provider_call(mailbox, lambda: provider.untrash_threads(ids))
            elif action == "spam":
                _provider_call(mailbox, lambda: provider.mark_spam(ids))
            elif action == "not_spam":
                _provider_call(mailbox, lambda: provider.mark_not_spam(ids))
            else:
                _provider_call(mailbox, lambda: provider.modify_threads(ids, add=add, remove=remove))
            store.apply_label_change_locally(group, add, remove)
        elif action == "delete_forever":
            _provider_call(mailbox, lambda: provider.delete_threads_permanently(ids))
            deleted_ids += [t.pk for t in group]
            Thread.objects.filter(pk__in=[t.pk for t in group]).delete()
        elif action in ("add_labels", "remove_labels", "move_to_label"):
            if not label_ids:
                raise ApiError("validation_error", "Choose a label.")
            if len(by_mailbox) > 1:
                raise ApiError("validation_error", "Labels belong to one mailbox. Select conversations from a single mailbox.")
            _check_labels(mailbox, label_ids)
            add = label_ids if action != "remove_labels" else []
            remove = label_ids if action == "remove_labels" else (["INBOX"] if action == "move_to_label" else [])
            _provider_call(mailbox, lambda: provider.modify_threads(ids, add=add, remove=remove))
            store.apply_label_change_locally(group, add, remove)
        elif action == "snooze":
            if not until or until <= timezone.now():
                raise ApiError("validation_error", "Pick a time in the future.", errors={"until": ["Must be in the future."]})
            _provider_call(mailbox, lambda: provider.modify_threads(ids, remove=["INBOX"]))
            store.apply_label_change_locally(group, [], ["INBOX"])
            for thread in group:
                SnoozedThread.objects.update_or_create(thread=thread, defaults={"until": until, "created_by": user})
        elif action == "unsnooze":
            _provider_call(mailbox, lambda: provider.modify_threads(ids, add=["INBOX"]))
            store.apply_label_change_locally(group, ["INBOX"], [])
            SnoozedThread.objects.filter(thread__in=group).delete()
        elif action == "mute":
            _provider_call(mailbox, lambda: provider.modify_threads(ids, remove=["INBOX"]))
            store.apply_label_change_locally(group, [], ["INBOX"])
            Thread.objects.filter(pk__in=[t.pk for t in group]).update(is_muted=True)
        elif action == "unmute":
            Thread.objects.filter(pk__in=[t.pk for t in group]).update(is_muted=False)
        elif action == "assign":
            _assign(user, group, assignee_id)
        elif action == "unassign":
            ThreadAssignment.objects.filter(thread__in=group).delete()
        store.refresh_label_counts(mailbox)
        _queue_sync(mailbox.pk)

    if action in AUDITED:
        for group in by_mailbox.values():
            record(
                f"mail.{action}", request=request, actor=user, mailbox=group[0].mailbox, target_type="thread",
                target_id=",".join(str(t.pk) for t in group)[:128],
                metadata={"threads": [t.pk for t in group], "subjects": [t.subject[:80] for t in group[:5]], "labels": label_ids, "assignee": assignee_id},
            )

    token = None
    if undoable and action in UNDOABLE:
        token = _undo_token(user, action, threads, before, snoozed_before)
    fresh = list(Thread.objects.filter(pk__in=[t.pk for t in threads]).select_related("mailbox", "mailbox__office", "assignment__assignee", "snooze"))
    return {"threads": fresh, "deleted_ids": deleted_ids, "undo_token": token}


def _assign(user, group: list[Thread], assignee_id: int | None) -> None:
    from django.contrib.auth import get_user_model

    assignee = get_user_model().objects.filter(pk=assignee_id, is_active=True).first() if assignee_id else None
    if not assignee:
        raise ApiError("validation_error", "Choose who to assign to.", errors={"assignee": ["Required."]})
    for thread in group:
        if not access.permissions_for(assignee, thread.mailbox)["read"]:
            raise ApiError("validation_error", f"{assignee.display_name} cannot open {thread.mailbox.email}. Give them access first.")
        ThreadAssignment.objects.update_or_create(thread=thread, defaults={"assignee": assignee, "assigned_by": user, "status": ThreadAssignment.OPEN})


def _undo_token(user, action, threads, before, snoozed_before) -> str:
    changes = []
    for thread in Thread.objects.filter(pk__in=[t.pk for t in threads]):
        old, new = set(before[thread.pk]), set(thread.label_ids)
        changes.append({"thread": thread.pk, "add": sorted(old - new), "remove": sorted(new - old), "snoozed": snoozed_before.get(thread.pk, None) and snoozed_before[thread.pk].isoformat()})
    token = secrets.token_urlsafe(24)
    UndoToken.objects.create(token=token, user=user, changes={"action": action, "items": changes}, expires_at=timezone.now() + UNDO_TTL)
    UndoToken.objects.filter(expires_at__lt=timezone.now()).delete()
    return token


@transaction.atomic
def undo(user, token: str, request=None) -> dict:
    row = UndoToken.objects.select_for_update().filter(token=token, user=user, expires_at__gt=timezone.now()).first()
    if not row:
        raise ApiError("undo_expired", "This can no longer be undone.", status.HTTP_410_GONE)
    items = row.changes["items"]
    action = row.changes["action"]
    row.delete()
    threads = {t.pk: t for t in access.get_threads(user, [i["thread"] for i in items], required_permission(action))}
    by_mailbox: dict[int, list[tuple[Thread, dict]]] = defaultdict(list)
    for item in items:
        thread = threads[item["thread"]]
        by_mailbox[thread.mailbox_id].append((thread, item))
    for pairs in by_mailbox.values():
        mailbox = pairs[0][0].mailbox
        provider = get_provider(mailbox)
        for thread, item in pairs:
            add, remove = item["add"], item["remove"]
            if "TRASH" in remove:
                _provider_call(mailbox, lambda: provider.untrash_threads([thread.provider_thread_id]))
                remove = [x for x in remove if x != "TRASH"]
            if add or remove:
                _provider_call(mailbox, lambda: provider.modify_threads([thread.provider_thread_id], add=add, remove=remove))
            store.apply_label_change_locally([thread], add, item["remove"])
            if action == "snooze":
                SnoozedThread.objects.filter(thread=thread).delete()
            if action == "mute":
                Thread.objects.filter(pk=thread.pk).update(is_muted=False)
        store.refresh_label_counts(mailbox)
        _queue_sync(mailbox.pk)
    if action in AUDITED:
        record(f"mail.undo_{action}", request=request, actor=user, target_type="thread", metadata={"threads": list(threads)})
    fresh = list(Thread.objects.filter(pk__in=list(threads)).select_related("mailbox", "mailbox__office", "assignment__assignee", "snooze"))
    return {"threads": fresh, "deleted_ids": [], "undo_token": None}


def _queue_sync(mailbox_id: int) -> None:
    from ..tasks import sync_mailbox_task

    transaction.on_commit(lambda: sync_mailbox_task.apply_async((mailbox_id,), countdown=2))


def wake_snoozed(now: datetime | None = None) -> int:
    """Return snoozed threads to the inbox (beat task)."""
    now = now or timezone.now()
    count = 0
    for snooze in SnoozedThread.objects.filter(until__lte=now).select_related("thread", "thread__mailbox"):
        thread = snooze.thread
        mailbox = thread.mailbox
        try:
            get_provider(mailbox).modify_threads([thread.provider_thread_id], add=["INBOX", "UNREAD"])
        except ProviderError:
            continue  # try again next run
        store.apply_label_change_locally([thread], ["INBOX", "UNREAD"], [])
        snooze.delete()
        store.refresh_label_counts(mailbox)
        count += 1
    return count
