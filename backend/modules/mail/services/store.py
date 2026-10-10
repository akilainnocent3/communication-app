"""The local index: provider threads/labels → Thread, Message, Label, Contact rows.

The provider is the source of truth. These functions only mirror what it reports, so they are safe to run
again (idempotent upserts keyed on provider ids).
"""

from __future__ import annotations

from collections.abc import Iterable

from django.db import connection, transaction
from django.utils import timezone

from ..models import Contact, Label, Mailbox, Message, Thread
from ..providers.base import ProviderLabel, ProviderThread

SYSTEM_LABEL_NAMES = {
    "INBOX": "Inbox", "SENT": "Sent", "DRAFT": "Drafts", "SPAM": "Spam", "TRASH": "Trash", "STARRED": "Starred",
    "IMPORTANT": "Important", "UNREAD": "Unread", "CATEGORY_PERSONAL": "Primary", "CATEGORY_SOCIAL": "Social",
    "CATEGORY_PROMOTIONS": "Promotions", "CATEGORY_UPDATES": "Updates", "CATEGORY_FORUMS": "Forums", "CHAT": "Chat",
}


def sync_labels(mailbox: Mailbox, labels: Iterable[ProviderLabel]) -> None:
    labels = list(labels)
    seen = set()
    for item in labels:
        seen.add(item.id)
        Label.objects.update_or_create(
            mailbox=mailbox,
            provider_label_id=item.id,
            defaults={
                "name": SYSTEM_LABEL_NAMES.get(item.id, item.name) if item.type == "system" else item.name,
                "type": Label.SYSTEM if item.type == "system" else Label.USER,
                "colour": item.colour or "",
                "text_colour": item.text_colour or "",
            },
        )
    Label.objects.filter(mailbox=mailbox).exclude(provider_label_id__in=seen).delete()
    refresh_label_counts(mailbox)


def refresh_label_counts(mailbox: Mailbox) -> None:
    """Counts come from the local index so they match what the user sees in lists."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT label, COUNT(*), COUNT(*) FILTER (WHERE t.is_unread)
            FROM mail_thread t, unnest(t.label_ids) AS label
            WHERE t.mailbox_id = %s
            GROUP BY label
            """,
            [mailbox.pk],
        )
        counts = {label: (total, unread) for label, total, unread in cursor.fetchall()}
    for label in Label.objects.filter(mailbox=mailbox):
        total, unread = counts.get(label.provider_label_id, (0, 0))
        if label.threads_total != total or label.threads_unread != unread:
            label.threads_total, label.threads_unread = total, unread
            label.save(update_fields=["threads_total", "threads_unread"])


def _participants(messages: list[Message]) -> list[dict]:
    """Distinct senders in order of first appearance (like Gmail's 'Anna, me, Joseph (3)')."""
    result, seen = [], set()
    for message in messages:
        sender = message.from_addr or {}
        email = (sender.get("email") or "").lower()
        if email and email not in seen:
            seen.add(email)
            result.append({"email": sender["email"], "name": sender.get("name", ""), "unread": "UNREAD" in message.label_ids, "is_me": message.is_outgoing})
    return result


def _search_text(subject: str, snippet: str, participants: list[dict], recipients: list[dict]) -> str:
    people = " ".join(f"{p.get('name', '')} {p.get('email', '')}" for p in participants + recipients)
    return f"{subject} {snippet} {people}"


@transaction.atomic
def apply_thread(mailbox: Mailbox, pthread: ProviderThread) -> Thread | None:
    """Upsert one thread and its messages. Returns None when the thread has no messages left."""
    existing = Thread.objects.filter(mailbox=mailbox, provider_thread_id=pthread.id).first()
    if pthread.partial and existing:
        _upsert_messages(mailbox, existing, pthread.messages)
        messages = list(existing.messages.all())
        return _recompute(existing, messages)

    messages = sorted(pthread.messages, key=lambda m: m.date)
    if not messages:
        if existing:
            existing.delete()
        return None
    thread = existing or Thread(mailbox=mailbox, provider_thread_id=pthread.id, last_message_at=messages[-1].date)
    if not thread.pk:
        thread.save()
    _upsert_messages(mailbox, thread, messages)
    keep = {m.id for m in messages}
    thread.messages.exclude(provider_message_id__in=keep).delete()
    return _recompute(thread, list(thread.messages.all()))


