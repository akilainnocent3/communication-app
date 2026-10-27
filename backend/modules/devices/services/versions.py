"""App version checks (`SMS_MIN_APP_VERSION`). Versions are dotted numbers; build suffixes (+12, -beta) are ignored."""

import re

from django.conf import settings


def parse(version: str) -> tuple[int, ...]:
    parts = re.split(r"[.+-]", (version or "").strip())
    numbers = []
    for part in parts[:3]:
        if not part.isdigit():
            break
        numbers.append(int(part))
    return tuple(numbers) + (0,) * (3 - len(numbers)) if numbers else ()


def is_supported(version: str) -> bool:
    current = parse(version)
    return bool(current) and current >= parse(settings.SMS_MIN_APP_VERSION)
