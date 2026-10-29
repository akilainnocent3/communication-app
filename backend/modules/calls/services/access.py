"""Object-level phone permissions for Calls. Every Calls endpoint goes through these helpers.

Users with `calls.access_all_devices` (Admin role, super admins) can do everything on every Calls phone. Everyone else
needs a `calls.DeviceAccess` row; its flags decide read / assign callbacks / annotate / export. Only phones enabled for
Calls (`Device.capabilities["calls"]`) are part of the platform. A phone (or a call on it) the user cannot read answers
404, so its existence is not revealed. A disabled Calls platform refuses everything.
"""

from __future__ import annotations

import uuid

from django.db.models import Q, QuerySet
from rest_framework import status

from common.errors import ApiError
from modules.devices.models import Device, DeviceStatus
from modules.platforms.services import is_platform_enabled

from ..models import CallbackTask, CallRecord, DeviceAccess

READ, ASSIGN, ANNOTATE, EXPORT = "read", "assign", "annotate", "export"
FLAGS = {READ: "can_read", ASSIGN: "can_assign_callbacks", ANNOTATE: "can_annotate", EXPORT: "can_export"}
PERM_MESSAGES = {
    READ: "You don't have permission to see this phone's calls.",
    ASSIGN: "You don't have permission to assign call-backs on this phone.",
    ANNOTATE: "You don't have permission to add notes to this phone's calls.",
    EXPORT: "You don't have permission to export this phone's calls.",
}


def is_calls_admin(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_superuser or user.has_perm("calls.access_all_devices")))


def can_use_calls(user) -> bool:
    return bool(user and user.is_authenticated and user.has_perm("calls.access") and is_platform_enabled("calls"))


def calls_devices() -> QuerySet[Device]:
    """OCM Phone devices (also when Calls is switched off for one: its history stays readable), plus older phones that
    reported calls before Calls became its own app."""
    return Device.objects.filter(Q(app="calls") | Q(capabilities__calls=True))


def accessible_devices(user, perm: str = READ) -> QuerySet[Device]:
    """Calls phones the user may see. Revoked phones stay readable (history is kept)."""
    if not can_use_calls(user):
        return Device.objects.none()
    qs = calls_devices().select_related("office", "assigned_to")
    if is_calls_admin(user):
        return qs
    return qs.filter(calls_access__user=user, **{f"calls_access__{FLAGS[perm]}": True}).distinct()


def devices_with(user, perm: str) -> QuerySet[Device]:
    return accessible_devices(user, perm)


def permissions_for(user, device: Device) -> dict[str, bool]:
    if not can_use_calls(user) or not device.has("calls"):
        return {key: False for key in FLAGS}
    if is_calls_admin(user):
        return {key: True for key in FLAGS}
    row = DeviceAccess.objects.filter(user=user, device=device).first()
    return {key: bool(row and row.can_read and getattr(row, flag)) for key, flag in FLAGS.items()}


def _uuid(value):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def get_device(user, device_id, perm: str = READ) -> Device:
    pk = _uuid(device_id)
    device = accessible_devices(user, READ).filter(pk=pk).first() if pk else None
    if not device:
        raise ApiError("not_found", "This phone was not found.", status.HTTP_404_NOT_FOUND)
    if perm != READ and not permissions_for(user, device)[perm]:
        raise ApiError("permission_denied", PERM_MESSAGES[perm], status.HTTP_403_FORBIDDEN)
    return device


def accessible_calls(user) -> QuerySet[CallRecord]:
    return CallRecord.objects.filter(device__in=accessible_devices(user, READ).values("pk"))


def get_call(user, call_id, perm: str = READ) -> CallRecord:
    try:
        call_id = int(call_id)
    except (TypeError, ValueError):
        call_id = 0
    call = accessible_calls(user).select_related("device", "device__office", "sim_line", "customer").filter(pk=call_id).first()
    if not call:
        raise ApiError("not_found", "This call was not found.", status.HTTP_404_NOT_FOUND)
    if perm != READ and not permissions_for(user, call.device)[perm]:
        raise ApiError("permission_denied", PERM_MESSAGES[perm], status.HTTP_403_FORBIDDEN)
    return call


def accessible_callbacks(user) -> QuerySet[CallbackTask]:
    return CallbackTask.objects.filter(device__in=accessible_devices(user, READ).values("pk"))


def get_callback(user, task_id, perm: str = READ) -> CallbackTask:
    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        task_id = 0
    task = accessible_callbacks(user).select_related("device", "customer", "assigned_by", "assignee").filter(pk=task_id).first()
    if not task:
        raise ApiError("not_found", "This call-back was not found.", status.HTTP_404_NOT_FOUND)
    if perm != READ and not permissions_for(user, task.device)[perm]:
        raise ApiError("permission_denied", PERM_MESSAGES[perm], status.HTTP_403_FORBIDDEN)
    return task


def device_summaries(user) -> list[dict]:
    """Small phone list for the Calls switcher, with live call state and health."""
    from modules.devices.services.health import is_online

    devices = accessible_devices(user).exclude(status=DeviceStatus.REVOKED).prefetch_related("sim_lines")
    admin = is_calls_admin(user)
    rows = {row.device_id: row for row in DeviceAccess.objects.filter(user=user)} if not admin else {}
    result = []
    for device in devices:
        if admin:
            perms = {key: True for key in FLAGS}
        else:
            row = rows.get(device.pk)
            perms = {key: bool(row and row.can_read and getattr(row, flag)) for key, flag in FLAGS.items()}
        result.append({
            "id": str(device.pk), "code": device.code, "name": device.name,
            "office": {"id": device.office_id, "name": device.office.name, "colour": device.office.colour},
            "status": device.status, "online": is_online(device), "last_seen_at": device.last_seen_at,
            "attention": list(device.attention or []), "call_state": device.call_state or "idle", "permissions": perms,
            "sims": [{"id": s.pk, "label": s.label, "slot": s.slot, "colour": s.colour} for s in device.sim_lines.all() if s.is_active],
        })
    return result
