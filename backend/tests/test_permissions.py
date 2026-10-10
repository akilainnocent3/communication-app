"""The permission matrix: who can see and change which mailbox."""

import pytest

from modules.mail.models import Thread

pytestmark = pytest.mark.django_db


def first_thread(mailbox, **filters):
    return Thread.objects.filter(mailbox=mailbox, **filters).order_by("-last_message_at").first()


def test_admin_sees_every_mailbox(client_for, admin, mailbox, other_mailbox):
    response = client_for(admin).get("/api/v1/mail/mailboxes/")
    assert response.status_code == 200
    assert {m["email"] for m in response.json()} == {mailbox.email, other_mailbox.email}


def test_viewer_without_access_sees_nothing(client_for, viewer, mailbox):
    client = client_for(viewer)
    assert client.get("/api/v1/mail/mailboxes/").json() == []
    assert client.get("/api/v1/mail/threads/?mailbox=all").json()["total"] == 0
    # A mailbox the user cannot read is a 404 (never reveal it exists).
    assert client.get(f"/api/v1/mail/threads/?mailbox={mailbox.pk}").status_code == 404
    thread = first_thread(mailbox)
    assert client.get(f"/api/v1/mail/threads/{thread.pk}/").status_code == 404
    message = thread.messages.first()
    assert client.get(f"/api/v1/mail/messages/{message.pk}/raw/").status_code == 404
    assert client.get(f"/api/v1/mail/threads/{thread.pk}/notes/").status_code == 404
    assert client.get(f"/api/v1/mail/labels/?mailbox={mailbox.pk}").status_code == 404


def test_unified_inbox_only_contains_accessible_mailboxes(client_for, manager, grant, mailbox, other_mailbox):
    grant(manager, other_mailbox, can_send=True)
    results = client_for(manager).get("/api/v1/mail/threads/?mailbox=all&label=INBOX").json()["results"]
    assert results and {t["mailbox"]["id"] for t in results} == {other_mailbox.pk}


def test_read_only_access_can_read_but_not_organise_or_delete(client_for, viewer, grant, mailbox):
    grant(viewer, mailbox)
    client = client_for(viewer)
    thread = first_thread(mailbox, label_ids__contains=["INBOX"])
    assert client.get(f"/api/v1/mail/threads/{thread.pk}/").status_code == 200
    assert client.post("/api/v1/mail/actions/", {"action": "star", "thread_ids": [thread.pk]}, format="json").status_code == 200
    assert client.post("/api/v1/mail/actions/", {"action": "archive", "thread_ids": [thread.pk]}, format="json").status_code == 403
    assert client.post("/api/v1/mail/actions/", {"action": "trash", "thread_ids": [thread.pk]}, format="json").status_code == 403
    assert client.post("/api/v1/mail/actions/", {"action": "delete_forever", "thread_ids": [thread.pk]}, format="json").status_code == 403
    send = client.post("/api/v1/mail/send/", {"mailbox": mailbox.pk, "to": [{"email": "a@b.example"}], "subject": "x", "html": "<p>x</p>"}, format="json")
    assert send.status_code == 403


def test_delete_needs_delete_flag(client_for, manager, grant, mailbox):
    grant(manager, mailbox, can_send=True)
    thread = first_thread(mailbox, label_ids__contains=["INBOX"])
    client = client_for(manager)
    assert client.post("/api/v1/mail/actions/", {"action": "archive", "thread_ids": [thread.pk]}, format="json").status_code == 200
    assert client.post("/api/v1/mail/actions/", {"action": "trash", "thread_ids": [thread.pk]}, format="json").status_code == 403
    grant(manager, mailbox, can_send=True, can_delete=True)
    assert client.post("/api/v1/mail/actions/", {"action": "trash", "thread_ids": [thread.pk]}, format="json").status_code == 200


