"""Gmail API provider (OAuth refresh token per mailbox).

Notes
* Attachment ids exposed to the app are Gmail **part ids** ("1", "1.2"): Gmail's own attachmentId changes
  between requests, so downloads look the current one up by part id.
* Access tokens are cached (encrypted) in the Django cache until shortly before they expire.
* Never log tokens or bodies. Errors become ProviderError subclasses with safe messages.
"""

from __future__ import annotations

import base64
import html as html_lib
import logging
from collections.abc import Iterable
from datetime import UTC, datetime

from django.conf import settings
from django.core.cache import cache

from common.crypto import decrypt_json, encrypt_json

from ..services.mime import _decode, parse_address_list, parse_date, snippet_of
from ..services.ratelimit import take_token
from .base import (
    AttachmentMeta,
    AuthError,
    Capabilities,
    ChangeSet,
    CursorExpired,
    MailProvider,
    NotFound,
    ProviderDraft,
    ProviderError,
    ProviderLabel,
    ProviderMessage,
    ProviderThread,
)

log = logging.getLogger(__name__)

TOKEN_URI = "https://oauth2.googleapis.com/token"
REVOKE_URI = "https://oauth2.googleapis.com/revoke"
METADATA_HEADERS = ["From", "To", "Cc", "Bcc", "Reply-To", "Subject", "Date", "Message-ID", "In-Reply-To", "References", "List-Unsubscribe", "List-Unsubscribe-Post"]
BATCH_SIZE = 50
INLINE_IMAGE_MAX_BYTES = 1_500_000
RETRYABLE_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "backendError", "concurrentLimitExceeded"}


def translate_error(exc: Exception, what: str = "item") -> ProviderError:
    """googleapiclient / google-auth exceptions → ProviderError."""
    from google.auth.exceptions import RefreshError, TransportError
    from googleapiclient.errors import HttpError

    if isinstance(exc, ProviderError):
        return exc
    if isinstance(exc, RefreshError):
        return AuthError("Google access was revoked or expired. Send a reconnect link.")
    if isinstance(exc, TransportError):
        return ProviderError("network", "Could not reach Google. Try again.", retryable=True)
    if isinstance(exc, HttpError):
        code = exc.resp.status
        reason = ""
        try:
            details = exc.error_details if isinstance(exc.error_details, list) else []
            reason = details[0].get("reason", "") if details else ""
        except Exception:  # noqa: BLE001 - best effort
            reason = ""
        if code == 401:
            return AuthError()
        if code == 429 or (code == 403 and reason in RETRYABLE_REASONS) or code >= 500:
            return ProviderError("rate_limited" if code in (403, 429) else "google_unavailable", "Google is busy. Retrying shortly.", retryable=True)
        if code == 404:
            return NotFound(what)
        if code == 403:
            return ProviderError("forbidden", "Google refused this action for this mailbox (missing permission or policy).")
        if code == 400:
            return ProviderError("bad_request", "Google rejected the request.")
    return ProviderError("provider_error", "The mail server returned an unexpected error.")


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _headers(payload: dict) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}


def _walk(part: dict):
    yield part
    for child in part.get("parts", []) or []:
        yield from _walk(child)


