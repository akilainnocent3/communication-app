import base64
import json
from datetime import datetime


def encode_cursor(values: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(values, default=str).encode()).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> dict | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if "t" in data:
            data["t"] = datetime.fromisoformat(data["t"])
        return data
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
