"""Device identity: human device codes, Keystore public keys, proof-of-possession signatures, key attestation.

The phone generates an EC P-256 key in the Android Keystore (StrongBox when available). The private key never
leaves the secure hardware. Every credential exchange is a signature over a canonical string:

    CMSMS-<PURPOSE>-1\\n<field>\\n<field>…

so a signature for one purpose (enrollment, token minting) can never be replayed as another.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone
from functools import lru_cache

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
KEY_DESCRIPTION_OID = x509.ObjectIdentifier("1.3.6.1.4.1.11129.2.1.17")
SECURITY_LEVELS = {0: "software", 1: "tee", 2: "strongbox"}


class IdentityError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def new_device_code() -> str:
    """DEV-7F3K-9Q2M: 40 random bits in Crockford base32 (no I, L, O, U), easy to read out over the phone."""
    chars = "".join(secrets.choice(CROCKFORD) for _ in range(8))
    return f"DEV-{chars[:4]}-{chars[4:]}"


def sha256_hex(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def _b64decode(value: str) -> bytes:
    value = (value or "").strip()
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_" if ("-" in value or "_" in value) else None, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise IdentityError("invalid_key", "The key is not valid base64.") from exc


def load_public_key(spki_b64: str) -> tuple[ec.EllipticCurvePublicKey, bytes]:
    """(key, DER) for a base64 SubjectPublicKeyInfo. Only EC P-256 is accepted (what the Keystore generates)."""
    der = _b64decode(spki_b64)
    if not der or len(der) > 512:
        raise IdentityError("invalid_key", "The public key is missing or too large.")
    try:
        key = serialization.load_der_public_key(der)
    except ValueError as exc:
        raise IdentityError("invalid_key", "The public key could not be read.") from exc
    if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
        raise IdentityError("invalid_key", "Only EC P-256 keys are accepted.")
    canonical = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return key, canonical


def fingerprint(spki_der: bytes) -> str:
    return sha256_hex(spki_der)


def canonical(purpose: str, *fields: str) -> bytes:
    for item in fields:
        if "\n" in str(item):
            raise IdentityError("invalid_request", "Fields may not contain line breaks.")
    return "\n".join([f"CMSMS-{purpose}-1", *[str(item) for item in fields]]).encode()


def verify_signature(key: ec.EllipticCurvePublicKey, message: bytes, signature_b64: str) -> None:
    """ECDSA P-256 / SHA-256, DER-encoded signature (what Android's `Signature("SHA256withECDSA")` produces)."""
    signature = _b64decode(signature_b64)
    if not signature or len(signature) > 80:
        raise IdentityError("bad_signature", "The signature is not valid.")
    try:
        key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:
        raise IdentityError("bad_signature", "The signature is not valid.") from exc


# --- Android key attestation -------------------------------------------------------------------------------


@dataclass
class Attestation:
    present: bool = False
    chain_valid: bool = False
    root_trusted: bool = False
    challenge_ok: bool = False
    security_level: str = "software"
    attestation_version: int | None = None
    error: str = ""
    root_fingerprint: str = ""
    chain_length: int = 0
    extra: dict = field(default_factory=dict)

    @property
    def hardware_backed(self) -> bool:
        return self.present and self.chain_valid and self.root_trusted and self.challenge_ok and self.security_level in ("tee", "strongbox")

    def as_dict(self) -> dict:
        return {
            "present": self.present, "chain_valid": self.chain_valid, "root_trusted": self.root_trusted, "challenge_ok": self.challenge_ok,
            "security_level": self.security_level, "attestation_version": self.attestation_version, "error": self.error,
            "root_fingerprint": self.root_fingerprint, "chain_length": self.chain_length, "hardware_backed": self.hardware_backed,
        }


@lru_cache(maxsize=4)
def _trusted_roots(path: str) -> frozenset[str]:
    """SHA-256 of each root's SubjectPublicKeyInfo from a PEM bundle (Google's published attestation roots)."""
    if not path:
        return frozenset()
    with open(path, "rb") as handle:
        certs = x509.load_pem_x509_certificates(handle.read())
    return frozenset(fingerprint(c.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)) for c in certs)


