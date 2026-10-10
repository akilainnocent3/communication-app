"""A realistic in-database mail server, so the whole product works without Google credentials.

It mimics Gmail's model: threads, label ids, monotonically increasing history ids, drafts and settings.
Mail sent to another demo mailbox is delivered to that mailbox's inbox, which makes demos feel alive.
"""

from __future__ import annotations

import base64
import secrets
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime

from django.db import transaction
from django.db.models import Max, Q

from ..models import FakeHistory, FakeMessage, FakeServerState, Mailbox
from ..services.mime import build_mime, parse_rfc822, snippet_of, html_to_text
from .base import (
    Address,
    AttachmentMeta,
    Capabilities,
    ChangeSet,
    CursorExpired,
    MailProvider,
    NotFound,
    ProviderDraft,
    ProviderLabel,
    ProviderMessage,
    ProviderThread,
)

SYSTEM_LABELS = [
    "INBOX", "SENT", "DRAFT", "SPAM", "TRASH", "STARRED", "IMPORTANT", "UNREAD",
    "CATEGORY_PERSONAL", "CATEGORY_SOCIAL", "CATEGORY_PROMOTIONS", "CATEGORY_UPDATES", "CATEGORY_FORUMS",
]


def new_id() -> str:
    return secrets.token_hex(8)


