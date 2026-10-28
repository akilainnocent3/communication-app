"""Auth, CSRF, platforms, audit, threads/search API, stats, error shape."""

import pytest
from django.core.cache import caches
from rest_framework.test import APIClient

from modules.audit.models import AuditEvent
from modules.mail.models import Thread
from modules.platforms.registry import PlatformSpec, registry
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def login(client, email, password=PASSWORD):
    return client.post("/api/v1/auth/login/", {"email": email, "password": password}, format="json")


def test_login_me_logout_and_csrf(admin, mailbox):
    client = APIClient(enforce_csrf_checks=True)
    client.get("/api/v1/auth/csrf/")
    token = client.cookies["cm_csrftoken"].value
    assert login(client, admin.email).status_code == 403  # no CSRF header
    response = client.post("/api/v1/auth/login/", {"email": admin.email, "password": PASSWORD}, format="json", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 200
    me = response.json()
    assert me["user"]["email"] == admin.email and "mail.access" in me["permissions"]
    assert me["platform_data"]["gmail"]["mailboxes"][0]["email"] == mailbox.email
    token = client.cookies["cm_csrftoken"].value
    assert client.post("/api/v1/mail/actions/", {"action": "read", "thread_ids": []}, format="json").status_code == 403
    assert client.post("/api/v1/mail/actions/", {"action": "read", "thread_ids": []}, format="json", HTTP_X_CSRFTOKEN=token).status_code == 200
    assert client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=token).status_code == 204
    assert client.get("/api/v1/auth/me/").status_code == 401


def test_bad_password_error_shape_and_lockout(admin):
    client = APIClient()
    response = login(client, admin.email, "wrong-password")
    assert response.status_code == 400
    assert response.json() == {"code": "invalid_credentials", "detail": "The email or password is not correct.", "errors": {}}
    for _ in range(8):
        login(client, admin.email, "wrong-password")
    assert login(client, admin.email).json()["code"] == "login_locked"
    caches["security"].clear()  # lockouts live in the security store, not the evictable cache
    assert login(client, admin.email).status_code == 200


def test_validation_error_shape(client_for, admin):
    response = client_for(admin).post("/api/v1/settings/offices/", {"name": "X", "code": "x", "colour": "red"}, format="json")
    body = response.json()
    assert response.status_code == 400 and body["code"] == "validation_error" and "colour" in body["errors"]


def test_platforms_registry_and_admin(client_for, superadmin, viewer, roles):
    assert [p["key"] for p in client_for(viewer).get("/api/v1/platforms/").json()] == ["gmail", "sms"]
    # A stub platform exercises the registry (SMS itself is a real platform now).
    registry.register(PlatformSpec(key="calls", name="Calls", permission="mail.access", order=30))
    try:
        assert [p["key"] for p in client_for(viewer).get("/api/v1/platforms/").json()] == ["gmail", "sms", "calls"]
        client = client_for(superadmin)
        client.put("/api/v1/settings/platforms/", [{"key": "calls", "is_enabled": False, "order": 30}, {"key": "gmail", "is_enabled": True, "order": 1}], format="json")
        assert [p["key"] for p in client_for(viewer).get("/api/v1/platforms/").json()] == ["gmail", "sms"]
        assert client_for(viewer).put("/api/v1/settings/platforms/", [], format="json").status_code == 403
    finally:
        registry.unregister("calls")


def test_thread_list_pagination_filters_and_categories(client_for, admin, mailbox):
    client = client_for(admin)
    first = client.get(f"/api/v1/mail/threads/?mailbox={mailbox.pk}&label=ALL").json()
    assert first["total"] == Thread.objects.filter(mailbox=mailbox).exclude(label_ids__overlap=["SPAM", "TRASH"]).exclude(label_ids=["DRAFT"]).count()
    unread = client.get(f"/api/v1/mail/threads/?mailbox={mailbox.pk}&label=INBOX&unread=true").json()["results"]
    assert unread and all(t["is_unread"] for t in unread)
    promos = client.get(f"/api/v1/mail/threads/?mailbox={mailbox.pk}&label=INBOX&category=promotions").json()["results"]
    assert all("CATEGORY_PROMOTIONS" in t["label_ids"] for t in promos)
    primary = client.get(f"/api/v1/mail/threads/?mailbox={mailbox.pk}&label=INBOX&category=primary").json()["results"]
    assert all("CATEGORY_PROMOTIONS" not in t["label_ids"] for t in primary)
    spam = client.get(f"/api/v1/mail/threads/?mailbox={mailbox.pk}&label=SPAM").json()["results"]
    assert all("SPAM" in t["label_ids"] for t in spam)


