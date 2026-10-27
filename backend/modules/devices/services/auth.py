"""Device access tokens with proof of possession.

No long-lived bearer secret exists on the phone. To get an access token the phone signs

    CMSMS-AUTH-1 / POST / /api/v1/device/auth/token/ / <device id> / <unix time> / <nonce>

with its Keystore key. The server checks the signature, a ±5 minute clock window and that the nonce was never
seen (cache, 10 minutes), then issues an opaque random token (only the SHA-256 is stored) valid for
`SMS_DEVICE_TOKEN_TTL` minutes.
"""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
import time
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from modules.audit.services import record

from ..models import Device, DeviceStatus, DeviceToken
from .identity import IdentityError, canonical, load_public_key, verify_signature

log = logging.getLogger(__name__)

CLOCK_SKEW_SECONDS = 300
NONCE_TTL_SECONDS = 600
NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
TOKEN_PATH = "/api/v1/device/auth/token/"


class DeviceAuthError(Exception):
    def __init__(self, code: str, message: str, status: int = 401):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def check_clock(timestamp) -> None:
    try:
        value = int(timestamp)
    except (TypeError, ValueError):
        raise IdentityError("bad_timestamp", "The request time is missing.") from None
    if abs(time.time() - value) > CLOCK_SKEW_SECONDS:
        raise IdentityError("clock_skew", "The phone's clock is wrong. Turn on automatic date and time, then try again.")


def use_nonce(scope: str, nonce: str) -> None:
    """Each nonce works once (per scope) within the replay window."""
    if not NONCE_RE.match(nonce or ""):
        raise IdentityError("bad_nonce", "The request nonce is not valid.")
    if not cache.add(f"devices:nonce:{scope}:{nonce}", 1, NONCE_TTL_SECONDS):
        raise IdentityError("replayed_nonce", "This request was already used.")


def issue_token(device: Device) -> tuple[str, int]:
    token = secrets.token_urlsafe(32)
    ttl = settings.SMS_DEVICE_TOKEN_TTL * 60
    DeviceToken.objects.create(device=device, token_hash=hash_token(token), expires_at=timezone.now() + timedelta(seconds=ttl))
    DeviceToken.objects.filter(device=device, expires_at__lt=timezone.now()).delete()
    return token, ttl


def _note_failure(device: Device | None, code: str, request) -> None:
    """Audit failed token requests, at most once per device and reason every 5 minutes (no log flooding)."""
    key = f"devices:authfail:{device.pk if device else 'unknown'}:{code}"
    if cache.add(key, 1, 300):
        record("device.token_failed", request=request, target_type="device", target_id=device.pk if device else "",
               metadata={"reason": code, "device": device.code if device else ""})
    log.info("device token refused: %s (device %s)", code, device.code if device else "-")


def mint(data: dict, request=None) -> tuple[Device, str, int]:
    try:
        device_id = uuid.UUID(str(data.get("device_id")))
    except ValueError:
        raise DeviceAuthError("invalid_device", "This phone is not enrolled.") from None
    device = Device.objects.filter(pk=device_id).first()
    if device is None:
        _note_failure(None, "unknown_device", request)
        raise DeviceAuthError("invalid_device", "This phone is not enrolled.")
    try:
        key, _ = load_public_key(device.public_key)
        check_clock(data.get("timestamp"))
        message = canonical("AUTH", "POST", TOKEN_PATH, str(device.pk), str(data.get("timestamp")), str(data.get("nonce") or ""))
        verify_signature(key, message, str(data.get("signature") or ""))
        use_nonce(f"auth:{device.pk}", str(data.get("nonce") or ""))
    except IdentityError as exc:
        _note_failure(device, exc.code, request)
        status = 400 if exc.code == "clock_skew" else 401
        raise DeviceAuthError(exc.code, str(exc), status) from None
    # Status is checked after the signature, so only the real phone learns that it was removed.
    if device.status == DeviceStatus.REVOKED:
        _note_failure(device, "device_revoked", request)
        raise DeviceAuthError("device_revoked", "This phone was removed by your administrator.")
    if device.status == DeviceStatus.SUSPENDED:
        raise DeviceAuthError("device_suspended", "This phone was paused by your administrator.", 403)
    token, ttl = issue_token(device)
    return device, token, ttl


def authenticate(token: str) -> DeviceToken:
    if not token or len(token) > 100:
        raise DeviceAuthError("invalid_token", "The device token is not valid.")
    row = DeviceToken.objects.select_related("device", "device__office").filter(token_hash=hash_token(token)).first()
    if row is None or row.expires_at <= timezone.now():
        raise DeviceAuthError("token_expired" if row else "invalid_token", "The device token expired. Request a new one.")
    if row.device.status == DeviceStatus.REVOKED:
        raise DeviceAuthError("device_revoked", "This phone was removed by your administrator.")
    if row.device.status == DeviceStatus.SUSPENDED:
        raise DeviceAuthError("device_suspended", "This phone was paused by your administrator.", 403)
    return row
