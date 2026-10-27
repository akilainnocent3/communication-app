"""Apply what a phone reports to the local copy: messages, read state, deletions, contacts and blocks.

Everything here is idempotent. A message is identified by (device, kind, provider _id, provider date), or by its
`client_uuid` when it was sent from the admin. Conversations are keyed by the phone and the sorted address keys of
their participants, so a device can only ever touch its own data.
"""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from modules.devices.models import Device, SimLine
from modules.devices.services.phone import address_key

from ..models import Contact, Conversation, Message, MessagePart, MessageStatus
from .crypto import decrypt_text, encrypt_text
from .text import detect_sensitive, mask_sensitive, segment_info, snippet

# Progress order of an outbound message. Terminal states (failed, expired, cancelled) are handled separately.
RANK = {
    MessageStatus.QUEUED: 0, MessageStatus.DISPATCHED: 1, MessageStatus.SENDING: 2, MessageStatus.UNKNOWN: 2,
    MessageStatus.SENT: 3, MessageStatus.FAILED: 3, MessageStatus.DELIVERED: 4,
}
PHONE_STATUSES = {"received", "queued", "sending", "sent", "delivered", "failed"}


class EventRejected(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def from_millis(value: int) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=dt_timezone.utc)


def region_for(device: Device, sim: SimLine | None) -> str:
    return (sim.country_iso if sim and sim.country_iso else settings.SMS_DEFAULT_REGION).upper()


def participants(device: Device, addresses: list[str], sim: SimLine | None = None) -> list[str]:
    region = region_for(device, sim)
    keys = sorted({address_key(raw, region) for raw in addresses if (raw or "").strip()})
    return [key for key in keys if key][:20]


def conversation_for(device: Device, keys: list[str], *, thread_id: int | None = None, at: datetime | None = None) -> Conversation:
    if not keys:
        raise EventRejected("no_addresses")
    participants_key = ",".join(keys)[:700]
    conversation, created = Conversation.objects.get_or_create(
        device=device, participants_key=participants_key,
        defaults={"addresses": keys, "is_group": len(keys) > 1, "last_message_at": at or timezone.now(), "thread_id": thread_id, "first_message_at": at},
    )
    if thread_id and conversation.thread_id != thread_id:
        Conversation.objects.filter(pk=conversation.pk).update(thread_id=thread_id)
        conversation.thread_id = thread_id
    if created:
        Contact.objects.bulk_create([Contact(device=device, address=key) for key in keys], ignore_conflicts=True)
    return conversation


def can_advance(current: str, new: str) -> bool:
    """Outbound status only moves forward; a late "sent" never hides "delivered". Unknown may be resolved later."""
    if current == new:
        return False
    if current == MessageStatus.CANCELLED:
        return False
    if current == MessageStatus.EXPIRED:
        return new in (MessageStatus.SENDING, MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.FAILED)  # the phone knows best
    if current == MessageStatus.DELIVERED:
        return False
    if current == MessageStatus.FAILED:
        return new == MessageStatus.DELIVERED
    return RANK.get(new, -1) >= RANK.get(current, 0)


def _sim(device: Device, sub_id) -> SimLine | None:
    if sub_id in (None, "", -1):
        return None
    return SimLine.objects.filter(device=device, subscription_id=sub_id).first()