def test_cursor_pagination_has_no_duplicates(client_for, admin, office):
    from tests.conftest import make_mailbox

    box = make_mailbox(office, "big@test.example", threads=70, seed=5)
    client = client_for(admin)
    page = client.get(f"/api/v1/mail/threads/?mailbox={box.pk}&label=ALL").json()
    ids = [t["id"] for t in page["results"]]
    while page["next_cursor"]:
        page = client.get(f"/api/v1/mail/threads/?mailbox={box.pk}&label=ALL&cursor={page['next_cursor']}").json()
        ids += [t["id"] for t in page["results"]]
    assert len(ids) == len(set(ids)) == Thread.objects.filter(mailbox=box).exclude(label_ids__overlap=["SPAM", "TRASH"]).exclude(label_ids=["DRAFT"]).count()


@pytest.mark.parametrize("query", ["from:neema", "has:attachment", "is:unread", "subject:order", "-is:unread", "older_than:1d", "larger:1k", 'cement', "label:clients", "in:anywhere"])
def test_search_operators_return_matching(client_for, admin, mailbox, query):
    response = client_for(admin).get("/api/v1/mail/threads/", {"mailbox": mailbox.pk, "q": query})
    assert response.status_code == 200
    results = response.json()["results"]
    if query == "has:attachment":
        assert results and all(t["has_attachments"] for t in results)
    if query == "is:unread":
        assert all(t["is_unread"] for t in results)
    if query == "-is:unread":
        assert not any(t["is_unread"] for t in results)


def test_server_search_indexes_results(client_for, admin, mailbox):
    response = client_for(admin).get("/api/v1/mail/threads/server-search/", {"mailbox": mailbox.pk, "q": "quotation"})
    assert response.status_code == 200


def test_open_thread_marks_read_and_audits_unless_peek(client_for, admin, mailbox):
    thread = Thread.objects.filter(mailbox=mailbox, is_unread=True).first()
    client = client_for(admin)
    detail = client.get(f"/api/v1/mail/threads/{thread.pk}/?peek=1").json()
    thread.refresh_from_db()
    assert thread.is_unread and detail["messages"]
    assert not AuditEvent.objects.filter(action="mail.open_thread").exists()
    client.get(f"/api/v1/mail/threads/{thread.pk}/")
    thread.refresh_from_db()
    assert not thread.is_unread
    assert AuditEvent.objects.filter(action="mail.open_thread", target_id=str(thread.pk), actor=admin).exists()


def test_remote_images_hidden_until_requested_or_trusted(client_for, admin, mailbox):
    from modules.mail.providers.fake import FakeMailProvider
    from modules.mail.services.mime import build_mime
    from modules.mail.services.sync import sync_mailbox

    provider = FakeMailProvider(mailbox)
    mime = build_mime(from_addr={"email": "news@shop.example", "name": "Shop"}, to=[{"email": mailbox.email}], subject="Sale", html='<p>Sale</p><img src="https://images.example/banner.png">')
    row = provider._store_mime(mime, mailbox=mailbox, label_ids=["INBOX", "CATEGORY_PROMOTIONS"], thread_id=None)
    provider._bump([row.thread_id])
    sync_mailbox(mailbox.pk)
    thread = Thread.objects.get(mailbox=mailbox, provider_thread_id=row.thread_id)
    client = client_for(admin)
    message = client.get(f"/api/v1/mail/threads/{thread.pk}/?peek=1").json()["messages"][0]
    assert message["remote_images"] == 1 and not message["images_shown"]
    assert ' src="https://' not in message["body_html"]
    shown = client.get(f"/api/v1/mail/threads/{thread.pk}/?peek=1&images=1").json()["messages"][0]
    assert ' src="https://images.example/banner.png"' in shown["body_html"]
    client.post("/api/v1/mail/trusted-senders/", {"email": "news@shop.example"}, format="json")
    assert client.get(f"/api/v1/mail/threads/{thread.pk}/?peek=1").json()["messages"][0]["images_shown"]


