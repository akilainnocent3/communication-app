"""Compose, reply threading, undo send, scheduled send, drafts, uploads, templates, notes."""

import email
import email.policy
from datetime import timedelta
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from modules.audit.models import AuditEvent
from modules.mail.models import Draft, FakeMessage, Mailbox, ScheduledEmail, Thread
from modules.mail.providers.fake import FakeMailProvider
from modules.mail.services.send import dispatch_due

pytestmark = pytest.mark.django_db


def incoming_thread(mailbox):
    return Thread.objects.filter(mailbox=mailbox, label_ids__contains=["INBOX", "CATEGORY_PERSONAL"]).order_by("-last_message_at").first()


def test_reply_is_threaded_with_headers(client_for, admin, mailbox):
    thread = incoming_thread(mailbox)
    source = thread.messages.order_by("-date").first()
    captured = {}
    original = FakeMailProvider.send

    def spy(self, mime, thread_id=None):
        captured["mime"], captured["thread"] = mime, thread_id
        return original(self, mime, thread_id)

    with mock.patch.object(FakeMailProvider, "send", spy):
        response = client_for(admin).post("/api/v1/mail/send/", {
            "mailbox": mailbox.pk, "to": [source.from_addr], "subject": f"Re: {thread.subject}", "html": "<p>Thanks</p>",
            "mode": "reply", "in_reply_to_message": source.pk, "undo_seconds": 0,
        }, format="json")
    assert response.status_code == 202
    parsed = email.message_from_bytes(captured["mime"], policy=email.policy.default)
    assert parsed["In-Reply-To"] == source.rfc_message_id
    assert source.rfc_message_id in parsed["References"]
    assert captured["thread"] == thread.provider_thread_id
    thread.refresh_from_db()
    assert thread.messages.filter(is_outgoing=True, subject=f"Re: {thread.subject}").exists()
    assert AuditEvent.objects.filter(action="mail.send", mailbox_id=mailbox.pk).exists()


def test_undo_window_cancel_returns_payload(client_for, admin, mailbox):
    client = client_for(admin)
    response = client.post("/api/v1/mail/send/", {"mailbox": mailbox.pk, "to": [{"email": "x@y.example"}], "subject": "Hi", "html": "<p>Hello</p>", "undo_seconds": 10}, format="json").json()
    assert response["kind"] == "undo" and response["status"] == "pending"
    assert dispatch_due() == 0  # not due yet
    cancelled = client.post(f"/api/v1/mail/send/{response['id']}/cancel/").json()
    assert cancelled["subject"] == "Hi" and cancelled["to"] == [{"email": "x@y.example", "name": ""}]
    ScheduledEmail.objects.filter(pk=response["id"]).update(send_at=timezone.now() - timedelta(seconds=1))
    assert dispatch_due() == 0  # cancelled stays unsent
    assert client.post(f"/api/v1/mail/send/{response['id']}/cancel/").status_code == 409


def test_due_message_is_sent_once(client_for, admin, mailbox):
    response = client_for(admin).post("/api/v1/mail/send/", {"mailbox": mailbox.pk, "to": [{"email": "x@y.example"}], "subject": "Later", "html": "<p>x</p>", "undo_seconds": 5}, format="json").json()
    ScheduledEmail.objects.filter(pk=response["id"]).update(send_at=timezone.now() - timedelta(seconds=1))
    assert dispatch_due() == 1
    assert dispatch_due() == 0
    item = ScheduledEmail.objects.get(pk=response["id"])
    assert item.status == "sent" and item.sent_message_id


def test_scheduled_send_list_reschedule_cancel(client_for, admin, mailbox):
    client = client_for(admin)
    when = timezone.now() + timedelta(days=1)
    body = {"mailbox": mailbox.pk, "to": [{"email": "x@y.example"}], "subject": "Tomorrow", "html": "<p>x</p>", "send_at": when.isoformat()}
    item = client.post("/api/v1/mail/send/", body, format="json").json()
    assert item["kind"] == "scheduled"
    assert [s["id"] for s in client.get("/api/v1/mail/scheduled/").json()] == [item["id"]]
    later = (when + timedelta(hours=2)).isoformat()
    assert client.patch(f"/api/v1/mail/scheduled/{item['id']}/", {"send_at": later}, format="json").status_code == 200
    assert client.delete(f"/api/v1/mail/scheduled/{item['id']}/").status_code == 204
    assert client.get("/api/v1/mail/scheduled/").json() == []
    body["send_at"] = (timezone.now() + timedelta(seconds=5)).isoformat()
    assert client.post("/api/v1/mail/send/", body, format="json").status_code == 400


