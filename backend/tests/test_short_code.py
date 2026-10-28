"""Enrollment short codes (XXXX-XXXX) and the background-health fields of the heartbeat."""

import hashlib
import re
from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone

from common.http import ClientIpScopedThrottle
from modules.audit.models import AuditEvent
from modules.devices.models import Device, EnrollmentInvite
from modules.devices.services import enrollment
from tests.phone import APP_VERSION, Phone

pytestmark = pytest.mark.django_db

SHORT = re.compile(r"^[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}$")


def create(client_for, admin, office, name="Desk"):
    response = client_for(admin).post("/api/v1/sms/enrollments/", {"name": name, "office": office.pk}, format="json")
    assert response.status_code == 201, response.json()
    return response.json()


def resolve(client_for, code, **extra):
    return client_for(None).post("/api/v1/device/enroll/resolve/", {"code": code}, format="json", **extra)


def test_short_code_is_shown_once_stored_as_an_hmac_and_resolves_to_a_working_token(client_for, admin, office):
    body = create(client_for, admin, office)
    assert SHORT.match(body["short_code"]) and body["short_code_used"] is False
    invite = EnrollmentInvite.objects.get()
    code = body["short_code"].replace("-", "")
    assert invite.short_code_hash != hashlib.sha256(code.encode()).hexdigest()  # keyed: a DB copy alone cannot be brute-forced
    assert code not in invite.short_code_hash
    assert timedelta(minutes=14) < invite.short_code_expires_at - timezone.now() <= timedelta(minutes=15)

    # Typed the way people type: lower case, a space, O for 0.
    typed = (body["short_code"][:4] + " " + body["short_code"][5:]).lower().replace("0", "o")
    response = resolve(client_for, typed)
    assert response.status_code == 200, response.json()
    token = response.json()["token"]
    assert response.json()["expires_in"] == 900
    assert token != body["code"]
    # The usual enrollment follows: the notice is shown, the phone enrolls with the resolved token.
    info = client_for(None).get(f"/api/v1/device/enroll/info/?token={token}").json()
    assert info["device_name"] == "Desk" and "notice" in info
    phone = Phone()
    assert phone.enroll(token).status_code == 201
    assert Device.objects.get().name == "Desk"
    assert AuditEvent.objects.filter(action="device.short_code_resolved").exists()


def test_short_code_is_single_use_expires_and_never_outlives_the_invite(client_for, admin, office):
    body = create(client_for, admin, office)
    assert resolve(client_for, body["short_code"]).status_code == 200
    second = resolve(client_for, body["short_code"])
    assert second.status_code == 404 and second.json()["code"] == "invalid_code"
    # A fresh code, then let it expire.
    invite = EnrollmentInvite.objects.get()
    fresh = client_for(admin).post(f"/api/v1/sms/enrollments/{invite.pk}/short-code/").json()["short_code"]
    EnrollmentInvite.objects.filter(pk=invite.pk).update(short_code_expires_at=timezone.now() - timedelta(seconds=1))
    assert resolve(client_for, fresh).status_code == 404
    # A revoked invite's code is dead too.
    fresh = client_for(admin).post(f"/api/v1/sms/enrollments/{invite.pk}/short-code/").json()["short_code"]
    client_for(admin).post(f"/api/v1/sms/enrollments/{invite.pk}/revoke/")
    assert resolve(client_for, fresh).status_code == 404
    assert client_for(admin).post(f"/api/v1/sms/enrollments/{invite.pk}/short-code/").status_code == 409


def test_a_resolved_token_works_only_for_the_codes_lifetime(client_for, admin, office):
    body = create(client_for, admin, office)
    token = resolve(client_for, body["short_code"]).json()["token"]
    EnrollmentInvite.objects.update(short_code_used_at=timezone.now() - timedelta(minutes=16))
    assert client_for(None).get(f"/api/v1/device/enroll/info/?token={token}").status_code == 404
    assert Phone().enroll(token).status_code == 404
    # The QR token itself is unaffected.
    assert Phone().enroll(body["code"]).status_code == 201


