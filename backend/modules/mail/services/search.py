"""Local search over the thread index with Gmail operators.

Supported: from: to: cc: subject: label: in: is:(unread|read|starred|important|snoozed|muted) has:attachment
before: after: older_than: newer_than: larger: smaller: and plain words / "quoted phrases" (full-text, prefix match).
Plain words match subject, snippet and people. Message bodies are searched on the mail server (`server_search`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from django.contrib.postgres.search import SearchQuery
from django.db import connection
from django.db.models import Exists, OuterRef, Q, QuerySet, TextField
from django.db.models.functions import Cast
from django.utils import timezone

from ..models import Label, Message, Thread

TOKEN = re.compile(r'(-)?(?:(\w+):)?("([^"]*)"|\S+)')
IN_LABELS = {"inbox": "INBOX", "sent": "SENT", "drafts": "DRAFT", "draft": "DRAFT", "spam": "SPAM", "trash": "TRASH", "starred": "STARRED", "important": "IMPORTANT"}
CATEGORY = {"primary": "CATEGORY_PERSONAL", "social": "CATEGORY_SOCIAL", "promotions": "CATEGORY_PROMOTIONS", "updates": "CATEGORY_UPDATES", "forums": "CATEGORY_FORUMS"}
SIZE = re.compile(r"^(\d+(?:\.\d+)?)([kmg]?)b?$", re.I)
AGE = re.compile(r"^(\d+)([dmy])$", re.I)


@dataclass
class ParsedQuery:
    words: list[str] = field(default_factory=list)
    filters: list[tuple[str, str, bool]] = field(default_factory=list)  # (operator, value, negated)

    @property
    def scopes_location(self) -> bool:
        """Gmail hides Spam/Trash from search unless the query names a location."""
        return any(op == "in" or (op == "label" and value.lower() in ("spam", "trash")) for op, value, _ in self.filters)


def parse(query: str) -> ParsedQuery:
    parsed = ParsedQuery()
    for negated, op, raw, quoted in TOKEN.findall(query or ""):
        value = quoted if raw.startswith('"') else raw
        if op:
            parsed.filters.append((op.lower(), value, bool(negated)))
        elif value:
            parsed.words.append(("-" if negated else "") + value)
    return parsed


def _date(value: str) -> datetime | None:
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            day = datetime.strptime(value, fmt).date()
            return timezone.make_aware(datetime.combine(day, time.min))
        except ValueError:
            continue
    return None


def _size(value: str) -> int | None:
    match = SIZE.match(value)
    if not match:
        return None
    number, unit = float(match.group(1)), match.group(2).lower()
    return int(number * {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3}[unit])


def _messages(**lookups):
    return Exists(Message.objects.filter(thread=OuterRef("pk"), **lookups))


def _address_q(field_name: str, value: str) -> Q:
    value = value.lower()
    if field_name == "from":
        return Q(_messages(from_addr__email__icontains=value)) | Q(_messages(from_addr__name__icontains=value))
    inner = Message.objects.annotate(_text=Cast(field_name, TextField())).filter(thread=OuterRef("pk"), _text__icontains=value)
    return Q(Exists(inner))


def _label_ids_named(qs: QuerySet[Thread], name: str) -> list[str]:
    mailbox_ids = qs.values("mailbox_id")
    lowered = name.lower().replace("-", " ")
    if lowered.upper() in {"INBOX", "SENT", "SPAM", "TRASH", "STARRED", "IMPORTANT", "UNREAD", "DRAFT"}:
        return [lowered.upper()]
    if lowered in CATEGORY:
        return [CATEGORY[lowered]]
    rows = Label.objects.filter(mailbox_id__in=mailbox_ids).values_list("provider_label_id", "name")
    return [label_id for label_id, label_name in rows if label_name.lower().replace("-", " ").replace("/", " ") in (lowered, lowered.replace("/", " "))]


def _filter_q(qs: QuerySet[Thread], op: str, value: str) -> Q | None:
    v = value.lower()
    now = timezone.now()
    if op in ("from", "to", "cc", "bcc"):
        return _address_q(op, value)
    if op == "subject":
        return Q(subject__icontains=value)
    if op == "is":
        return {
            "unread": Q(is_unread=True), "read": Q(is_unread=False), "starred": Q(is_starred=True),
            "important": Q(is_important=True), "muted": Q(is_muted=True), "snoozed": Q(snooze__isnull=False),
        }.get(v, Q(pk__in=[]))
    if op == "has":
        if v in ("attachment", "attachments"):
            return Q(has_attachments=True)
        if v in ("userlabels",):
            return Q(label_ids__overlap=list(Label.objects.filter(type=Label.USER).values_list("provider_label_id", flat=True)))
        return Q(pk__in=[])
    if op in ("in", "label", "category"):
        if op == "in" and v in ("anywhere", "all"):
            return Q()
        if op == "in" and v == "snoozed":
            return Q(snooze__isnull=False)
        if op == "category":
            return Q(label_ids__contains=[CATEGORY.get(v, "-")])
        label = IN_LABELS.get(v) if op == "in" else None
        ids = [label] if label else _label_ids_named(qs, value)
        return Q(label_ids__overlap=ids) if ids else Q(pk__in=[])
    if op in ("before", "after"):
        moment = _date(value)
        if not moment:
            return None
        return Q(last_message_at__lt=moment) if op == "before" else Q(last_message_at__gte=moment)
    if op in ("older_than", "newer_than"):
        match = AGE.match(v)
        if not match:
            return None
        amount, unit = int(match.group(1)), match.group(2)
        moment = now - timedelta(days=amount * {"d": 1, "m": 30, "y": 365}[unit])
        return Q(last_message_at__lt=moment) if op == "older_than" else Q(last_message_at__gte=moment)
    if op in ("larger", "smaller"):
        size = _size(v)
        if size is None:
            return None
        return Q(_messages(size__gt=size)) if op == "larger" else ~Q(_messages(size__gte=size))
    return None


def _words_q(words: list[str]) -> Q:
    q = Q()
    for word in words:
        negated = word.startswith("-")
        word = word.lstrip("-")
        if not word:
            continue
        if connection.vendor == "postgresql":
            terms = [t for t in re.findall(r"\w+", word, re.UNICODE)]
            if not terms:
                continue
            raw = " <-> ".join(f"{t}:*" for t in terms)
            match = Q(search_vector=SearchQuery(raw, search_type="raw", config="simple")) | Q(subject__icontains=word)
        else:
            match = Q(subject__icontains=word) | Q(snippet__icontains=word) | Q(participants__icontains=word)
        q &= ~match if negated else match
    return q


def apply(qs: QuerySet[Thread], query: str, include_spam_trash: bool = False) -> QuerySet[Thread]:
    parsed = parse(query)
    q = _words_q(parsed.words)
    for op, value, negated in parsed.filters:
        part = _filter_q(qs, op, value)
        if part is None:
            # Unknown operator: treat "op:value" as plain text, like Gmail does.
            part = _words_q([f"{op} {value}"])
        q &= ~part if negated else part
    if not parsed.scopes_location and not include_spam_trash:
        q &= ~Q(label_ids__overlap=["SPAM", "TRASH"])
    return qs.filter(q)
