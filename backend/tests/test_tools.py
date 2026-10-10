"""Mail tools (signatures, vacation, filters), access management and the mailbox lifecycle services."""

from unittest import mock

import pytest

from modules.audit.models import AuditEvent
from modules.mail.models import Mailbox, MailboxAccess, MailboxStatus, Thread
from modules.mail.services import connect

pytestmark = pytest.mark.django_db


def test_attachment_pdf_preview_still_blocks_scripts(client_for, admin, mailbox):
    message = next(
        m for t in Thread.objects.filter(mailbox=mailbox, has_attachments=True) for m in t.messages.all()
        if any(a.get("mime_type") == "application/pdf" for a in m.attachments)
    )
    pdf = next(a for a in message.attachments if a["mime_type"] == "application/pdf")
    url = f"/api/v1/mail/messages/{message.pk}/attachments/{pdf['id']}/"
    assert "sandbox" in client_for(admin).get(url)["Content-Security-Policy"]
    preview = client_for(admin).get(url + "?preview=1")
    assert preview.status_code == 200 and preview["Content-Disposition"].startswith("inline")
    assert "default-src 'none'" in preview["Content-Security-Policy"]
    download = client_for(admin).get(url + "?download=1")
    assert download["Content-Type"] == "application/octet-stream" and download["Content-Disposition"].startswith("attachment")
    assert "sandbox" in download["Content-Security-Policy"]


def test_signature_is_sanitised_and_needs_manage(client_for, admin, manager, grant, mailbox):
    url = f"/api/v1/mail/settings/{mailbox.pk}/signature/"
    send_as = client_for(admin).get(url).json()
    assert send_as[0]["email"] == mailbox.email
    payload = {"send_as": mailbox.email, "signature": '<p onclick="x()">Asha<script>alert(1)</script></p>'}
    grant(manager, mailbox, can_send=True)
    assert client_for(manager).put(url, payload, format="json").status_code == 403
    response = client_for(admin).put(url, payload, format="json")
    assert response.status_code == 200
    assert "script" not in response.json()["signature"] and "onclick" not in response.json()["signature"]
    assert AuditEvent.objects.filter(action="mail.signature_update", mailbox_id=mailbox.pk).exists()


def test_vacation_validates_dates_and_round_trips(client_for, admin, mailbox):
    url = f"/api/v1/mail/settings/{mailbox.pk}/vacation/"
    bad = {"enable_auto_reply": True, "response_subject": "Away", "start_time": "2026-10-12T00:00:00Z", "end_time": "2026-10-11T00:00:00Z"}
    assert client_for(admin).put(url, bad, format="json").json()["code"] == "validation_error"
    good = {**bad, "end_time": "2026-10-20T00:00:00Z", "response_body_html": "<p>Back soon</p><img src=x onerror=alert(1)>"}
    response = client_for(admin).put(url, good, format="json")
    assert response.status_code == 200
    saved = client_for(admin).get(url).json()
    assert saved["enable_auto_reply"] is True and "onerror" not in saved["response_body_html"]


def test_filters_create_list_delete(client_for, admin, viewer, grant, mailbox):
    url = f"/api/v1/mail/settings/{mailbox.pk}/filters/"
    assert client_for(admin).post(url, {"criteria": {}, "action": {"removeLabelIds": ["INBOX"]}}, format="json").status_code == 400
    assert client_for(admin).post(url, {"criteria": {"from": "spam@x.example"}, "action": {}}, format="json").status_code == 400
    created = client_for(admin).post(url, {"criteria": {"from": "spam@x.example"}, "action": {"addLabelIds": ["TRASH"]}}, format="json")
    assert created.status_code == 201
    filter_id = created.json()["id"]
    assert any(f["id"] == filter_id for f in client_for(admin).get(url).json())
    grant(viewer, mailbox)
    assert client_for(viewer).delete(f"{url}{filter_id}/").status_code == 403
    assert client_for(admin).delete(f"{url}{filter_id}/").status_code == 204
    assert not any(f["id"] == filter_id for f in client_for(admin).get(url).json())
    assert AuditEvent.objects.filter(action="mail.filter_delete").exists()


def test_tools_hidden_from_users_without_access(client_for, viewer, mailbox):
    for path in ("signature", "vacation", "filters", "send-as"):
        assert client_for(viewer).get(f"/api/v1/mail/settings/{mailbox.pk}/{path}/").status_code == 404


