"""Building and parsing RFC 5322 messages (shared by the fake, IMAP and Gmail providers)."""

from __future__ import annotations

import base64
import email
import email.header
import email.policy
import email.utils
import re
from datetime import UTC, datetime
from email.message import EmailMessage, Message as PyMessage

from ..providers.base import Address, AttachmentMeta, ProviderMessage

INLINE_IMAGE_MAX_BYTES = 1_500_000


def parse_address_list(value: str | None) -> list[Address]:
    if not value:
        return []
    result = []
    for name, addr in email.utils.getaddresses([str(value)]):
        addr = (addr or "").strip()
        if addr and "@" in addr:
            result.append(Address(email=addr.lower(), name=_decode(name).strip().strip('"')))
    return result


def _decode(value) -> str:
    if value is None:
        return ""
    try:
        return str(email.header.make_header(email.header.decode_header(str(value))))
    except Exception:  # malformed encoded-words: keep the raw text
        return str(value)


def format_address(address: dict | Address) -> str:
    if isinstance(address, Address):
        address = address.as_dict()
    return email.utils.formataddr((address.get("name") or "", address["email"]))


def parse_date(value: str | None, fallback: datetime | None = None) -> datetime:
    if value:
        try:
            parsed = email.utils.parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        except (TypeError, ValueError, IndexError):
            pass
    return fallback or datetime.now(UTC)


def html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", "", html or "")
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>|</h\d>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    import html as html_lib

    text = html_lib.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def snippet_of(text: str, length: int = 180) -> str:
    return re.sub(r"\s+", " ", text or "").strip()[:length]


def build_mime(
    *,
    from_addr: dict,
    to: list[dict],
    cc: list[dict] | None = None,
    bcc: list[dict] | None = None,
    subject: str = "",
    html: str = "",
    text: str | None = None,
    in_reply_to: str = "",
    references: str = "",
    attachments: list[tuple[str, str, bytes]] | None = None,
    message_id: str | None = None,
) -> bytes:
    msg = EmailMessage(policy=email.policy.SMTP)
    msg["From"] = format_address(from_addr)
    if to:
        msg["To"] = ", ".join(format_address(a) for a in to)
    if cc:
        msg["Cc"] = ", ".join(format_address(a) for a in cc)
    if bcc:
        msg["Bcc"] = ", ".join(format_address(a) for a in bcc)
    msg["Subject"] = subject
    msg["Date"] = email.utils.format_datetime(datetime.now(UTC))
    domain = from_addr["email"].split("@", 1)[-1]
    msg["Message-ID"] = message_id or email.utils.make_msgid(domain=domain)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    msg["MIME-Version"] = "1.0"
    plain = text if text is not None else html_to_text(html)
    msg.set_content(plain or " ")
    if html:
        msg.add_alternative(html, subtype="html")
    for filename, content_type, data in attachments or []:
        maintype, _, subtype = (content_type or "application/octet-stream").partition("/")
        msg.add_attachment(data, maintype=maintype or "application", subtype=subtype or "octet-stream", filename=filename)
    return msg.as_bytes()


def _walk_parts(message: PyMessage):
    """Yield (part_id, part) for every leaf part, ids like '1', '1.2' (stable for a given message)."""

    def walk(part, prefix):
        if part.is_multipart():
            for index, child in enumerate(part.get_payload(), start=1):
                yield from walk(child, f"{prefix}.{index}" if prefix else str(index))
        else:
            yield prefix or "1", part

    yield from walk(message, "")


def parse_rfc822(raw: bytes, *, message_id: str, thread_id: str, label_ids: list[str], internal_date: datetime | None = None, full: bool = True) -> ProviderMessage:
    message = email.message_from_bytes(raw, policy=email.policy.default)
    html_body, text_body = None, None
    attachments: list[AttachmentMeta] = []
    inline_images: dict[str, str] = {}
    for part_id, part in _walk_parts(message):
        content_type = part.get_content_type()
        disposition = (part.get_content_disposition() or "").lower()
        filename = part.get_filename()
        content_id = (part.get("Content-ID") or "").strip("<> ")
        if not filename and disposition != "attachment" and content_type in ("text/html", "text/plain"):
            try:
                content = part.get_content()
            except (LookupError, ValueError):
                content = part.get_payload(decode=True).decode("utf-8", "replace") if part.get_payload(decode=True) else ""
            if content_type == "text/html" and html_body is None:
                html_body = content
            elif content_type == "text/plain" and text_body is None:
                text_body = content
            continue
        payload = part.get_payload(decode=True) or b""
        inline = bool(content_id) and disposition != "attachment" and content_type.startswith("image/")
        attachments.append(AttachmentMeta(id=part_id, filename=filename or ("image" if inline else "attachment"), mime_type=content_type, size=len(payload), content_id=content_id, inline=inline))
        if full and inline and len(payload) <= INLINE_IMAGE_MAX_BYTES:
            inline_images[content_id] = f"data:{content_type};base64,{base64.b64encode(payload).decode()}"

    text_for_snippet = text_body or html_to_text(html_body or "")
    return ProviderMessage(
        id=message_id,
        thread_id=thread_id,
        label_ids=list(label_ids),
        date=parse_date(message.get("Date"), internal_date),
        subject=_decode(message.get("Subject")),
        snippet=snippet_of(text_for_snippet),
        from_addr=(parse_address_list(message.get("From")) or [None])[0],
        to=parse_address_list(message.get("To")),
        cc=parse_address_list(message.get("Cc")),
        bcc=parse_address_list(message.get("Bcc")),
        reply_to=parse_address_list(message.get("Reply-To")),
        rfc_message_id=(message.get("Message-ID") or "").strip(),
        in_reply_to=(message.get("In-Reply-To") or "").strip(),
        references=" ".join((message.get("References") or "").split()),
        size=len(raw),
        attachments=attachments,
        list_unsubscribe=str(message.get("List-Unsubscribe") or ""),
        list_unsubscribe_post=str(message.get("List-Unsubscribe-Post") or ""),
        body_html=html_body if full else None,
        body_text=text_body if full else None,
        inline_images=inline_images,
    )


def attachment_bytes(raw: bytes, part_id: str) -> tuple[bytes, str, str]:
    """(data, mime_type, filename) of the part `part_id` in an RFC 822 message."""
    message = email.message_from_bytes(raw, policy=email.policy.default)
    for pid, part in _walk_parts(message):
        if pid == part_id:
            return part.get_payload(decode=True) or b"", part.get_content_type(), part.get_filename() or "attachment"
    raise KeyError(part_id)
