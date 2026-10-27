"""Conversation actions (one or many conversations at once). Each action is validated against the phone access
flags of every selected conversation; a selection with any inaccessible conversation fails entirely.

Undo is the inverse action (read ↔ unread, archive ↔ unarchive …), which the UI offers in its toast.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status

from common.errors import ApiError
from modules.audit.services import record
from modules.devices.services.manage import queue_command

from ..models import Contact, Conversation, Message
from . import access, store

ACTIONS = {
    # action: (required flag, field changes, audit?)
    "read": (access.READ, None, False),
    "unread": (access.READ, None, False),
    "pin": (access.SEND, {"is_pinned": True}, False),
    "unpin": (access.SEND, {"is_pinned": False}, False),
    "star": (access.READ, {"is_starred": True}, False),
    "unstar": (access.READ, {"is_starred": False}, False),
    "archive": (access.SEND, {"is_archived": True}, False),
    "unarchive": (access.SEND, {"is_archived": False}, False),
    "mute": (access.SEND, {"is_muted": True}, False),
    "unmute": (access.SEND, {"is_muted": False}, False),
    "spam": (access.SEND, {"is_spam": True}, True),
    "not_spam": (access.SEND, {"is_spam": False}, True),
    "done": (access.SEND, {"state": Conversation.DONE}, False),
    "reopen": (access.SEND, {"state": Conversation.OPEN}, False),
    "assign": (access.SEND, None, True),
    "unassign": (access.SEND, {"assigned_to": None}, True),
    "block": (access.MANAGE, None, True),
    "unblock": (access.MANAGE, None, True),
}


def perform(user, action: str, ids: list[int], *, assignee_id: int | None = None, request=None) -> list[Conversation]:
    if action not in ACTIONS:
        raise ApiError("validation_error", "Unknown action.")
    if not ids:
        return []
    if len(ids) > 500:
        raise ApiError("validation_error", "Select at most 500 conversations.")
    flag, changes, audited = ACTIONS[action]
    conversations = access.get_conversations(user, ids, flag)
    with transaction.atomic():
        if action in ("read", "unread"):
            _set_read(user, conversations, action == "read")
        elif action == "assign":
            assignee = get_user_model().objects.filter(pk=assignee_id, is_active=True).first()
            if not assignee:
                raise ApiError("validation_error", "Choose someone to assign to.")
            for conversation in conversations:
                if not access.permissions_for(assignee, conversation.device)["read"]:
                    raise ApiError("permission_denied", f"{assignee.display_name} cannot open this phone's messages.", status.HTTP_403_FORBIDDEN)
            Conversation.objects.filter(pk__in=[c.pk for c in conversations]).update(assigned_to=assignee, state=Conversation.OPEN)
        elif action in ("block", "unblock"):
            for conversation in conversations:
                for address in conversation.addresses:
                    store.set_blocked(conversation.device, address, action == "block")
                    queue_command(conversation.device, "block" if action == "block" else "unblock", {"address": address}, user)
            Conversation.objects.filter(pk__in=[c.pk for c in conversations]).update(is_spam=action == "block")
        else:
            Conversation.objects.filter(pk__in=[c.pk for c in conversations]).update(**changes)
        if audited:
            for conversation in conversations:
                record(f"sms.conversation_{action}", request=request, actor=user, target_type="sms_conversation", target_id=conversation.pk,
                       metadata={"device": conversation.device.code, **({"assignee": assignee_id} if action == "assign" else {})})
    return list(Conversation.objects.filter(pk__in=[c.pk for c in conversations]))


def _set_read(user, conversations: list[Conversation], read: bool) -> None:
    for conversation in conversations:
        if read:
            conversation.messages.filter(direction=Message.IN, is_read=False).update(is_read=True)
            mark_read_on_phone(conversation, user)
        else:
            latest = conversation.messages.filter(direction=Message.IN).order_by("-provider_date").first()
            if latest:
                Message.objects.filter(pk=latest.pk).update(is_read=False)
        store.refresh_conversation(conversation.pk)


def mark_read_on_phone(conversation: Conversation, user=None) -> None:
    """Ask the phone to mark the thread read too, when the phone's "mark read on open" option is on."""
    if (conversation.device.options or {}).get("mark_read_on_open", True) and conversation.thread_id:
        queue_command(conversation.device, "mark_read", {"thread_id": conversation.thread_id}, user)


def blocked_contacts(user, device_id=None):
    devices = access.accessible_devices(user)
    if device_id:
        devices = devices.filter(pk=access.get_device(user, device_id).pk)
    return Contact.objects.filter(device__in=devices, is_blocked=True).select_related("device")