def test_access_management(client_for, admin, manager, viewer, grant, mailbox):
    url = f"/api/v1/mail/mailboxes/{mailbox.pk}/access/"
    response = client_for(admin).put(url, [{"user": viewer.pk, "can_send": True}], format="json")
    assert response.status_code == 200
    row = MailboxAccess.objects.get(user=viewer, mailbox=mailbox)
    assert row.can_read and row.can_send and not row.can_manage
    # A mailbox manager can share access but cannot hand out "manage".
    grant(manager, mailbox, can_manage=True)
    entries = [{"user": manager.pk, "can_manage": True}, {"user": viewer.pk, "can_manage": True}]
    assert client_for(manager).put(url, entries, format="json").status_code == 403
    assert client_for(manager).put(url, [{"user": manager.pk, "can_manage": True}], format="json").status_code == 200
    assert not MailboxAccess.objects.filter(user=viewer, mailbox=mailbox).exists()
    assert client_for(viewer).get(url).status_code == 404
    assert client_for(admin).put(url, [{"user": 999999}], format="json").json()["code"] == "validation_error"


def test_add_demo_mailbox_and_duplicate(client_for, admin, office, settings):
    settings.MAIL_ENABLE_FAKE_PROVIDER = True
    payload = {"office": office.pk, "email": "demo@new.example", "display_name": "Demo", "colour": "", "provider": "fake"}
    response = client_for(admin).post("/api/v1/mail/mailboxes/", payload, format="json")
    assert response.status_code == 201
    mailbox = Mailbox.objects.get(email="demo@new.example")
    assert mailbox.status == MailboxStatus.CONNECTED and Thread.objects.filter(mailbox=mailbox).count() > 0
    duplicate = client_for(admin).post("/api/v1/mail/mailboxes/", payload, format="json")
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "mailbox_exists"


def test_microsoft_365_is_refused(client_for, admin, office):
    detection = connect.Detection("unsupported", "Microsoft 365 mailboxes are not supported yet.", "corp.example", ["corp-example.mail.protection.outlook.com"], supported=False)
    with mock.patch.object(connect, "detect", return_value=detection):
        response = client_for(admin).post("/api/v1/mail/mailboxes/", {"office": office.pk, "email": "boss@corp.example", "display_name": "", "colour": ""}, format="json")
    assert response.status_code == 400 and "Microsoft 365" in response.json()["detail"]
    assert not Mailbox.objects.filter(email="boss@corp.example").exists()


def test_delete_mailbox_removes_it_and_audits(client_for, admin, viewer, mailbox):
    assert client_for(viewer).delete(f"/api/v1/mail/mailboxes/{mailbox.pk}/").status_code in (403, 404)
    assert client_for(admin).delete(f"/api/v1/mail/mailboxes/{mailbox.pk}/").status_code == 204
    assert not Mailbox.objects.filter(pk=mailbox.pk).exists()
    assert AuditEvent.objects.filter(action="mailbox.delete").exists()


def test_imap_save_only_stores_working_settings(client_for, admin, office):
    mailbox = Mailbox.objects.create(office=office, email="ceo@hosted.example", provider="imap_smtp", status=MailboxStatus.PENDING)
    server = {"imap_host": "mail.hosted.example", "imap_port": 993, "imap_security": "ssl", "smtp_host": "mail.hosted.example", "smtp_port": 465, "smtp_security": "ssl"}
    url = f"/api/v1/mail/mailboxes/{mailbox.pk}/imap/"
    failing = {"imap": {"ok": False, "detail": "Login failed"}, "smtp": {"ok": True, "detail": ""}}
    with mock.patch("modules.mail.providers.imap_smtp.test_connection", return_value=failing):
        response = client_for(admin).post(url, {**server, "username": "", "password": "secret"}, format="json")
    assert response.status_code == 400 and response.json()["code"] == "connection_failed"
    mailbox.refresh_from_db()
    assert mailbox.status == MailboxStatus.PENDING and not mailbox.encrypted_credentials
    working = {"imap": {"ok": True, "detail": ""}, "smtp": {"ok": True, "detail": ""}}
    with mock.patch("modules.mail.providers.imap_smtp.test_connection", return_value=working), mock.patch("modules.mail.tasks.sync_mailbox_task.delay"):
        response = client_for(admin).post(url, {**server, "username": "", "password": "secret"}, format="json")
    assert response.json()["ok"] is True
    mailbox.refresh_from_db()
    assert mailbox.status == MailboxStatus.CONNECTED and mailbox.encrypted_credentials and "secret" not in mailbox.encrypted_credentials
