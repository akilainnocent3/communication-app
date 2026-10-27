"""A scripted phone for tests: signs requests with a real EC P-256 key, exactly like the Android app."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from rest_framework.test import APIClient

from modules.devices.services.identity import canonical

APP_VERSION = "1.2.0"


def spki_b64(key) -> str:
    return base64.b64encode(key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).decode()


def fingerprint(key) -> str:
    return hashlib.sha256(base64.b64decode(spki_b64(key))).hexdigest()


def sign(key, message: bytes) -> str:
    return base64.b64encode(key.sign(message, ec.ECDSA(hashes.SHA256()))).decode()


class Phone:
    def __init__(self, key=None):
        self.key = key or ec.generate_private_key(ec.SECP256R1())
        self.client = APIClient()
        self.device_id: str | None = None
        self.token: str | None = None
        self.seq = 0
        self.provider_id = 100

    def enroll_body(self, token: str, *, timestamp=None, nonce=None, signature=None, **extra) -> dict:
        timestamp = int(time.time()) if timestamp is None else timestamp
        nonce = nonce or secrets.token_urlsafe(18)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        message = canonical("ENROLL", token_hash, fingerprint(self.key), str(timestamp), nonce)
        body = {
            "token": token, "public_key": spki_b64(self.key), "signature": signature or sign(self.key, message), "timestamp": timestamp, "nonce": nonce,
            "app_version": APP_VERSION, "device": {"manufacturer": "Samsung", "model": "Galaxy A15", "android_version": "14", "sdk_int": 34},
            "sims": [{"subscription_id": 1, "slot": 0, "carrier": "Vodacom", "country_iso": "TZ", "number": "0754000111", "is_default": True}],
            "notice_accepted": True, "notice_text": "notice",
        }
        body.update(extra)
        return body

    def enroll(self, token: str, **extra):
        response = self.client.post("/api/v1/device/enroll/", self.enroll_body(token, **extra), format="json")
        if response.status_code == 201:
            self.device_id = response.json()["device_id"]
            self.token = response.json()["access_token"]
        return response

    def token_body(self, *, timestamp=None, nonce=None, device_id=None, key=None) -> dict:
        timestamp = int(time.time()) if timestamp is None else timestamp
        nonce = nonce or secrets.token_urlsafe(18)
        device_id = device_id or self.device_id
        message = canonical("AUTH", "POST", "/api/v1/device/auth/token/", str(device_id), str(timestamp), nonce)
        return {"device_id": device_id, "timestamp": timestamp, "nonce": nonce, "signature": sign(key or self.key, message)}

    def authenticate(self, **kwargs):
        response = self.client.post("/api/v1/device/auth/token/", self.token_body(**kwargs), format="json")
        if response.status_code == 200:
            self.token = response.json()["access_token"]
        return response

    def headers(self, version: str = APP_VERSION) -> dict:
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}", "HTTP_X_CM_APP_VERSION": version}

    def post(self, path: str, data=None, fmt="json", **kwargs):
        if fmt:
            return self.client.post(f"/api/v1/device/{path}", data, format=fmt, **{**self.headers(), **kwargs})
        return self.client.post(f"/api/v1/device/{path}", data, **{**self.headers(), **kwargs})

    def get(self, path: str, **kwargs):
        return self.client.get(f"/api/v1/device/{path}", **{**self.headers(), **kwargs})

    # --- sync helpers -------------------------------------------------------------------------------------

    def message(self, address="+255754210331", direction="in", body="Habari, bei gani?", *, at_ms=None, provider_id=None, **extra) -> dict:
        if provider_id is None:
            self.provider_id += 1
            provider_id = self.provider_id
        payload = {
            "kind": "sms", "provider_id": provider_id, "date": at_ms or int(time.time() * 1000) - 60_000, "thread_id": 7,
            "addresses": [address] if isinstance(address, str) else address, "direction": direction, "body": body, "is_read": direction == "out", "sub_id": 1,
        }
        payload.update(extra)
        return {"type": "message.upsert", "payload": payload}

    def send_events(self, *events, seqs=None):
        batch = []
        for index, event in enumerate(events):
            if seqs:
                seq = seqs[index]
            else:
                self.seq += 1
                seq = self.seq
            batch.append({**event, "seq": seq})
        return self.post("sync/events/", {"events": batch})
