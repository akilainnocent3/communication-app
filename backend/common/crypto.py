"""Encryption for stored credentials (refresh tokens, IMAP passwords, service-account keys).

Uses MultiFernet so keys can be rotated: put the new key first in MAIL_TOKEN_KEYS, keep the old ones after it,
then run `manage.py rotate_mail_keys` to re-encrypt everything with the newest key.
"""

import json
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@lru_cache(maxsize=4)
def _fernet(keys: tuple[str, ...]) -> MultiFernet:
    if not keys:
        raise ImproperlyConfigured("MAIL_TOKEN_KEYS is not set. Generate a key and add it to the environment.")
    return MultiFernet([Fernet(key.encode() if isinstance(key, str) else key) for key in keys])


def fernet() -> MultiFernet:
    return _fernet(tuple(settings.MAIL_TOKEN_KEYS))


def encrypt_json(data: dict) -> str:
    return fernet().encrypt(json.dumps(data, separators=(",", ":")).encode()).decode()


def decrypt_json(token: str) -> dict:
    if not token:
        return {}
    try:
        return json.loads(fernet().decrypt(token.encode()))
    except InvalidToken as exc:  # wrong/rotated-away key: never echo the ciphertext
        raise ImproperlyConfigured("Stored credentials cannot be decrypted with MAIL_TOKEN_KEYS.") from exc


def rotate(token: str) -> str:
    return fernet().rotate(token.encode()).decode() if token else token
