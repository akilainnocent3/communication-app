"""Opening a thread: bodies are fetched on demand, sanitised, cached, and the thread is marked read."""

from __future__ import annotations

from django.utils import timezone
from rest_framework import status

from common.errors import ApiError
from modules.audit.services import record

from ..models import Message, Thread, TrustedSender
from ..providers import get_provider
from ..providers.base import AuthError, NotFound, ProviderError
from . import store
from .ratelimit import with_backoff
from .sanitize import sanitize_email_html, text_to_html, with_images


def load_bodies(thread: Thread) -> list[Message]:
    messages = list(thread.messages.order_by("date", "id"))
    if all(m.body_cached_at for m in messages):
        return messages
    provider = get_provider(thread.mailbox)
    try:
        full = with_backoff(lambda: provider.get_thread(thread.provider_thread_id, format="full"))
    except NotFound:
        store.delete_threads(thread.mailbox, [thread.provider_thread_id])
        raise ApiError("not_found", "This conversation was deleted on the mail server.", status.HTTP_404_NOT_FOUND) from None
    except AuthError as exc:
        from .sync import mark_needs_reconnect

        mark_needs_reconnect(thread.mailbox, str(exc))
        raise ApiError("needs_reconnect", f"{thread.mailbox.email} needs to be reconnected before its mail can be opened.", status.HTTP_409_CONFLICT) from None
    except ProviderError as exc:
        raise ApiError(exc.code, str(exc), status.HTTP_503_SERVICE_UNAVAILABLE) from None
    by_id = {m.provider_message_id: m for m in messages}
    now = timezone.now()
    for pm in full.messages:
        row = by_id.get(pm.id)
        if not row:
            continue
        if pm.body_html:
            html, meta = sanitize_email_html(pm.body_html, pm.inline_images)
        else:
            html, meta = text_to_html(pm.body_text or ""), {"remote_images": 0, "link_warnings": []}
        row.body_html, row.body_text, row.body_meta, row.body_cached_at = html, pm.body_text or "", meta, now
        # Full format has real attachment ids (IMAP metadata only knows "has attachments").
        row.attachments = [a.as_dict() for a in pm.attachments]
        row.save(update_fields=["body_html", "body_text", "body_meta", "body_cached_at", "attachments"])
    return messages


def open_thread(user, thread: Thread, *, peek: bool = False, request=None) -> tuple[Thread, list[Message]]:
    messages = load_bodies(thread)
    if not peek:
        record("mail.open_thread", request=request, actor=user, mailbox=thread.mailbox, target_type="thread", target_id=thread.pk, metadata={"subject": thread.subject[:120]})
        if thread.is_unread:
            from .actions import perform

            perform(user, "read", [thread.pk], request=request, undoable=False)
            thread.refresh_from_db()
            messages = list(thread.messages.order_by("date", "id"))
    return thread, messages


def trusted_senders(user) -> set[str]:
    return set(TrustedSender.objects.filter(user=user).values_list("email", flat=True))


def images_allowed(message: Message, show_images: bool, trusted: set[str]) -> bool:
    sender = (message.from_addr or {}).get("email", "").lower()
    return show_images or message.is_outgoing or sender in trusted


def body_for(message: Message, allowed: bool) -> str:
    html = message.body_html or ""
    return with_images(html) if html and allowed else html
