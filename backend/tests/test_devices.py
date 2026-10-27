"""Device enrollment, key attestation, proof-of-possession tokens, device auth, heartbeat, admin controls, push."""

import base64
import hashlib
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from django.utils import timezone

from modules.audit.models import AuditEvent
from modules.devices.models import Device, DeviceHeartbeat, DeviceStatus, DeviceToken, EnrollmentInvite
from modules.devices.services import enrollment, health, identity, manage, push
from tests.phone import APP_VERSION, Phone

pytestmark = pytest.mark.django_db


# --- Invites ---------------------------------------------------------------------------------------------------


def test_admin_creates_enrollment_with_qr_and_only_the_hash_is_stored(client_for, admin, office):
    response = client_for(admin).post("/api/v1/sms/enrollments/", {"name": "Arusha front desk", "office": office.pk, "signature_enabled": True, "signature": "— Head Office"}, format="json")
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["uri"].startswith("cmsms://enroll?server=http%3A%2F%2Ftestserver&token=")
    assert "<svg" in body["qr_svg"] and body["state"] == "active"
    invite = EnrollmentInvite.objects.get()
    assert invite.token_hash == hashlib.sha256(body["code"].encode()).hexdigest() and body["code"] not in invite.token_hash
    assert len(base64.urlsafe_b64decode(body["code"] + "=")) == 32
    assert invite.expires_at - timezone.now() > timedelta(hours=23)
    assert invite.options["signature_enabled"] is True and invite.options["backfill_days"] == 90
    assert AuditEvent.objects.filter(action="device.invite_create").exists()
    # Status polling and revoke.
    assert client_for(admin).get(f"/api/v1/sms/enrollments/{invite.pk}/").json()["state"] == "active"
    assert client_for(admin).post(f"/api/v1/sms/enrollments/{invite.pk}/revoke/").json()["state"] == "revoked"
    assert AuditEvent.objects.filter(action="device.invite_revoke").exists()


def test_qr_points_phones_at_the_device_api_domain(client_for, admin, office, settings):
    """With the API on its own domain, the QR carries that domain (the one the app's allow-list names)."""
    settings.SMS_DEVICE_API_URL = "https://communicationapi.example.com"
    body = client_for(admin).post("/api/v1/sms/enrollments/", {"name": "Desk", "office": office.pk}, format="json").json()
    assert body["uri"].startswith("cmsms://enroll?server=https%3A%2F%2Fcommunicationapi.example.com&token=")


def test_only_device_managers_create_enrollments(client_for, manager, office):
    response = client_for(manager).post("/api/v1/sms/enrollments/", {"name": "X", "office": office.pk}, format="json")
    assert response.status_code == 403


def test_enroll_info_shows_the_monitoring_notice(client_for, invite_token):
    _, token = invite_token()
    info = client_for(None).get(f"/api/v1/device/enroll/info/?token={token}").json()
    assert info["device_name"] == "Front desk" and info["state"] == "active" and "All access is logged" in info["notice"]
    assert client_for(None).get("/api/v1/device/enroll/info/?token=nope").status_code == 404


# --- Enrollment ------------------------------------------------------------------------------------------------


def test_enroll_creates_device_consumes_invite_and_audits(invite_token):
    invite, token = invite_token()
    phone = Phone()
    response = phone.enroll(token)
    assert response.status_code == 201, response.json()
    body = response.json()
    device = Device.objects.get(pk=body["device_id"])
    assert body["device_code"] == device.code and device.code.startswith("DEV-") and len(device.code) == 13
    assert set(device.code[4:].replace("-", "")) <= set(identity.CROCKFORD)
    assert device.key_fingerprint == hashlib.sha256(base64.b64decode(body and phone.enroll_body(token)["public_key"])).hexdigest()
    assert device.status == DeviceStatus.ACTIVE and device.notice_accepted_at and device.hardware_backed is False
    assert device.attestation["present"] is False
    sim = device.sim_lines.get()
    assert sim.number == "+255754000111" and sim.carrier == "Vodacom"
    invite.refresh_from_db()
    assert invite.state == "used" and invite.device_id == device.pk
    assert DeviceToken.objects.filter(device=device).count() == 1 and body["token_type"] == "Bearer"
    assert AuditEvent.objects.filter(action="device.enroll", target_id=str(device.pk)).exists()
    assert AuditEvent.objects.filter(action="device.notice_accepted").exists()
    # Single use.
    again = Phone().enroll(token)
    assert again.status_code == 410 and again.json()["code"] == "invite_inactive"


