"""IMAP + SMTP provider for company mailboxes on non-Google hosting (cPanel, Zoho, Plesk, ...).

Mapping onto the Gmail vocabulary used everywhere else:
* Folders → labels: Inbox=INBOX, Sent=SENT, Drafts=DRAFT, Junk=SPAM, Trash=TRASH, Archive=no system label
  (archived), other folders = user labels `folder:<name>`. A message has exactly one folder.
* Flags: no \\Seen → UNREAD, \\Flagged → STARRED.
* Message id = "<folder>|<uidvalidity>|<uid>". Thread id = hash of the conversation's root Message-ID
  (from References / In-Reply-To), so replies group like Gmail.
* Incremental sync per folder: UIDVALIDITY check, new UIDs above the last seen one, flags of known UIDs,
  and vanished UIDs (deleted or moved).
"""

from __future__ import annotations

import hashlib
import json
import smtplib
import ssl
from collections import defaultdict
from contextlib import contextmanager
from datetime import UTC, datetime

from common.crypto import decrypt_json

from ..services.mime import attachment_bytes, parse_rfc822
from .base import (
    AuthError,
    Capabilities,
    ChangeSet,
    MailProvider,
    NotFound,
    ProviderDraft,
    ProviderError,
    ProviderLabel,
    ProviderMessage,
    ProviderThread,
    Unsupported,
)

SPECIAL_USE = {b"\\Sent": "SENT", b"\\Drafts": "DRAFT", b"\\Junk": "SPAM", b"\\Trash": "TRASH", b"\\Archive": "ARCHIVE"}
COMMON_NAMES = {
    "SENT": ["Sent", "Sent Items", "Sent Messages", "INBOX.Sent"],
    "DRAFT": ["Drafts", "INBOX.Drafts"],
    "SPAM": ["Junk", "Spam", "Junk E-mail", "INBOX.Junk", "INBOX.spam"],
    "TRASH": ["Trash", "Deleted Items", "Deleted Messages", "INBOX.Trash"],
    "ARCHIVE": ["Archive", "INBOX.Archive", "Archives"],
}
HEADER_FIELDS = b"BODY.PEEK[HEADER.FIELDS (FROM TO CC BCC REPLY-TO SUBJECT DATE MESSAGE-ID IN-REPLY-TO REFERENCES LIST-UNSUBSCRIBE LIST-UNSUBSCRIBE-POST CONTENT-TYPE)]"


def thread_key(rfc_message_id: str, in_reply_to: str, references: str) -> str:
    refs = references.split()
    root = refs[0] if refs else (in_reply_to.strip() or rfc_message_id.strip())
    return "t" + hashlib.sha1((root or "").lower().encode()).hexdigest()[:16]


def split_id(message_id: str) -> tuple[str, int, int]:
    folder, validity, uid = message_id.rsplit("|", 2)
    return folder, int(validity), int(uid)


def test_connection(server: dict, username: str, password: str) -> dict:
    """Log in to IMAP and SMTP with these settings. Returns {"imap": ok/msg, "smtp": ok/msg}."""
    result = {"imap": {"ok": False, "message": ""}, "smtp": {"ok": False, "message": ""}}
    try:
        with _imap(server, username, password) as client:
            client.select_folder("INBOX", readonly=True)
        result["imap"] = {"ok": True, "message": "Signed in to incoming mail (IMAP)."}
    except ProviderError as exc:
        result["imap"] = {"ok": False, "message": str(exc)}
    try:
        with _smtp(server, username, password):
            pass
        result["smtp"] = {"ok": True, "message": "Signed in to outgoing mail (SMTP)."}
    except ProviderError as exc:
        result["smtp"] = {"ok": False, "message": str(exc)}
    return result