def test_send_validation(client_for, admin, mailbox):
    client = client_for(admin)
    assert client.post("/api/v1/mail/send/", {"mailbox": mailbox.pk, "subject": "x"}, format="json").status_code == 400
    assert client.post("/api/v1/mail/send/", {"mailbox": mailbox.pk, "to": [{"email": "not-an-email"}]}, format="json").status_code == 400


def test_html_is_sanitised_before_sending(client_for, admin, mailbox):
    client_for(admin).post("/api/v1/mail/send/", {"mailbox": mailbox.pk, "to": [{"email": "x@y.example"}], "subject": "s", "html": "<p onclick='x()'>Hi</p><script>alert(1)</script>", "undo_seconds": 0}, format="json")
    row = FakeMessage.objects.filter(mailbox=mailbox, label_ids__contains=["SENT"], headers__subject="s").get()
    assert "script" not in row.body_html and "onclick" not in row.body_html


def test_send_between_demo_mailboxes_delivers(client_for, admin, mailbox, other_mailbox):
    client_for(admin).post("/api/v1/mail/send/", {"mailbox": mailbox.pk, "to": [{"email": other_mailbox.email}], "subject": "Internal memo", "html": "<p>Hi team</p>", "undo_seconds": 0}, format="json")
    from modules.mail.services.sync import sync_mailbox

    sync_mailbox(other_mailbox.pk)
    assert Thread.objects.filter(mailbox=other_mailbox, subject="Internal memo", is_unread=True, label_ids__contains=["INBOX"]).exists()


def test_attachments_upload_send_and_limits(client_for, admin, mailbox, settings):
    client = client_for(admin)
    upload = client.post("/api/v1/mail/uploads/", {"mailbox": mailbox.pk, "file": SimpleUploadedFile("report.pdf", b"%PDF-1.4 data", content_type="application/pdf")}, format="multipart")
    assert upload.status_code == 201
    blocked = client.post("/api/v1/mail/uploads/", {"mailbox": mailbox.pk, "file": SimpleUploadedFile("run.exe", b"MZ", content_type="application/octet-stream")}, format="multipart")
    assert blocked.status_code == 400
    client.post("/api/v1/mail/send/", {"mailbox": mailbox.pk, "to": [{"email": "x@y.example"}], "subject": "With file", "html": "<p>see attached</p>", "attachment_ids": [upload.json()["id"]], "undo_seconds": 0}, format="json")
    row = FakeMessage.objects.get(mailbox=mailbox, headers__subject="With file")
    assert [a["filename"] for a in row.attachments] == ["report.pdf"]
    settings.MAIL_MAX_ATTACHMENT_BYTES = 5
    big = client.post("/api/v1/mail/uploads/", {"mailbox": mailbox.pk, "file": SimpleUploadedFile("big.pdf", b"0123456789")}, format="multipart")
    assert big.status_code == 400


def test_forward_includes_original_attachments(client_for, admin, mailbox):
    source = next(m for t in Thread.objects.filter(mailbox=mailbox, has_attachments=True) for m in t.messages.all() if m.attachments)
    client_for(admin).post("/api/v1/mail/send/", {
        "mailbox": mailbox.pk, "to": [{"email": "x@y.example"}], "subject": f"Fwd: {source.subject}", "html": "<p>fyi</p>",
        "mode": "forward", "in_reply_to_message": source.pk, "forward_attachment_ids": [source.attachments[0]["id"]], "undo_seconds": 0,
    }, format="json")
    row = FakeMessage.objects.get(mailbox=mailbox, headers__subject=f"Fwd: {source.subject}")
    assert row.attachments[0]["filename"] == source.attachments[0]["filename"]
    assert not row.headers.get("in_reply_to")


