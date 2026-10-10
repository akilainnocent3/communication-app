"""Provider interface. Everything Google/IMAP specific stays behind `MailProvider`.

Label ids follow Gmail's vocabulary everywhere (INBOX, SENT, DRAFT, SPAM, TRASH, STARRED, IMPORTANT, UNREAD,
CATEGORY_*). Providers without labels (IMAP) map their folders and flags onto these ids.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime


class ProviderError(Exception):
    """A provider call failed. `code` is stable and safe to show (never contains tokens or bodies)."""

    def __init__(self, code: str, message: str = "", *, retryable: bool = False):
        super().__init__(message or code)
        self.code = code
        self.retryable = retryable


class AuthError(ProviderError):
    """Credentials are no longer valid (invalid_grant, revoked, password changed): the mailbox needs reconnecting."""

    def __init__(self, message: str = "The mailbox needs to be reconnected."):
        super().__init__("needs_reconnect", message)


class CursorExpired(ProviderError):
    """The incremental sync cursor is too old (Gmail history 404): do a full resync."""

    def __init__(self):
        super().__init__("cursor_expired", "Sync cursor expired.")


class NotFound(ProviderError):
    def __init__(self, what: str = "item"):
        super().__init__("not_found", f"The {what} no longer exists on the mail server.")


class Unsupported(ProviderError):
    def __init__(self, feature: str):
        super().__init__("unsupported", f"{feature} is not available for this mailbox.")


@dataclass
class Address:
    email: str
    name: str = ""

    def as_dict(self) -> dict:
        return {"email": self.email, "name": self.name}


@dataclass
class AttachmentMeta:
    id: str
    filename: str
    mime_type: str
    size: int
    content_id: str = ""
    inline: bool = False

    def as_dict(self) -> dict:
        return {"id": self.id, "filename": self.filename, "mime_type": self.mime_type, "size": self.size, "content_id": self.content_id, "inline": self.inline}


@dataclass
class ProviderMessage:
    id: str
    thread_id: str
    label_ids: list[str]
    date: datetime
    subject: str = ""
    snippet: str = ""
    from_addr: Address | None = None
    to: list[Address] = field(default_factory=list)
    cc: list[Address] = field(default_factory=list)
    bcc: list[Address] = field(default_factory=list)
    reply_to: list[Address] = field(default_factory=list)
    rfc_message_id: str = ""
    in_reply_to: str = ""
    references: str = ""
    size: int = 0
    attachments: list[AttachmentMeta] = field(default_factory=list)
    list_unsubscribe: str = ""
    list_unsubscribe_post: str = ""
    # Present only for format="full".
    body_html: str | None = None
    body_text: str | None = None
    # content-id -> data: URI for small inline images (format="full").
    inline_images: dict[str, str] = field(default_factory=dict)

    @property
    def has_attachments(self) -> bool:
        return any(not a.inline for a in self.attachments)


@dataclass
class ProviderThread:
    id: str
    messages: list[ProviderMessage]
    # True when `messages` lists only changed messages (IMAP); False replaces the thread's messages.
    partial: bool = False


@dataclass
class ProviderLabel:
    id: str
    name: str
    type: str = "user"
    colour: str = ""
    text_colour: str = ""
    messages_total: int = 0
    messages_unread: int = 0
    threads_total: int = 0
    threads_unread: int = 0


@dataclass
class ProviderDraft:
    id: str
    message_id: str
    thread_id: str = ""


@dataclass
class ChangeSet:
    threads: list[ProviderThread] = field(default_factory=list)
    deleted_thread_ids: list[str] = field(default_factory=list)
    deleted_message_ids: list[str] = field(default_factory=list)
    cursor: str = ""
    drafts_changed: bool = False


@dataclass
class Capabilities:
    labels: bool = True  # many labels per thread (else: folders, one per message)
    categories: bool = True
    filters: bool = True
    vacation: bool = True
    signatures: bool = True
    send_as: bool = True
    important: bool = True
    server_search: bool = True
    revoke: bool = True

    def as_dict(self) -> dict:
        return dict(self.__dict__)


ProgressCallback = Callable[[int, int], None]


class MailProvider:
    """Base class. Methods raise `Unsupported` unless the provider implements them."""

    key = "base"

    def __init__(self, mailbox):
        self.mailbox = mailbox

    # --- metadata ---
    def capabilities(self) -> Capabilities:
        return Capabilities()

    def get_profile(self) -> dict:
        raise Unsupported("Profile")

    # --- labels ---
    def list_labels(self) -> list[ProviderLabel]:
        raise Unsupported("Labels")

    def create_label(self, name: str, colour: str = "", text_colour: str = "") -> ProviderLabel:
        raise Unsupported("Creating labels")

    def update_label(self, label_id: str, name: str | None = None, colour: str | None = None, text_colour: str | None = None) -> ProviderLabel:
        raise Unsupported("Editing labels")

    def delete_label(self, label_id: str) -> None:
        raise Unsupported("Deleting labels")

    # --- threads & messages ---
    def list_threads(self, label: str | None = None, query: str = "", page_token: str | None = None, max_results: int = 50) -> tuple[list[str], str | None]:
        raise Unsupported("Server search")

    def get_thread(self, thread_id: str, format: str = "metadata") -> ProviderThread:
        raise Unsupported("Reading threads")

    def get_threads(self, thread_ids: list[str], format: str = "metadata") -> tuple[list[ProviderThread], list[str]]:
        """Many threads at once (Gmail: batched). Returns (threads, missing_ids)."""
        found, missing = [], []
        for thread_id in thread_ids:
            try:
                found.append(self.get_thread(thread_id, format))
            except NotFound:
                missing.append(thread_id)
        return found, missing

    def modify_threads(self, thread_ids: list[str], add: Iterable[str] = (), remove: Iterable[str] = ()) -> None:
        raise Unsupported("Changing labels")

    def trash_threads(self, thread_ids: list[str]) -> None:
        self.modify_threads(thread_ids, add=["TRASH"], remove=["INBOX", "SPAM"])

    def untrash_threads(self, thread_ids: list[str]) -> None:
        self.modify_threads(thread_ids, add=["INBOX"], remove=["TRASH"])

    def delete_threads_permanently(self, thread_ids: list[str]) -> None:
        raise Unsupported("Deleting forever")

    def mark_spam(self, thread_ids: list[str]) -> None:
        self.modify_threads(thread_ids, add=["SPAM"], remove=["INBOX"])

    def mark_not_spam(self, thread_ids: list[str]) -> None:
        self.modify_threads(thread_ids, add=["INBOX"], remove=["SPAM"])

    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        raise Unsupported("Attachments")

    def get_raw(self, message_id: str) -> bytes:
        raise Unsupported("Show original")

    # --- sending & drafts ---
    def send(self, mime_bytes: bytes, thread_id: str | None = None) -> ProviderMessage:
        raise Unsupported("Sending")

    def drafts_list(self) -> list[ProviderDraft]:
        raise Unsupported("Drafts")

    def drafts_create(self, mime_bytes: bytes, thread_id: str | None = None) -> ProviderDraft:
        raise Unsupported("Drafts")

    def drafts_update(self, draft_id: str, mime_bytes: bytes, thread_id: str | None = None) -> ProviderDraft:
        raise Unsupported("Drafts")

    def drafts_delete(self, draft_id: str) -> None:
        raise Unsupported("Drafts")

    # --- sync ---
    def sync_full(self, since: datetime, max_threads: int, on_progress: ProgressCallback | None = None) -> tuple[Iterable[ProviderThread], str]:
        """Returns (threads, cursor). `cursor` is taken *before* listing so nothing is missed."""
        raise Unsupported("Sync")

    def sync_incremental(self, cursor: str) -> ChangeSet:
        raise Unsupported("Sync")

    def watch(self, topic_name: str) -> dict:
        """Hook for Gmail push notifications (Pub/Sub users.watch). Optional; polling works without it."""
        raise Unsupported("Push notifications")

    # --- settings ---
    def list_send_as(self) -> list[dict]:
        return [{"email": self.mailbox.email, "display_name": self.mailbox.display_name, "is_default": True, "is_primary": True, "signature": ""}]

    def update_signature(self, send_as_email: str, signature_html: str) -> dict:
        raise Unsupported("Signatures")

    def filters_list(self) -> list[dict]:
        raise Unsupported("Filters")

    def filters_create(self, criteria: dict, action: dict) -> dict:
        raise Unsupported("Filters")

    def filters_delete(self, filter_id: str) -> None:
        raise Unsupported("Filters")

    def vacation_get(self) -> dict:
        raise Unsupported("Vacation responder")

    def vacation_set(self, settings: dict) -> dict:
        raise Unsupported("Vacation responder")

    def revoke(self) -> None:
        """Revoke the stored credential at the provider (disconnect)."""
        return None