@contextmanager
def _imap(server: dict, username: str, password: str):
    from imapclient import IMAPClient
    from imapclient.exceptions import LoginError

    host, port = server.get("imap_host"), int(server.get("imap_port") or 993)
    security = server.get("imap_security", "ssl")
    try:
        client = IMAPClient(host, port=port, ssl=security == "ssl", timeout=30, ssl_context=ssl.create_default_context())
        if security == "starttls":
            client.starttls(ssl.create_default_context())
    except (OSError, ssl.SSLError) as exc:
        raise ProviderError("imap_unreachable", f"Could not connect to {host}:{port}. Check the server name and port.", retryable=True) from exc
    try:
        try:
            client.login(username, password)
        except LoginError as exc:
            raise AuthError("The mail server rejected the email or password.") from exc
        yield client
    finally:
        try:
            client.logout()
        except Exception:  # noqa: BLE001
            pass


@contextmanager
def _smtp(server: dict, username: str, password: str):
    host, port = server.get("smtp_host"), int(server.get("smtp_port") or 465)
    security = server.get("smtp_security", "ssl")
    try:
        if security == "ssl":
            client = smtplib.SMTP_SSL(host, port, timeout=30, context=ssl.create_default_context())
        else:
            client = smtplib.SMTP(host, port, timeout=30)
            client.starttls(context=ssl.create_default_context())
    except (OSError, smtplib.SMTPException, ssl.SSLError) as exc:
        raise ProviderError("smtp_unreachable", f"Could not connect to {host}:{port} for sending.", retryable=True) from exc
    try:
        try:
            client.login(username, password)
        except smtplib.SMTPAuthenticationError as exc:
            raise AuthError("The outgoing mail server rejected the email or password.") from exc
        yield client
    finally:
        try:
            client.quit()
        except Exception:  # noqa: BLE001
            pass