def test_wrong_codes_trip_a_global_breaker_that_locks_every_live_code(client_for, admin, office, settings):
    settings.SMS_SHORT_CODE_MAX_FAILURES = 3
    live = create(client_for, admin, office)
    for guess in ["AAAA-AAAA", "not a code", "BBBB-BBBB"]:
        assert resolve(client_for, guess).status_code == 404
    assert AuditEvent.objects.filter(action="device.short_code_failed").count() == 3
    assert AuditEvent.objects.filter(action="device.short_code_lockdown").count() == 1
    # The right code no longer works (it was locked), and resolution is refused while the breaker is open.
    response = resolve(client_for, live["short_code"])
    assert response.status_code == 429 and response.json()["code"] == "throttled"
    assert EnrollmentInvite.objects.get().short_code_expires_at <= timezone.now()
    # QR enrollment is not affected by the lock.
    assert Phone().enroll(live["code"]).status_code == 201


def test_short_codes_are_throttled_per_ip(client_for, admin, office):
    rates = {**ClientIpScopedThrottle.THROTTLE_RATES, "device_short_code": "2/min", "device_short_code_hour": "100/hour"}
    with mock.patch.object(ClientIpScopedThrottle, "THROTTLE_RATES", rates):
        assert resolve(client_for, "AAAA-AAAA", REMOTE_ADDR="10.0.0.1").status_code == 404
        assert resolve(client_for, "AAAA-AAAA", REMOTE_ADDR="10.0.0.1").status_code == 404
        assert resolve(client_for, "AAAA-AAAA", REMOTE_ADDR="10.0.0.1").status_code == 429
        assert resolve(client_for, "AAAA-AAAA", REMOTE_ADDR="10.0.0.2").status_code == 404  # another address has its own budget


def test_normalisation_follows_crockford():
    assert enrollment.normalise_short_code("7f3k-9q2m") == "7F3K9Q2M"
    assert enrollment.normalise_short_code("OIL1 ABCD") == "0111ABCD"
    assert enrollment.normalise_short_code("7F3K-9Q2U") is None
    assert enrollment.normalise_short_code("7F3K9Q2") is None


# --- Background health in the heartbeat ------------------------------------------------------------------------


def test_heartbeat_reports_background_restrictions_with_alerts_and_how_to_fix_them(phone, client_for, admin):
    response = phone.post("heartbeat/", {
        "is_default_sms_app": True, "battery_optimised": True, "background_restricted": True, "standby_bucket": 40, "manufacturer": "TECNO",
        "app_version": APP_VERSION,
    })
    assert response.status_code == 200, response.json()
    assert {"battery_optimised", "background_restricted", "standby_restricted"} <= set(response.json()["attention"])
    device = Device.objects.get(pk=phone.device_id)
    assert device.background_restricted is True and device.standby_bucket == 40 and device.manufacturer == "TECNO"
    detail = client_for(admin).get(f"/api/v1/sms/devices/{device.pk}/").json()
    assert detail["background_restricted"] is True and detail["standby_bucket"] == 40
    assert any("Phone Master" in step for step in detail["background_help"])
    labels = {a["code"]: a["label"] for a in detail["attention"]}
    assert labels["background_restricted"] == "Background use is restricted"
    # Fixed on the phone: the alerts clear with the next heartbeat.
    phone.post("heartbeat/", {"is_default_sms_app": True, "background_restricted": False, "standby_bucket": 10})
    assert not {"background_restricted", "standby_restricted"} & set(Device.objects.get(pk=phone.device_id).attention)


def test_heartbeat_validates_the_new_fields(phone):
    assert phone.post("heartbeat/", {"is_default_sms_app": True, "standby_bucket": 500}).status_code == 400
    assert phone.post("heartbeat/", {"is_default_sms_app": True, "manufacturer": "x" * 200}).status_code == 400
