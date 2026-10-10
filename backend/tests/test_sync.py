"""Sync engine (fake provider end-to-end) and the Gmail provider's parsing/history handling (mocked API)."""

import base64
from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone

from modules.mail.models import FakeServerState, Mailbox, MailboxStatus, Thread
from modules.mail.providers.base import CursorExpired, ProviderError
from modules.mail.providers.fake import FakeMailProvider
from modules.mail.providers.gmail_api import GmailApiProvider, parse_message, translate_error
from modules.mail.services import ratelimit, sync

pytestmark = pytest.mark.django_db


def test_full_sync_indexes_threads_labels_and_progress(mailbox):
    assert Thread.objects.filter(mailbox=mailbox).count() > 10
    assert mailbox.status == MailboxStatus.CONNECTED and mailbox.history_id and mailbox.last_synced_at
    assert mailbox.labels.filter(provider_label_id="INBOX").exists()
    inbox = mailbox.labels.get(provider_label_id="INBOX")
    assert inbox.threads_total == Thread.objects.filter(mailbox=mailbox, label_ids__contains=["INBOX"]).count()


def test_incremental_sync_picks_up_server_side_changes(mailbox):
    thread = Thread.objects.filter(mailbox=mailbox, label_ids__contains=["INBOX"]).first()
    FakeMailProvider(mailbox).modify_threads([thread.provider_thread_id], add=["STARRED"], remove=["INBOX"])
    assert sync.sync_mailbox(mailbox.pk).startswith("ok:")
    thread.refresh_from_db()
    assert thread.is_starred and "INBOX" not in thread.label_ids


def test_incremental_sync_removes_deleted_threads(mailbox):
    thread = Thread.objects.filter(mailbox=mailbox).first()
    FakeMailProvider(mailbox).delete_threads_permanently([thread.provider_thread_id])
    sync.sync_mailbox(mailbox.pk)
    assert not Thread.objects.filter(pk=thread.pk).exists()


def test_expired_history_falls_back_to_full_resync(mailbox):
    state = FakeServerState.objects.get(mailbox=mailbox)
    state.settings = {**state.settings, "history_floor": state.history_id + 100}
    state.save()
    with pytest.raises(CursorExpired):
        FakeMailProvider(mailbox).sync_incremental(mailbox.history_id)
    with mock.patch.object(sync, "full_sync", wraps=sync.full_sync) as full:
        assert sync.sync_mailbox(mailbox.pk).startswith("ok:")
    full.assert_called_once()


def test_provider_error_sets_error_status_and_recovers(mailbox):
    with mock.patch.object(FakeMailProvider, "sync_incremental", side_effect=ProviderError("boom", "Server unhappy")):
        assert sync.sync_mailbox(mailbox.pk) == "error:boom"
    mailbox.refresh_from_db()
    assert mailbox.status == MailboxStatus.ERROR and "unhappy" in mailbox.sync_error
    assert sync.sync_mailbox(mailbox.pk).startswith("ok")
    mailbox.refresh_from_db()
    assert mailbox.status == MailboxStatus.CONNECTED


def test_sync_lock_prevents_parallel_syncs(mailbox):
    with sync.SyncLock(mailbox.pk) as acquired:
        assert acquired
        assert sync.sync_mailbox(mailbox.pk) == "locked"


def test_disabled_mailbox_is_skipped(mailbox):
    Mailbox.objects.filter(pk=mailbox.pk).update(status=MailboxStatus.DISABLED)
    assert sync.sync_mailbox(mailbox.pk) == "skipped:disabled"


def test_backoff_retries_retryable_errors_only():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ProviderError("rate_limited", retryable=True)
        return "ok"

    assert ratelimit.with_backoff(flaky, sleep=lambda s: None) == "ok" and len(calls) == 3
    with pytest.raises(ProviderError):
        ratelimit.with_backoff(lambda: (_ for _ in ()).throw(ProviderError("bad")), sleep=lambda s: None)


def test_token_bucket_limits_burst(settings):
    settings.MAIL_RATE_PER_SECOND = 1000
    for _ in range(50):
        ratelimit.take_token(999)
    settings.MAIL_RATE_PER_SECOND = 0.001
    ratelimit.take_token(998, cost=0.001)
    with pytest.raises(ProviderError):
        ratelimit.take_token(998, cost=5, max_wait=0.01)


# --- Gmail API provider (no network) ---------------------------------------------------------------------


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


GMAIL_MESSAGE = {
    "id": "m1", "threadId": "t1", "labelIds": ["INBOX", "UNREAD"], "snippet": "Hello &amp; welcome", "internalDate": "1760000000000", "sizeEstimate": 2048,
    "payload": {
        "mimeType": "multipart/mixed", "partId": "",
        "headers": [
            {"name": "From", "value": "Neema <neema@x.example>"}, {"name": "To", "value": "office@gmail.com"},
            {"name": "Subject", "value": "=?UTF-8?B?SGFiYXJp?="}, {"name": "Date", "value": "Thu, 09 Oct 2025 10:00:00 +0300"},
            {"name": "Message-ID", "value": "<abc@x.example>"}, {"name": "List-Unsubscribe", "value": "<https://x.example/u>"},
        ],
        "parts": [
            {"partId": "0", "mimeType": "multipart/alternative", "parts": [
                {"partId": "0.0", "mimeType": "text/plain", "headers": [], "body": {"data": b64("Hello plain")}},
                {"partId": "0.1", "mimeType": "text/html", "headers": [], "body": {"data": b64("<p>Hello <b>html</b></p>")}},
            ]},
            {"partId": "1", "mimeType": "application/pdf", "filename": "invoice.pdf", "headers": [{"name": "Content-Disposition", "value": "attachment"}], "body": {"attachmentId": "ANGjdJ8", "size": 1234}},
            {"partId": "2", "mimeType": "image/png", "filename": "logo.png", "headers": [{"name": "Content-ID", "value": "<logo>"}], "body": {"attachmentId": "XYZ", "size": 100}},
        ],
    },
}


