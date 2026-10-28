"""The two Redis roles (docs/decisions.md, decision 59).

- `security` (cache alias "security"): replay nonces, login lockouts, short-code breaker, rate-limit counters, throttle
  history and locks. In production it is the Celery broker's Redis, run with `maxmemory-policy noeviction` and AOF, so
  nothing in it is ever evicted to make room: when it is full, writes fail and the request is refused.
- `default`: plain cache data that may be evicted at any time (token buckets, push coalescing, cached access tokens).
  Its own Redis instance runs `allkeys-lru`.

Anything whose loss would weaken a control belongs in `security_store()`. Its helpers fail closed: an error from the
store raises `SecurityStoreUnavailable`, which callers turn into a refusal (503), never into "allowed".
"""

from __future__ import annotations

import logging

from django.core.cache import caches

log = logging.getLogger(__name__)


class SecurityStoreUnavailable(Exception):
    """The security store could not be read or written. The request must be refused."""


def security_store():
    return caches["security"]


def add_once(key: str, ttl: int) -> bool:
    """True the first time `key` is seen within `ttl` seconds (replay protection, locks)."""
    try:
        return bool(security_store().add(key, 1, ttl))
    except Exception as exc:  # noqa: BLE001 - any backend error must refuse, not allow
        log.error("security store write failed (%s): refusing", type(exc).__name__)
        raise SecurityStoreUnavailable() from exc


def bump(key: str, window: int) -> int:
    """Increment a fixed-window counter and return its value."""
    store = security_store()
    try:
        store.add(key, 0, window)
        try:
            return int(store.incr(key))
        except ValueError:  # expired between add and incr
            store.set(key, 1, window)
            return 1
    except SecurityStoreUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        log.error("security store counter failed (%s): refusing", type(exc).__name__)
        raise SecurityStoreUnavailable() from exc


def read(key: str, default=None):
    try:
        return security_store().get(key, default)
    except Exception as exc:  # noqa: BLE001
        log.error("security store read failed (%s): refusing", type(exc).__name__)
        raise SecurityStoreUnavailable() from exc


def write(key: str, value, ttl: int) -> None:
    try:
        security_store().set(key, value, ttl)
    except Exception as exc:  # noqa: BLE001
        log.error("security store write failed (%s): refusing", type(exc).__name__)
        raise SecurityStoreUnavailable() from exc


def delete(key: str) -> None:
    try:
        security_store().delete(key)
    except Exception as exc:  # noqa: BLE001
        raise SecurityStoreUnavailable() from exc
