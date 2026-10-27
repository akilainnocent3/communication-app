"""Phone number normalisation and masking.

Addresses on a phone are not always numbers: short codes ("15300") and alphanumeric sender IDs ("M-PESA") are
common. `address_key` gives every address a stable key: E.164 for real numbers (using the SIM's country, default
`SMS_DEFAULT_REGION`), the bare digits for short codes and the upper-cased text for sender IDs.
"""

from __future__ import annotations

import re

import phonenumbers
from django.conf import settings

ALNUM = re.compile(r"[A-Za-z]")


def normalise_e164(raw: str, region: str | None = None) -> str | None:
    raw = (raw or "").strip()
    if not raw or ALNUM.search(raw):
        return None
    try:
        number = phonenumbers.parse(raw, (region or settings.SMS_DEFAULT_REGION).upper())
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(number):
        return None
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def address_kind(raw: str) -> str:
    """"number", "short_code" or "alphanumeric"."""
    raw = (raw or "").strip()
    if ALNUM.search(raw):
        return "alphanumeric"
    digits = re.sub(r"\D", "", raw)
    if len(digits) <= 6 and not raw.startswith("+"):
        return "short_code"
    return "number"


def address_key(raw: str, region: str | None = None) -> str:
    raw = (raw or "").strip()[:64]
    kind = address_kind(raw)
    if kind == "alphanumeric":
        return re.sub(r"\s+", " ", raw).upper()
    if kind == "short_code":
        return re.sub(r"\D", "", raw)
    return normalise_e164(raw, region) or re.sub(r"[^\d+]", "", raw)


def display_number(key: str) -> str:
    """International format for E.164 keys ("+255 712 345 678"); anything else unchanged."""
    if not key.startswith("+"):
        return key
    try:
        return phonenumbers.format_number(phonenumbers.parse(key), phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    except phonenumbers.NumberParseException:
        return key


def mask(value: str | None) -> str:
    """For logs and audit metadata: "+2557•••••123". Never log a full number."""
    value = (value or "").strip()
    if not value:
        return "-"
    if ALNUM.search(value):
        return value[:2] + "•" * max(0, len(value) - 2)
    keep_head = 5 if value.startswith("+") else 2
    if len(value) <= keep_head + 3:
        return value[:1] + "•" * (len(value) - 1)
    return value[:keep_head] + "•" * (len(value) - keep_head - 3) + value[-3:]
