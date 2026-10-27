"""Text helpers: GSM-7 / UCS-2 segment counting, one-time-code and money-message detection, masking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

# GSM 03.38 basic character set and the extension table (extension characters cost two septets).
GSM7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM7_EXTENDED = set("^{}\\[~]|€\f")
MAX_BODY = 5000


@dataclass(frozen=True)
class SegmentInfo:
    encoding: str  # gsm7 | ucs2
    units: int  # septets (gsm7) or UTF-16 code units (ucs2)
    segments: int
    per_segment: int
    remaining: int


def segment_info(text: str) -> SegmentInfo:
    """How the carrier will split `text`: 160/153 GSM-7 septets or 70/67 UCS-2 units per (multipart) segment."""
    text = text or ""
    if all(ch in GSM7_BASIC or ch in GSM7_EXTENDED for ch in text):
        units = sum(2 if ch in GSM7_EXTENDED else 1 for ch in text)
        single, multi, encoding = 160, 153, "gsm7"
    else:
        units = len(text.encode("utf-16-le")) // 2
        single, multi, encoding = 70, 67, "ucs2"
    if units <= single:
        return SegmentInfo(encoding, units, 1 if units else 1, single, single - units)
    segments = -(-units // multi)
    return SegmentInfo(encoding, units, segments, multi, segments * multi - units)


# --- Sensitive messages ----------------------------------------------------------------------------------------

CODE = r"(\d{4,8}|\d{3}[- ]\d{3})"
DEFAULT_RULES = [
    # (kind, sender regex, body regex). English and Swahili wording.
    ("otp", "", r"(?i)\b(otp|one[- ]time|verification|verify|security|login|auth(entication)?|confirmation)\b.{0,40}\b(code|pin|password)\b"),
    ("otp", "", r"(?i)\b(code|pin|msimbo|nambari ya siri|neno la siri)\b\W{0,3}.{0,30}?\b" + CODE + r"\b"),
    ("otp", "", r"(?i)\b" + CODE + r"\b.{0,30}\b(is your|ni (namba|msimbo))"),
    ("otp", "", r"(?i)\bG-\d{6}\b"),
    ("money", r"(?i)^(m-?pesa|mpesa|tigo ?pesa|airtel ?money|halo ?pesa|t-?pesa|ezy ?pesa|crdb|nmb|nbc|stanbic|absa|equity|exim|azania)", ""),
    ("money", "", r"(?i)\b(confirmed|imethibitishwa|umepokea|you have received|salio|balance|new m-?pesa balance)\b.{0,80}\b(tsh|tzs|ksh|kes|ugx)\b"),
]
DIGIT_TOKEN = re.compile(r"\S*\d\S*")


@lru_cache(maxsize=64)
def _compile(pattern: str):
    try:
        return re.compile(pattern) if pattern else None
    except re.error:
        return None


def active_rules() -> list[tuple[str, str, str]]:
    from ..models import SensitiveRule

    custom = [(r.kind, r.sender_pattern, r.body_pattern) for r in SensitiveRule.objects.filter(is_enabled=True)]
    return DEFAULT_RULES + custom


def detect_sensitive(sender: str, body: str, rules: list[tuple[str, str, str]] | None = None) -> str:
    """"otp", "money" or "" for a message. A rule matches when every pattern it sets matches."""
    for kind, sender_pattern, body_pattern in rules if rules is not None else active_rules():
        if not sender_pattern and not body_pattern:
            continue
        sender_re, body_re = _compile(sender_pattern), _compile(body_pattern)
        if sender_pattern and (not sender_re or not sender_re.search(sender or "")):
            continue
        if body_pattern and (not body_re or not body_re.search(body or "")):
            continue
        return kind
    return ""


def mask_sensitive(body: str) -> str:
    """Hide every token that contains a digit (codes, amounts, balances, transaction ids): "Your code is ••••••"."""
    return DIGIT_TOKEN.sub(lambda match: "•" * min(len(match.group()), 8), body or "")


def snippet(body: str, length: int = 140) -> str:
    return re.sub(r"\s+", " ", body or "").strip()[:length]