@pytest.mark.parametrize("state", ["expired", "revoked"])
def test_enroll_refuses_inactive_invites(invite_token, state):
    invite, token = invite_token()
    if state == "expired":
        EnrollmentInvite.objects.filter(pk=invite.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    else:
        EnrollmentInvite.objects.filter(pk=invite.pk).update(revoked_at=timezone.now())
    response = Phone().enroll(token)
    assert response.status_code == 410 and response.json()["code"] == "invite_inactive"
    assert AuditEvent.objects.filter(action="device.enroll_failed", metadata__reason="invite_inactive").exists()
    assert not Device.objects.exists()


def test_enroll_refuses_unknown_token(client_for):
    response = Phone().enroll("not-a-real-token")
    assert response.status_code == 404 and response.json()["code"] == "invalid_token"


def test_enroll_proof_of_possession_failures(invite_token):
    invite, token = invite_token()
    phone, impostor = Phone(), Phone()
    # Signed by another key than the one being enrolled.
    stolen = impostor.enroll_body(token)
    response = phone.client.post("/api/v1/device/enroll/", {**phone.enroll_body(token), "signature": stolen["signature"]}, format="json")
    assert response.json()["code"] == "bad_signature"
    # Clock skew.
    assert phone.enroll(token, timestamp=int(time.time()) - 3600).json()["code"] == "clock_skew"
    # Notice not accepted.
    assert phone.enroll(token, notice_accepted=False).json()["code"] == "notice_not_accepted"
    # App too old.
    old = phone.enroll(token, app_version="0.9.0")
    assert old.status_code == 426 and old.json()["code"] == "upgrade_required"
    # Replayed nonce: the same signed body twice.
    body = phone.enroll_body(token)
    first = phone.client.post("/api/v1/device/enroll/", body, format="json")
    assert first.status_code == 201
    other = invite_token(name="Second")[1]
    replay = phone.client.post("/api/v1/device/enroll/", {**phone.enroll_body(other, nonce=body["nonce"])}, format="json")
    assert replay.json()["code"] in ("replayed_nonce", "key_in_use")
    assert AuditEvent.objects.filter(action="device.enroll_failed").count() >= 4


def test_repeated_failures_burn_the_token(invite_token):
    invite, token = invite_token()
    phone = Phone()
    for _ in range(enrollment.MAX_FAILED_ATTEMPTS):
        phone.enroll(token, notice_accepted=False)
    invite.refresh_from_db()
    assert invite.state == "revoked"
    assert phone.enroll(token).json()["code"] == "invite_inactive"


def test_the_same_key_cannot_enroll_twice(invite_token):
    phone = Phone()
    assert phone.enroll(invite_token()[1]).status_code == 201
    response = phone.enroll(invite_token(name="Again")[1])
    assert response.status_code == 409 and response.json()["code"] == "key_in_use"


# --- Key attestation ------------------------------------------------------------------------------------------


def _tlv(tag: int, content: bytes) -> bytes:
    length = len(content)
    if length < 0x80:
        return bytes([tag, length]) + content
    raw = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([tag, 0x80 | len(raw)]) + raw + content


def _key_description(challenge: bytes, level: int = 1) -> bytes:
    fields = _tlv(0x02, b"\x64") + _tlv(0x0A, bytes([level])) + _tlv(0x02, b"\x64") + _tlv(0x0A, bytes([level])) + _tlv(0x04, challenge) + _tlv(0x04, b"") + _tlv(0x30, b"") + _tlv(0x30, b"")
    return _tlv(0x30, fields)


def _chain(device_key, challenge: bytes, level: int = 1):
    root_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test attestation root")])
    now = datetime.now(dt_timezone.utc)
    root = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(root_key.public_key()).serial_number(1)
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True).sign(root_key, hashes.SHA256()))
    leaf = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Android Keystore Key")])).issuer_name(name)
            .public_key(device_key.public_key()).serial_number(2).not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=30))
            .add_extension(x509.UnrecognizedExtension(identity.KEY_DESCRIPTION_OID, _key_description(challenge, level)), critical=False).sign(root_key, hashes.SHA256()))
    der = [base64.b64encode(c.public_bytes(serialization.Encoding.DER)).decode() for c in (leaf, root)]
    return der, root


