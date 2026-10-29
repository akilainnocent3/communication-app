import pytest
from django.core.cache import caches
from rest_framework.test import APIClient

from modules.identity.models import Office, Role, User
from modules.identity.services import assign_role, ensure_roles
from modules.mail.models import Mailbox, MailboxAccess, MailboxStatus
from modules.mail.services.demo import seed_mailbox
from modules.mail.services.sync import sync_mailbox

PASSWORD = "Test-pass-2026!"


@pytest.fixture(autouse=True)
def _run_on_commit_immediately(monkeypatch):
    """Tests run inside one transaction, so on_commit hooks (queued syncs and sends) would never fire."""
    monkeypatch.setattr("django.db.transaction.on_commit", lambda func, using=None, robust=False: func())


@pytest.fixture(autouse=True)
def _clear_cache():
    for alias in ("default", "security"):
        caches[alias].clear()
    yield
    for alias in ("default", "security"):
        caches[alias].clear()


@pytest.fixture
def roles(db):
    ensure_roles()
    return {r.slug: r for r in Role.objects.all()}


@pytest.fixture
def office(db):
    return Office.objects.create(name="Head Office", code="hq")


@pytest.fixture
def other_office(db):
    return Office.objects.create(name="Arusha", code="arusha", colour="#10b981")


def make_user(email, role, roles):
    user = User.objects.create_user(email=email, password=PASSWORD, full_name=email.split("@")[0].title())
    assign_role(user, roles[role] if role else None)
    return User.objects.get(pk=user.pk)


@pytest.fixture
def superadmin(roles):
    return make_user("super@test.example", Role.SUPER_ADMIN, roles)


@pytest.fixture
def admin(roles):
    return make_user("admin@test.example", Role.ADMIN, roles)


@pytest.fixture
def manager(roles):
    return make_user("manager@test.example", Role.OFFICE_MANAGER, roles)


@pytest.fixture
def viewer(roles):
    return make_user("viewer@test.example", Role.VIEWER, roles)


def make_mailbox(office, email, threads=12, seed=1):
    mailbox = Mailbox.objects.create(office=office, email=email, display_name=email.split("@")[0], provider="fake", status=MailboxStatus.CONNECTED)
    seed_mailbox(mailbox, threads=threads, seed=seed)
    assert sync_mailbox(mailbox.pk, full=True).startswith("ok")
    mailbox.refresh_from_db()
    return mailbox


@pytest.fixture
def mailbox(office):
    return make_mailbox(office, "hq@test.example", threads=15, seed=1)


@pytest.fixture
def other_mailbox(other_office):
    return make_mailbox(other_office, "arusha@test.example", threads=8, seed=2)


@pytest.fixture
def client_for():
    def build(user, csrf=False):
        client = APIClient(enforce_csrf_checks=csrf)
        if user:
            client.force_authenticate(user)
        return client

    return build


@pytest.fixture
def grant():
    def build(user, mailbox, **flags):
        values = {"can_read": True, "can_send": False, "can_delete": False, "can_manage": False, **flags}
        return MailboxAccess.objects.update_or_create(user=user, mailbox=mailbox, defaults=values)[0]

    return build


# --- Devices and SMS -----------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _sms_media_root(tmp_path, settings):
    settings.SMS_MEDIA_ROOT = str(tmp_path / "sms-media")


@pytest.fixture
def invite_token(admin, office):
    from modules.devices.services.enrollment import create_invite

    def build(name="Front desk", target_office=None, **options):
        invite, token = create_invite(admin, name=name, office=target_office or office, options=options)
        return invite, token

    return build


@pytest.fixture
def enrolled(invite_token):
    """An enrolled phone (tests.phone.Phone) with a fresh access token."""
    from tests.phone import Phone

    def build(name="Front desk", target_office=None, **options):
        _, token = invite_token(name=name, target_office=target_office, **options)
        phone = Phone()
        response = phone.enroll(token)
        assert response.status_code == 201, response.json()
        return phone

    return build


@pytest.fixture
def phone(enrolled):
    return enrolled()


@pytest.fixture
def other_phone(enrolled, other_office):
    return enrolled(name="Arusha desk", target_office=other_office)


@pytest.fixture
def device_grant():
    from modules.sms.models import DeviceAccess

    def build(user, device_id, **flags):
        values = {"can_read": True, "can_send": False, "can_manage": False, "can_reveal_sensitive": False, **flags}
        return DeviceAccess.objects.update_or_create(user=user, device_id=device_id, defaults=values)[0]

    return build


# --- Calls ---------------------------------------------------------------------------------------------------


@pytest.fixture
def calls_phone(admin, office):
    """An enrolled OCM Phone (the dialer app: Calls only), optionally on the same handset as an SMS phone (tests.phone.Phone)."""
    from modules.devices.models import Device
    from modules.devices.services.enrollment import create_invite
    from tests.phone import Phone

    def build(name="Front desk", target_office=None, companion=None):
        companion_device = Device.objects.get(pk=companion.device_id) if companion is not None else None
        _, token = create_invite(admin, name=name, office=target_office or office, platform="calls", companion=companion_device)
        phone = Phone()
        assert phone.enroll(token, app="calls").status_code == 201
        return phone

    return build


@pytest.fixture
def calls_grant():
    from modules.calls.models import DeviceAccess

    def build(user, device_id, **flags):
        values = {"can_read": True, "can_assign_callbacks": False, "can_annotate": False, "can_export": False, **flags}
        return DeviceAccess.objects.update_or_create(user=user, device_id=device_id, defaults=values)[0]

    return build