def trusted_roots() -> frozenset[str]:
    return _trusted_roots(settings.SMS_ATTESTATION_ROOTS_FILE)


def _der_read(data: bytes, offset: int) -> tuple[int, bytes, int]:
    """(tag, value, next offset) of one DER TLV. Enough for the first fields of KeyDescription."""
    if offset + 2 > len(data):
        raise ValueError("truncated")
    tag = data[offset]
    length = data[offset + 1]
    offset += 2
    if length & 0x80:
        count = length & 0x7F
        if count == 0 or count > 4 or offset + count > len(data):
            raise ValueError("bad length")
        length = int.from_bytes(data[offset:offset + count], "big")
        offset += count
    if offset + length > len(data):
        raise ValueError("truncated value")
    return tag, data[offset:offset + length], offset + length


def parse_key_description(value: bytes) -> dict:
    """attestationVersion, attestationSecurityLevel, keyMintVersion, keyMintSecurityLevel, attestationChallenge."""
    tag, body, _ = _der_read(value, 0)
    if tag != 0x30:
        raise ValueError("KeyDescription is not a SEQUENCE")
    fields, offset = [], 0
    for expected in (0x02, 0x0A, 0x02, 0x0A, 0x04):
        tag, item, offset = _der_read(body, offset)
        if tag != expected:
            raise ValueError("unexpected KeyDescription field")
        fields.append(item)
    return {
        "attestation_version": int.from_bytes(fields[0], "big"),
        "attestation_security_level": int.from_bytes(fields[1], "big"),
        "keymint_version": int.from_bytes(fields[2], "big"),
        "keymint_security_level": int.from_bytes(fields[3], "big"),
        "challenge": fields[4],
    }


def verify_attestation(chain_b64: list[str], spki_der: bytes, challenge: bytes, now: datetime | None = None) -> Attestation:
    """Check an Android key attestation chain (leaf first) for the enrolling key.

    The leaf must carry exactly this public key, every certificate must be signed by the next and be within its
    validity, the root must be one of the configured Google roots, and the attestation challenge must equal
    SHA-256(enrollment token), which binds the key to this one enrollment. Never raises; the result says why.
    """
    result = Attestation(present=bool(chain_b64), chain_length=len(chain_b64 or []))
    if not chain_b64:
        return result
    now = now or datetime.now(dt_timezone.utc)
    try:
        if len(chain_b64) > 8:
            raise ValueError("chain too long")
        certs = [x509.load_der_x509_certificate(_b64decode(item)) for item in chain_b64]
        leaf = certs[0]
        leaf_spki = leaf.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        if leaf_spki != spki_der:
            result.error = "leaf_key_mismatch"
            return result
        for child, issuer in zip(certs, certs[1:]):
            child.verify_directly_issued_by(issuer)
        for cert in certs:
            if not (cert.not_valid_before_utc <= now <= cert.not_valid_after_utc):
                result.error = "certificate_expired"
                return result
        result.chain_valid = True
        root = certs[-1]
        result.root_fingerprint = fingerprint(root.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo))
        result.root_trusted = result.root_fingerprint in trusted_roots()
        extension = leaf.extensions.get_extension_for_oid(KEY_DESCRIPTION_OID)
        description = parse_key_description(extension.value.value)
        result.attestation_version = description["attestation_version"]
        result.security_level = SECURITY_LEVELS.get(description["attestation_security_level"], "software")
        result.challenge_ok = secrets.compare_digest(description["challenge"], challenge)
        if not result.root_trusted:
            result.error = "untrusted_root"
        elif not result.challenge_ok:
            result.error = "challenge_mismatch"
    except x509.ExtensionNotFound:
        result.error = "no_key_description"
    except (ValueError, TypeError, InvalidSignature, IdentityError) as exc:
        result.chain_valid = False
        result.error = "invalid_chain" if not isinstance(exc, IdentityError) else exc.code
    return result
