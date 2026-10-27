"""Enrolling a company phone, modelled on Gmail's connect links.

1. An admin creates an `EnrollmentInvite` (32 random bytes; only the SHA-256 is stored; single use; TTL
   `SMS_ENROLL_TTL_HOURS`; revocable). The admin screen shows a QR of `cmsms://enroll?server=…&token=…`.
2. The app (which only accepts servers in its compile-time allow-list, over HTTPS) shows the monitoring notice,
   generates a Keystore key with attestation challenge SHA-256(token), and calls `enroll(...)`.
3. `enroll` locks the invite, verifies the proof-of-possession signature, the attestation and (optionally) Play
   Integrity, creates the Device and consumes the invite in one transaction.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from modules.audit.services import record

from ..models import Device, DeviceStatus, EnrollmentInvite, SimLine
from . import identity, integrity
from .auth import check_clock, issue_token, use_nonce
from .versions import is_supported

log = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5
DEFAULT_OPTIONS = {"signature_enabled": False, "signature": "", "mark_read_on_open": True, "backfill_days": None}


class EnrollmentError(Exception):
    """A refused enrollment. `code` is stable for the app; `status` is the HTTP status."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def enroll_uri(token: str) -> str:
    """What the QR code encodes. The app refuses servers outside its build-time allow-list and non-HTTPS URLs."""
    return f"cmsms://enroll?{urlencode({'server': settings.SMS_DEVICE_API_URL, 'token': token})}"


def clean_options(options: dict | None) -> dict:
    options = options or {}
    result = dict(DEFAULT_OPTIONS)
    result["signature_enabled"] = bool(options.get("signature_enabled"))
    result["signature"] = str(options.get("signature") or "").strip()[:40]
    result["mark_read_on_open"] = bool(options.get("mark_read_on_open", True))
    days = options.get("backfill_days")
    result["backfill_days"] = max(0, min(int(days), 730)) if days not in (None, "") else settings.SMS_INITIAL_SYNC_DAYS
    return result


@transaction.atomic
def create_invite(user, *, name: str, office, assigned_to=None, options: dict | None = None, platform: str = "sms", request=None) -> tuple[EnrollmentInvite, str]:
    token = secrets.token_urlsafe(32)
    invite = EnrollmentInvite.objects.create(
        token_hash=hash_token(token), name=name.strip()[:120], office=office, assigned_to=assigned_to, options=clean_options(options),
        platform=platform, expires_at=timezone.now() + timedelta(hours=settings.SMS_ENROLL_TTL_HOURS), created_by=user,
    )
    record("device.invite_create", request=request, actor=user, target_type="enrollment", target_id=invite.pk,
           metadata={"name": invite.name, "office": office.pk, "expires_at": invite.expires_at.isoformat()})
    return invite, token


def revoke_invite(invite: EnrollmentInvite, user, request=None) -> None:
    if invite.state == "active":
        invite.revoked_at = timezone.now()
        invite.save(update_fields=["revoked_at"])
        record("device.invite_revoke", request=request, actor=user, target_type="enrollment", target_id=invite.pk, metadata={"name": invite.name})


def invite_for_token(token: str) -> EnrollmentInvite | None:
    if not token or len(token) > 100:
        return None
    return EnrollmentInvite.objects.select_related("office").filter(token_hash=hash_token(token)).first()


def _fail(invite: EnrollmentInvite | None, code: str, message: str, request, status: int = 400) -> EnrollmentError:
    """Record a failed attempt (outside the enrollment transaction, so it survives the rollback)."""
    if invite is not None:
        EnrollmentInvite.objects.filter(pk=invite.pk).update(failed_attempts=invite.failed_attempts + 1, last_failure=code)
        if invite.failed_attempts + 1 >= MAX_FAILED_ATTEMPTS and invite.state == "active":
            # Repeated failures against one token look like an attack: burn the token.
            EnrollmentInvite.objects.filter(pk=invite.pk).update(revoked_at=timezone.now())
            record("device.invite_revoke", request=request, target_type="enrollment", target_id=invite.pk, metadata={"reason": "too_many_failures"})
    record("device.enroll_failed", request=request, target_type="enrollment", target_id=invite.pk if invite else "", metadata={"reason": code})
    log.info("device enrollment refused: %s (invite %s)", code, invite.pk if invite else "-")
    return EnrollmentError(code, message, status)


def _unique_code() -> str:
    for _ in range(20):
        code = identity.new_device_code()
        if not Device.objects.filter(code=code).exists():
            return code
    raise RuntimeError("Could not allocate a device code.")  # pragma: no cover - 2^40 space


