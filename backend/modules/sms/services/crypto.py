"""Encryption at rest for SMS bodies, snippets and MMS files. The key ring (SMS_DATA_KEYS) is shared with Calls and the
directory: see common/devicecrypto.py.

Consequence (docs/decisions.md): the database cannot search message text. Search works on contact names and
numbers (plaintext), and inside one open conversation (decrypted server-side for that request only).
"""

from common.devicecrypto import decrypt_bytes, decrypt_text, encrypt_bytes, encrypt_text, ring, rotate_bytes, rotate_text

__all__ = ["decrypt_bytes", "decrypt_text", "encrypt_bytes", "encrypt_text", "ring", "rotate_bytes", "rotate_text"]
