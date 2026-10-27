"""MMS media: encrypted files in private storage (SMS_MEDIA_ROOT), resumable chunked uploads, type sniffing.

- The phone declares each part (seq, size, SHA-256) in its `message.upsert` event, then uploads the bytes in
  chunks (`offset` must equal what the server already has, so a dropped connection resumes where it stopped).
- Each chunk is encrypted before it touches the disk. When the last chunk arrives the server reassembles the
  file in memory, verifies the declared SHA-256 and size, sniffs the real type from the magic bytes and writes
  one encrypted file. Nothing is ever stored in plaintext or served under a public URL.
"""

from __future__ import annotations

import hashlib
import secrets
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from ..models import Message, MessagePart
from .crypto import decrypt_bytes, encrypt_bytes

MAX_CHUNK = 512 * 1024
SAFE_INLINE = {"image/jpeg", "image/png", "image/gif", "image/webp", "video/mp4", "video/3gpp", "audio/amr", "audio/mpeg", "audio/ogg", "audio/mp4", "text/plain"}


class MediaError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def sniff(data: bytes) -> str:
    """Content type from magic bytes. Anything unrecognised is served as a download only."""
    head = data[:16]
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand.startswith(b"3g"):
            return "video/3gpp"
        if brand in (b"M4A ", b"M4B "):
            return "audio/mp4"
        return "video/mp4"
    if head.startswith(b"#!AMR"):
        return "audio/amr"
    if head.startswith(b"ID3") or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"
    if head.startswith(b"OggS"):
        return "audio/ogg"
    if data[:11].upper() == b"BEGIN:VCARD":
        return "text/x-vcard"
    try:
        data[:2048].decode("utf-8")
        if b"\x00" not in data[:2048]:
            return "text/plain"
    except UnicodeDecodeError:
        pass
    return "application/octet-stream"


def _root() -> Path:
    root = Path(settings.SMS_MEDIA_ROOT)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def _path(name: str) -> Path:
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise MediaError("invalid_name", "Invalid media name.")
    return _root() / name


def _chunk_dir(part: MessagePart) -> Path:
    path = _root() / "partial" / f"{part.pk}"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def receive_chunk(part: MessagePart, offset: int, chunk: bytes) -> MessagePart:
    if part.uploaded_at:
        return part  # already complete: idempotent
    if offset != part.received_bytes:
        raise MediaError("offset_mismatch", f"Resume from byte {part.received_bytes}.", 409)
    if not chunk or len(chunk) > MAX_CHUNK:
        raise MediaError("bad_chunk", "Chunks must be between 1 byte and 512 KB.")
    if part.received_bytes + len(chunk) > min(part.size, settings.SMS_MAX_MMS_BYTES):
        raise MediaError("too_large", "The upload is larger than declared or allowed.", 413)
    (_chunk_dir(part) / f"{offset:010d}").write_bytes(encrypt_bytes(chunk))
    part.received_bytes += len(chunk)
    part.save(update_fields=["received_bytes"])
    if part.received_bytes == part.size:
        _finish(part)
    return part


def _finish(part: MessagePart) -> None:
    directory = _chunk_dir(part)
    data = b"".join(decrypt_bytes(path.read_bytes()) for path in sorted(directory.iterdir()))
    for path in directory.iterdir():
        path.unlink()
    directory.rmdir()
    if hashlib.sha256(data).hexdigest() != part.sha256 or len(data) != part.size:
        part.received_bytes = 0
        part.save(update_fields=["received_bytes"])
        raise MediaError("checksum_mismatch", "The file did not match its checksum. Upload it again.", 422)
    store(part, data)


def store(part: MessagePart, data: bytes) -> None:
    name = f"{secrets.token_hex(16)}.bin"
    _path(name).write_bytes(encrypt_bytes(data))
    part.storage_name = name
    part.content_type = sniff(data)
    part.size = len(data)
    part.sha256 = hashlib.sha256(data).hexdigest()
    part.received_bytes = len(data)
    part.uploaded_at = timezone.now()
    part.save()


def read(part: MessagePart) -> bytes:
    if not part.storage_name:
        raise MediaError("not_uploaded", "This attachment has not arrived from the phone yet.", 404)
    return decrypt_bytes(_path(part.storage_name).read_bytes())


def delete_files(message: Message) -> None:
    for part in message.parts.all():
        if part.storage_name:
            _path(part.storage_name).unlink(missing_ok=True)
        partial = _root() / "partial" / f"{part.pk}"
        if partial.exists():
            for path in partial.iterdir():
                path.unlink()
            partial.rmdir()


def cleanup_orphans() -> int:
    """Remove stored files no part points to and abandoned partial uploads older than a day."""
    import time

    root = _root()
    known = set(MessagePart.objects.exclude(storage_name="").values_list("storage_name", flat=True))
    removed = 0
    for path in root.glob("*.bin"):
        if path.name not in known and time.time() - path.stat().st_mtime > 3600:
            path.unlink(missing_ok=True)
            removed += 1
    partial = root / "partial"
    if partial.exists():
        live = {str(pk) for pk in MessagePart.objects.filter(uploaded_at__isnull=True).values_list("pk", flat=True)}
        for directory in partial.iterdir():
            if directory.name not in live or time.time() - directory.stat().st_mtime > 86400:
                for path in directory.iterdir():
                    path.unlink()
                directory.rmdir()
                # The phone restarts that upload from byte 0.
                MessagePart.objects.filter(pk=int(directory.name) if directory.name.isdigit() else 0, uploaded_at__isnull=True).update(received_bytes=0)
                removed += 1
    return removed