class FakeMailProvider(MailProvider):
    key = "fake"

    def __init__(self, mailbox: Mailbox):
        super().__init__(mailbox)

    # --- internals -----------------------------------------------------------------------------------
    def _state(self) -> FakeServerState:
        state, _ = FakeServerState.objects.get_or_create(mailbox=self.mailbox)
        return state

    def _bump(self, thread_ids: Iterable[str], deleted: bool = False) -> int:
        state = FakeServerState.objects.select_for_update().get_or_create(mailbox=self.mailbox)[0]
        thread_ids = list(dict.fromkeys(thread_ids))
        state.history_id += 1
        state.save(update_fields=["history_id"])
        FakeHistory.objects.bulk_create([FakeHistory(mailbox=self.mailbox, history_id=state.history_id, thread_id=t, deleted=deleted) for t in thread_ids])
        return state.history_id

    def _messages(self, thread_ids: Iterable[str]):
        return FakeMessage.objects.filter(mailbox=self.mailbox, thread_id__in=list(thread_ids)).order_by("internal_date", "id")

    def _to_provider(self, row: FakeMessage, full: bool) -> ProviderMessage:
        h = row.headers
        attachments = [AttachmentMeta(id=a["id"], filename=a["filename"], mime_type=a["mime_type"], size=a["size"], content_id=a.get("content_id", ""), inline=a.get("inline", False)) for a in row.attachments]
        inline_images = {}
        if full:
            for a in row.attachments:
                if a.get("inline") and a.get("content_id"):
                    inline_images[a["content_id"]] = f"data:{a['mime_type']};base64,{a['data']}"
        addr = lambda items: [Address(**item) for item in items or []]  # noqa: E731
        return ProviderMessage(
            id=row.message_id,
            thread_id=row.thread_id,
            label_ids=list(row.label_ids),
            date=row.internal_date,
            subject=h.get("subject", ""),
            snippet=snippet_of(row.body_text or html_to_text(row.body_html)),
            from_addr=Address(**h["from"]) if h.get("from") else None,
            to=addr(h.get("to")),
            cc=addr(h.get("cc")),
            bcc=addr(h.get("bcc")),
            reply_to=addr(h.get("reply_to")),
            rfc_message_id=h.get("message_id", ""),
            in_reply_to=h.get("in_reply_to", ""),
            references=h.get("references", ""),
            size=len(row.body_html or "") + len(row.body_text or "") + sum(a["size"] for a in row.attachments),
            attachments=attachments,
            list_unsubscribe=h.get("list_unsubscribe", ""),
            list_unsubscribe_post=h.get("list_unsubscribe_post", ""),
            body_html=row.body_html if full else None,
            body_text=row.body_text if full else None,
            inline_images=inline_images,
        )

    def _thread(self, rows: list[FakeMessage], full: bool) -> ProviderThread:
        return ProviderThread(id=rows[0].thread_id, messages=[self._to_provider(r, full) for r in rows])

    # --- metadata -------------------------------------------------------------------------------------
    def capabilities(self) -> Capabilities:
        return Capabilities(revoke=False)

    def get_profile(self) -> dict:
        return {"emailAddress": self.mailbox.email, "historyId": str(self._state().history_id)}

    # --- labels ---------------------------------------------------------------------------------------
    def list_labels(self) -> list[ProviderLabel]:
        labels = [ProviderLabel(id=label, name=label, type="system") for label in SYSTEM_LABELS]
        labels += [ProviderLabel(id=item["id"], name=item["name"], type="user", colour=item.get("colour", ""), text_colour=item.get("text_colour", "")) for item in self._state().labels]
        return labels

    @transaction.atomic
    def create_label(self, name: str, colour: str = "", text_colour: str = "") -> ProviderLabel:
        state = FakeServerState.objects.select_for_update().get_or_create(mailbox=self.mailbox)[0]
        if any(item["name"].lower() == name.lower() for item in state.labels):
            from .base import ProviderError

            raise ProviderError("label_exists", "A label with this name already exists.")
        item = {"id": f"Label_{new_id()}", "name": name, "colour": colour, "text_colour": text_colour}
        state.labels = [*state.labels, item]
        state.save(update_fields=["labels"])
        return ProviderLabel(id=item["id"], name=name, type="user", colour=colour, text_colour=text_colour)

    @transaction.atomic
    def update_label(self, label_id, name=None, colour=None, text_colour=None) -> ProviderLabel:
        state = FakeServerState.objects.select_for_update().get(mailbox=self.mailbox)
        for item in state.labels:
            if item["id"] == label_id:
                if name is not None:
                    item["name"] = name
                if colour is not None:
                    item["colour"] = colour
                if text_colour is not None:
                    item["text_colour"] = text_colour
                state.save(update_fields=["labels"])
                return ProviderLabel(id=label_id, name=item["name"], type="user", colour=item.get("colour", ""), text_colour=item.get("text_colour", ""))
        raise NotFound("label")

    @transaction.atomic
    def delete_label(self, label_id: str) -> None:
        state = FakeServerState.objects.select_for_update().get(mailbox=self.mailbox)
        state.labels = [item for item in state.labels if item["id"] != label_id]
        state.save(update_fields=["labels"])
        touched = set()
        for row in FakeMessage.objects.filter(mailbox=self.mailbox, label_ids__contains=[label_id]):
            row.label_ids = [x for x in row.label_ids if x != label_id]
            row.save(update_fields=["label_ids"])
            touched.add(row.thread_id)
        if touched:
            self._bump(touched)

    # --- threads --------------------------------------------------------------------------------------
    def list_threads(self, label=None, query="", page_token=None, max_results=50):
        qs = FakeMessage.objects.filter(mailbox=self.mailbox)
        if label:
            qs = qs.filter(label_ids__contains=[label])
        for word in (query or "").split():
            if ":" in word:
                continue  # operators are handled by the local index; the fake searches plain words
            qs = qs.filter(Q(headers__subject__icontains=word) | Q(body_text__icontains=word) | Q(body_html__icontains=word) | Q(headers__from__email__icontains=word))
        ids = list(qs.values("thread_id").annotate(last=Max("internal_date")).order_by("-last").values_list("thread_id", flat=True))
        start = int(page_token or 0)
        page = ids[start : start + max_results]
        return page, (str(start + max_results) if start + max_results < len(ids) else None)

    def get_thread(self, thread_id: str, format: str = "metadata") -> ProviderThread:
        rows = list(self._messages([thread_id]))
        if not rows:
            raise NotFound("conversation")
        return self._thread(rows, format == "full")

    def get_threads(self, thread_ids, format="metadata"):
        grouped = defaultdict(list)
        for row in self._messages(thread_ids):
            grouped[row.thread_id].append(row)
        found = [self._thread(grouped[t], format == "full") for t in thread_ids if grouped.get(t)]
        missing = [t for t in thread_ids if not grouped.get(t)]
        return found, missing

    @transaction.atomic
    def modify_threads(self, thread_ids, add=(), remove=()) -> None:
        add, remove = list(add), set(remove)
        rows = list(self._messages(thread_ids).select_for_update())
        for row in rows:
            labels = [x for x in row.label_ids if x not in remove]
            for label in add:
                if label not in labels:
                    labels.append(label)
            if labels != row.label_ids:
                row.label_ids = labels
                row.save(update_fields=["label_ids"])
        if rows:
            self._bump(thread_ids)

    @transaction.atomic
    def delete_threads_permanently(self, thread_ids) -> None:
        self._messages(thread_ids).delete()
        self._bump(thread_ids, deleted=True)

    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        row = FakeMessage.objects.filter(mailbox=self.mailbox, message_id=message_id).first()
        if not row:
            raise NotFound("message")
        for item in row.attachments:
            if item["id"] == attachment_id:
                return base64.b64decode(item["data"])
        raise NotFound("attachment")

    def get_raw(self, message_id: str) -> bytes:
        row = FakeMessage.objects.filter(mailbox=self.mailbox, message_id=message_id).first()
        if not row:
            raise NotFound("message")
        h = row.headers
        return build_mime(
            from_addr=h.get("from") or {"email": self.mailbox.email, "name": ""},
            to=h.get("to", []), cc=h.get("cc", []), subject=h.get("subject", ""), html=row.body_html, text=row.body_text or None,
            in_reply_to=h.get("in_reply_to", ""), references=h.get("references", ""), message_id=h.get("message_id") or None,
            attachments=[(a["filename"], a["mime_type"], base64.b64decode(a["data"])) for a in row.attachments],
        )

    # --- sending & drafts -----------------------------------------------------------------------------
    def _store_mime(self, mime_bytes: bytes, *, mailbox: Mailbox, label_ids: list[str], thread_id: str | None, draft_id: str = "") -> FakeMessage:
        message_id = new_id()
        parsed = parse_rfc822(mime_bytes, message_id=message_id, thread_id=thread_id or "", label_ids=label_ids)
        if not thread_id:
            thread_id = self._thread_for(mailbox, parsed) or message_id
        attachments = []
        import email as email_lib
        import email.policy

        from ..services.mime import _walk_parts

        msg = email_lib.message_from_bytes(mime_bytes, policy=email.policy.default)
        by_id = {pid: part for pid, part in _walk_parts(msg)}
        for meta in parsed.attachments:
            data = by_id[meta.id].get_payload(decode=True) or b""
            attachments.append({**meta.as_dict(), "data": base64.b64encode(data).decode()})
        row = FakeMessage.objects.create(
            mailbox=mailbox,
            message_id=message_id,
            thread_id=thread_id,
            draft_id=draft_id,
            label_ids=label_ids,
            headers={
                "subject": parsed.subject,
                "from": parsed.from_addr.as_dict() if parsed.from_addr else None,
                "to": [a.as_dict() for a in parsed.to],
                "cc": [a.as_dict() for a in parsed.cc],
                "bcc": [a.as_dict() for a in parsed.bcc],
                "message_id": parsed.rfc_message_id,
                "in_reply_to": parsed.in_reply_to,
                "references": parsed.references,
            },
            body_html=parsed.body_html or "",
            body_text=parsed.body_text or "",
            attachments=attachments,
            internal_date=datetime.now(UTC),
        )
        return row

    @staticmethod
    def _thread_for(mailbox: Mailbox, parsed: ProviderMessage) -> str | None:
        """Gmail threads a reply by its In-Reply-To/References headers: do the same."""
        refs = [r for r in (parsed.references.split() + [parsed.in_reply_to]) if r]
        if not refs:
            return None
        row = FakeMessage.objects.filter(mailbox=mailbox, headers__message_id__in=refs).order_by("internal_date").first()
        return row.thread_id if row else None

    @transaction.atomic
    def send(self, mime_bytes: bytes, thread_id: str | None = None) -> ProviderMessage:
        row = self._store_mime(mime_bytes, mailbox=self.mailbox, label_ids=["SENT"], thread_id=thread_id)
        self._bump([row.thread_id])
        self._deliver_locally(mime_bytes, row)
        return self._to_provider(row, full=False)

    def _deliver_locally(self, mime_bytes: bytes, sent: FakeMessage) -> None:
        recipients = {a["email"].lower() for key in ("to", "cc", "bcc") for a in sent.headers.get(key) or []}
        for other in Mailbox.objects.filter(provider="fake", email__in=recipients).exclude(pk=self.mailbox.pk):
            provider = FakeMailProvider(other)
            row = provider._store_mime(mime_bytes, mailbox=other, label_ids=["INBOX", "UNREAD", "CATEGORY_PERSONAL", "IMPORTANT"], thread_id=None)
            provider._bump([row.thread_id])

    def drafts_list(self) -> list[ProviderDraft]:
        return [ProviderDraft(id=r.draft_id, message_id=r.message_id, thread_id=r.thread_id) for r in FakeMessage.objects.filter(mailbox=self.mailbox).exclude(draft_id="")]

    @transaction.atomic
    def drafts_create(self, mime_bytes: bytes, thread_id: str | None = None) -> ProviderDraft:
        draft_id = f"r{new_id()}"
        row = self._store_mime(mime_bytes, mailbox=self.mailbox, label_ids=["DRAFT"], thread_id=thread_id, draft_id=draft_id)
        self._bump([row.thread_id])
        return ProviderDraft(id=draft_id, message_id=row.message_id, thread_id=row.thread_id)

    @transaction.atomic
    def drafts_update(self, draft_id: str, mime_bytes: bytes, thread_id: str | None = None) -> ProviderDraft:
        old = FakeMessage.objects.filter(mailbox=self.mailbox, draft_id=draft_id).first()
        if not old:
            raise NotFound("draft")
        old_thread = old.thread_id
        old.delete()
        row = self._store_mime(mime_bytes, mailbox=self.mailbox, label_ids=["DRAFT"], thread_id=thread_id or old_thread, draft_id=draft_id)
        self._bump({old_thread, row.thread_id})
        return ProviderDraft(id=draft_id, message_id=row.message_id, thread_id=row.thread_id)

    @transaction.atomic
    def drafts_delete(self, draft_id: str) -> None:
        row = FakeMessage.objects.filter(mailbox=self.mailbox, draft_id=draft_id).first()
        if not row:
            raise NotFound("draft")
        thread_id = row.thread_id
        row.delete()
        self._bump([thread_id])

    # --- sync -----------------------------------------------------------------------------------------
    def sync_full(self, since, max_threads, on_progress=None):
        cursor = str(self._state().history_id)
        ids = list(
            FakeMessage.objects.filter(mailbox=self.mailbox, internal_date__gte=since)
            .values("thread_id").annotate(last=Max("internal_date")).order_by("-last").values_list("thread_id", flat=True)[:max_threads]
        )

        def threads():
            total = len(ids)
            for start in range(0, total, 50):
                found, _ = self.get_threads(ids[start : start + 50])
                yield from found
                if on_progress:
                    on_progress(min(start + 50, total), total)

        return threads(), cursor

    def sync_incremental(self, cursor: str) -> ChangeSet:
        state = self._state()
        start = int(cursor or 0)
        floor = int(state.settings.get("history_floor", 0))
        if start < floor:
            raise CursorExpired()
        rows = list(FakeHistory.objects.filter(mailbox=self.mailbox, history_id__gt=start).values_list("thread_id", flat=True).distinct())
        found, missing = self.get_threads(rows)
        return ChangeSet(threads=found, deleted_thread_ids=missing, cursor=str(state.history_id), drafts_changed=bool(rows))

    # --- settings -------------------------------------------------------------------------------------
    def _settings(self) -> dict:
        return self._state().settings

    def _save_settings(self, **values) -> dict:
        state = self._state()
        state.settings = {**state.settings, **values}
        state.save(update_fields=["settings"])
        return state.settings

    def list_send_as(self) -> list[dict]:
        s = self._settings()
        aliases = s.get("send_as") or [{"email": self.mailbox.email, "display_name": self.mailbox.name, "is_default": True, "is_primary": True}]
        signatures = s.get("signatures", {})
        return [{**alias, "signature": signatures.get(alias["email"], "")} for alias in aliases]

    def update_signature(self, send_as_email: str, signature_html: str) -> dict:
        signatures = {**self._settings().get("signatures", {}), send_as_email: signature_html}
        self._save_settings(signatures=signatures)
        return next(a for a in self.list_send_as() if a["email"] == send_as_email)

    def filters_list(self) -> list[dict]:
        return list(self._settings().get("filters", []))

    def filters_create(self, criteria: dict, action: dict) -> dict:
        item = {"id": f"F{new_id()}", "criteria": criteria, "action": action}
        self._save_settings(filters=[*self.filters_list(), item])
        return item

    def filters_delete(self, filter_id: str) -> None:
        items = self.filters_list()
        if not any(f["id"] == filter_id for f in items):
            raise NotFound("filter")
        self._save_settings(filters=[f for f in items if f["id"] != filter_id])

    def vacation_get(self) -> dict:
        return self._settings().get("vacation") or {"enable_auto_reply": False, "response_subject": "", "response_body_html": "", "restrict_to_contacts": False, "restrict_to_domain": False, "start_time": None, "end_time": None}

    def vacation_set(self, settings: dict) -> dict:
        self._save_settings(vacation=settings)
        return settings
