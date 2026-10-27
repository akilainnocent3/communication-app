"""Object-level phone permissions. Every SMS endpoint goes through these helpers.

Users with `sms.access_all_devices` (Admin role, super admins) can do everything on every phone. Everyone else
needs a `DeviceAccess` row; its flags decide read / send / manage / reveal sensitive. A phone (or anything on it)
the user cannot read answers 404, so its existence is not revealed. A disabled SMS platform refuses everything.
"""

from __future__ import annotations

from django.db.models import Q, QuerySet, Sum
from rest_framework import status

from common.errors import ApiError
from modules.devices.models import Device, DeviceStatus
from modules.platforms.services import is_platform_enabled

from ..models import Conversation, DeviceAccess, Message

READ, SEND, MANAGE, REVEAL = "read", "send", "manage", "reveal"
FLAGS = {READ: "can_read", SEND: "can_send", MANAGE: "can_manage", REVEAL: "can_reveal_sensitive"}
PERM_MESSAGES = {
    READ: "You don't have permission to read this phone's messages.",
    SEND: "You don't have permission to send from this phone.",
    MANAGE: "You don't have permission to manage this phone.",
    REVEAL: "You don't have permission to reveal sensitive messages on this phone.",
}


def is_sms_admin(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_superuser or user.has_perm("sms.access_all_devices")))


def can_use_sms(user) -> bool:
    return bool(user and user.is_authenticated and user.has_perm("sms.access") and is_platform_enabled("sms"))


def accessible_devices(user, perm: str = READ) -> QuerySet[Device]:
    """Phones the user may see. Revoked phones stay readable (their history is kept) but never accept sends."""
    if not can_use_sms(user):
        return Device.objects.none()
    qs = Device.objects.select_related("office", "assigned_to")
    if is_sms_admin(user):
        return qs
    return qs.filter(sms_access__user=user, **{f"sms_access__{FLAGS[perm]}": True}).distinct()


def permissions_for(user, device: Device) -> dict[str, bool]:
    if not can_use_sms(user):
        return {key: False for key in FLAGS}
    if is_sms_admin(user):
        return {key: True for key in FLAGS}
    row = DeviceAccess.objects.filter(user=user, device=device).first()
    return {key: bool(row and getattr(row, flag)) for key, flag in FLAGS.items()}


def get_device(user, device_id, perm: str = READ) -> Device:
    device = accessible_devices(user, READ).filter(pk=_uuid(device_id)).first() if _uuid(device_id) else None
    if not device:
        raise ApiError("not_found", "This phone was not found.", status.HTTP_404_NOT_FOUND)
    if perm != READ and not permissions_for(user, device)[perm]:
        raise ApiError("permission_denied", PERM_MESSAGES[perm], status.HTTP_403_FORBIDDEN)
    return device


def _uuid(value):
    import uuid

    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def accessible_conversations(user) -> QuerySet[Conversation]:
    return Conversation.objects.filter(device__in=accessible_devices(user, READ).values("pk"))


def get_conversation(user, conversation_id, perm: str = READ) -> Conversation:
    try:
        conversation_id = int(conversation_id)
    except (TypeError, ValueError):
        conversation_id = 0
    conversation = accessible_conversations(user).select_related("device", "device__office", "assigned_to", "sim_line").filter(pk=conversation_id).first()
    if not conversation:
        raise ApiError("not_found", "This conversation was not found.", status.HTTP_404_NOT_FOUND)
    if perm != READ and not permissions_for(user, conversation.device)[perm]:
        raise ApiError("permission_denied", PERM_MESSAGES[perm], status.HTTP_403_FORBIDDEN)
    return conversation


def get_conversations(user, ids: list[int], perm: str = READ) -> list[Conversation]:
    """Any id the user cannot see makes the whole request fail (no partial leaks)."""
    wanted = {int(i) for i in ids}
    rows = list(accessible_conversations(user).filter(pk__in=wanted).select_related("device"))
    if len(rows) != len(wanted):
        raise ApiError("not_found", "Some conversations were not found. Refresh and try again.", status.HTTP_404_NOT_FOUND)
    if perm != READ:
        for device in {row.device for row in rows}:
            if not permissions_for(user, device)[perm]:
                raise ApiError("permission_denied", PERM_MESSAGES[perm], status.HTTP_403_FORBIDDEN)
    return rows


def get_message(user, message_id, perm: str = READ) -> Message:
    try:
        message_id = int(message_id)
    except (TypeError, ValueError):
        message_id = 0
    message = Message.objects.select_related("device", "conversation", "sent_by", "sim_line").filter(pk=message_id, device__in=accessible_devices(user, READ).values("pk")).first()
    if not message:
        raise ApiError("not_found", "This message was not found.", status.HTTP_404_NOT_FOUND)
    if perm != READ and not permissions_for(user, message.device)[perm]:
        raise ApiError("permission_denied", PERM_MESSAGES[perm], status.HTTP_403_FORBIDDEN)
    return message


def require_sendable(device: Device) -> None:
    if device.status != DeviceStatus.ACTIVE:
        raise ApiError("device_inactive", "This phone is suspended or removed, so it cannot send messages.", status.HTTP_409_CONFLICT)


def device_summaries(user) -> list[dict]:
    """Small phone list for the switcher, with unread counts and health."""
    from modules.devices.services.health import is_online

    devices = accessible_devices(user).exclude(status=DeviceStatus.REVOKED).annotate(
        unread=Sum("sms_conversations__unread_count", filter=Q(sms_conversations__is_archived=False, sms_conversations__is_spam=False))
    ).prefetch_related("sim_lines")
    admin = is_sms_admin(user)
    rows = {row.device_id: row for row in DeviceAccess.objects.filter(user=user)} if not admin else {}
    result = []
    for device in devices:
        if admin:
            perms = {key: True for key in FLAGS}
        else:
            row = rows.get(device.pk)
            perms = {key: bool(row and getattr(row, flag)) for key, flag in FLAGS.items()}
        result.append({
            "id": str(device.pk), "code": device.code, "name": device.name,
            "office": {"id": device.office_id, "name": device.office.name, "colour": device.office.colour},
            "status": device.status, "online": is_online(device), "last_seen_at": device.last_seen_at,
            "attention": list(device.attention or []), "unread": device.unread or 0, "permissions": perms,
            "sims": [{"id": s.pk, "label": s.label, "slot": s.slot, "colour": s.colour} for s in device.sim_lines.all() if s.is_active],
        })
    return result
