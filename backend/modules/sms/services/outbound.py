"""Admin reply → phone sends it as a normal carrier SMS. One mechanism for undo send and scheduled send.

Lifecycle of an admin message (`Message.status`):

    queued ──claim──▶ dispatched ──phone: "sending"──▶ sending ──▶ sent ──▶ delivered
      │                   │ (lease expires, not acknowledged: offered again)   └──▶ failed
      ├─cancel─▶ cancelled │                                                 └──▶ unknown
      └─too old─▶ expired ◀┘

- `send_at` is the undo window (now + the user's undo_send_seconds) or the scheduled time. The phone only claims
  messages whose `send_at` has passed. Cancelling is possible only while `queued` (never offered to a phone).
- **At most once.** SMS costs money and duplicates confuse customers. A claim leases messages to the phone for
  `LEASE_SECONDS`. The phone writes the message durably and reports `sending` *before* calling SmsManager; from
  then on the server never offers it again. The phone never sends a `client_uuid` it has already started; if it
  died between `sending` and the result it reports `unknown` and a person decides whether to resend.
- Messages older than `SMS_OUTBOUND_TTL_HOURS` expire instead of being sent days late.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

import phonenumbers
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status

from common import stores
from common.errors import ApiError
from modules.audit.services import record
from modules.devices.models import Device, DeviceCommand, SimLine
from modules.devices.services.phone import address_kind, address_key, mask

from ..models import Contact, Conversation, Message, MessageStatus
from . import access, store
from .crypto import decrypt_text, encrypt_text
from .text import MAX_BODY, segment_info

log = logging.getLogger(__name__)

LEASE_SECONDS = 120
# Messages the server asks the phone to send: written by an admin, or automatic (Calls' missed-call SMS). One queue,
# one daily cap, one at-most-once lifecycle.
SERVER_ORIGINS = (Message.ORIGIN_ADMIN, Message.ORIGIN_AUTO)
CLAIM_LIMIT = 10
MAX_RECIPIENTS = 20
MAX_SCHEDULE_DAYS = 30
ERROR_REASONS = {
    1: "The phone could not send the message (generic failure).",
    2: "The phone's radio is off (airplane mode?).",
    3: "The phone could not encode the message.",
    4: "The phone has no mobile service.",
    5: "The phone reached its sending limit. Android asked for confirmation.",
    6: "Blocked by the SIM's fixed dialling numbers.",
    7: "The carrier does not allow sending to this short code.",
    8: "The carrier never allows sending to this short code.",
    1001: "The app is no longer the phone's default SMS app.",
    1002: "The SMS permission was revoked on the phone.",
    1003: "The message expired on the phone before it could be sent.",
    1004: "The chosen SIM is not available on the phone.",
}


def reason_for(code: int | None) -> str:
    if code is None:
        return ""
    return ERROR_REASONS.get(code, f"Carrier or network error (code {code}).")


# --- Recipients and limits -------------------------------------------------------------------------------------


def check_recipient(raw: str, region: str) -> str:
    """The address key for a recipient, or a friendly refusal (sender IDs, short codes, premium rate, invalid)."""
    kind = address_kind(raw)
    if kind == "alphanumeric":
        raise ApiError("invalid_recipient", f"“{raw}” is a sender name, not a phone number. It cannot receive replies.", errors={"to": ["Not a phone number."]})
    if kind == "short_code":
        if not settings.SMS_ALLOW_SHORT_CODES:
            raise ApiError("short_code_refused", "Sending to short codes is turned off on this server (they can be premium-rate).", errors={"to": ["Short codes are not allowed."]})
        return address_key(raw, region)
    try:
        number = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        raise ApiError("invalid_recipient", f"“{raw}” is not a valid phone number.", errors={"to": ["Not a valid number."]}) from None
    if not phonenumbers.is_valid_number(number):
        raise ApiError("invalid_recipient", f"“{raw}” is not a valid phone number.", errors={"to": ["Not a valid number."]})
    if phonenumbers.number_type(number) in (phonenumbers.PhoneNumberType.PREMIUM_RATE, phonenumbers.PhoneNumberType.SHARED_COST):
        raise ApiError("premium_refused", "Premium-rate numbers are not allowed.", errors={"to": ["Premium-rate number."]})
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def _bump(key: str, limit: int, window: int = 60) -> bool:
    """Fixed-window counter in the security store (never evicted). False when the limit is reached."""
    try:
        return stores.bump(key, window) <= limit
    except stores.SecurityStoreUnavailable:
        raise ApiError("try_later", "Sending is paused for a moment. Try again in a minute.", status.HTTP_503_SERVICE_UNAVAILABLE) from None


def check_limits(user, device: Device) -> None:
    if not _bump(f"sms:rate:user:{user.pk}", settings.SMS_USER_RATE_PER_MINUTE):
        raise ApiError("rate_limited", "You're sending too fast. Wait a minute and try again.", status.HTTP_429_TOO_MANY_REQUESTS)
    if not _bump(f"sms:rate:device:{device.pk}", settings.SMS_DEVICE_RATE_PER_MINUTE):
        raise ApiError("rate_limited", "This phone is sending too fast. Wait a minute so the carrier does not block the SIM.", status.HTTP_429_TOO_MANY_REQUESTS)
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    today = Message.objects.filter(device=device, origin__in=SERVER_ORIGINS, created_at__gte=start).exclude(status=MessageStatus.CANCELLED).count()
    if today >= settings.SMS_DEVICE_DAILY_CAP:
        raise ApiError("daily_cap", f"This phone reached today's limit of {settings.SMS_DEVICE_DAILY_CAP} messages from the admin. This protects the SIM from carrier spam blocks.", status.HTTP_429_TOO_MANY_REQUESTS)


def _sim_for(device: Device, sim_id, conversation: Conversation | None) -> SimLine | None:
    lines = SimLine.objects.filter(device=device, is_active=True)
    if sim_id not in (None, ""):
        line = lines.filter(pk=sim_id).first()
        if not line:
            raise ApiError("validation_error", "Choose a SIM on this phone.", errors={"sim_line": ["Unknown SIM."]})
        return line
    if conversation and conversation.sim_line_id and lines.filter(pk=conversation.sim_line_id).exists():
        return conversation.sim_line
    return lines.filter(is_default=True).first() or lines.first()


def with_signature(device: Device, body: str) -> str:
    options = device.options or {}
    signature = (options.get("signature") or "").strip()
    if options.get("signature_enabled") and signature and not body.rstrip().endswith(signature):
        return f"{body.rstrip()}\n{signature}"
    return body


# --- Compose ---------------------------------------------------------------------------------------------------


def compose(user, data: dict, request=None) -> Message:
    device = access.get_device(user, data.get("device"), access.SEND)
    access.require_sendable(device)
    conversation = None
    if data.get("conversation"):
        conversation = access.get_conversation(user, data["conversation"], access.SEND)
        if conversation.device_id != device.pk:
            raise ApiError("validation_error", "Reply from the phone that holds the conversation.")
    region = settings.SMS_DEFAULT_REGION
    raw_recipients = conversation.addresses if conversation else [str(item).strip() for item in data.get("to") or [] if str(item).strip()]
    if not raw_recipients:
        raise ApiError("validation_error", "Add a phone number.", errors={"to": ["Add a phone number."]})
    if len(raw_recipients) > MAX_RECIPIENTS:
        raise ApiError("validation_error", f"Send to at most {MAX_RECIPIENTS} people at once.", errors={"to": ["Too many recipients."]})
    keys = sorted({check_recipient(raw, region) for raw in raw_recipients})
    blocked = Contact.objects.filter(device=device, address__in=keys, is_blocked=True).values_list("address", flat=True)
    if blocked:
        raise ApiError("recipient_blocked", "This number is blocked on the phone. Unblock it first.")
    body = (data.get("body") or "").strip()
    if not body:
        raise ApiError("validation_error", "Write a message first.", errors={"body": ["Write a message first."]})
    body = with_signature(device, body)
    if len(body) > MAX_BODY:
        raise ApiError("validation_error", f"Messages can be at most {MAX_BODY} characters.", errors={"body": ["Too long."]})

    client_uuid = data.get("client_uuid") or uuid.uuid4()
    existing = Message.objects.filter(client_uuid=client_uuid).first()
    if existing:
        if existing.sent_by_id == user.pk and existing.device_id == device.pk:
            return existing  # double submit: same message
        raise ApiError("conflict", "This message id is already used.", status.HTTP_409_CONFLICT)

    now = timezone.now()
    send_at = data.get("send_at")
    scheduled = bool(send_at)
    if scheduled:
        if send_at <= now + timedelta(seconds=30):
            raise ApiError("validation_error", "Pick a time at least a minute from now.", errors={"send_at": ["Too soon."]})
        if send_at > now + timedelta(days=MAX_SCHEDULE_DAYS):
            raise ApiError("validation_error", f"Schedule at most {MAX_SCHEDULE_DAYS} days ahead.", errors={"send_at": ["Too far ahead."]})
    else:
        delay = data.get("undo_seconds")
        if delay is None:
            delay = (user.preferences or {}).get("undo_send_seconds", 10)
        send_at = now + timedelta(seconds=max(0, min(int(delay), 30)))
    check_limits(user, device)

    with transaction.atomic():
        if conversation is None:
            conversation = store.conversation_for(device, keys, at=send_at)
        sim = _sim_for(device, data.get("sim_line"), conversation)
        info = segment_info(body)
        message = Message(
            device=device, conversation=conversation, sim_line=sim, kind=Message.MMS if len(keys) > 1 else Message.SMS, direction=Message.OUT,
            address=keys[0], addresses=keys, encrypted_body=encrypt_text(body), body_length=len(body), segments=info.segments, encoding=info.encoding,
            provider_date=send_at, is_read=True, origin=Message.ORIGIN_ADMIN, sent_by=user, client_uuid=client_uuid, send_at=send_at, is_scheduled=scheduled,
        )
        message.set_status(MessageStatus.QUEUED, now)
        message.save()
        store.refresh_conversation(conversation.pk)
        record(
            "sms.schedule" if scheduled else "sms.send", request=request, actor=user, target_type="sms_message", target_id=message.pk,
            metadata={"device": device.code, "conversation": conversation.pk, "recipients": [mask(k) for k in keys], "segments": info.segments,
                      "send_at": send_at.isoformat(), "sim": sim.subscription_id if sim else None},
        )
        if not scheduled and send_at <= now + timedelta(seconds=1):
            from modules.devices.tasks import push_task

            transaction.on_commit(lambda: push_task.delay(str(device.pk), "outbox"))
    log.info("sms queued %s on %s to %s", message.pk, device.code, ",".join(mask(k) for k in keys))
    return message


def queue_automatic(device: Device, raw_number: str, body: str, *, reason: str) -> Message:
    """A message the server sends on its own (Calls: the missed-call SMS). Same path and rules as an admin message —
    recipient checks (no sender IDs, short codes or premium numbers), blocks, the per-phone rate and the daily cap —
    but no user: origin "auto", sent at once. Raises ApiError when a rule refuses it."""
    from modules.platforms.services import is_platform_enabled

    if not (device.has("sms") and is_platform_enabled("sms")):
        raise ApiError("sms_unavailable", "This phone does not send SMS through OCM.", status.HTTP_409_CONFLICT)
    access.require_sendable(device)
    key = check_recipient(raw_number, settings.SMS_DEFAULT_REGION)
    if Contact.objects.filter(device=device, address=key, is_blocked=True).exists():
        raise ApiError("recipient_blocked", "This number is blocked on the phone.")
    body = with_signature(device, (body or "").strip())[:MAX_BODY]
    if not body:
        raise ApiError("validation_error", "The message is empty.")
    if not _bump(f"sms:rate:device:{device.pk}", settings.SMS_DEVICE_RATE_PER_MINUTE):
        raise ApiError("rate_limited", "This phone is sending too fast.", status.HTTP_429_TOO_MANY_REQUESTS)
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    if Message.objects.filter(device=device, origin__in=SERVER_ORIGINS, created_at__gte=start).exclude(status=MessageStatus.CANCELLED).count() >= settings.SMS_DEVICE_DAILY_CAP:
        raise ApiError("daily_cap", "This phone reached today's message limit.", status.HTTP_429_TOO_MANY_REQUESTS)
    now = timezone.now()
    with transaction.atomic():
        conversation = store.conversation_for(device, [key], at=now)
        sim = _sim_for(device, None, conversation)
        info = segment_info(body)
        message = Message(
            device=device, conversation=conversation, sim_line=sim, kind=Message.SMS, direction=Message.OUT, address=key, addresses=[key],
            encrypted_body=encrypt_text(body), body_length=len(body), segments=info.segments, encoding=info.encoding, provider_date=now,
            is_read=True, origin=Message.ORIGIN_AUTO, client_uuid=uuid.uuid4(), send_at=now,
        )
        message.set_status(MessageStatus.QUEUED, now)
        message.save()
        store.refresh_conversation(conversation.pk)
        record("sms.auto_send", target_type="sms_message", target_id=message.pk, metadata={"device": device.code, "recipient": mask(key), "reason": reason})
        from modules.devices.tasks import push_task

        transaction.on_commit(lambda: push_task.delay(str(device.pk), "outbox"))
    return message


@transaction.atomic
def cancel(user, message_id, request=None) -> Message:
    message = access.get_message(user, message_id, access.SEND)
    message = Message.objects.select_for_update().get(pk=message.pk)
    if message.origin != Message.ORIGIN_ADMIN or message.status != MessageStatus.QUEUED:
        raise ApiError("already_sent", "Too late: the phone has already picked up this message.", status.HTTP_409_CONFLICT)
    message.set_status(MessageStatus.CANCELLED)
    message.save(update_fields=["status", "status_history"])
    store.refresh_conversation(message.conversation_id)
    record("sms.cancel", request=request, actor=user, target_type="sms_message", target_id=message.pk, metadata={"device": message.device.code, "scheduled": message.is_scheduled})
    return message


def retry(user, message_id, request=None) -> Message:
    source = access.get_message(user, message_id, access.SEND)
    if source.direction != Message.OUT or source.status not in (MessageStatus.FAILED, MessageStatus.EXPIRED, MessageStatus.UNKNOWN, MessageStatus.CANCELLED):
        raise ApiError("validation_error", "Only failed, expired, cancelled or unknown messages can be sent again.")
    message = compose(user, {
        "device": source.device_id, "conversation": source.conversation_id, "body": decrypt_text(source.encrypted_body),
        "sim_line": source.sim_line_id, "undo_seconds": 0, "client_uuid": uuid.uuid4(),
    }, request=request)
    Message.objects.filter(pk=message.pk).update(retry_of=source)
    record("sms.retry", request=request, actor=user, target_type="sms_message", target_id=message.pk, metadata={"device": source.device.code, "retry_of": source.pk, "previous_status": source.status})
    return message


# --- Phone side ------------------------------------------------------------------------------------------------


def claim(device: Device, limit: int = CLAIM_LIMIT) -> dict:
    """Lease due messages (and pending commands) to the phone. Acknowledged messages are never offered again."""
    now = timezone.now()
    ttl = timedelta(hours=settings.SMS_OUTBOUND_TTL_HOURS)
    with transaction.atomic():
        due = list(
            Message.objects.select_for_update(skip_locked=True)
            .filter(device=device, origin__in=SERVER_ORIGINS, direction=Message.OUT, send_at__lte=now, send_at__gt=now - ttl)
            .filter(Q(status=MessageStatus.QUEUED) | Q(status=MessageStatus.DISPATCHED, lease_expires_at__lt=now))
            .order_by("send_at", "id")[:limit]
        )
        for message in due:
            if message.status == MessageStatus.QUEUED:
                message.set_status(MessageStatus.DISPATCHED, now)
                message.dispatched_at = now
            message.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
            message.save(update_fields=["status", "status_history", "dispatched_at", "lease_expires_at"])
        commands = list(DeviceCommand.objects.select_for_update(skip_locked=True).filter(device=device, status__in=[DeviceCommand.PENDING, DeviceCommand.DELIVERED]).order_by("id")[:50])
        DeviceCommand.objects.filter(pk__in=[c.pk for c in commands], status=DeviceCommand.PENDING).update(status=DeviceCommand.DELIVERED, delivered_at=now)
    for conversation_id in {m.conversation_id for m in due}:
        store.refresh_conversation(conversation_id)
    return {
        "messages": [_claim_payload(message, ttl) for message in due],
        "commands": [{"id": c.pk, "kind": c.kind, "payload": c.payload} for c in commands],
        "lease_seconds": LEASE_SECONDS,
    }


def _claim_payload(message: Message, ttl: timedelta) -> dict:
    sender = ""
    if message.sent_by_id and settings.SMS_SHOW_ADMIN_NAME_ON_PHONE:
        sender = message.sent_by.display_name
    return {
        "client_uuid": str(message.client_uuid), "kind": message.kind, "addresses": message.addresses, "body": decrypt_text(message.encrypted_body),
        "subscription_id": message.sim_line.subscription_id if message.sim_line_id else None, "thread_id": message.conversation.thread_id,
        "sent_by": sender, "queued_at": message.created_at, "expires_at": (message.send_at or message.created_at) + ttl,
    }


ALLOWED_REPORTS = {
    MessageStatus.SENDING: {MessageStatus.QUEUED, MessageStatus.DISPATCHED, MessageStatus.EXPIRED},
    MessageStatus.SENT: {MessageStatus.DISPATCHED, MessageStatus.SENDING, MessageStatus.UNKNOWN, MessageStatus.EXPIRED, MessageStatus.FAILED},
    MessageStatus.DELIVERED: {MessageStatus.DISPATCHED, MessageStatus.SENDING, MessageStatus.SENT, MessageStatus.UNKNOWN, MessageStatus.EXPIRED, MessageStatus.FAILED},
    MessageStatus.FAILED: {MessageStatus.DISPATCHED, MessageStatus.SENDING, MessageStatus.UNKNOWN, MessageStatus.EXPIRED},
    MessageStatus.UNKNOWN: {MessageStatus.DISPATCHED, MessageStatus.SENDING},
}


def report(device: Device, reports: list[dict]) -> dict:
    """Status reports from the phone. Only this phone's own admin messages can be updated."""
    results, touched = [], set()
    for item in reports:
        new = item["status"]
        with transaction.atomic():
            message = Message.objects.select_for_update().filter(device=device, client_uuid=item["client_uuid"], origin__in=SERVER_ORIGINS).first()
            if not message:
                results.append({"client_uuid": str(item["client_uuid"]), "result": "unknown_message"})
                continue
            if message.status == new or message.status not in ALLOWED_REPORTS[new]:
                results.append({"client_uuid": str(item["client_uuid"]), "result": "ignored", "status": message.status})
                continue
            at = store.from_millis(item["at"]) if item.get("at") else timezone.now()
            message.set_status(new, at)
            message.lease_expires_at = None
            if new == MessageStatus.SENT:
                message.sent_at = at
                if item.get("parts"):
                    message.segments = item["parts"]
            if new == MessageStatus.DELIVERED:
                message.delivered_at = at
                message.sent_at = message.sent_at or at
            if new == MessageStatus.FAILED:
                message.error_code = item.get("error_code")
                message.error_detail = reason_for(item.get("error_code"))[:200]
            if new == MessageStatus.UNKNOWN:
                message.error_detail = "The phone restarted while sending. Check with the customer before resending."
            message.save()
            touched.add(message.conversation_id)
            results.append({"client_uuid": str(item["client_uuid"]), "result": "ok", "status": new})
            if new in (MessageStatus.FAILED, MessageStatus.UNKNOWN):
                log.info("sms %s on %s: %s (code %s)", message.pk, device.code, new, item.get("error_code"))
    for conversation_id in touched:
        store.refresh_conversation(conversation_id)
    return {"results": results}


