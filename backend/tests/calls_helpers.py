"""Helpers for Calls tests: call events as the OCM dialer sends them."""

import secrets
import time

MINUTE = 60_000


def now_ms(offset_minutes: float = 0) -> int:
    return int(time.time() * 1000 + offset_minutes * MINUTE)


def log_row(number="+255754210331", direction="in", result="answered", *, at=None, duration=60, log_id=None, sub_id=1, **extra) -> dict:
    """A CallLog.Calls row (backfill / ContentObserver)."""
    at = at if at is not None else now_ms(-30)
    payload = {"call_log_id": log_id if log_id is not None else secrets.randbelow(10**9), "direction": direction, "result": result, "number": number,
               "started_at": at, "duration": duration if result == "answered" else 0, "sub_id": sub_id}
    if result == "answered":
        payload["answered_at"] = at + 5000
    payload.update(extra)
    return {"type": "call.upsert", "payload": payload}


def live(number="+255754210331", direction="in", result="answered", *, at=None, ring_s=5, talk_s=60, key=None, ended=True, sub_id=1, **extra) -> dict:
    """The dialer's InCallService view of a call."""
    at = at if at is not None else now_ms(-10)
    payload = {"call_key": key or secrets.token_urlsafe(12), "direction": direction, "result": result, "number": number, "started_at": at, "sub_id": sub_id}
    if result == "answered":
        payload["answered_at"] = at + ring_s * 1000
        if ended:
            payload["ended_at"] = at + (ring_s + talk_s) * 1000
    elif ended:
        payload["ended_at"] = at + ring_s * 1000
    payload.update(extra)
    return {"type": "call.upsert", "payload": payload}