def test_drafts_autosave_update_send_deletes_draft(client_for, admin, mailbox):
    client = client_for(admin)
    draft = client.post("/api/v1/mail/drafts/", {"mailbox": mailbox.pk, "to": [{"email": "x@y.example"}], "subject": "Draft 1", "html": "<p>a</p>"}, format="json").json()
    updated = client.patch(f"/api/v1/mail/drafts/{draft['id']}/", {"mailbox": mailbox.pk, "to": [{"email": "x@y.example"}], "subject": "Draft 2", "html": "<p>b</p>"}, format="json").json()
    assert updated["subject"] == "Draft 2" and updated["id"] == draft["id"]
    assert FakeMessage.objects.filter(mailbox=mailbox, draft_id__startswith="r").count() == 1
    client.post("/api/v1/mail/send/", {"mailbox": mailbox.pk, "to": [{"email": "x@y.example"}], "subject": "Draft 2", "html": "<p>b</p>", "draft_id": draft["id"], "undo_seconds": 0}, format="json")
    assert not Draft.objects.filter(pk=draft["id"]).exists()
    assert not FakeMessage.objects.filter(mailbox=mailbox).exclude(draft_id="").exists()


def test_send_as_alias_must_belong_to_mailbox(client_for, admin, mailbox):
    response = client_for(admin).post("/api/v1/mail/send/", {"mailbox": mailbox.pk, "send_as": "ceo@elsewhere.example", "to": [{"email": "x@y.example"}], "subject": "s"}, format="json")
    assert response.status_code == 400


def test_templates_and_notes(client_for, admin, manager, grant, mailbox):
    client = client_for(admin)
    template = client.post("/api/v1/mail/templates/", {"name": "Hello", "subject": "Hi", "body_html": "<p>Dear {{first_name}}</p><script>x</script>"}, format="json").json()
    assert "script" not in template["body_html"] and "{{first_name}}" in template["body_html"]
    grant(manager, mailbox, can_send=True)
    assert client_for(manager).patch(f"/api/v1/mail/templates/{template['id']}/", {"name": "x"}, format="json").status_code == 403
    thread = incoming_thread(mailbox)
    note = client.post(f"/api/v1/mail/threads/{thread.pk}/notes/", {"body": "Called the client, waiting for PO."}, format="json").json()
    assert client.get(f"/api/v1/mail/threads/{thread.pk}/notes/").json()[0]["body"].startswith("Called")
    assert client_for(manager).delete(f"/api/v1/mail/threads/{thread.pk}/notes/{note['id']}/").status_code == 403
    assert client.delete(f"/api/v1/mail/threads/{thread.pk}/notes/{note['id']}/").status_code == 204
    # Notes are never sent to the provider.
    assert not FakeMessage.objects.filter(body_html__contains="waiting for PO").exists()


def test_mailbox_settings_signature_vacation_filters(client_for, admin, viewer, grant, mailbox):
    client = client_for(admin)
    base = f"/api/v1/mail/settings/{mailbox.pk}"
    assert client.put(f"{base}/signature/", {"send_as": mailbox.email, "signature": "<p>Regards</p><img src=x onerror=y>"}, format="json").status_code == 200
    assert "onerror" not in client.get(f"{base}/signature/").json()[0]["signature"]
    vacation = {"enable_auto_reply": True, "response_subject": "Away", "response_body_html": "<p>Back Monday</p>", "restrict_to_contacts": True,
                "start_time": timezone.now().isoformat(), "end_time": (timezone.now() + timedelta(days=3)).isoformat()}
    assert client.put(f"{base}/vacation/", vacation, format="json").json()["enable_auto_reply"] is True
    bad = {**vacation, "end_time": (timezone.now() - timedelta(days=3)).isoformat()}
    assert client.put(f"{base}/vacation/", bad, format="json").status_code == 400
    created = client.post(f"{base}/filters/", {"criteria": {"from": "spam@x.example"}, "action": {"addLabelIds": ["TRASH"]}}, format="json")
    assert created.status_code == 201
    assert client.get(f"{base}/filters/").json()[0]["criteria"] == {"from": "spam@x.example"}
    grant(viewer, mailbox)
    assert client_for(viewer).put(f"{base}/vacation/", vacation, format="json").status_code == 403
    assert client.delete(f"{base}/filters/{created.json()['id']}/").status_code == 204


def test_imap_mailbox_hides_unsupported_features(client_for, admin, office):
    box = Mailbox.objects.create(office=office, email="boss@company.example", provider="imap_smtp")
    caps = client_for(admin).get(f"/api/v1/mail/mailboxes/{box.pk}/").json()["capabilities"]
    assert caps["filters"] is False and caps["vacation"] is False and caps["categories"] is False