def upsert_message(device: Device, data: dict) -> tuple[Message, bool, int]:
    """Create or update one message from a phone event. Returns (message, created, conversation id to refresh)."""
    sim = _sim(device, data.get("sub_id"))
    keys = participants(device, data["addresses"], sim)
    date = from_millis(data["date"])
    body = data.get("body") or ""
    direction = data["direction"]

    message = None
    if data.get("client_uuid"):
        message = Message.objects.filter(client_uuid=data["client_uuid"]).select_related("conversation").first()
        if message and message.device_id != device.pk:
            raise EventRejected("foreign_message")
    if message is None:
        message = Message.objects.filter(device=device, kind=data["kind"], provider_id=data["provider_id"], provider_date=date).select_related("conversation").first()

    created = message is None
    if created:
        conversation = conversation_for(device, keys, thread_id=data.get("thread_id"), at=date)
        info = segment_info(body)
        sender = data["addresses"][0] if data["addresses"] else ""
        sensitive = detect_sensitive(sender, body) if direction == Message.IN else ""
        status = data.get("status") or ("received" if direction == Message.IN else "sent")
        message = Message(
            device=device, conversation=conversation, sim_line=sim, kind=data["kind"], direction=direction,
            address=keys[0], addresses=[a[:64] for a in data["addresses"]][:20], encrypted_body=encrypt_text(body), body_length=len(body),
            segments=info.segments, encoding=info.encoding, subject=(data.get("subject") or "")[:200], provider_id=data["provider_id"],
            provider_date=date, is_read=bool(data.get("is_read", direction == Message.OUT)), origin=Message.ORIGIN_PHONE,
            is_sensitive=bool(sensitive), sensitive_kind=sensitive, is_starred=bool(data.get("starred")), error_code=data.get("error_code"),
        )
        message.set_status(status if direction == Message.OUT else MessageStatus.RECEIVED, date)
        if status == MessageStatus.SENT:
            message.sent_at = date
        message.save()
        if direction == Message.IN:
            # Like Google Messages: a new incoming message brings an archived or "done" conversation back.
            Conversation.objects.filter(pk=conversation.pk).filter(Q(is_archived=True) | Q(state=Conversation.DONE)).update(is_archived=False, state=Conversation.OPEN)
    else:
        fields = []
        if message.provider_id is None and data.get("provider_id") is not None:
            # An admin message the phone has now written to its message store.
            message.provider_id, message.provider_date = data["provider_id"], date
            fields += ["provider_id", "provider_date"]
            if data.get("thread_id") and message.conversation.thread_id != data["thread_id"]:
                Conversation.objects.filter(pk=message.conversation_id).update(thread_id=data["thread_id"])
        if sim and message.sim_line_id != sim.pk:
            message.sim_line = sim
            fields.append("sim_line")
        if "is_read" in data and message.direction == Message.IN and message.is_read != bool(data["is_read"]):
            message.is_read = bool(data["is_read"])
            fields.append("is_read")
        if "starred" in data and message.is_starred != bool(data["starred"]):
            message.is_starred = bool(data["starred"])
            fields.append("is_starred")
        status = data.get("status")
        if message.direction == Message.OUT and status and status in PHONE_STATUSES and can_advance(message.status, status):
            message.set_status(status)
            fields += ["status", "status_history"]
            if status == MessageStatus.SENT and not message.sent_at:
                message.sent_at = timezone.now()
                fields.append("sent_at")
            if status == MessageStatus.DELIVERED and not message.delivered_at:
                message.delivered_at = timezone.now()
                fields.append("delivered_at")
        if fields:
            message.save(update_fields=list(set(fields)))
    if data["kind"] == Message.MMS and data.get("parts"):
        _upsert_parts(message, data["parts"])
    return message, created, message.conversation_id


def _upsert_parts(message: Message, parts: list[dict]) -> None:
    for part in parts:
        MessagePart.objects.get_or_create(
            message=message, seq=part["seq"],
            defaults={"declared_type": part.get("content_type", "")[:100], "filename": (part.get("filename") or "")[:120], "size": part["size"], "sha256": part["sha256"].lower()},
        )


def find_message(device: Device, data: dict) -> Message | None:
    return Message.objects.filter(device=device, kind=data["kind"], provider_id=data["provider_id"], provider_date=from_millis(data["date"])).first()


def delete_message(device: Device, data: dict) -> int | None:
    message = find_message(device, data)
    if not message:
        return None
    conversation_id = message.conversation_id
    if settings.SMS_MIRROR_DEVICE_DELETES:
        from .media import delete_files

        delete_files(message)
        message.delete()
    elif not message.deleted_on_device_at:
        Message.objects.filter(pk=message.pk).update(deleted_on_device_at=timezone.now())
    return conversation_id


