"""Play Integrity verdicts (optional, `SMS_REQUIRE_PLAY_INTEGRITY`).

The phone asks Google for an integrity token bound to the enrollment (`requestHash` = SHA-256 of the enrollment
token). This server decrypts and verifies it through Google's `decodeIntegrityToken` API, so no Play key ever
reaches the phone or this code.
"""

from __future__ import annotations

import logging

from django.conf import settings

log = logging.getLogger(__name__)

SCOPE = "https://www.googleapis.com/auth/playintegrity"


def configured() -> bool:
    return bool(settings.PLAY_INTEGRITY_PACKAGE_NAME and settings.PLAY_INTEGRITY_SERVICE_ACCOUNT_FILE)


def decode_integrity_token(token: str) -> dict:  # pragma: no cover - network call, mocked in tests
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_file(settings.PLAY_INTEGRITY_SERVICE_ACCOUNT_FILE, scopes=[SCOPE])
    session = AuthorizedSession(credentials)
    url = f"https://playintegrity.googleapis.com/v1/{settings.PLAY_INTEGRITY_PACKAGE_NAME}:decodeIntegrityToken"
    response = session.post(url, json={"integrity_token": token}, timeout=15)
    response.raise_for_status()
    return response.json().get("tokenPayloadExternal", {})


def verify(token: str, request_hash: str) -> dict:
    """A summary of the verdict. `ok` is True only for a genuine, unmodified app on a device with device integrity."""
    summary = {"present": bool(token), "configured": configured(), "ok": False, "error": ""}
    if not token or not configured():
        summary["error"] = "missing" if not token else "not_configured"
        return summary
    try:
        payload = decode_integrity_token(token)
    except Exception as exc:  # noqa: BLE001 - Google errors become a failed verdict, never a 500
        log.warning("play integrity decode failed: %s", type(exc).__name__)
        summary["error"] = "decode_failed"
        return summary
    details = payload.get("requestDetails", {})
    app = payload.get("appIntegrity", {})
    device = payload.get("deviceIntegrity", {})
    verdicts = device.get("deviceRecognitionVerdict", []) or []
    summary.update({
        "request_hash_ok": details.get("requestHash") == request_hash and details.get("requestPackageName") == settings.PLAY_INTEGRITY_PACKAGE_NAME,
        "app_verdict": app.get("appRecognitionVerdict", ""),
        "device_verdicts": verdicts,
    })
    # Privately distributed builds are UNRECOGNIZED_VERSION to Play. Accept them only when they are signed with one of
    # the company's own release certificates (PLAY_INTEGRITY_CERT_DIGESTS).
    digests = set(app.get("certificateSha256Digest", []) or [])
    app_ok = summary["app_verdict"] == "PLAY_RECOGNIZED" or (
        summary["app_verdict"] == "UNRECOGNIZED_VERSION" and bool(digests & set(settings.PLAY_INTEGRITY_CERT_DIGESTS))
    )
    summary["ok"] = bool(summary["request_hash_ok"] and app_ok and "MEETS_DEVICE_INTEGRITY" in verdicts)
    if not summary["ok"]:
        summary["error"] = "verdict_failed"
    return summary