@pytest.fixture
def trusted_root(tmp_path, settings):
    def install(root):
        path = tmp_path / "roots.pem"
        path.write_bytes(root.public_bytes(serialization.Encoding.PEM))
        settings.SMS_ATTESTATION_ROOTS_FILE = str(path)
        identity._trusted_roots.cache_clear()
    yield install
    identity._trusted_roots.cache_clear()


def test_hardware_attestation_verified_against_trusted_root(invite_token, trusted_root):
    _, token = invite_token()
    phone = Phone()
    chain, root = _chain(phone.key, hashlib.sha256(token.encode()).digest(), level=2)
    trusted_root(root)
    assert phone.enroll(token, attestation_chain=chain).status_code == 201
    device = Device.objects.get(pk=phone.device_id)
    assert device.hardware_backed is True and device.attestation["security_level"] == "strongbox" and device.attestation["root_trusted"]


def test_attestation_rejects_untrusted_root_wrong_challenge_and_foreign_key(invite_token, trusted_root):
    _, token = invite_token()
    phone = Phone()
    challenge = hashlib.sha256(token.encode()).digest()
    spki = base64.b64decode(phone.enroll_body(token)["public_key"])
    chain, root = _chain(phone.key, challenge)
    assert identity.verify_attestation(chain, spki, challenge).error == "untrusted_root"
    trusted_root(root)
    wrong, root2 = _chain(phone.key, b"x" * 32)
    trusted_root(root2)
    assert identity.verify_attestation(wrong, spki, challenge).error == "challenge_mismatch"
    foreign, _ = _chain(Phone().key, challenge)
    assert identity.verify_attestation(foreign, spki, challenge).error == "leaf_key_mismatch"
    assert identity.verify_attestation(["bm9wZQ=="], spki, challenge).error == "invalid_chain"


def _cert(subject: str, issuer: x509.Certificate, signer, public_key, *, ca: bool, extensions=()):
    now = datetime.now(dt_timezone.utc)
    builder = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject)])).issuer_name(issuer.subject)
               .public_key(public_key).serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=30)))
    if ca:
        builder = builder.add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    for extension in extensions:
        builder = builder.add_extension(extension, critical=False)
    return builder.sign(signer, hashes.SHA256())


def _der(*certs) -> list[str]:
    return [base64.b64encode(c.public_bytes(serialization.Encoding.DER)).decode() for c in certs]


def test_attestation_rejects_leaf_forged_with_a_genuine_attested_key(invite_token, trusted_root):
    """A real phone's attested key can sign anything, so it must not be accepted as an issuer of another "attested" key."""
    _, token = invite_token()
    challenge = hashlib.sha256(token.encode()).digest()
    software = Phone()  # the key the attacker wants enrolled as hardware-backed
    genuine_key = ec.generate_private_key(ec.SECP256R1())  # stands in for a real phone's Keystore key
    genuine_chain, root = _chain(genuine_key, b"any" * 8, level=1)
    trusted_root(root)
    genuine_leaf = x509.load_der_x509_certificate(base64.b64decode(genuine_chain[0]))
    forged = _cert("Android Keystore Key", genuine_leaf, genuine_key, software.key.public_key(), ca=False,
                   extensions=[x509.UnrecognizedExtension(identity.KEY_DESCRIPTION_OID, _key_description(challenge, 2))])
    chain = [*_der(forged), *genuine_chain]
    spki = base64.b64decode(software.enroll_body(token)["public_key"])
    result = identity.verify_attestation(chain, spki, challenge)
    assert result.error == "invalid_chain" and not result.hardware_backed
    # Enrolled anyway (attestation is optional by default), but never marked hardware-backed.
    assert software.enroll(token, attestation_chain=chain).status_code == 201
    assert Device.objects.get(pk=software.device_id).hardware_backed is False


