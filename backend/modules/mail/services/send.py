"""Compose, drafts, undo send and scheduled send.

Every send becomes a `ScheduledEmail`: `kind=undo` with send_at = now + undo window, or `kind=scheduled` at the
chosen time. `dispatch_due()` (Celery beat, plus a Celery eta when a worker is running) claims due rows and
sends them. Cancelling during the window returns the payload so the UI can reopen the compose window.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status

from common.errors import ApiError
from modules.audit.services import record

from ..models import Draft, Mailbox, Message, OutgoingAttachment, ScheduledEmail
from ..providers import get_provider
from ..providers.base import AuthError, ProviderError
from . import access
from .mime import build_mime
from .ratelimit import with_backoff
from .sanitize import sanitize_compose_html

log = logging.getLogger(__name__)

MODES = ("new", "reply", "reply_all", "forward")


def _addresses(items) -> list[dict]:
    result = []
    for item in items or []:
        email = (item.get("email") or "").strip()
        if email:
            result.append({"email": email, "name": (item.get("name") or "").strip()})
    return result


def _source_message(user, message_id) -> Message | None:
    if not message_id:
        return None
    message = Message.objects.select_related("thread", "mailbox").filter(pk=message_id, thread__in=access.accessible_threads(user)).first()
    if not message:
        raise ApiError("not_found", "The message you are replying to was not found.", status.HTTP_404_NOT_FOUND)
    return message


def _from_address(mailbox: Mailbox, send_as: str | None) -> dict:
    if not send_as or send_as.lower() == mailbox.email.lower():
        return {"email": mailbox.email, "name": mailbox.display_name or mailbox.office.name}
    try:
        aliases = get_provider(mailbox).list_send_as()
    except ProviderError:
        aliases = []
    for alias in aliases:
        if alias["email"].lower() == send_as.lower():
            return {"email": alias["email"], "name": alias.get("display_name") or ""}
    raise ApiError("validation_error", "You cannot send from this address.", errors={"send_as": ["Not an alias of this mailbox."]})


def prepare(user, data: dict) -> dict:
    """Validate a compose request and turn it into a self-contained payload for the queue."""
    mailbox = access.get_mailbox(user, data.get("mailbox"), access.SEND)
    mode = data.get("mode") or "new"
    if mode not in MODES:
        raise ApiError("validation_error", "Unknown compose mode.")
    to, cc, bcc = _addresses(data.get("to")), _addresses(data.get("cc")), _addresses(data.get("bcc"))
    if not (to or cc or bcc):
        raise ApiError("validation_error", "Add at least one recipient.", errors={"to": ["Add at least one recipient."]})
    source = _source_message(user, data.get("in_reply_to_message"))
    if source and source.mailbox_id != mailbox.pk:
        raise ApiError("validation_error", "Reply from the mailbox that received the message.")
    attachment_ids = [int(a) for a in data.get("attachment_ids") or []]
    uploads = OutgoingAttachment.objects.filter(pk__in=attachment_ids, mailbox=mailbox)
    if uploads.count() != len(set(attachment_ids)):
        raise ApiError("validation_error", "An attachment is missing. Upload it again.")
    forwarded = [str(a) for a in data.get("forward_attachment_ids") or []]
    total = sum(u.size for u in uploads)
    if source and forwarded:
        total += sum(a["size"] for a in source.attachments if a["id"] in forwarded)
    if total > settings.MAIL_MAX_ATTACHMENT_BYTES:
        raise ApiError("attachments_too_large", "Attachments are larger than 25 MB. Remove some or share a link instead.")

    payload = {
        "mailbox": mailbox.pk,
        "from": _from_address(mailbox, data.get("send_as")),
        "to": to,
        "cc": cc,
        "bcc": bcc,
        "subject": (data.get("subject") or "").strip()[:900],
        "html": sanitize_compose_html(data.get("html") or ""),
        "mode": mode,
        "in_reply_to_message": source.pk if source else None,
        "attachment_ids": attachment_ids,
        "forward_attachment_ids": forwarded,
        "draft_id": data.get("draft_id") or None,
    }
    if source and mode in ("reply", "reply_all", "forward"):
        if mode != "forward":
            payload["in_reply_to"] = source.rfc_message_id
            payload["references"] = " ".join(x for x in (source.references, source.rfc_message_id) if x)[-4000:]
        payload["thread"] = source.thread.provider_thread_id if mode != "forward" else None
    return payload


def queue_send(user, data: dict, request=None) -> ScheduledEmail:
    payload = prepare(user, data)
    send_at: datetime | None = data.get("send_at")
    if send_at:
        if send_at <= timezone.now() + timedelta(seconds=30):
            raise ApiError("validation_error", "Pick a time at least a minute from now.", errors={"send_at": ["Too soon."]})
        kind = ScheduledEmail.SCHEDULED
    else:
        delay = data.get("undo_seconds")
        if delay is None:
            delay = (user.preferences or {}).get("undo_send_seconds", 10)
        kind = ScheduledEmail.UNDO
        send_at = timezone.now() + timedelta(seconds=int(delay))
    item = ScheduledEmail.objects.create(mailbox_id=payload["mailbox"], created_by=user, kind=kind, send_at=send_at, payload=payload)
    if kind == ScheduledEmail.SCHEDULED:
        record("mail.schedule_send", request=request, actor=user, mailbox=item.mailbox, target_type="scheduled", target_id=item.pk, metadata={"subject": payload["subject"][:120], "send_at": send_at.isoformat()})
    _enqueue(item)
    return item


def _enqueue(item: ScheduledEmail) -> None:
    from ..tasks import send_scheduled_task

    if settings.CELERY_TASK_ALWAYS_EAGER:
        # No worker: zero-delay sends go now; delayed ones are picked up by dispatch_due (beat or the next poll).
        if item.send_at <= timezone.now():
            transaction.on_commit(lambda: send_scheduled_task.delay(item.pk))
        return
    transaction.on_commit(lambda: send_scheduled_task.apply_async((item.pk,), eta=item.send_at))


@transaction.atomic
def cancel(user, item_id: int, request=None) -> dict:
    item = ScheduledEmail.objects.select_for_update().filter(pk=item_id).first()
    if not item or not access.accessible_mailboxes(user, access.SEND).filter(pk=item.mailbox_id).exists():
        raise ApiError("not_found", "This message was not found.", status.HTTP_404_NOT_FOUND)
    if item.status != ScheduledEmail.PENDING:
        raise ApiError("already_sent", "Too late — this message has already been sent.", status.HTTP_409_CONFLICT)
    item.status = ScheduledEmail.CANCELLED
    item.save(update_fields=["status"])
    if item.kind == ScheduledEmail.SCHEDULED:
        record("mail.schedule_cancel", request=request, actor=user, mailbox=item.mailbox, target_type="scheduled", target_id=item.pk)
    return item.payload


def _claim(item_id: int) -> ScheduledEmail | None:
    with transaction.atomic():
        item = ScheduledEmail.objects.select_for_update(skip_locked=True).filter(pk=item_id, status=ScheduledEmail.PENDING, send_at__lte=timezone.now()).first()
        if not item:
            return None
        item.status = ScheduledEmail.SENDING
        item.save(update_fields=["status"])
        return item


def build_payload_mime(mailbox: Mailbox, payload: dict) -> bytes:
    attachments = [(a.filename, a.content_type, bytes(a.content)) for a in OutgoingAttachment.objects.filter(pk__in=payload.get("attachment_ids") or [], mailbox=mailbox)]
    if payload.get("forward_attachment_ids") and payload.get("in_reply_to_message"):
        source = Message.objects.filter(pk=payload["in_reply_to_message"], mailbox=mailbox).first()
        if source:
            provider = get_provider(mailbox)
            for meta in source.attachments:
                if meta["id"] in payload["forward_attachment_ids"]:
                    attachments.append((meta["filename"], meta["mime_type"], provider.get_attachment(source.provider_message_id, meta["id"])))
    return build_mime(
        from_addr=payload["from"], to=payload["to"], cc=payload.get("cc"), bcc=payload.get("bcc"), subject=payload.get("subject", ""),
        html=payload.get("html", ""), in_reply_to=payload.get("in_reply_to", ""), references=payload.get("references", ""), attachments=attachments,
    )


def send_now(item_id: int) -> str:
    item = _claim(item_id)
    if not item:
        return "skipped"
    mailbox = item.mailbox
    payload = item.payload
    try:
        mime = build_payload_mime(mailbox, payload)
        provider = get_provider(mailbox)
        sent = with_backoff(lambda: provider.send(mime, payload.get("thread")))
    except AuthError as exc:
        from .sync import mark_needs_reconnect

        mark_needs_reconnect(mailbox, str(exc))
        _fail(item, "The mailbox needs to be reconnected. Reconnect it and send again.")
        return "needs_reconnect"
    except ProviderError as exc:
        _fail(item, str(exc))
        return "failed"
    item.status = ScheduledEmail.SENT
    item.sent_message_id = sent.id
    item.save(update_fields=["status", "sent_message_id"])
    OutgoingAttachment.objects.filter(pk__in=payload.get("attachment_ids") or []).delete()
    if payload.get("draft_id"):
        draft = Draft.objects.filter(pk=payload["draft_id"], mailbox=mailbox).first()
        if draft:
            try:
                provider.drafts_delete(draft.provider_draft_id)
            except ProviderError:
                pass
            draft.delete()
    record(
        "mail.send", actor=item.created_by, mailbox=mailbox, target_type="message", target_id=sent.id,
        metadata={"mode": payload.get("mode"), "subject": payload.get("subject", "")[:120], "recipients": len(payload["to"]) + len(payload.get("cc") or []) + len(payload.get("bcc") or []), "scheduled": item.kind == ScheduledEmail.SCHEDULED},
    )
    from .sync import sync_mailbox

    sync_mailbox(mailbox.pk)
    return "sent"


def _fail(item: ScheduledEmail, error: str) -> None:
    item.status = ScheduledEmail.FAILED
    item.error = error[:500]
    item.save(update_fields=["status", "error"])
    log.warning("send failed for scheduled email %s", item.pk)


def dispatch_due() -> int:
    due = list(ScheduledEmail.objects.filter(status=ScheduledEmail.PENDING, send_at__lte=timezone.now()).values_list("pk", flat=True)[:100])
    return sum(1 for pk in due if send_now(pk) == "sent")


# --- Drafts ---------------------------------------------------------------------------------------------


def save_draft(user, data: dict, draft: Draft | None = None) -> Draft:
    mailbox = access.get_mailbox(user, data.get("mailbox") or (draft and draft.mailbox_id), access.SEND)
    source = _source_message(user, data.get("in_reply_to_message"))
    to, cc, bcc = _addresses(data.get("to")), _addresses(data.get("cc")), _addresses(data.get("bcc"))
    html = sanitize_compose_html(data.get("html") or "")
    subject = (data.get("subject") or "").strip()[:900]
    mode = data.get("mode") or "new"
    in_reply_to = source.rfc_message_id if source and mode != "forward" else ""
    references = " ".join(x for x in ((source.references, source.rfc_message_id) if source and mode != "forward" else ()) if x)
    mime = build_mime(from_addr=_from_address(mailbox, data.get("send_as")), to=to, cc=cc, bcc=bcc, subject=subject, html=html, in_reply_to=in_reply_to, references=references)
    thread_id = source.thread.provider_thread_id if source and mode != "forward" else None
    provider = get_provider(mailbox)
    try:
        if draft:
            result = with_backoff(lambda: provider.drafts_update(draft.provider_draft_id, mime, thread_id))
        else:
            result = with_backoff(lambda: provider.drafts_create(mime, thread_id))
    except AuthError as exc:
        raise ApiError("needs_reconnect", "This mailbox needs to be reconnected before drafts can be saved.", status.HTTP_409_CONFLICT) from exc
    except ProviderError as exc:
        raise ApiError(exc.code, str(exc), status.HTTP_503_SERVICE_UNAVAILABLE if exc.retryable else status.HTTP_400_BAD_REQUEST) from exc
    from html import unescape
    import re

    snippet = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()[:180]
    values = {
        "provider_message_id": result.message_id, "to": to, "cc": cc, "bcc": bcc, "subject": subject, "body_html": html, "snippet": snippet,
        "mode": mode, "in_reply_to_message": source, "thread": source.thread if source and mode != "forward" else None,
        "attachment_ids": [int(a) for a in data.get("attachment_ids") or []], "updated_at": timezone.now(),
    }
    if draft:
        for key, value in values.items():
            setattr(draft, key, value)
        draft.save()
    else:
        draft = Draft.objects.create(mailbox=mailbox, provider_draft_id=result.id, created_by=user, **values)
    return draft


def delete_draft(user, draft: Draft) -> None:
    access.get_mailbox(user, draft.mailbox_id, access.SEND)
    try:
        get_provider(draft.mailbox).drafts_delete(draft.provider_draft_id)
    except ProviderError:
        pass
    draft.delete()