def parse_message(raw: dict, full: bool = False) -> ProviderMessage:
    payload = raw.get("payload", {}) or {}
    h = _headers(payload)
    attachments: list[AttachmentMeta] = []
    html_body, text_body = None, None
    for part in _walk(payload):
        mime = part.get("mimeType", "")
        body = part.get("body", {}) or {}
        filename = part.get("filename") or ""
        part_headers = _headers(part)
        disposition = part_headers.get("content-disposition", "").lower()
        content_id = part_headers.get("content-id", "").strip("<> ")
        if mime.startswith("multipart/"):
            continue
        if not filename and not body.get("attachmentId") and mime in ("text/html", "text/plain") and "attachment" not in disposition:
            if full and body.get("data"):
                text = _b64url_decode(body["data"]).decode(_charset(part_headers), "replace")
                if mime == "text/html" and html_body is None:
                    html_body = text
                elif mime == "text/plain" and text_body is None:
                    text_body = text
            continue
        if filename or body.get("attachmentId"):
            inline = bool(content_id) and "attachment" not in disposition and mime.startswith("image/")
            attachments.append(AttachmentMeta(id=part.get("partId") or "0", filename=filename or ("image" if inline else "attachment"), mime_type=mime, size=int(body.get("size") or 0), content_id=content_id, inline=inline))
    internal = datetime.fromtimestamp(int(raw.get("internalDate", "0")) / 1000, tz=UTC)
    return ProviderMessage(
        id=raw["id"],
        thread_id=raw.get("threadId", ""),
        label_ids=list(raw.get("labelIds", [])),
        date=parse_date(h.get("date"), internal) if h.get("date") else internal,
        subject=_decode(h.get("subject", "")),
        snippet=snippet_of(html_lib.unescape(raw.get("snippet", ""))),
        from_addr=(parse_address_list(h.get("from")) or [None])[0],
        to=parse_address_list(h.get("to")),
        cc=parse_address_list(h.get("cc")),
        bcc=parse_address_list(h.get("bcc")),
        reply_to=parse_address_list(h.get("reply-to")),
        rfc_message_id=h.get("message-id", ""),
        in_reply_to=h.get("in-reply-to", ""),
        references=" ".join(h.get("references", "").split()),
        size=int(raw.get("sizeEstimate", 0)),
        attachments=attachments,
        list_unsubscribe=h.get("list-unsubscribe", ""),
        list_unsubscribe_post=h.get("list-unsubscribe-post", ""),
        body_html=html_body if full else None,
        body_text=text_body if full else None,
    )


def _charset(part_headers: dict) -> str:
    content_type = part_headers.get("content-type", "")
    for piece in content_type.split(";"):
        piece = piece.strip()
        if piece.lower().startswith("charset="):
            charset = piece.split("=", 1)[1].strip('"\' ')
            try:
                "".encode(charset)
                return charset
            except LookupError:
                break
    return "utf-8"


def parse_thread(raw: dict, full: bool = False) -> ProviderThread:
    return ProviderThread(id=raw["id"], messages=[parse_message(m, full) for m in raw.get("messages", [])])