def test_mixed_selection_with_inaccessible_thread_fails_entirely(client_for, manager, grant, mailbox, other_mailbox):
    grant(manager, mailbox, can_send=True)
    mine = first_thread(mailbox, label_ids__contains=["INBOX"])
    theirs = first_thread(other_mailbox, label_ids__contains=["INBOX"])
    response = client_for(manager).post("/api/v1/mail/actions/", {"action": "archive", "thread_ids": [mine.pk, theirs.pk]}, format="json")
    assert response.status_code == 404
    mine.refresh_from_db()
    assert "INBOX" in mine.label_ids


def test_manage_needed_for_mailbox_admin_endpoints(client_for, manager, grant, mailbox):
    grant(manager, mailbox, can_send=True, can_delete=True)
    client = client_for(manager)
    assert client.patch(f"/api/v1/mail/mailboxes/{mailbox.pk}/", {"display_name": "X"}, format="json").status_code == 403
    assert client.get(f"/api/v1/mail/mailboxes/{mailbox.pk}/access/").status_code == 403
    assert client.post(f"/api/v1/mail/mailboxes/{mailbox.pk}/invites/").status_code == 403
    assert client.delete(f"/api/v1/mail/mailboxes/{mailbox.pk}/").status_code == 403
    grant(manager, mailbox, can_send=True, can_delete=True, can_manage=True)
    assert client.patch(f"/api/v1/mail/mailboxes/{mailbox.pk}/", {"display_name": "X"}, format="json").status_code == 200


def test_mailbox_manager_cannot_hand_out_manage(client_for, manager, viewer, grant, mailbox):
    grant(manager, mailbox, can_manage=True)
    client = client_for(manager)
    payload = [{"user": manager.pk, "can_manage": True}, {"user": viewer.pk, "can_manage": True}]
    assert client.put(f"/api/v1/mail/mailboxes/{mailbox.pk}/access/", payload, format="json").status_code == 403
    payload[1]["can_manage"] = False
    assert client.put(f"/api/v1/mail/mailboxes/{mailbox.pk}/access/", payload, format="json").status_code == 200


def test_only_admins_add_mailboxes(client_for, manager, admin, office):
    body = {"office": office.pk, "email": "new@demo.example", "provider": "fake"}
    assert client_for(manager).post("/api/v1/mail/mailboxes/", body, format="json").status_code == 403
    response = client_for(admin).post("/api/v1/mail/mailboxes/", body, format="json")
    assert response.status_code == 201
    assert response.json()["mailbox"]["status"] == "connected"


def test_user_without_mail_access_is_refused(client_for, roles, mailbox):
    from tests.conftest import make_user

    nobody = make_user("nobody@test.example", None, roles)
    assert client_for(nobody).get("/api/v1/mail/threads/").status_code == 403


def test_anonymous_is_401(client_for, mailbox):
    assert client_for(None).get("/api/v1/mail/threads/").status_code == 401


def test_attachment_requires_access(client_for, admin, viewer, mailbox):
    message = next(m for t in Thread.objects.filter(mailbox=mailbox, has_attachments=True) for m in t.messages.all() if m.attachments)
    attachment = message.attachments[0]
    url = f"/api/v1/mail/messages/{message.pk}/attachments/{attachment['id']}/"
    assert client_for(viewer).get(url).status_code == 404
    response = client_for(admin).get(url)
    assert response.status_code == 200
    assert response["X-Content-Type-Options"] == "nosniff"
    assert "sandbox" in response["Content-Security-Policy"]


def test_login_throttle_keys_on_first_forwarded_address():
    from types import SimpleNamespace

    from common.http import ClientIpScopedThrottle

    throttle = ClientIpScopedThrottle()
    a = SimpleNamespace(META={"HTTP_X_FORWARDED_FOR": "41.59.1.2, 10.0.0.5", "REMOTE_ADDR": "10.0.0.9"})
    b = SimpleNamespace(META={"HTTP_X_FORWARDED_FOR": "41.59.1.2, 10.0.0.6", "REMOTE_ADDR": "10.0.0.9"})
    assert throttle.get_ident(a) == throttle.get_ident(b) == "41.59.1.2"