def ack_commands(device: Device, acks: list[dict]) -> None:
    for ack in acks:
        DeviceCommand.objects.filter(device=device, pk=ack["id"]).exclude(status=DeviceCommand.DONE).update(
            status=DeviceCommand.DONE if ack.get("ok", True) else DeviceCommand.FAILED, done_at=timezone.now(),
        )


# --- Housekeeping ----------------------------------------------------------------------------------------------


def expire_stale(now=None) -> dict:
    now = now or timezone.now()
    cutoff = now - timedelta(hours=settings.SMS_OUTBOUND_TTL_HOURS)
    counts = {"expired": 0, "unknown": 0}
    stale = Message.objects.filter(origin__in=SERVER_ORIGINS, send_at__lt=cutoff).filter(
        Q(status=MessageStatus.QUEUED) | Q(status=MessageStatus.DISPATCHED, lease_expires_at__lt=now)
    )
    stuck = Message.objects.filter(origin__in=SERVER_ORIGINS, status=MessageStatus.SENDING, dispatched_at__lt=cutoff)
    touched = set()
    for qs, new, key in ((stale, MessageStatus.EXPIRED, "expired"), (stuck, MessageStatus.UNKNOWN, "unknown")):
        for message in qs.select_related("device")[:500]:
            message.set_status(new, now)
            message.error_detail = (
                f"Not sent: the phone was offline for more than {settings.SMS_OUTBOUND_TTL_HOURS} hours." if new == MessageStatus.EXPIRED
                else "The phone never reported a result. Check with the customer before resending."
            )
            message.lease_expires_at = None
            message.save(update_fields=["status", "status_history", "error_detail", "lease_expires_at"])
            record(f"sms.{key}", target_type="sms_message", target_id=message.pk, metadata={"device": message.device.code, "sent_by": message.sent_by_id})
            touched.add(message.conversation_id)
            counts[key] += 1
    for conversation_id in touched:
        store.refresh_conversation(conversation_id)
    return counts


def dispatch_due(now=None) -> int:
    """Wake phones whose scheduled or undo-window messages just became due (at most once a minute per phone)."""
    from modules.devices.tasks import push_task

    now = now or timezone.now()
    device_ids = set(Message.objects.filter(origin__in=SERVER_ORIGINS, status=MessageStatus.QUEUED, send_at__lte=now, send_at__gt=now - timedelta(minutes=10)).values_list("device_id", flat=True).distinct())
    woken = 0
    for device_id in device_ids:
        if cache.add(f"sms:dispatch-woken:{device_id}", 1, 60):
            push_task.delay(str(device_id), "outbox")
            woken += 1
    return woken
