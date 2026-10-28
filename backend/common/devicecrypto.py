"""Encryption at rest for device-derived data: SMS bodies, snippets and MMS files, call notes, callback reasons and
directory notes. One MultiFernet key ring, SMS_DATA_KEYS (the name predates Calls; it now protects everything that
comes from or concerns company phones). Separate from MAIL_TOKEN_KEYS so each ring protects one kind of data.

Rotate: put a new key first, keep the old ones after it, run `manage.py rotate_sms_keys` (it re-encrypts SMS, Calls and
directory data), then drop the old key.
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@lru_cache(maxsize=4)
def _ring(keys: tuple[str, ...]) -> MultiFernet:
    if not keys:
        raise ImproperlyConfigured("SMS_DATA_KEYS is not set. Generate a key and add it to the environment.")
    return MultiFernet([Fernet(key.encode() if isinstance(key, str) else key) for key in keys])


def ring() -> MultiFernet:
    return _ring(tuple(settings.SMS_DATA_KEYS))


def encrypt_text(text: str) -> str:
    return ring().encrypt((text or "").encode()).decode() if text else ""


def decrypt_text(token: str) -> str:
    if not token:
        return ""
    try:
        return ring().decrypt(token.encode()).decode()
    except InvalidToken as exc:  # never echo the ciphertext
        raise ImproperlyConfigured("Stored device data cannot be decrypted with SMS_DATA_KEYS.") from exc


def encrypt_bytes(data: bytes) -> bytes:
    return ring().encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    try:
        return ring().decrypt(data)
    except InvalidToken as exc:
        raise ImproperlyConfigured("Stored SMS media cannot be decrypted with SMS_DATA_KEYS.") from exc


def rotate_text(token: str) -> str:
    return ring().rotate(token.encode()).decode() if token else token


def rotate_bytes(data: bytes) -> bytes:
    return ring().rotate(data)