class ImapSmtpProvider(MailProvider):
    key = "imap_smtp"

    def __init__(self, mailbox):
        super().__init__(mailbox)
        secret = decrypt_json(mailbox.encrypted_credentials) if mailbox.encrypted_credentials else {}
        self.username = secret.get("username") or mailbox.email
        self.password = secret.get("password", "")
        self.server = mailbox.server_settings or {}
        self._folders: dict[str, str] | None = None

    def capabilities(self) -> Capabilities:
        return Capabilities(labels=False, categories=False, filters=False, vacation=False, signatures=False, send_as=False, important=False, server_search=True, revoke=False)

    @contextmanager
    def client(self):
        if not self.password:
            raise AuthError("This mailbox has no password saved.")
        with _imap(self.server, self.username, self.password) as client:
            yield client

    # --- folders --------------------------------------------------------------------------------------
    def folder_map(self, client) -> dict[str, str]:
        """{label id: folder name} for system folders plus folder:<name> for the rest."""
        if self._folders is not None:
            return self._folders
        folders = client.list_folders()
        names = {name for _, _, name in folders}
        mapping = {"INBOX": "INBOX"}
        for flags, _, name in folders:
            for flag in flags:
                label = SPECIAL_USE.get(flag if isinstance(flag, bytes) else str(flag).encode())
                if label and label not in mapping:
                    mapping[label] = name
        for label, candidates in COMMON_NAMES.items():
            if label not in mapping:
                found = next((c for c in candidates if c in names), None)
                if found:
                    mapping[label] = found
        special = set(mapping.values())
        for flags, _, name in folders:
            if name not in special and b"\\Noselect" not in flags and b"\\NonExistent" not in flags:
                mapping[f"folder:{name}"] = name
        self._folders = mapping
        return mapping

    def _label_for_folder(self, folder: str, mapping: dict[str, str]) -> list[str]:
        for label, name in mapping.items():
            if name == folder:
                return [] if label == "ARCHIVE" else [label]
        return [f"folder:{folder}"]

    def list_labels(self) -> list[ProviderLabel]:
        with self.client() as client:
            mapping = self.folder_map(client)
        labels = [ProviderLabel(id=label, name=label, type="system") for label in ("INBOX", "SENT", "DRAFT", "SPAM", "TRASH", "STARRED", "UNREAD")]
        labels += [ProviderLabel(id=label, name=label.split(":", 1)[1], type="user") for label in mapping if label.startswith("folder:")]
        return labels

    def create_label(self, name, colour="", text_colour="") -> ProviderLabel:
        with self.client() as client:
            client.create_folder(name)
        return ProviderLabel(id=f"folder:{name}", name=name, type="user")

    def delete_label(self, label_id) -> None:
        if not label_id.startswith("folder:"):
            raise Unsupported("Deleting system folders")
        with self.client() as client:
            client.delete_folder(label_id.split(":", 1)[1])

    # --- reading --------------------------------------------------------------------------------------
    def _message_from_fetch(self, folder: str, validity: int, uid: int, data: dict, mapping, full: bool) -> ProviderMessage:
        raw = data.get(b"BODY[]") or b""
        if not raw:
            raw = next((v for k, v in data.items() if isinstance(k, bytes) and k.startswith(b"BODY[HEADER")), b"")
        flags = set(data.get(b"FLAGS", ()))
        labels = self._label_for_folder(folder, mapping)
        if b"\\Seen" not in flags:
            labels.append("UNREAD")
        if b"\\Flagged" in flags:
            labels.append("STARRED")
        internal = data.get(b"INTERNALDATE")
        if isinstance(internal, datetime) and internal.tzinfo is None:
            internal = internal.replace(tzinfo=UTC)
        pm = parse_rfc822(raw, message_id=f"{folder}|{validity}|{uid}", thread_id="", label_ids=labels, internal_date=internal, full=full)
        pm.thread_id = thread_key(pm.rfc_message_id, pm.in_reply_to, pm.references)
        pm.size = int(data.get(b"RFC822.SIZE", pm.size))
        if not full and b"BODYSTRUCTURE" in data:
            pm.attachments = []  # metadata fetch: attachment flag comes from the structure below
            pm.size = int(data.get(b"RFC822.SIZE", 0))
            if _has_attachment(data[b"BODYSTRUCTURE"]):
                from .base import AttachmentMeta

                pm.attachments = [AttachmentMeta(id="?", filename="attachment", mime_type="application/octet-stream", size=0)]
        return pm

    def _fetch(self, client, folder: str, uids: list[int], full: bool, mapping) -> list[ProviderMessage]:
        if not uids:
            return []
        info = client.select_folder(folder, readonly=True)
        validity = int(info.get(b"UIDVALIDITY", 0))
        parts = [b"FLAGS", b"INTERNALDATE", b"RFC822.SIZE"] + ([b"BODY.PEEK[]"] if full else [HEADER_FIELDS, b"BODYSTRUCTURE"])
        result = []
        for start in range(0, len(uids), 200):
            fetched = client.fetch(uids[start : start + 200], parts)
            for uid, data in fetched.items():
                result.append(self._message_from_fetch(folder, validity, uid, data, mapping, full))
        return result

    def _local_messages(self, thread_ids: list[str]):
        from ..models import Message

        return Message.objects.filter(mailbox=self.mailbox, thread__provider_thread_id__in=thread_ids)

    def get_thread(self, thread_id, format="metadata") -> ProviderThread:
        found, _ = self.get_threads([thread_id], format)
        if not found:
            raise NotFound("conversation")
        return found[0]

    def get_threads(self, thread_ids, format="metadata"):
        by_folder: dict[str, list[int]] = defaultdict(list)
        for provider_id in self._local_messages(thread_ids).values_list("provider_message_id", flat=True):
            folder, _, uid = split_id(provider_id)
            by_folder[folder].append(uid)
        grouped: dict[str, list[ProviderMessage]] = defaultdict(list)
        with self.client() as client:
            mapping = self.folder_map(client)
            for folder, uids in by_folder.items():
                for pm in self._fetch(client, folder, uids, format == "full", mapping):
                    grouped[pm.thread_id].append(pm)
        found = [ProviderThread(id=t, messages=grouped[t]) for t in thread_ids if grouped.get(t)]
        return found, [t for t in thread_ids if not grouped.get(t)]

    def list_threads(self, label=None, query="", page_token=None, max_results=50):
        with self.client() as client:
            mapping = self.folder_map(client)
            folder = mapping.get(label or "INBOX", "INBOX")
            client.select_folder(folder, readonly=True)
            criteria = ["TEXT", query] if query else ["ALL"]
            uids = sorted(client.search(criteria, charset="UTF-8"), reverse=True)
            start = int(page_token or 0)
            page = uids[start : start + max_results]
            messages = self._fetch(client, folder, page, False, mapping)
        from ..services import store

        thread_ids = []
        for pm in messages:
            store.apply_thread(self.mailbox, ProviderThread(id=pm.thread_id, messages=[pm], partial=True))
            if pm.thread_id not in thread_ids:
                thread_ids.append(pm.thread_id)
        return thread_ids, (str(start + max_results) if start + max_results < len(uids) else None)

    def get_attachment(self, message_id, attachment_id) -> bytes:
        return attachment_bytes(self.get_raw(message_id), attachment_id)[0]

    def get_raw(self, message_id) -> bytes:
        folder, validity, uid = split_id(message_id)
        with self.client() as client:
            info = client.select_folder(folder, readonly=True)
            if int(info.get(b"UIDVALIDITY", 0)) != validity:
                raise NotFound("message")
            data = client.fetch([uid], [b"BODY.PEEK[]"]).get(uid)
        if not data:
            raise NotFound("message")
        return data[b"BODY[]"]

    # --- changing -------------------------------------------------------------------------------------
    def _uids_by_folder(self, thread_ids) -> dict[str, list[int]]:
        by_folder: dict[str, list[int]] = defaultdict(list)
        for provider_id in self._local_messages(thread_ids).values_list("provider_message_id", flat=True):
            folder, _, uid = split_id(provider_id)
            by_folder[folder].append(uid)
        return by_folder

    def _move(self, client, folder: str, uids: list[int], target: str) -> None:
        if folder == target or not uids:
            return
        client.select_folder(folder)
        if client.has_capability("MOVE"):
            client.move(uids, target)
        else:
            client.copy(uids, target)
            client.delete_messages(uids)
            client.expunge()

    def modify_threads(self, thread_ids, add=(), remove=()) -> None:
        add, remove = list(add), set(remove)
        with self.client() as client:
            mapping = self.folder_map(client)
            for folder, uids in self._uids_by_folder(thread_ids).items():
                client.select_folder(folder)
                if "UNREAD" in remove:
                    client.add_flags(uids, [b"\\Seen"])
                if "UNREAD" in add:
                    client.remove_flags(uids, [b"\\Seen"])
                if "STARRED" in add:
                    client.add_flags(uids, [b"\\Flagged"])
                if "STARRED" in remove:
                    client.remove_flags(uids, [b"\\Flagged"])
                target = None
                for label in add:
                    if label in ("TRASH", "SPAM", "INBOX") or label.startswith("folder:"):
                        target = mapping.get(label) or (label.split(":", 1)[1] if label.startswith("folder:") else None)
                if target is None and "INBOX" in remove and folder == "INBOX":
                    target = mapping.get("ARCHIVE") or self._ensure_archive(client, mapping)
                if target is None and any(label.startswith("folder:") and mapping.get(label) == folder for label in remove):
                    target = "INBOX"
                if target:
                    self._move(client, folder, uids, target)

    def _ensure_archive(self, client, mapping) -> str:
        client.create_folder("Archive")
        mapping["ARCHIVE"] = "Archive"
        return "Archive"

    def delete_threads_permanently(self, thread_ids) -> None:
        with self.client() as client:
            for folder, uids in self._uids_by_folder(thread_ids).items():
                client.select_folder(folder)
                client.delete_messages(uids)
                client.expunge()

    # --- sending & drafts -----------------------------------------------------------------------------
    def send(self, mime_bytes, thread_id=None) -> ProviderMessage:
        import email
        import email.policy
        import email.utils

        message = email.message_from_bytes(mime_bytes, policy=email.policy.SMTP)
        recipients = [addr for header in ("To", "Cc", "Bcc") for _, addr in email.utils.getaddresses(message.get_all(header, []))]
        del message["Bcc"]
        with _smtp(self.server, self.username, self.password) as smtp:
            try:
                smtp.send_message(message, from_addr=self.mailbox.email, to_addrs=recipients)
            except smtplib.SMTPRecipientsRefused as exc:
                raise ProviderError("recipients_refused", "The server refused one or more recipients.") from exc
            except smtplib.SMTPException as exc:
                raise ProviderError("smtp_error", "The outgoing mail server could not send this message.", retryable=True) from exc
        with self.client() as client:
            sent_folder = self.folder_map(client).get("SENT")
            if sent_folder:
                client.append(sent_folder, message.as_bytes(), flags=[b"\\Seen"])
        rfc_id = message.get("Message-ID", "")
        return ProviderMessage(id="", thread_id=thread_key(rfc_id, message.get("In-Reply-To", ""), message.get("References", "")), label_ids=["SENT"], date=datetime.now(UTC))

    def drafts_list(self) -> list[ProviderDraft]:
        with self.client() as client:
            folder = self.folder_map(client).get("DRAFT")
            if not folder:
                return []
            info = client.select_folder(folder, readonly=True)
            validity = int(info.get(b"UIDVALIDITY", 0))
            uids = client.search(["ALL"])
        return [ProviderDraft(id=f"{folder}|{validity}|{uid}", message_id=f"{folder}|{validity}|{uid}") for uid in uids]

    def drafts_create(self, mime_bytes, thread_id=None) -> ProviderDraft:
        with self.client() as client:
            folder = self.folder_map(client).get("DRAFT") or "Drafts"
            response = client.append(folder, mime_bytes, flags=[b"\\Draft", b"\\Seen"])
            info = client.select_folder(folder, readonly=True)
            validity = int(info.get(b"UIDVALIDITY", 0))
            uid = _appended_uid(response) or max(client.search(["ALL"]) or [0])
        draft_id = f"{folder}|{validity}|{uid}"
        return ProviderDraft(id=draft_id, message_id=draft_id, thread_id=thread_id or "")

    def drafts_update(self, draft_id, mime_bytes, thread_id=None) -> ProviderDraft:
        self.drafts_delete(draft_id)
        return self.drafts_create(mime_bytes, thread_id)

    def drafts_delete(self, draft_id) -> None:
        folder, _, uid = split_id(draft_id)
        with self.client() as client:
            client.select_folder(folder)
            client.delete_messages([uid])
            client.expunge()

    # --- sync -----------------------------------------------------------------------------------------
    def _sync_folders(self, mapping) -> list[str]:
        return list(dict.fromkeys(mapping.values()))

    def sync_full(self, since, max_threads, on_progress=None):
        cursor: dict[str, dict] = {}
        messages: list[ProviderMessage] = []
        with self.client() as client:
            mapping = self.folder_map(client)
            folders = self._sync_folders(mapping)
            for folder in folders:
                try:
                    info = client.select_folder(folder, readonly=True)
                except Exception:  # noqa: BLE001 - folder vanished or not selectable
                    continue
                uids = sorted(client.search(["SINCE", since.date()]), reverse=True)[: max_threads * 2]
                cursor[folder] = {"v": int(info.get(b"UIDVALIDITY", 0)), "last": int(max(client.search(["ALL"]) or [0]))}
                messages += self._fetch(client, folder, uids, False, mapping)
                if on_progress:
                    on_progress(folders.index(folder) + 1, len(folders))
        grouped: dict[str, list[ProviderMessage]] = defaultdict(list)
        for pm in messages:
            grouped[pm.thread_id].append(pm)
        ordered = sorted(grouped.items(), key=lambda item: max(m.date for m in item[1]), reverse=True)[:max_threads]
        return [ProviderThread(id=t, messages=ms) for t, ms in ordered], json.dumps(cursor)

    def sync_incremental(self, cursor) -> ChangeSet:
        from ..models import Message

        state = json.loads(cursor or "{}")
        known: dict[str, dict[int, str]] = defaultdict(dict)
        for provider_id in Message.objects.filter(mailbox=self.mailbox).values_list("provider_message_id", flat=True):
            try:
                folder, validity, uid = split_id(provider_id)
            except ValueError:
                continue
            known[folder][uid] = provider_id
        changed: list[ProviderMessage] = []
        deleted: list[str] = []
        with self.client() as client:
            mapping = self.folder_map(client)
            for folder in self._sync_folders(mapping):
                try:
                    info = client.select_folder(folder, readonly=True)
                except Exception:  # noqa: BLE001
                    continue
                validity = int(info.get(b"UIDVALIDITY", 0))
                previous = state.get(folder, {})
                current = set(client.search(["ALL"]))
                if previous.get("v") != validity:
                    deleted += list(known[folder].values())
                    new_uids = sorted(current)[-500:]
                else:
                    new_uids = sorted(uid for uid in current if uid > previous.get("last", 0))
                    deleted += [pid for uid, pid in known[folder].items() if uid not in current]
                    # Flag changes on messages we already have.
                    still = [uid for uid in known[folder] if uid in current]
                    if still:
                        local = {m.provider_message_id: m for m in Message.objects.filter(mailbox=self.mailbox, provider_message_id__in=[known[folder][u] for u in still])}
                        for uid, data in client.fetch(still, [b"FLAGS"]).items():
                            flags = set(data.get(b"FLAGS", ()))
                            row = local.get(known[folder][uid])
                            if not row:
                                continue
                            labels = [x for x in row.label_ids if x not in ("UNREAD", "STARRED")]
                            if b"\\Seen" not in flags:
                                labels.append("UNREAD")
                            if b"\\Flagged" in flags:
                                labels.append("STARRED")
                            if set(labels) != set(row.label_ids):
                                changed.append(_message_from_row(row, labels))
                changed += self._fetch(client, folder, new_uids, False, mapping)
                state[folder] = {"v": validity, "last": max(current or {0})}
        grouped: dict[str, list[ProviderMessage]] = defaultdict(list)
        for pm in changed:
            grouped[pm.thread_id].append(pm)
        threads = [ProviderThread(id=t, messages=ms, partial=True) for t, ms in grouped.items()]
        return ChangeSet(threads=threads, deleted_message_ids=deleted, cursor=json.dumps(state), drafts_changed=bool(changed or deleted))