def enroll(data: dict, request=None) -> tuple[Device, str, int]:
    """Create the Device from a validated enroll request. Returns (device, access token, expires_in seconds)."""
    token = data["token"]
    candidate = invite_for_token(token)
    if candidate is None:
        raise _fail(None, "invalid_token", "This enrollment code is not valid. Ask your administrator for a new one.", request, 404)
    if not is_supported(data.get("app_version", "")):
        raise _fail(candidate, "upgrade_required", "This app version is too old. Install the latest version and try again.", request, 426)
    try:
        key, spki = identity.load_public_key(data["public_key"])
        fp = identity.fingerprint(spki)
        check_clock(data["timestamp"])
        message = identity.canonical("ENROLL", hash_token(token), fp, str(data["timestamp"]), data["nonce"])
        identity.verify_signature(key, message, data["signature"])
        use_nonce(f"enroll:{fp}", data["nonce"])
    except identity.IdentityError as exc:
        raise _fail(candidate, exc.code, str(exc), request) from None

    challenge = hashlib.sha256(token.encode()).digest()
    attestation = identity.verify_attestation(data.get("attestation_chain") or [], spki, challenge)
    if settings.SMS_REQUIRE_KEY_ATTESTATION and not attestation.hardware_backed:
        raise _fail(candidate, "attestation_failed", "This phone could not prove its key is protected by secure hardware. Use a supported company phone.", request, 403)
    verdict = {}
    if settings.SMS_REQUIRE_PLAY_INTEGRITY or data.get("integrity_token"):
        verdict = integrity.verify(data.get("integrity_token") or "", hash_token(token))
        if settings.SMS_REQUIRE_PLAY_INTEGRITY and not verdict.get("ok"):
            raise _fail(candidate, "integrity_failed", "This phone or app did not pass Google Play Integrity checks.", request, 403)
    if not data.get("notice_accepted"):
        raise _fail(candidate, "notice_not_accepted", "The monitoring notice must be accepted before this phone can be enrolled.", request)

    try:
        with transaction.atomic():
            invite = EnrollmentInvite.objects.select_for_update(of=("self",)).select_related("office", "created_by").get(pk=candidate.pk)
            if invite.state != "active":
                raise EnrollmentError("invite_inactive", "This enrollment code was already used, revoked or has expired. Ask your administrator for a new one.", 410)
            if Device.objects.filter(key_fingerprint=fp).exists():
                raise EnrollmentError("key_in_use", "This key is already enrolled.", 409)
            facts = data.get("device") or {}
            device = Device.objects.create(
                code=_unique_code(), name=invite.name, office=invite.office, assigned_to=invite.assigned_to, status=DeviceStatus.ACTIVE,
                public_key=data["public_key"].strip(), key_fingerprint=fp, hardware_backed=attestation.hardware_backed,
                attestation=attestation.as_dict(), integrity=verdict,
                manufacturer=str(facts.get("manufacturer", ""))[:80], model=str(facts.get("model", ""))[:80],
                android_version=str(facts.get("android_version", ""))[:20], sdk_int=int(facts.get("sdk_int") or 0),
                app_version=str(data.get("app_version", ""))[:32], options=invite.options, notice_text=data.get("notice_text", "")[:4000],
                notice_accepted_at=timezone.now(), enrolled_by=invite.created_by, last_seen_at=timezone.now(),
                sync_progress={"phase": "waiting", "done": 0, "total": 0},
            )
            save_sims(device, data.get("sims") or [])
            invite.used_at = timezone.now()
            invite.device = device
            invite.save(update_fields=["used_at", "device"])
            access, expires_in = issue_token(device)
            record("device.enroll", request=request, actor=invite.created_by, target_type="device", target_id=device.pk,
                   metadata={"device": device.code, "name": device.name, "hardware_backed": device.hardware_backed, "security_level": attestation.security_level,
                             "model": f"{device.manufacturer} {device.model}".strip(), "android": device.android_version, "app_version": device.app_version})
            record("device.notice_accepted", request=request, target_type="device", target_id=device.pk, metadata={"device": device.code})
    except EnrollmentError as exc:
        raise _fail(candidate, exc.code, exc.message, request, exc.status) from None
    except IntegrityError:
        raise _fail(candidate, "key_in_use", "This key is already enrolled.", request, 409) from None
    return device, access, expires_in


def save_sims(device: Device, sims: list[dict]) -> None:
    """Upsert the phone's SIM lines (subscription ids are stable per SIM on a device). Missing lines go inactive."""
    from .phone import normalise_e164

    seen = []
    for index, sim in enumerate(sims[:4]):
        try:
            sub_id = int(sim.get("subscription_id"))
        except (TypeError, ValueError):
            continue
        seen.append(sub_id)
        country = str(sim.get("country_iso") or "")[:2].upper()
        number = normalise_e164(str(sim.get("number") or ""), country or settings.SMS_DEFAULT_REGION) or ""
        line, created = SimLine.objects.get_or_create(device=device, subscription_id=sub_id, defaults={"slot": int(sim.get("slot") or index)})
        line.slot = int(sim.get("slot") if sim.get("slot") is not None else index)
        line.carrier = str(sim.get("carrier") or "")[:80]
        line.country_iso = country
        if number:
            line.number = number
        line.is_default = bool(sim.get("is_default"))
        line.is_active = True
        if created:
            line.colour = ["#10b981", "#8b5cf6", "#f59e0b", "#ef4444"][line.slot % 4]
        line.save()
    SimLine.objects.filter(device=device).exclude(subscription_id__in=seen).update(is_active=False)