def test_parse_gmail_message_full():
    pm = parse_message(GMAIL_MESSAGE, full=True)
    assert pm.subject == "Habari" and pm.from_addr.email == "neema@x.example" and pm.from_addr.name == "Neema"
    assert pm.body_html == "<p>Hello <b>html</b></p>" and pm.body_text == "Hello plain"
    assert pm.snippet == "Hello & welcome"
    assert [(a.id, a.filename, a.inline) for a in pm.attachments] == [("1", "invoice.pdf", False), ("2", "logo.png", True)]
    assert pm.has_attachments and pm.list_unsubscribe == "<https://x.example/u>"
    assert pm.date.utcoffset() == timedelta(hours=3)


def test_parse_gmail_message_metadata_has_no_body():
    pm = parse_message(GMAIL_MESSAGE, full=False)
    assert pm.body_html is None and pm.body_text is None


class FakeRequest:
    def __init__(self, result):
        self.result = result

    def execute(self, num_retries=0):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def http_error(status, reason=""):
    from googleapiclient.errors import HttpError

    response = mock.Mock(status=status, reason="x")
    content = ('{"error": {"errors": [{"reason": "%s"}], "message": "m"}}' % reason).encode()
    return HttpError(response, content)


def test_translate_errors():
    from google.auth.exceptions import RefreshError

    assert translate_error(RefreshError("invalid_grant")).code == "needs_reconnect"
    assert translate_error(http_error(401)).code == "needs_reconnect"
    assert translate_error(http_error(429)).retryable
    assert translate_error(http_error(403, "userRateLimitExceeded")).retryable
    assert not translate_error(http_error(403, "insufficientPermissions")).retryable
    assert translate_error(http_error(404)).code == "not_found"
    assert translate_error(http_error(503)).retryable


def gmail_provider(mailbox):
    provider = GmailApiProvider(mailbox)
    provider._service = mock.MagicMock()
    return provider


def test_history_404_raises_cursor_expired(mailbox):
    provider = gmail_provider(mailbox)
    provider._service.users().history().list.return_value = FakeRequest(http_error(404))
    with pytest.raises(CursorExpired):
        provider.sync_incremental("123")


def test_history_collects_changed_threads(mailbox):
    provider = gmail_provider(mailbox)
    history = {
        "historyId": "200",
        "history": [
            {"messagesAdded": [{"message": {"id": "m1", "threadId": "t1"}}]},
            {"labelsRemoved": [{"message": {"id": "m2", "threadId": "t2"}, "labelIds": ["INBOX"]}]},
            {"messagesDeleted": [{"message": {"id": "m3", "threadId": "t3"}}]},
        ],
    }
    provider._service.users().history().list.return_value = FakeRequest(history)
    with mock.patch.object(GmailApiProvider, "get_threads", return_value=([], ["t3"])) as get_threads:
        changes = provider.sync_incremental("100")
    get_threads.assert_called_once_with(["t1", "t2", "t3"])
    assert changes.cursor == "200" and changes.deleted_thread_ids == ["t3"]


def test_modify_and_send_call_gmail(mailbox):
    provider = gmail_provider(mailbox)
    users = provider._service.users()
    users.threads().modify.return_value = FakeRequest({})
    provider.modify_threads(["t1", "t2"], add=["STARRED"], remove=["INBOX"])
    calls = users.threads().modify.call_args_list
    assert [c.kwargs["id"] for c in calls[-2:]] == ["t1", "t2"]
    assert calls[-1].kwargs["body"] == {"addLabelIds": ["STARRED"], "removeLabelIds": ["INBOX"]}
    users.messages().send.return_value = FakeRequest({"id": "s1", "threadId": "t1", "labelIds": ["SENT"]})
    sent = provider.send(b"From: a@b\r\n\r\nhi", thread_id="t1")
    body = users.messages().send.call_args.kwargs["body"]
    assert body["threadId"] == "t1" and base64.urlsafe_b64decode(body["raw"]) == b"From: a@b\r\n\r\nhi"
    assert sent.id == "s1"


def test_attachment_download_uses_part_id_lookup(mailbox):
    provider = gmail_provider(mailbox)
    users = provider._service.users()
    users.messages().get.return_value = FakeRequest(GMAIL_MESSAGE)
    users.messages().attachments().get.return_value = FakeRequest({"data": b64("%PDF-1.4")})
    assert provider.get_attachment("m1", "1") == b"%PDF-1.4"
    assert users.messages().attachments().get.call_args.kwargs["id"] == "ANGjdJ8"


def test_body_cache_eviction(client_for, admin, mailbox):
    from modules.mail.tasks import evict_cached_bodies

    thread = Thread.objects.filter(mailbox=mailbox).first()
    client_for(admin).get(f"/api/v1/mail/threads/{thread.pk}/")
    message = thread.messages.first()
    message.refresh_from_db()
    assert message.body_cached_at
    type(message).objects.filter(pk=message.pk).update(body_cached_at=timezone.now() - timedelta(days=30))
    assert evict_cached_bodies() >= 1
    message.refresh_from_db()
    assert message.body_html is None
