"""Server → phone wake-ups through Firebase Cloud Messaging (HTTP v1).

Messages are high-priority and data-only, and carry no message content: `{"type": "sync" | "outbox", "device": id}`.
The phone then pulls over authenticated HTTPS. FCM is optional; without `FCM_*` settings the phone's foreground
service polls every `SMS_DEVICE_POLL_SECONDS` and WorkManager syncs periodically.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from django.conf import settings
from django.core.cache import cache

from ..models import Device

log = logging.getLogger(__name__)

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
KINDS = ("sync", "outbox", "command")


def configured() -> bool:
    return bool(settings.FCM_PROJECT_ID and settings.FCM_SERVICE_ACCOUNT_FILE)


@lru_cache(maxsize=1)
def _session(path: str):  # pragma: no cover - needs real credentials
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    return AuthorizedSession(service_account.Credentials.from_service_account_file(path, scopes=[SCOPE]))


def send(token: str, data: dict) -> tuple[int, dict]:  # pragma: no cover - network call, mocked in tests
    url = f"https://fcm.googleapis.com/v1/projects/{settings.FCM_PROJECT_ID}/messages:send"
    body = {"message": {"token": token, "data": {k: str(v) for k, v in data.items()}, "android": {"priority": "HIGH", "ttl": "300s"}}}
    response = _session(settings.FCM_SERVICE_ACCOUNT_FILE).post(url, json=body, timeout=10)
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    return response.status_code, payload


def wake(device_id, kind: str = "sync") -> bool:
    """Best effort. Coalesces wake-ups (one per device and kind every 2 s) and forgets dead registrations."""
    if kind not in KINDS or not configured():
        return False
    device = Device.objects.filter(pk=device_id).only("pk", "push_token", "status", "code").first()
    if not device or not device.push_token or device.status != "active":
        return False
    if not cache.add(f"devices:push:{device.pk}:{kind}", 1, 2):
        return True
    try:
        status, payload = send(device.push_token, {"type": kind, "device": str(device.pk)})
    except Exception as exc:  # noqa: BLE001 - a push failure must never break the caller
        log.warning("push to %s failed: %s", device.code, type(exc).__name__)
        return False
    if status == 404 or "UNREGISTERED" in str(payload):
        Device.objects.filter(pk=device.pk).update(push_token="")
        log.info("push token for %s is no longer registered; cleared", device.code)
        return False
    if status >= 400:
        log.warning("push to %s answered HTTP %s", device.code, status)
        return False
    return True
