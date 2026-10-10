"""Per-mailbox token bucket (kept below Gmail's per-user quota) and retry with exponential backoff + jitter."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

from django.conf import settings
from django.core.cache import cache

from ..providers.base import ProviderError

T = TypeVar("T")


def take_token(mailbox_id: int, cost: float = 1.0, max_wait: float = 10.0) -> None:
    """Block (briefly) until the mailbox's bucket has `cost` tokens. Shared across workers via the cache."""
    rate = settings.MAIL_RATE_PER_SECOND
    capacity = rate * 2
    key = f"mail-bucket:{mailbox_id}"
    deadline = time.monotonic() + max_wait
    while True:
        now = time.time()
        tokens, stamp = cache.get(key, (capacity, now))
        tokens = min(capacity, tokens + (now - stamp) * rate)
        if tokens >= cost:
            cache.set(key, (tokens - cost, now), 60)
            return
        wait = (cost - tokens) / rate
        if time.monotonic() + wait > deadline:
            raise ProviderError("rate_limited", "The mail server is busy. Try again in a moment.", retryable=True)
        time.sleep(wait)


def with_backoff(call: Callable[[], T], *, attempts: int = 5, base: float = 0.5, cap: float = 20.0, sleep=time.sleep) -> T:
    """Retry `call` on retryable ProviderErrors (429, rateLimitExceeded, 5xx) with full-jitter backoff."""
    for attempt in range(attempts):
        try:
            return call()
        except ProviderError as exc:
            if not exc.retryable or attempt == attempts - 1:
                raise
            sleep(random.uniform(0, min(cap, base * 2**attempt)))
    raise AssertionError("unreachable")