def test_attestation_rejects_key_description_outside_the_leaf(trusted_root):
    challenge = b"c" * 32
    root_key, mid_key, leaf_key = (ec.generate_private_key(ec.SECP256R1()) for _ in range(3))
    now = datetime.now(dt_timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test attestation root")])
    root = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(root_key.public_key()).serial_number(1)
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True).sign(root_key, hashes.SHA256()))
    trusted_root(root)
    description = x509.UnrecognizedExtension(identity.KEY_DESCRIPTION_OID, _key_description(challenge, 2))
    spki = leaf_key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    leaf_of = lambda mid: _cert("Android Keystore Key", mid, mid_key, leaf_key.public_key(), ca=False, extensions=[description])  # noqa: E731

    good_mid = _cert("Intermediate", root, root_key, mid_key.public_key(), ca=True)
    assert identity.verify_attestation(_der(leaf_of(good_mid), good_mid, root), spki, challenge).hardware_backed  # control
    bad_mid = _cert("Intermediate", root, root_key, mid_key.public_key(), ca=True, extensions=[description])
    assert identity.verify_attestation(_der(leaf_of(bad_mid), bad_mid, root), spki, challenge).error == "invalid_chain"


def test_required_attestation_refuses_software_keys(invite_token, settings):
    settings.SMS_REQUIRE_KEY_ATTESTATION = True
    response = Phone().enroll(invite_token()[1])
    assert response.status_code == 403 and response.json()["code"] == "attestation_failed"


def test_required_play_integrity(invite_token, settings):
    settings.SMS_REQUIRE_PLAY_INTEGRITY = True
    settings.PLAY_INTEGRITY_PACKAGE_NAME = "com.example.cm.sms"
    settings.PLAY_INTEGRITY_SERVICE_ACCOUNT_FILE = "/secret/sa.json"
    _, token = invite_token()
    good = {"requestDetails": {"requestHash": hashlib.sha256(token.encode()).hexdigest(), "requestPackageName": "com.example.cm.sms"},
            "appIntegrity": {"appRecognitionVerdict": "PLAY_RECOGNIZED"}, "deviceIntegrity": {"deviceRecognitionVerdict": ["MEETS_DEVICE_INTEGRITY"]}}
    with mock.patch("modules.devices.services.integrity.decode_integrity_token", return_value={**good, "deviceIntegrity": {"deviceRecognitionVerdict": []}}):
        assert Phone().enroll(token, integrity_token="t").json()["code"] == "integrity_failed"
    with mock.patch("modules.devices.services.integrity.decode_integrity_token", return_value=good):
        phone = Phone()
        assert phone.enroll(token, integrity_token="t").status_code == 201
    assert Device.objects.get(pk=phone.device_id).integrity["ok"] is True


# --- Tokens ----------------------------------------------------------------------------------------------------


def test_token_minting_with_proof_of_possession(phone):
    response = phone.authenticate()
    assert response.status_code == 200 and response.json()["expires_in"] == 15 * 60
    token = response.json()["access_token"]
    row = DeviceToken.objects.get(token_hash=hashlib.sha256(token.encode()).hexdigest())
    assert token not in row.token_hash


def test_token_minting_failures(phone):
    assert phone.authenticate(key=Phone().key).json()["code"] == "bad_signature"
    body = phone.token_body()
    assert phone.client.post("/api/v1/device/auth/token/", body, format="json").status_code == 200
    replay = phone.client.post("/api/v1/device/auth/token/", body, format="json")
    assert replay.status_code == 401 and replay.json()["code"] == "replayed_nonce"
    skew = phone.authenticate(timestamp=int(time.time()) + 600)
    assert skew.status_code == 400 and skew.json()["code"] == "clock_skew"
    assert phone.authenticate(device_id="00000000-0000-0000-0000-000000000000").json()["code"] == "invalid_device"
    assert AuditEvent.objects.filter(action="device.token_failed", metadata__reason="bad_signature").count() == 1


def test_failed_token_audit_is_rate_limited(phone):
    for _ in range(5):
        phone.authenticate(key=Phone().key)
    assert AuditEvent.objects.filter(action="device.token_failed").count() == 1


