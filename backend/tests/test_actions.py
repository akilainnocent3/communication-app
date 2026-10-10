"""Bulk actions reach the provider correctly; undo, snooze, labels, assignment, select-all."""

from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone

from modules.audit.models import AuditEvent
from modules.mail.models import Label, SnoozedThread, Thread, ThreadAssignment
from modules.mail.providers.fake import FakeMailProvider
from modules.mail.services.actions import wake_snoozed

pytestmark = pytest.mark.django_db


def inbox(mailbox, n=2):
    return list(Thread.objects.filter(mailbox=mailbox, label_ids__contains=["INBOX"]).order_by("-last_message_at")[:n])


def act(client, action, threads, **extra):
    return client.post("/api/v1/mail/actions/", {"action": action, "thread_ids": [t.pk for t in threads], **extra}, format="json")


@pytest.mark.parametrize(
    "action,method,kwargs",
    [
        ("archive", "modify_threads", {"add": [], "remove": ["INBOX"]}),
        ("read", "modify_threads", {"add": [], "remove": ["UNREAD"]}),
        ("unread", "modify_threads", {"add": ["UNREAD"], "remove": []}),
        ("star", "modify_threads", {"add": ["STARRED"], "remove": []}),
        ("important", "modify_threads", {"add": ["IMPORTANT"], "remove": []}),
        ("trash", "trash_threads", {}),
        ("spam", "mark_spam", {}),
        ("delete_forever", "delete_threads_permanently", {}),
    ],
)
def test_action_calls_provider(client_for, admin, mailbox, action, method, kwargs):
    threads = inbox(mailbox)
    ids = [t.provider_thread_id for t in threads]
    with mock.patch.object(FakeMailProvider, method, autospec=True) as fake:
        response = act(client_for(admin), action, threads)
    assert response.status_code == 200, response.json()
    fake.assert_called_once()
    args = fake.call_args
    assert sorted(args.args[1]) == sorted(ids)
    for key, value in kwargs.items():
        assert list(args.kwargs.get(key, [])) == value


def test_archive_updates_index_and_undo_restores(client_for, admin, mailbox):
    client = client_for(admin)
    threads = inbox(mailbox)
    response = act(client, "archive", threads).json()
    assert all("INBOX" not in t["label_ids"] for t in response["threads"])
    assert not Thread.objects.filter(pk__in=[t.pk for t in threads], label_ids__contains=["INBOX"]).exists()
    undo = client.post("/api/v1/mail/actions/undo/", {"undo_token": response["undo_token"]}, format="json")
    assert undo.status_code == 200
    assert Thread.objects.filter(pk__in=[t.pk for t in threads], label_ids__contains=["INBOX"]).count() == 2
    # Tokens are single use.
    assert client.post("/api/v1/mail/actions/undo/", {"undo_token": response["undo_token"]}, format="json").status_code == 410


def test_trash_undo_and_delete_forever(client_for, admin, mailbox):
    client = client_for(admin)
    thread = inbox(mailbox, 1)[0]
    response = act(client, "trash", [thread]).json()
    thread.refresh_from_db()
    assert "TRASH" in thread.label_ids and "INBOX" not in thread.label_ids
    client.post("/api/v1/mail/actions/undo/", {"undo_token": response["undo_token"]}, format="json")
    thread.refresh_from_db()
    assert "INBOX" in thread.label_ids and "TRASH" not in thread.label_ids
    response = act(client, "delete_forever", [thread]).json()
    assert response["deleted_ids"] == [thread.pk] and response["undo_token"] is None
    assert not Thread.objects.filter(pk=thread.pk).exists()
    assert AuditEvent.objects.filter(action="mail.delete_forever").exists()


def test_labels_add_remove_move(client_for, admin, mailbox):
    client = client_for(admin)
    label = Label.objects.filter(mailbox=mailbox, type=Label.USER).first()
    thread = inbox(mailbox, 1)[0]
    act(client, "remove_labels", [thread], label_ids=[label.provider_label_id])
    act(client, "add_labels", [thread], label_ids=[label.provider_label_id])
    thread.refresh_from_db()
    assert label.provider_label_id in thread.label_ids
    act(client, "move_to_label", [thread], label_ids=[label.provider_label_id])
    thread.refresh_from_db()
    assert "INBOX" not in thread.label_ids
    assert act(client, "add_labels", [thread], label_ids=["Label_nope"]).status_code == 400


