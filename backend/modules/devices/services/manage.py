"""Admin actions on enrolled phones: options, suspend, resume, revoke, resync, SIM names. Every one is audited."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from modules.audit.services import record

from ..models import Device, DeviceCommand, DeviceStatus, DeviceToken, SimLine
from .enrollment import clean_options
from .health import attention_for


def queue_command(device: Device, kind: str, payload: dict | None = None, user=None) -> DeviceCommand:
    from ..tasks import push_task

    command = DeviceCommand.objects.create(device=device, kind=kind, payload=payload or {}, created_by=user)
    transaction.on_commit(lambda: push_task.delay(str(device.pk), "command"))
    return command


def update(device: Device, user, values: dict, request=None) -> Device:
    changes = {}
    for key in ("name", "office", "assigned_to"):
        if key in values and getattr(device, key) != values[key]:
            setattr(device, key, values[key])
            changes[key] = str(getattr(values[key], "pk", values[key]) or "")
    if "options" in values:
        options = clean_options({**device.options, **values["options"]})
        if options != device.options:
            changes["options"] = {k: v for k, v in options.items() if device.options.get(k) != v and k != "signature"}
            if options.get("signature") != device.options.get("signature"):
                changes["options"]["signature"] = "changed"
            device.options = options
    if changes:
        device.save(update_fields=list(changes))
        record("device.update", request=request, actor=user, target_type="device", target_id=device.pk, metadata={"device": device.code, "changes": changes})
    return device


def _set_status(device: Device, user, status: str, action: str, request=None, reason: str = "") -> Device:
    now = timezone.now()
    with transaction.atomic():
        device = Device.objects.select_for_update().get(pk=device.pk)
        device.status = status
        if status == DeviceStatus.SUSPENDED:
            device.suspended_at = now
        elif status == DeviceStatus.ACTIVE:
            device.suspended_at = None
        elif status == DeviceStatus.REVOKED:
            device.revoked_at = now
            device.push_token = ""
        device.attention = attention_for(device, now)
        device.save()
        if status == DeviceStatus.REVOKED:
            DeviceToken.objects.filter(device=device, expires_at__lt=now).delete()
        # Live tokens are kept on purpose: every request re-checks the device status (services/auth.authenticate), so
        # outstanding tokens stop working at once and the phone is told why (device_suspended / device_revoked).
        # That check is only sound because nothing else writes `status` from a stale copy (save(update_fields=...)).
        record(action, request=request, actor=user, target_type="device", target_id=device.pk, metadata={"device": device.code, "reason": reason[:200]})
    return device


def suspend(device: Device, user, request=None, reason: str = "") -> Device:
    return _set_status(device, user, DeviceStatus.SUSPENDED, "device.suspend", request, reason)


def resume(device: Device, user, request=None) -> Device:
    return _set_status(device, user, DeviceStatus.ACTIVE, "device.resume", request)


def revoke(device: Device, user, request=None, reason: str = "") -> Device:
    """Permanent: the phone wipes its credentials, key and sync database at its next request. Server data stays."""
    return _set_status(device, user, DeviceStatus.REVOKED, "device.revoke", request, reason)


def request_resync(device: Device, user, request=None) -> DeviceCommand:
    record("device.resync_request", request=request, actor=user, target_type="device", target_id=device.pk, metadata={"device": device.code})
    return queue_command(device, "resync", {"days": device.options.get("backfill_days")}, user)


def rename_sim(line: SimLine, user, *, display_name: str | None = None, colour: str | None = None, request=None) -> SimLine:
    if display_name is not None:
        line.display_name = display_name.strip()[:60]
    if colour:
        line.colour = colour
    line.save()
    record("device.sim_update", request=request, actor=user, target_type="device", target_id=line.device_id, metadata={"sim": line.subscription_id, "display_name": line.display_name})
    return line