def test_revoked_and_suspended_devices(client_for, admin, phone):
    device = Device.objects.get(pk=phone.device_id)
    client = client_for(admin)
    assert client.post(f"/api/v1/sms/devices/{device.pk}/suspend/", {"reason": "lost"}, format="json").json()["status"] == "suspended"
    assert phone.get("config/").json()["code"] == "device_suspended"  # existing tokens died with the suspension
    suspended = phone.authenticate()
    assert suspended.status_code == 403 and suspended.json()["code"] == "device_suspended"
    assert client.post(f"/api/v1/sms/devices/{device.pk}/resume/", format="json").json()["status"] == "active"
    assert phone.authenticate().status_code == 200
    wrong = client.post(f"/api/v1/sms/devices/{device.pk}/revoke/", {"confirm_code": "DEV-0000-0000"}, format="json")
    assert wrong.status_code == 400
    assert client.post(f"/api/v1/sms/devices/{device.pk}/revoke/", {"confirm_code": device.code.lower()}, format="json").json()["status"] == "revoked"
    revoked = phone.get("config/")
    assert revoked.status_code == 401 and revoked.json()["code"] == "device_revoked"
    assert phone.authenticate().json()["code"] == "device_revoked"
    actions = set(AuditEvent.objects.filter(target_id=str(device.pk)).values_list("action", flat=True))
    assert {"device.suspend", "device.resume", "device.revoke"} <= actions


# --- Auth surfaces ---------------------------------------------------------------------------------------------


def test_device_and_session_surfaces_never_mix(admin, phone):
    from rest_framework.test import APIClient

    from tests.conftest import PASSWORD

    # A real browser session cannot call the phone API (no cookies are read there).
    browser = APIClient()
    assert browser.login(email=admin.email, password=PASSWORD)
    assert browser.get("/api/v1/sms/devices/").status_code == 200
    assert browser.post("/api/v1/device/heartbeat/", {"is_default_sms_app": True}, format="json", HTTP_X_CM_APP_VERSION=APP_VERSION).status_code == 401
    assert browser.get("/api/v1/device/config/", HTTP_X_CM_APP_VERSION=APP_VERSION).status_code == 401
    # A device token cannot call the admin API.
    assert phone.client.get("/api/v1/sms/devices/", HTTP_AUTHORIZATION=f"Bearer {phone.token}").status_code == 401
    assert phone.client.get("/api/v1/auth/me/", HTTP_AUTHORIZATION=f"Bearer {phone.token}").status_code == 401
    # Garbage and expired tokens.
    assert phone.client.post("/api/v1/device/heartbeat/", {}, format="json", HTTP_AUTHORIZATION="Bearer nope", HTTP_X_CM_APP_VERSION=APP_VERSION).json()["code"] == "invalid_token"
    DeviceToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    assert phone.post("heartbeat/", {"is_default_sms_app": True}).json()["code"] == "token_expired"


def test_minimum_app_version_answers_426(phone, settings):
    settings.SMS_MIN_APP_VERSION = "2.0.0"
    response = phone.post("heartbeat/", {"is_default_sms_app": True})
    assert response.status_code == 426 and response.json()["code"] == "upgrade_required"
    assert phone.client.post("/api/v1/device/heartbeat/", {}, format="json", HTTP_AUTHORIZATION=f"Bearer {phone.token}").status_code == 426


# --- Heartbeat and health -------------------------------------------------------------------------------------


def test_heartbeat_updates_state_history_and_alerts(phone):
    response = phone.post("heartbeat/", {
        "battery": 41, "charging": False, "network_type": "cellular", "signal": 3, "is_default_sms_app": False,
        "permissions": {"READ_SMS": True, "SEND_SMS": False}, "battery_optimised": True, "pending_outbox": 75, "app_version": APP_VERSION,
        "sims": [{"subscription_id": 1, "slot": 0, "carrier": "Vodacom", "country_iso": "TZ"}, {"subscription_id": 4, "slot": 1, "carrier": "Airtel", "country_iso": "TZ"}],
    })
    assert response.status_code == 200, response.json()
    assert set(response.json()["attention"]) == {"not_default_sms_app", "permission_revoked", "battery_optimised", "outbox_backlog"}
    device = Device.objects.get(pk=phone.device_id)
    assert device.battery == 41 and device.network_type == "cellular" and device.sim_lines.filter(is_active=True).count() == 2
    assert DeviceHeartbeat.objects.filter(device=device).count() == 1
    assert health.is_online(device)
    Device.objects.filter(pk=device.pk).update(last_seen_at=timezone.now() - timedelta(hours=3))
    health.refresh_all()
    assert "offline" in Device.objects.get(pk=device.pk).attention