def _message_from_row(row, labels) -> ProviderMessage:
    from .base import Address, AttachmentMeta

    return ProviderMessage(
        id=row.provider_message_id, thread_id=row.thread.provider_thread_id, label_ids=labels, date=row.date, subject=row.subject,
        snippet=row.snippet, from_addr=Address(**row.from_addr) if row.from_addr else None, to=[Address(**a) for a in row.to],
        cc=[Address(**a) for a in row.cc], rfc_message_id=row.rfc_message_id, in_reply_to=row.in_reply_to, references=row.references,
        size=row.size, attachments=[AttachmentMeta(**a) for a in row.attachments], list_unsubscribe=row.list_unsubscribe,
    )


def _appended_uid(response) -> int | None:
    """Parse `[APPENDUID <validity> <uid>]` from an APPEND response (UIDPLUS servers)."""
    text = response.decode() if isinstance(response, bytes) else str(response or "")
    if "APPENDUID" in text:
        try:
            return int(text.split("APPENDUID", 1)[1].split("]")[0].split()[1])
        except (IndexError, ValueError):
            return None
    return None


def _has_attachment(structure) -> bool:
    """True when a BODYSTRUCTURE contains a part with an attachment disposition or a filename."""
    try:
        if structure.is_multipart:
            return any(_has_attachment(part) for part in structure[0])
    except AttributeError:
        pass
    text = repr(structure).lower()
    return "attachment" in text or "filename" in text