def test_labels_crud(client_for, admin, mailbox):
    client = client_for(admin)
    created = client.post("/api/v1/mail/labels/", {"mailbox": mailbox.pk, "name": "Projects", "colour": "#16a765", "text_colour": "#ffffff"}, format="json")
    assert created.status_code == 201
    label = created.json()
    assert client.post("/api/v1/mail/labels/", {"mailbox": mailbox.pk, "name": "Inbox"}, format="json").status_code == 400
    renamed = client.patch(f"/api/v1/mail/labels/{label['id']}/", {"name": "Projects 2026"}, format="json").json()
    assert renamed["name"] == "Projects 2026"
    assert client.delete(f"/api/v1/mail/labels/{label['id']}/").status_code == 204
    system = mailbox.labels.get(provider_label_id="INBOX")
    assert client.delete(f"/api/v1/mail/labels/{system.pk}/").status_code == 400


def test_stats_and_contacts(client_for, admin, mailbox):
    client = client_for(admin)
    stats = client.get("/api/v1/mail/stats/?range=7").json()
    assert len(stats["series"]) == 7 and stats["kpis"]["unread"] >= 0 and stats["mailboxes"][0]["email"] == mailbox.email
    assert client.get("/api/v1/mail/contacts/suggest/?q=ne").status_code == 200


def test_audit_log_admin_only_and_csv(client_for, admin, viewer, mailbox):
    client = client_for(admin)
    thread = Thread.objects.filter(mailbox=mailbox).first()
    client.get(f"/api/v1/mail/threads/{thread.pk}/")
    events = client.get("/api/v1/audit/events/?action=mail.open_thread").json()["results"]
    assert events and events[0]["mailbox_email"] == mailbox.email
    assert client_for(viewer).get("/api/v1/audit/events/").status_code == 403
    response = client.get("/api/v1/audit/events/export/")
    body = b"".join(response.streaming_content).decode()
    assert body.splitlines()[0].startswith("time,actor,action") and "mail.open_thread" in body


def test_audit_events_are_append_only(admin):
    event = AuditEvent.objects.create(action="x")
    event.action = "y"
    with pytest.raises(RuntimeError):
        event.save()
    with pytest.raises(RuntimeError):
        event.delete()


def test_mailbox_lifecycle_invites_status_disconnect(client_for, admin, mailbox):
    client = client_for(admin)
    assert client.get(f"/api/v1/mail/mailboxes/{mailbox.pk}/status/").json()["status"] == "connected"
    assert client.post(f"/api/v1/mail/mailboxes/{mailbox.pk}/sync/").status_code == 202
    response = client.post(f"/api/v1/mail/mailboxes/{mailbox.pk}/disconnect/").json()
    assert response["status"] == "pending"
    assert not Thread.objects.filter(mailbox=mailbox).exists()
    assert AuditEvent.objects.filter(action="mailbox.disconnect").exists()
    assert client.delete(f"/api/v1/mail/mailboxes/{mailbox.pk}/").status_code == 204


def test_integrations_settings(client_for, admin, superadmin, viewer):
    client = client_for(admin)
    assert client.put("/api/v1/settings/integrations/", {"connect_notice": "All access is logged."}, format="json").json()["connect_notice"] == "All access is logged."
    assert client_for(viewer).get("/api/v1/settings/integrations/").status_code == 403
    assert client.get("/api/v1/settings/integrations/workspace/").status_code == 403
    bad = client_for(superadmin).post("/api/v1/settings/integrations/workspace/", {"domain": "company.example", "service_account_json": "{}"}, format="json")
    assert bad.status_code == 400
    key = '{"type": "service_account", "client_id": "123", "private_key": "-----BEGIN PRIVATE KEY-----", "client_email": "sa@p.iam.gserviceaccount.com"}'
    ok = client_for(superadmin).post("/api/v1/settings/integrations/workspace/", {"domain": "Company.example", "service_account_json": key}, format="json").json()
    assert ok["domain"] == "company.example" and ok["client_id"] == "123" and "https://mail.google.com/" in ok["scopes"]
    assert "private_key" not in str(ok)