def test_stale_heartbeat_or_edit_cannot_undo_a_revoke(phone, admin):
    """The phone's request holds the device row it authenticated with; saving it must not write `status` back."""
    stale = Device.objects.get(pk=phone.device_id)
    stale_admin_copy = Device.objects.get(pk=phone.device_id)
    manage.revoke(Device.objects.get(pk=phone.device_id), admin)
    health.record_heartbeat(stale, {"battery": 50, "is_default_sms_app": True})
    manage.update(stale_admin_copy, admin, {"name": "Renamed"})
    device = Device.objects.get(pk=phone.device_id)
    assert device.status == DeviceStatus.REVOKED and device.revoked_at is not None and device.push_token == ""
    assert device.battery == 50 and device.name == "Renamed"
    assert phone.get("config/").json()["code"] == "device_revoked"


def test_heartbeat_validates_input(phone):
    assert phone.post("heartbeat/", {"is_default_sms_app": True, "battery": 140}).status_code == 400
    assert phone.post("heartbeat/", {"is_default_sms_app": True, "network_type": "<script>"}).status_code == 400


def test_prune_removes_old_rows(phone):
    device = Device.objects.get(pk=phone.device_id)
    DeviceHeartbeat.objects.create(device=device, created_at=timezone.now() - timedelta(days=30))
    DeviceToken.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
    result = health.prune()
    assert result["heartbeats"] == 1 and result["tokens"] >= 1


# --- Admin device management -----------------------------------------------------------------------------------


def test_device_detail_options_sims_and_resync(client_for, admin, phone):
    from modules.devices.models import DeviceCommand

    device = Device.objects.get(pk=phone.device_id)
    client = client_for(admin)
    detail = client.get(f"/api/v1/sms/devices/{device.pk}/").json()
    assert detail["code"] == device.code and detail["online"] and detail["sims"][0]["label"] == "Vodacom"
    updated = client.patch(f"/api/v1/sms/devices/{device.pk}/", {"name": "Reception", "options": {"signature_enabled": True, "signature": "— HQ"}}, format="json").json()
    assert updated["name"] == "Reception" and updated["options"]["signature"] == "— HQ"
    sim = detail["sims"][0]["id"]
    assert client.patch(f"/api/v1/sms/devices/{device.pk}/sims/{sim}/", {"display_name": "Sales line"}, format="json").json()["label"] == "Sales line"
    assert client.post(f"/api/v1/sms/devices/{device.pk}/resync/").status_code == 202
    assert DeviceCommand.objects.filter(device=device, kind="resync").exists()
    assert {"device.update", "device.sim_update", "device.resync_request"} <= set(AuditEvent.objects.values_list("action", flat=True))


# --- Push ------------------------------------------------------------------------------------------------------


def test_push_wake_is_data_only_and_forgets_dead_tokens(phone, settings):
    device = Device.objects.get(pk=phone.device_id)
    assert phone.post("push-token/", {"token": "fcm-registration"}).status_code == 204
    assert push.wake(device.pk, "outbox") is False  # FCM not configured
    settings.FCM_PROJECT_ID, settings.FCM_SERVICE_ACCOUNT_FILE = "cm-test", "/secret/fcm.json"
    with mock.patch("modules.devices.services.push.send", return_value=(200, {"name": "ok"})) as send:
        assert push.wake(device.pk, "outbox") is True
    token, data = send.call_args.args
    assert token == "fcm-registration" and data == {"type": "outbox", "device": str(device.pk)}
    from django.core.cache import cache

    cache.clear()
    with mock.patch("modules.devices.services.push.send", return_value=(404, {"error": {"status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}})):
        assert push.wake(device.pk, "sync") is False
    assert Device.objects.get(pk=device.pk).push_token == ""
