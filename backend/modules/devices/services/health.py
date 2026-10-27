"""Heartbeats, online state and "needs attention" alerts.

The phone sends a heartbeat every 5 minutes while its service runs and on every connectivity change. A device is
online while its last heartbeat (or any authenticated request) is younger than two heartbeat intervals.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from ..models import Device, DeviceHeartbeat, DeviceStatus
from .versions import is_supported

HEARTBEAT_SECONDS = 300
ONLINE_WINDOW = timedelta(seconds=HEARTBEAT_SECONDS * 2)
BACKLOG_THRESHOLD = 50
REQUIRED_PERMISSIONS = ("RECEIVE_SMS", "READ_SMS", "SEND_SMS", "RECEIVE_MMS", "READ_CONTACTS", "READ_PHONE_STATE", "POST_NOTIFICATIONS")

ATTENTION_LABELS = {
    "offline": "Offline",
    "not_default_sms_app": "No longer the default SMS app",
    "permission_revoked": "A permission was revoked",
    "battery_optimised": "Battery optimisation is on",
    "outbox_backlog": "Upload backlog",
    "app_outdated": "App needs an update",
    "suspended": "Suspended",
    "risk_signals": "Rooted or emulated phone",
}


def is_online(device: Device, now=None) -> bool:
    now = now or timezone.now()
    return bool(device.last_seen_at and device.last_seen_at >= now - ONLINE_WINDOW)


def attention_for(device: Device, now=None) -> list[str]:
    codes = []
    if device.status == DeviceStatus.SUSPENDED:
        codes.append("suspended")
    if device.status != DeviceStatus.ACTIVE:
        return codes
    if not is_online(device, now):
        codes.append("offline")
    if not device.is_default_sms_app and not device.is_simulated:
        codes.append("not_default_sms_app")
    if device.permissions and any(device.permissions.get(name) is False for name in REQUIRED_PERMISSIONS):
        codes.append("permission_revoked")
    if device.battery_optimised:
        codes.append("battery_optimised")
    if device.pending_outbox >= BACKLOG_THRESHOLD:
        codes.append("outbox_backlog")
    if device.app_version and not is_supported(device.app_version):
        codes.append("app_outdated")
    if any(device.risk_signals.get(name) for name in ("rooted", "emulator")) and not device.is_simulated:
        codes.append("risk_signals")
    return codes


def touch(device: Device) -> None:
    """Any authenticated request proves the phone is reachable."""
    now = timezone.now()
    if not device.last_seen_at or now - device.last_seen_at > timedelta(seconds=30):
        Device.objects.filter(pk=device.pk).update(last_seen_at=now)
        device.last_seen_at = now


def record_heartbeat(device: Device, data: dict) -> Device:
    from .enrollment import save_sims

    now = timezone.now()
    device.last_seen_at = now
    device.battery = data.get("battery")
    device.charging = bool(data.get("charging"))
    device.network_type = str(data.get("network_type") or "")[:16]
    device.signal = data.get("signal")
    device.is_default_sms_app = bool(data.get("is_default_sms_app"))
    device.permissions = {str(k)[:64]: bool(v) for k, v in (data.get("permissions") or {}).items()}
    device.battery_optimised = bool(data.get("battery_optimised"))
    device.pending_outbox = int(data.get("pending_outbox") or 0)
    if data.get("app_version"):
        device.app_version = str(data["app_version"])[:32]
    if data.get("android_version"):
        device.android_version = str(data["android_version"])[:20]
    if data.get("last_sync_at"):
        device.last_sync_at = data["last_sync_at"]
    device.risk_signals = {str(k)[:32]: bool(v) for k, v in (data.get("risk_signals") or {}).items()}
    device.attention = attention_for(device, now)
    device.save()
    if data.get("sims") is not None:
        save_sims(device, data["sims"])
    DeviceHeartbeat.objects.create(
        device=device, created_at=now, battery=device.battery, charging=device.charging, network_type=device.network_type,
        signal=device.signal, is_default_sms_app=device.is_default_sms_app, pending_outbox=device.pending_outbox, app_version=device.app_version,
    )
    return device


def refresh_all() -> int:
    """Recompute alerts (a phone goes offline by *not* sending anything). Runs every minute."""
    now = timezone.now()
    changed = 0
    for device in Device.objects.exclude(status=DeviceStatus.REVOKED).iterator():
        codes = attention_for(device, now)
        if codes != device.attention:
            Device.objects.filter(pk=device.pk).update(attention=codes)
            changed += 1
    return changed


def prune(now=None) -> dict:
    from ..models import DeviceCommand, DeviceToken, EnrollmentInvite

    now = now or timezone.now()
    return {
        "heartbeats": DeviceHeartbeat.objects.filter(created_at__lt=now - timedelta(days=14)).delete()[0],
        "tokens": DeviceToken.objects.filter(expires_at__lt=now).delete()[0],
        "invites": EnrollmentInvite.objects.filter(expires_at__lt=now - timedelta(days=30), used_at__isnull=True).delete()[0],
        "commands": DeviceCommand.objects.filter(status__in=[DeviceCommand.DONE, DeviceCommand.FAILED], created_at__lt=now - timedelta(days=7)).delete()[0],
    }