def delete_thread(device: Device, thread_id: int) -> int | None:
    conversation = Conversation.objects.filter(device=device, thread_id=thread_id).first()
    if not conversation:
        return None
    now = timezone.now()
    if settings.SMS_MIRROR_DEVICE_DELETES:
        from .media import delete_files

        for message in conversation.messages.all():
            delete_files(message)
        conversation.messages.all().delete()
    else:
        conversation.messages.filter(deleted_on_device_at__isnull=True).update(deleted_on_device_at=now)
    Conversation.objects.filter(pk=conversation.pk).update(deleted_on_device_at=now)
    return conversation.pk


def set_read(device: Device, data: dict) -> int | None:
    message = find_message(device, data)
    if not message or message.direction != Message.IN:
        return None
    if message.is_read != bool(data["is_read"]):
        Message.objects.filter(pk=message.pk).update(is_read=bool(data["is_read"]))
    return message.conversation_id


def set_thread_read(device: Device, thread_id: int) -> int | None:
    conversation = Conversation.objects.filter(device=device, thread_id=thread_id).first()
    if not conversation:
        return None
    conversation.messages.filter(direction=Message.IN, is_read=False).update(is_read=True)
    return conversation.pk


def upsert_contact(device: Device, data: dict) -> bool:
    """Only for numbers already in this phone's conversations (data minimisation): unknown numbers are ignored."""
    key = address_key(data["address"])
    updated = Contact.objects.filter(device=device, address=key).update(display_name=(data.get("display_name") or "")[:120], photo_hash=(data.get("photo_hash") or "")[:64])
    return bool(updated)


def set_blocked(device: Device, address: str, blocked: bool) -> None:
    key = address_key(address)
    contact, _ = Contact.objects.get_or_create(device=device, address=key)
    if contact.is_blocked != blocked:
        contact.is_blocked = blocked
        contact.save(update_fields=["is_blocked", "updated_at"])


def refresh_conversation(conversation_id: int) -> None:
    """Recompute the list-row fields of one conversation from its messages (latest first)."""
    conversation = Conversation.objects.filter(pk=conversation_id).first()
    if not conversation:
        return
    visible = conversation.messages.all()
    latest = visible.order_by("-provider_date", "-id").first()
    if latest is None:
        conversation.delete()
        return
    counts = visible.aggregate(
        total=Count("id"), unread=Count("id", filter=Q(direction=Message.IN, is_read=False, deleted_on_device_at__isnull=True)),
        mms=Count("id", filter=Q(kind=Message.MMS)),
    )
    last_in = visible.filter(direction=Message.IN).order_by("-provider_date").values_list("provider_date", flat=True).first()
    last_out = visible.filter(direction=Message.OUT).exclude(status__in=[MessageStatus.CANCELLED]).order_by("-provider_date").values_list("provider_date", flat=True).first()
    first = visible.order_by("provider_date").values_list("provider_date", flat=True).first()
    body = decrypt_text(latest.encrypted_body)
    text = snippet(body) or ("📎 Attachment" if latest.kind == Message.MMS else "")
    conversation.last_message_at = latest.provider_date
    conversation.encrypted_snippet = encrypt_text(mask_sensitive(text) if latest.is_sensitive else text)
    conversation.snippet_sensitive = latest.is_sensitive
    conversation.last_direction = latest.direction
    conversation.last_status = latest.status
    conversation.message_count = counts["total"]
    conversation.unread_count = counts["unread"]
    conversation.has_mms = counts["mms"] > 0
    conversation.first_message_at = first
    conversation.last_inbound_at = last_in
    conversation.last_outbound_at = last_out
    conversation.awaiting_since = last_in if last_in and (not last_out or last_out < last_in) else None
    if latest.sim_line_id:
        conversation.sim_line_id = latest.sim_line_id
    if latest.deleted_on_device_at is None:
        conversation.deleted_on_device_at = None
    conversation.save()