class GmailApiProvider(MailProvider):
    key = "gmail_oauth"

    def __init__(self, mailbox):
        super().__init__(mailbox)
        self._service = None

    # --- credentials ----------------------------------------------------------------------------------
    def _token_cache_key(self) -> str:
        return f"gmail-access-token:{self.mailbox.pk}"

    def credentials(self):
        from google.oauth2.credentials import Credentials

        secret = decrypt_json(self.mailbox.encrypted_credentials)
        refresh_token = secret.get("refresh_token")
        if not refresh_token:
            raise AuthError("This mailbox is not connected yet.")
        cached = cache.get(self._token_cache_key())
        token, expiry = None, None
        if cached:
            data = decrypt_json(cached)
            token, expiry = data.get("token"), datetime.fromisoformat(data["expiry"]).replace(tzinfo=None)
        return Credentials(
            token=token, refresh_token=refresh_token, token_uri=TOKEN_URI, client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET, scopes=secret.get("scopes") or None, expiry=expiry,
        )

    def _remember_token(self, creds) -> None:
        if creds.token and creds.expiry:
            ttl = int((creds.expiry - datetime.now(UTC).replace(tzinfo=None)).total_seconds()) - 120
            if ttl > 0:
                cache.set(self._token_cache_key(), encrypt_json({"token": creds.token, "expiry": creds.expiry.isoformat()}), ttl)

    def service(self):
        if self._service is None:
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            creds = self.credentials()
            if not creds.valid:
                try:
                    creds.refresh(Request())
                except Exception as exc:  # noqa: BLE001
                    raise translate_error(exc) from None
                self._remember_token(creds)
            self._service = build("gmail", "v1", credentials=creds, cache_discovery=False, static_discovery=True)
        return self._service

    def _execute(self, request, what: str = "item", cost: float = 1.0):
        take_token(self.mailbox.pk, cost)
        try:
            return request.execute(num_retries=0)
        except Exception as exc:  # noqa: BLE001
            raise translate_error(exc, what) from None

    @property
    def users(self):
        return self.service().users()

    # --- metadata -------------------------------------------------------------------------------------
    def capabilities(self) -> Capabilities:
        return Capabilities()

    def get_profile(self) -> dict:
        return self._execute(self.users.getProfile(userId="me"))

    # --- labels ---------------------------------------------------------------------------------------
    def list_labels(self) -> list[ProviderLabel]:
        data = self._execute(self.users.labels().list(userId="me"))
        result = []
        for item in data.get("labels", []):
            colour = item.get("color", {}) or {}
            result.append(ProviderLabel(
                id=item["id"], name=item["name"], type="system" if item.get("type") == "system" else "user",
                colour=colour.get("backgroundColor", ""), text_colour=colour.get("textColor", ""),
                messages_total=item.get("messagesTotal", 0), messages_unread=item.get("messagesUnread", 0),
                threads_total=item.get("threadsTotal", 0), threads_unread=item.get("threadsUnread", 0),
            ))
        return result

    def _label_body(self, name=None, colour=None, text_colour=None) -> dict:
        body: dict = {}
        if name is not None:
            body.update(name=name, labelListVisibility="labelShow", messageListVisibility="show")
        if colour:
            body["color"] = {"backgroundColor": colour, "textColor": text_colour or "#ffffff"}
        return body

    def create_label(self, name, colour="", text_colour="") -> ProviderLabel:
        try:
            item = self._execute(self.users.labels().create(userId="me", body=self._label_body(name, colour, text_colour)), "label")
        except ProviderError as exc:
            if exc.code == "bad_request":
                raise ProviderError("label_invalid", "Google rejected this label. The name may already exist or the colour is not in Gmail's palette.") from None
            raise
        return ProviderLabel(id=item["id"], name=item["name"], type="user", colour=colour, text_colour=text_colour)

    def update_label(self, label_id, name=None, colour=None, text_colour=None) -> ProviderLabel:
        item = self._execute(self.users.labels().patch(userId="me", id=label_id, body=self._label_body(name, colour, text_colour)), "label")
        c = item.get("color", {}) or {}
        return ProviderLabel(id=item["id"], name=item["name"], type="user", colour=c.get("backgroundColor", ""), text_colour=c.get("textColor", ""))

    def delete_label(self, label_id) -> None:
        self._execute(self.users.labels().delete(userId="me", id=label_id), "label")

    # --- threads --------------------------------------------------------------------------------------
    def list_threads(self, label=None, query="", page_token=None, max_results=50):
        kwargs = {"userId": "me", "maxResults": max_results, "q": query or None, "pageToken": page_token or None, "includeSpamTrash": bool(label in ("SPAM", "TRASH"))}
        if label:
            kwargs["labelIds"] = [label]
        data = self._execute(self.users.threads().list(**{k: v for k, v in kwargs.items() if v is not None}), cost=2)
        return [t["id"] for t in data.get("threads", [])], data.get("nextPageToken")

    def _thread_request(self, thread_id: str, format: str):
        if format == "full":
            return self.users.threads().get(userId="me", id=thread_id, format="full")
        return self.users.threads().get(userId="me", id=thread_id, format="metadata", metadataHeaders=METADATA_HEADERS)

    def get_thread(self, thread_id, format="metadata") -> ProviderThread:
        raw = self._execute(self._thread_request(thread_id, format), "conversation", cost=2)
        thread = parse_thread(raw, full=format == "full")
        if format == "full":
            self._load_inline_images(raw, thread)
        return thread

    def _load_inline_images(self, raw: dict, thread: ProviderThread) -> None:
        by_id = {m["id"]: m for m in raw.get("messages", [])}
        for message in thread.messages:
            for meta in message.attachments:
                if not (meta.inline and meta.content_id and meta.size <= INLINE_IMAGE_MAX_BYTES):
                    continue
                part = next((p for p in _walk(by_id[message.id].get("payload", {})) if p.get("partId") == meta.id), None)
                body = (part or {}).get("body", {})
                data = body.get("data")
                if not data and body.get("attachmentId"):
                    try:
                        data = self._execute(self.users.messages().attachments().get(userId="me", messageId=message.id, id=body["attachmentId"]), "attachment").get("data")
                    except ProviderError:
                        data = None
                if data:
                    message.inline_images[meta.content_id] = f"data:{meta.mime_type};base64,{base64.b64encode(_b64url_decode(data)).decode()}"

    def get_threads(self, thread_ids, format="metadata"):
        """Batched threads.get (≤ 50 per HTTP batch). Rate-limited sub-requests are retried once, one by one."""
        found: dict[str, ProviderThread] = {}
        missing: list[str] = []
        retry: list[str] = []
        ids = list(thread_ids)
        for start in range(0, len(ids), BATCH_SIZE):
            chunk = ids[start : start + BATCH_SIZE]
            take_token(self.mailbox.pk, cost=2 * len(chunk), max_wait=30)

            def callback(request_id, response, exception, _chunk=chunk):
                if exception is None:
                    found[request_id] = parse_thread(response, full=format == "full")
                    return
                error = translate_error(exception, "conversation")
                if isinstance(error, NotFound):
                    missing.append(request_id)
                elif error.retryable:
                    retry.append(request_id)
                else:
                    raise error

            batch = self.service().new_batch_http_request(callback=callback)
            for thread_id in chunk:
                batch.add(self._thread_request(thread_id, format), request_id=thread_id)
            try:
                batch.execute()
            except ProviderError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise translate_error(exc) from None
        for thread_id in retry:
            try:
                found[thread_id] = self.get_thread(thread_id, format)
            except NotFound:
                missing.append(thread_id)
        return [found[t] for t in ids if t in found], missing

    def modify_threads(self, thread_ids, add=(), remove=()) -> None:
        add, remove = list(add), list(remove)
        for thread_id in thread_ids:
            self._execute(self.users.threads().modify(userId="me", id=thread_id, body={"addLabelIds": add, "removeLabelIds": remove}), "conversation", cost=2)

    def trash_threads(self, thread_ids) -> None:
        for thread_id in thread_ids:
            self._execute(self.users.threads().trash(userId="me", id=thread_id), "conversation", cost=2)

    def untrash_threads(self, thread_ids) -> None:
        for thread_id in thread_ids:
            self._execute(self.users.threads().untrash(userId="me", id=thread_id), "conversation", cost=2)
        self.modify_threads(thread_ids, add=["INBOX"])

    def delete_threads_permanently(self, thread_ids) -> None:
        for thread_id in thread_ids:
            self._execute(self.users.threads().delete(userId="me", id=thread_id), "conversation", cost=2)

    def get_attachment(self, message_id, attachment_id) -> bytes:
        raw = self._execute(self.users.messages().get(userId="me", id=message_id, format="full"), "message", cost=1)
        part = next((p for p in _walk(raw.get("payload", {})) if p.get("partId") == attachment_id), None)
        if not part:
            raise NotFound("attachment")
        body = part.get("body", {})
        if body.get("data"):
            return _b64url_decode(body["data"])
        if not body.get("attachmentId"):
            return b""
        data = self._execute(self.users.messages().attachments().get(userId="me", messageId=message_id, id=body["attachmentId"]), "attachment")
        return _b64url_decode(data.get("data", ""))

    def get_raw(self, message_id) -> bytes:
        data = self._execute(self.users.messages().get(userId="me", id=message_id, format="raw"), "message")
        return _b64url_decode(data.get("raw", ""))

    # --- sending & drafts -----------------------------------------------------------------------------
    @staticmethod
    def _raw(mime_bytes: bytes) -> str:
        return base64.urlsafe_b64encode(mime_bytes).decode()

    def send(self, mime_bytes, thread_id=None) -> ProviderMessage:
        body = {"raw": self._raw(mime_bytes)}
        if thread_id:
            body["threadId"] = thread_id
        sent = self._execute(self.users.messages().send(userId="me", body=body), cost=10)
        return ProviderMessage(id=sent["id"], thread_id=sent.get("threadId", ""), label_ids=sent.get("labelIds", []), date=datetime.now(UTC))

    def drafts_list(self) -> list[ProviderDraft]:
        drafts, token = [], None
        while True:
            data = self._execute(self.users.drafts().list(userId="me", maxResults=500, **({"pageToken": token} if token else {})))
            drafts += [ProviderDraft(id=d["id"], message_id=d["message"]["id"], thread_id=d["message"].get("threadId", "")) for d in data.get("drafts", [])]
            token = data.get("nextPageToken")
            if not token or len(drafts) > 2000:
                return drafts

    def _draft_body(self, mime_bytes, thread_id):
        message = {"raw": self._raw(mime_bytes)}
        if thread_id:
            message["threadId"] = thread_id
        return {"message": message}

    def drafts_create(self, mime_bytes, thread_id=None) -> ProviderDraft:
        d = self._execute(self.users.drafts().create(userId="me", body=self._draft_body(mime_bytes, thread_id)), cost=10)
        return ProviderDraft(id=d["id"], message_id=d["message"]["id"], thread_id=d["message"].get("threadId", ""))

    def drafts_update(self, draft_id, mime_bytes, thread_id=None) -> ProviderDraft:
        d = self._execute(self.users.drafts().update(userId="me", id=draft_id, body=self._draft_body(mime_bytes, thread_id)), "draft", cost=10)
        return ProviderDraft(id=d["id"], message_id=d["message"]["id"], thread_id=d["message"].get("threadId", ""))

    def drafts_delete(self, draft_id) -> None:
        self._execute(self.users.drafts().delete(userId="me", id=draft_id), "draft")

    # --- sync -----------------------------------------------------------------------------------------
    def sync_full(self, since, max_threads, on_progress=None):
        cursor = str(self.get_profile().get("historyId", ""))
        ids: list[str] = []
        token = None
        query = f"after:{since.strftime('%Y/%m/%d')}"
        while len(ids) < max_threads:
            data = self._execute(self.users.threads().list(userId="me", q=query, maxResults=min(500, max_threads - len(ids)), includeSpamTrash=True, **({"pageToken": token} if token else {})), cost=2)
            ids += [t["id"] for t in data.get("threads", [])]
            token = data.get("nextPageToken")
            if not token:
                break
        ids = ids[:max_threads]

        def threads() -> Iterable[ProviderThread]:
            total = len(ids)
            if on_progress:
                on_progress(0, total)
            for start in range(0, total, BATCH_SIZE):
                found, _ = self.get_threads(ids[start : start + BATCH_SIZE])
                yield from found
                if on_progress:
                    on_progress(min(start + BATCH_SIZE, total), total)

        return threads(), cursor

    def sync_incremental(self, cursor) -> ChangeSet:
        changed: list[str] = []
        token = None
        latest = cursor
        while True:
            try:
                data = self._execute(self.users.history().list(userId="me", startHistoryId=cursor, maxResults=500, **({"pageToken": token} if token else {})), "history", cost=2)
            except NotFound:
                raise CursorExpired() from None
            latest = data.get("historyId", latest)
            for record in data.get("history", []):
                for key in ("messagesAdded", "messagesDeleted", "labelsAdded", "labelsRemoved"):
                    for item in record.get(key, []):
                        thread_id = item.get("message", {}).get("threadId")
                        if thread_id and thread_id not in changed:
                            changed.append(thread_id)
                for message in record.get("messages", []):
                    if message.get("threadId") and message["threadId"] not in changed:
                        changed.append(message["threadId"])
            token = data.get("nextPageToken")
            if not token:
                break
        found, missing = self.get_threads(changed) if changed else ([], [])
        return ChangeSet(threads=found, deleted_thread_ids=missing, cursor=str(latest), drafts_changed=bool(changed))

    def watch(self, topic_name: str) -> dict:
        return self._execute(self.users.watch(userId="me", body={"topicName": topic_name, "labelFilterBehavior": "include", "labelIds": ["INBOX"]}))

    # --- settings -------------------------------------------------------------------------------------
    def list_send_as(self) -> list[dict]:
        data = self._execute(self.users.settings().sendAs().list(userId="me"))
        return [
            {"email": a["sendAsEmail"], "display_name": a.get("displayName", ""), "is_default": a.get("isDefault", False), "is_primary": a.get("isPrimary", False), "signature": a.get("signature", "")}
            for a in data.get("sendAs", [])
            if a.get("verificationStatus", "accepted") == "accepted" or a.get("isPrimary")
        ]

    def update_signature(self, send_as_email, signature_html) -> dict:
        a = self._execute(self.users.settings().sendAs().patch(userId="me", sendAsEmail=send_as_email, body={"signature": signature_html}), "alias")
        return {"email": a["sendAsEmail"], "display_name": a.get("displayName", ""), "is_default": a.get("isDefault", False), "is_primary": a.get("isPrimary", False), "signature": a.get("signature", "")}

    def filters_list(self) -> list[dict]:
        data = self._execute(self.users.settings().filters().list(userId="me"))
        return [{"id": f["id"], "criteria": f.get("criteria", {}), "action": f.get("action", {})} for f in data.get("filter", [])]

    def filters_create(self, criteria, action) -> dict:
        f = self._execute(self.users.settings().filters().create(userId="me", body={"criteria": criteria, "action": action}), "filter")
        return {"id": f["id"], "criteria": f.get("criteria", {}), "action": f.get("action", {})}

    def filters_delete(self, filter_id) -> None:
        self._execute(self.users.settings().filters().delete(userId="me", id=filter_id), "filter")

    VACATION_KEYS = {
        "enableAutoReply": "enable_auto_reply", "responseSubject": "response_subject", "responseBodyHtml": "response_body_html",
        "restrictToContacts": "restrict_to_contacts", "restrictToDomain": "restrict_to_domain", "startTime": "start_time", "endTime": "end_time",
    }

    def vacation_get(self) -> dict:
        data = self._execute(self.users.settings().getVacation(userId="me"))
        result = {ours: data.get(theirs) for theirs, ours in self.VACATION_KEYS.items()}
        for key in ("start_time", "end_time"):
            if result[key]:
                result[key] = datetime.fromtimestamp(int(result[key]) / 1000, tz=UTC).isoformat()
        return result

    def vacation_set(self, values) -> dict:
        body = {}
        for theirs, ours in self.VACATION_KEYS.items():
            value = values.get(ours)
            if ours in ("start_time", "end_time"):
                if value:
                    moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                    body[theirs] = str(int(moment.timestamp() * 1000))
                continue
            if value is not None:
                body[theirs] = value
        self._execute(self.users.settings().updateVacation(userId="me", body=body))
        return self.vacation_get()

    def revoke(self) -> None:
        import requests

        secret = decrypt_json(self.mailbox.encrypted_credentials) if self.mailbox.encrypted_credentials else {}
        token = secret.get("refresh_token")
        cache.delete(self._token_cache_key())
        if not token:
            return
        try:
            requests.post(REVOKE_URI, data={"token": token}, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=10)
        except requests.RequestException:
            log.warning("token revoke request failed for mailbox %s", self.mailbox.pk)