def test_labels_cannot_span_mailboxes(client_for, admin, mailbox, other_mailbox):
    label = Label.objects.filter(mailbox=mailbox, type=Label.USER).first()
    response = act(client_for(admin), "add_labels", inbox(mailbox, 1) + inbox(other_mailbox, 1), label_ids=[label.provider_label_id])
    assert response.status_code == 400


def test_snooze_and_wake(client_for, admin, mailbox):
    thread = inbox(mailbox, 1)[0]
    client = client_for(admin)
    assert act(client, "snooze", [thread], until=(timezone.now() - timedelta(minutes=1)).isoformat()).status_code == 400
    response = act(client, "snooze", [thread], until=(timezone.now() + timedelta(hours=3)).isoformat())
    assert response.json()["threads"][0]["snoozed_until"]
    thread.refresh_from_db()
    assert "INBOX" not in thread.label_ids
    listed = client.get(f"/api/v1/mail/threads/?mailbox={mailbox.pk}&label=SNOOZED").json()["results"]
    assert [t["id"] for t in listed] == [thread.pk]
    assert wake_snoozed(timezone.now() + timedelta(hours=4)) == 1
    thread.refresh_from_db()
    assert "INBOX" in thread.label_ids and thread.is_unread
    assert not SnoozedThread.objects.exists()


def test_assign_and_assigned_to_me(client_for, admin, manager, grant, mailbox):
    client = client_for(admin)
    thread = inbox(mailbox, 1)[0]
    assert act(client, "assign", [thread], assignee=manager.pk).status_code == 400  # manager cannot read it yet
    grant(manager, mailbox, can_send=True)
    response = act(client, "assign", [thread], assignee=manager.pk).json()
    assert response["threads"][0]["assignment"]["assignee"]["id"] == manager.pk
    mine = client_for(manager).get(f"/api/v1/mail/threads/?mailbox=all&label=ASSIGNED").json()["results"]
    assert [t["id"] for t in mine] == [thread.pk]
    act(client, "unassign", [thread])
    assert not ThreadAssignment.objects.exists()


def test_select_all_matching(client_for, admin, mailbox):
    client = client_for(admin)
    total = Thread.objects.filter(mailbox=mailbox, label_ids__contains=["INBOX"], is_unread=True).count()
    assert total > 0
    response = client.post("/api/v1/mail/actions/", {"action": "read", "select_all": {"mailbox": str(mailbox.pk), "label": "INBOX", "unread": True}}, format="json")
    assert response.status_code == 200
    assert len(response.json()["threads"]) == total
    assert not Thread.objects.filter(mailbox=mailbox, label_ids__contains=["INBOX"], is_unread=True).exists()


def test_mute_keeps_new_replies_out_of_inbox(client_for, admin, mailbox):
    from modules.mail.services.mime import build_mime
    from modules.mail.services.sync import sync_mailbox

    thread = inbox(mailbox, 1)[0]
    act(client_for(admin), "mute", [thread])
    last = thread.messages.order_by("-date").first()
    # A new reply arrives on the server, labelled INBOX.
    mime = build_mime(from_addr={"email": "someone@x.example", "name": "S"}, to=[{"email": mailbox.email}], subject="Re", html="<p>again</p>", in_reply_to=last.rfc_message_id, references=last.rfc_message_id)
    provider = FakeMailProvider(mailbox)
    row = provider._store_mime(mime, mailbox=mailbox, label_ids=["INBOX", "UNREAD"], thread_id=thread.provider_thread_id)
    provider._bump([row.thread_id])
    sync_mailbox(mailbox.pk)
    thread.refresh_from_db()
    assert thread.is_muted and "INBOX" not in thread.label_ids


def test_unknown_action_rejected(client_for, admin, mailbox):
    assert act(client_for(admin), "explode", inbox(mailbox, 1)).status_code == 400
