"""The security store fails closed (decision 59): if Redis cannot record a nonce, a counter or a lock, the request is
refused. A replayed signed request must never be accepted because the replay check could not run."""

from unittest import mock

import pytest
from django.core.cache import caches
from rest_framework.test import APIClient

from common import stores
from modules.devices.models import DeviceToken, EnrollmentInvite


class BrokenStore:
    """Every call raises, like a Redis that is down or refusing writes (OOM under noeviction)."""

    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise ConnectionError("redis down")

        return fail


@pytest.fixture
def broken_security_store():
    with mock.patch("common.stores.security_store", return_value=BrokenStore()):
        yield


def test_helpers_raise_instead_of_allowing(broken_security_store):
    for call in (lambda: stores.add_once("k", 10), lambda: stores.bump("k", 10), lambda: stores.read("k"), lambda: stores.write("k", 1, 10), lambda: stores.delete("k")):
        with pytest.raises(stores.SecurityStoreUnavailable):
            call()


def test_nonce_is_single_use_in_the_security_store(phone):
    body = phone.token_body()
    assert phone.client.post("/api/v1/device/auth/token/", body, format="json").status_code == 200
    replay = phone.client.post("/api/v1/device/auth/token/", body, format="json")
    assert replay.status_code == 401 and replay.json()["code"] == "replayed_nonce"
    # The nonce lives in the security store, not the evictable cache: clearing the cache changes nothing.
    caches["default"].clear()
    assert phone.client.post("/api/v1/device/auth/token/", body, format="json").json()["code"] == "replayed_nonce"


def test_token_mint_fails_closed_when_nonces_cannot_be_written(phone):
    before = DeviceToken.objects.count()
    with mock.patch("common.stores.security_store", return_value=BrokenStore()):
        response = phone.authenticate()
    assert response.status_code == 503 and response.json()["code"] == "try_later"
    assert DeviceToken.objects.count() == before  # no token issued


def test_enroll_fails_closed_without_burning_the_invite(invite_token):
    from tests.phone import Phone

    invite, token = invite_token()
    phone = Phone()
    with mock.patch("common.stores.security_store", return_value=BrokenStore()):
        for _ in range(6):
            response = phone.enroll(token)
            assert response.status_code == 503 and response.json()["code"] == "try_later"
    invite.refresh_from_db()
    assert invite.state == "active" and invite.failed_attempts == 0
    assert phone.enroll(token).status_code == 201


def test_login_fails_closed_when_lockouts_cannot_be_read(admin):
    client = APIClient()
    with mock.patch("common.stores.security_store", return_value=BrokenStore()):
        response = client.post("/api/v1/auth/login/", {"email": admin.email, "password": "Test-pass-2026!"}, format="json")
    assert response.status_code == 503 and response.json()["code"] == "try_later"
    assert "_auth_user_id" not in client.session


def test_short_code_resolve_fails_closed(db, broken_security_store):
    response = APIClient().post("/api/v1/device/enroll/resolve/", {"code": "ABCD-EFGH"}, format="json")
    assert response.status_code == 503
    assert not EnrollmentInvite.objects.filter(short_code_used_at__isnull=False).exists()


def test_deploy_check_flags_an_evicting_broker(settings):
    from common import checks

    settings.REDIS_URL, settings.REDIS_CACHE_URL = "redis://broker:6379/0", ""
    with mock.patch.object(checks, "_redis_config", return_value={"maxmemory-policy": "allkeys-lru", "appendonly": "no"}):
        ids = {issue.id for issue in checks.check_redis_roles(None)}
    assert ids == {"cm.E003", "cm.W001", "cm.W002"}
    settings.REDIS_CACHE_URL = "redis://cache:6379/0"
    with mock.patch.object(checks, "_redis_config", return_value={"maxmemory-policy": "noeviction", "appendonly": "yes"}):
        assert checks.check_redis_roles(None) == []
    settings.REDIS_URL = ""
    assert [issue.id for issue in checks.check_redis_roles(None)] == ["cm.E001"]