def _upsert_messages(mailbox, thread, messages) -> None:
    current = {m.provider_message_id: m for m in thread.messages.all()}
    for pm in messages:
        values = {
            "rfc_message_id": pm.rfc_message_id[:998],
            "in_reply_to": pm.in_reply_to[:998],
            "references": pm.references,
            "from_addr": pm.from_addr.as_dict() if pm.from_addr else {},
            "to": [a.as_dict() for a in pm.to],
            "cc": [a.as_dict() for a in pm.cc],
            "bcc": [a.as_dict() for a in pm.bcc],
            "reply_to": [a.as_dict() for a in pm.reply_to],
            "subject": pm.subject,
            "date": pm.date,
            "snippet": pm.snippet,
            "label_ids": pm.label_ids,
            "size": pm.size,
            "has_attachments": pm.has_attachments,
            "attachments": [a.as_dict() for a in pm.attachments],
            "list_unsubscribe": pm.list_unsubscribe,
            "list_unsubscribe_post": pm.list_unsubscribe_post[:255],
            "is_outgoing": "SENT" in pm.label_ids,
        }
        row = current.get(pm.id)
        if row is None:
            # A message can move between threads (drafts becoming sent replies): reuse its row.
            row = Message.objects.filter(mailbox=mailbox, provider_message_id=pm.id).first()
        if row is None:
            Message.objects.create(thread=thread, mailbox=mailbox, provider_message_id=pm.id, **values)
            _note_contacts(mailbox, pm)
        else:
            row.thread = thread
            for key, value in values.items():
                setattr(row, key, value)
            row.save()


def _recompute(thread: Thread, rows: list[Message]) -> Thread | None:
    if not rows:
        thread.delete()
        return None
    rows.sort(key=lambda m: (m.date, m.pk))
    # Drafts and trashed/spam copies don't define what the list shows unless they are all there is.
    visible = [m for m in rows if "DRAFT" not in m.label_ids] or rows
    labels: list[str] = []
    for message in rows:
        for label in message.label_ids:
            if label not in labels:
                labels.append(label)
    latest = visible[-1]
    participants = _participants(visible)
    thread.subject = visible[0].subject or latest.subject
    thread.snippet = latest.snippet
    thread.participants = participants
    thread.last_message_at = latest.date
    thread.message_count = len(visible)
    thread.has_attachments = any(m.has_attachments for m in rows)
    thread.label_ids = labels
    thread.is_unread = "UNREAD" in labels
    thread.is_starred = "STARRED" in labels
    thread.is_important = "IMPORTANT" in labels
    thread.save()
    update_search_vector(thread, [r for m in visible for r in (m.to + m.cc)])
    return thread


def update_search_vector(thread: Thread, recipients: list[dict]) -> None:
    if connection.vendor != "postgresql":
        return
    text = _search_text(thread.subject, thread.snippet, thread.participants, recipients)
    with connection.cursor() as cursor:
        cursor.execute("UPDATE mail_thread SET search_vector = to_tsvector('simple', %s) WHERE id = %s", [text[:20000], thread.pk])


def delete_threads(mailbox: Mailbox, provider_thread_ids: Iterable[str]) -> int:
    count, _ = Thread.objects.filter(mailbox=mailbox, provider_thread_id__in=list(provider_thread_ids)).delete()
    return count


def delete_messages(mailbox: Mailbox, provider_message_ids: Iterable[str]) -> None:
    rows = list(Message.objects.filter(mailbox=mailbox, provider_message_id__in=list(provider_message_ids)).select_related("thread"))
    threads = {row.thread for row in rows}
    Message.objects.filter(pk__in=[row.pk for row in rows]).delete()
    for thread in threads:
        _recompute(thread, list(thread.messages.all()))


def apply_label_change_locally(threads: Iterable[Thread], add: Iterable[str], remove: Iterable[str]) -> None:
    """Optimistic local update after a successful provider call (the next sync confirms it)."""
    add, remove = list(add), set(remove)
    for thread in threads:
        for message in thread.messages.all():
            labels = [x for x in message.label_ids if x not in remove]
            for label in add:
                # Gmail applies SENT/DRAFT only by sending; don't invent them locally.
                if label not in labels:
                    labels.append(label)
            if labels != message.label_ids:
                message.label_ids = labels
                message.save(update_fields=["label_ids"])
        _recompute(thread, list(thread.messages.all()))


def _note_contacts(mailbox: Mailbox, pm) -> None:
    people = ([pm.from_addr] if pm.from_addr else []) + list(pm.to) + list(pm.cc)
    now = timezone.now()
    for person in people:
        email = (person.email or "").lower()
        if not email or email == mailbox.email.lower() or "noreply" in email or "no-reply" in email:
            continue
        contact, created = Contact.objects.get_or_create(mailbox=mailbox, email=email, defaults={"name": person.name or "", "last_seen": pm.date or now})
        if not created:
            contact.frequency += 1
            if person.name and not contact.name:
                contact.name = person.name
            if pm.date and pm.date > contact.last_seen:
                contact.last_seen = pm.date
            contact.save(update_fields=["frequency", "name", "last_seen"])
