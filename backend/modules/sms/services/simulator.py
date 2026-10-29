"""A simulated company phone, for demos and end-to-end tests without real hardware.

It behaves like the Android app from the server's point of view: it enrolls through the real enroll and token
endpoints with a real EC P-256 key, uploads its message store as sync events (Swahili and English conversations,
M-PESA-style sender IDs, one-time codes, an MMS image), claims the outbox, reports sending → sent → delivered (or
failed for numbers ending in 000), receives new messages, and can be switched offline and online.

Production refuses to start with SMS_ENABLE_SIMULATOR on, and these phones are flagged `is_simulated`.
"""

from __future__ import annotations

import base64
import hashlib
import random
import secrets
import struct
import time
import zlib
from datetime import timedelta

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.utils import timezone

from modules.devices.models import Device, DeviceStatus
from modules.devices.services import enrollment
from modules.devices.services.identity import canonical

from ..models import SimulatedDevice, SmsSettings
from .crypto import decrypt_text, encrypt_text

APP_VERSION = "1.0.0"
CONTACTS = [
    ("Neema Mushi", "+255754210331"), ("Baraka Mwakyusa", "+255713402118"), ("Rehema Kimaro", "+255688120554"),
    ("Juma Hassan", "+255765330912"), ("Grace Massawe", "+255742611087"), ("Fatma Said", "+255777301245"),
    ("Daudi Mrema", "+255715889320"), ("Peter Swai", "+255689455102"),
]
UNSAVED = ["+255746118920", "+255656702113", "+255719004587", "+255782335610"]
CUSTOMER_IN = [
    "Habari, bei ya mifuko 50 ya saruji ni kiasi gani?", "Good morning, is the order for {city} ready?", "Nimetuma malipo kupitia M-Pesa, tafadhali thibitisha.",
    "Can you deliver tomorrow before 10am?", "Asante sana, mzigo umefika salama.", "Please send the invoice for last week's delivery.",
    "Mna stock ya mabati ya rangi ya bluu?", "I'm at the gate, who should I ask for?", "Naomba namba ya akaunti ya benki.",
    "Is the {city} office open on Saturday?", "Bei ya mwisho ni ngapi kwa tani moja?", "Thank you for the quick reply!",
]
PHONE_OUT = [
    "Habari, bei ni TSh 19,500 kwa mfuko. Tunaweza kuleta kesho.", "Yes, it's ready. The driver leaves at 2pm.", "Tumepokea, asante. Risiti itatumwa leo.",
    "Sure, we'll be there by 9:30.", "Karibu tena!", "I've emailed the invoice just now.", "Ndiyo, zipo. Unahitaji ngapi?",
    "Ask for Salim at reception.", "Akaunti: CRDB 0150 2xxx xxxx, jina Kilimanjaro Trading.", "Yes, 8:00 to 13:00.",
]
CITIES = ["Arusha", "Mwanza", "Dodoma", "Moshi", "Tanga"]
AUTOMATED = [
    ("M-PESA", "QJK{tx} Imethibitishwa. Umepokea Tsh{amount}.00 kutoka JUMA HASSAN 255765330912 tarehe {date}. Salio jipya la M-Pesa ni Tsh{balance}.00."),
    ("CRDB BANK", "Dear Customer, your account ending 4417 has been credited TZS {amount}.00 on {date}. Available balance TZS {balance}.00."),
    ("GOOGLE", "G-{otp} is your Google verification code."),
    ("WhatsApp", "Your WhatsApp code: {otp3}-{otp3b}. Don't share this code with others."),
    ("Vodacom", "Ofa! Pata GB 5 kwa Tsh 5,000 tu. Piga *149*01#."),
]


def _png(colour: tuple[int, int, int], size: int = 48) -> bytes:
    """A small valid PNG (a coloured square), to stand in for an MMS photo."""
    raw = b"".join(b"\x00" + bytes(colour) * size for _ in range(size))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def _app_version() -> str:
    from modules.devices.services.versions import parse

    return APP_VERSION if parse(APP_VERSION) >= parse(settings.SMS_MIN_APP_VERSION) else settings.SMS_MIN_APP_VERSION


def _host() -> str:
    for host in settings.ALLOWED_HOSTS:
        if host and not host.startswith(".") and host != "*":
            return host
    return "localhost"


class SimulatedPhone:
    def __init__(self, sim: SimulatedDevice):
        from rest_framework.test import APIClient

        self.sim = sim
        self.device = sim.device
        self.key = serialization.load_pem_private_key(decrypt_text(sim.encrypted_private_key).encode(), password=None)
        self.client = APIClient(HTTP_HOST=_host())

    # --- transport -----------------------------------------------------------------------------------------

    def _sign(self, message: bytes) -> str:
        return base64.b64encode(self.key.sign(message, ec.ECDSA(hashes.SHA256()))).decode()

    def token(self) -> str:
        state = self.sim.state
        if state.get("token") and state.get("token_expires", 0) > time.time() + 30:
            return state["token"]
        timestamp, nonce = int(time.time()), secrets.token_urlsafe(18)
        message = canonical("AUTH", "POST", "/api/v1/device/auth/token/", str(self.device.pk), str(timestamp), nonce)
        response = self.client.post("/api/v1/device/auth/token/", {"device_id": str(self.device.pk), "timestamp": timestamp, "nonce": nonce, "signature": self._sign(message)}, format="json")
        if response.status_code != 200:
            raise RuntimeError(f"simulator token refused: {response.status_code} {response.json().get('code')}")
        state["token"], state["token_expires"] = response.json()["access_token"], time.time() + response.json()["expires_in"]
        self._save()
        return state["token"]

    def call(self, method: str, path: str, data=None, fmt="json"):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token()}", "HTTP_X_CM_APP_VERSION": _app_version()}
        response = getattr(self.client, method)(f"/api/v1/device/{path}", data, format=fmt, **headers) if fmt else getattr(self.client, method)(f"/api/v1/device/{path}", data, **headers)
        if response.status_code >= 400:
            raise RuntimeError(f"simulator {path} failed: {response.status_code} {response.content[:200]!r}")
        return response.json() if response.content else {}

    def _save(self) -> None:
        SimulatedDevice.objects.filter(pk=self.sim.pk).update(state=self.sim.state, next_seq=self.sim.next_seq, next_provider_id=self.sim.next_provider_id, online=self.sim.online)

    # --- events --------------------------------------------------------------------------------------------

    def _thread(self, key: str) -> int:
        threads = self.sim.state.setdefault("threads", {})
        if key not in threads:
            threads[key] = len(threads) + 1
        return threads[key]

    def message_event(self, *, addresses: list[str], direction: str, body: str, at, is_read=True, status="", sub_id=None, kind="sms", parts=None, client_uuid=None) -> dict:
        provider_id = self.sim.next_provider_id
        self.sim.next_provider_id += 1
        payload = {
            "kind": kind, "provider_id": provider_id, "date": int(at.timestamp() * 1000), "thread_id": self._thread(",".join(sorted(addresses))),
            "addresses": addresses, "direction": direction, "body": body, "is_read": is_read, "status": status, "sub_id": sub_id,
        }
        if parts:
            payload["parts"] = parts
        if client_uuid:
            payload["client_uuid"] = client_uuid
        return {"type": "message.upsert", "payload": payload}

    def push(self, events: list[dict]) -> dict:
        result = {}
        for start in range(0, len(events), 150):
            batch = []
            for event in events[start:start + 150]:
                batch.append({**event, "seq": self.sim.next_seq})
                self.sim.next_seq += 1
            self._save()
            result = self.call("post", "sync/events/", {"events": batch})
        return result

    def upload(self, provider_id: int, at, seq: int, data: bytes) -> None:
        from django.core.files.uploadedfile import SimpleUploadedFile

        offset = 0
        while offset < len(data):
            chunk = data[offset:offset + 64 * 1024]
            self.call("post", "sync/media/", {"provider_id": provider_id, "date": int(at.timestamp() * 1000), "seq": seq, "offset": offset, "chunk": SimpleUploadedFile("chunk", chunk)}, fmt=None)
            offset += len(chunk)

    def subs(self) -> list[int]:
        return [line.subscription_id for line in self.device.sim_lines.filter(is_active=True)] or [None]

    # --- behaviour ---------------------------------------------------------------------------------------------

    def heartbeat(self) -> None:
        sims = [{"subscription_id": line.subscription_id, "slot": line.slot, "carrier": line.carrier, "country_iso": line.country_iso, "number": line.number, "is_default": line.is_default}
                for line in self.device.sim_lines.all()]
        if self.device.app == "calls":
            role = {"is_default_dialer": True, "full_screen_intent_allowed": True, "call_state": "idle",
                    "permissions": {name: True for name in ("READ_CALL_LOG", "CALL_PHONE", "ANSWER_PHONE_CALLS", "READ_PHONE_STATE", "READ_CONTACTS", "POST_NOTIFICATIONS")}}
        else:
            role = {"is_default_sms_app": True,
                    "permissions": {name: True for name in ("RECEIVE_SMS", "READ_SMS", "SEND_SMS", "RECEIVE_MMS", "READ_CONTACTS", "READ_PHONE_STATE", "POST_NOTIFICATIONS")}}
        self.call("post", "heartbeat/", {
            "battery": random.randint(35, 98), "charging": random.random() < 0.3, "network_type": random.choice(["wifi", "cellular"]), "signal": random.randint(2, 4),
            **role,
            "battery_optimised": False, "pending_outbox": 0, "app_version": APP_VERSION, "android_version": "14", "sims": sims,
        })
        self.sim.state["last_heartbeat"] = time.time()
        self._save()

    def backfill(self, days: int, seed: int = 7) -> int:
        rng = random.Random(seed)
        now = timezone.now()
        subs = self.subs()
        events, uploads = [], []
        people = CONTACTS[: 5 + seed % 3] + UNSAVED[: 2 + seed % 2]
        for index, person in enumerate(people):
            name, number = person if isinstance(person, tuple) else ("", person)
            sub = subs[index % len(subs)]
            at = now - timedelta(days=rng.uniform(0.2, max(1, days - 1)))
            for turn in range(rng.randint(2, 7)):
                city = rng.choice(CITIES)
                body = rng.choice(CUSTOMER_IN).format(city=city)
                latest = turn > 0 and at > now - timedelta(hours=30)
                events.append(self.message_event(addresses=[number], direction="in", body=body, at=at, is_read=not latest or rng.random() < 0.4, sub_id=sub))
                at += timedelta(minutes=rng.randint(3, 240))
                if at >= now or (turn > 0 and rng.random() < 0.25):
                    break
                events.append(self.message_event(addresses=[number], direction="out", body=rng.choice(PHONE_OUT), at=at, status="delivered", sub_id=sub))
                at += timedelta(hours=rng.uniform(2, 40))
                if at >= now:
                    break
            if index == 1:
                # An MMS photo from a customer.
                at_mms = now - timedelta(hours=rng.uniform(5, 40))
                image = _png((rng.randint(30, 220), rng.randint(60, 200), rng.randint(80, 240)))
                event = self.message_event(addresses=[number], direction="in", body="Picha ya mzigo uliofika 📦", at=at_mms, kind="mms", sub_id=sub,
                                           parts=[{"seq": 0, "content_type": "image/png", "filename": "mzigo.png", "size": len(image), "sha256": hashlib.sha256(image).hexdigest()}])
                events.append(event)
                uploads.append((event["payload"]["provider_id"], at_mms, 0, image))
        for sender, template in AUTOMATED:
            at = now - timedelta(days=rng.uniform(0.05, max(1, days / 3)))
            body = template.format(tx=rng.randint(1000, 9999), amount=f"{rng.randint(5, 900)},000", balance=f"{rng.randint(100, 9000)},{rng.randint(100, 999)}",
                                   date=at.strftime("%d/%m/%y"), otp=rng.randint(100000, 999999), otp3=rng.randint(100, 999), otp3b=rng.randint(100, 999))
            events.append(self.message_event(addresses=[sender], direction="in", body=body, at=at, is_read=rng.random() < 0.6, sub_id=subs[0]))
        total = len(events)
        self.push([{"type": "backfill.progress", "payload": {"phase": "running", "done": 0, "total": total}}])
        self.push(events)
        for provider_id, at, seq, data in uploads:
            self.upload(provider_id, at, seq, data)
        contacts = [{"type": "contact.upsert", "payload": {"address": number, "display_name": name}} for name, number in CONTACTS]
        self.push(contacts + [{"type": "backfill.progress", "payload": {"phase": "done", "done": total, "total": total}}])
        return total

    def receive(self, rng: random.Random | None = None) -> None:
        rng = rng or random.Random()
        name, number = rng.choice(CONTACTS + [("", n) for n in UNSAVED])
        self.push([self.message_event(addresses=[number], direction="in", body=rng.choice(CUSTOMER_IN).format(city=rng.choice(CITIES)), at=timezone.now(), is_read=False, sub_id=rng.choice(self.subs()))])

    def work_outbox(self, force: bool = False) -> int:
        """Claim due messages, then move each through sending → sent → delivered with realistic delays."""
        now = time.time()
        claimed = self.call("post", "outbox/claim/", {"limit": 10})
        pending = self.sim.state.setdefault("pending", {})
        acks, events = [], []
        for command in claimed["commands"]:
            if command["kind"] == "mark_read" and command["payload"].get("thread_id"):
                self.push([{"type": "thread.read", "payload": {"thread_id": command["payload"]["thread_id"]}}])
            acks.append({"id": command["id"], "ok": True})
        reports = []
        for message in claimed["messages"]:
            uuid = message["client_uuid"]
            if uuid in pending or uuid in self.sim.state.get("done", []):
                continue  # at most once: never start a message twice
            reports.append({"client_uuid": uuid, "status": "sending", "at": int(now * 1000)})
            fail = any(a.endswith("000") for a in message["addresses"])
            pending[uuid] = {"step": "sending", "due": now + (0 if force else random.uniform(1, 4)), "fail": fail, "message": message}
        for uuid, item in list(pending.items()):
            if not force and item["due"] > now:
                continue
            if item["step"] == "sending":
                if item["fail"]:
                    reports.append({"client_uuid": uuid, "status": "failed", "error_code": 4, "at": int(now * 1000)})
                    self._finish(uuid)
                    continue
                parts = max(1, -(-len(item["message"]["body"]) // 153))
                reports.append({"client_uuid": uuid, "status": "sent", "parts": parts, "at": int(now * 1000)})
                # Like the app, write the sent message to the phone's own store (reported after the status).
                events.append(self.message_event(addresses=item["message"]["addresses"], direction="out", body=item["message"]["body"], at=timezone.now(), status="sent",
                                                 sub_id=item["message"].get("subscription_id"), client_uuid=uuid, kind=item["message"]["kind"]))
                item.update(step="sent", due=now + (0 if force else random.uniform(3, 12)))
            elif item["step"] == "sent":
                reports.append({"client_uuid": uuid, "status": "delivered", "at": int(now * 1000)})
                self._finish(uuid)
        self._save()
        if reports or acks:
            self.call("post", "outbox/status/", {"reports": reports, "command_acks": acks})
        if events:
            self.push(events)
        return len(reports)

    def _finish(self, uuid: str) -> None:
        self.sim.state["pending"].pop(uuid, None)
        done = self.sim.state.setdefault("done", [])
        done.append(uuid)
        self.sim.state["done"] = done[-500:]

    def tick(self, force: bool = False, rng: random.Random | None = None) -> int:
        if not self.sim.online or self.device.status != DeviceStatus.ACTIVE:
            return 0
        if force or time.time() - self.sim.state.get("last_heartbeat", 0) > 240:
            self.heartbeat()
        handled = self.work_outbox(force=force)
        if not force and (rng or random).random() < 1 / 40:
            self.receive(rng)
        return handled


# --- Entry points ------------------------------------------------------------------------------------------------


def create(*, name: str, office, user=None, dual_sim: bool = False, backfill_days: int = 30, seed: int = 7, app: str = "sms", companion: Device | None = None) -> Device:
    """Enroll a simulated phone through the real endpoints and upload its message history. `app="calls"` enrolls a
    simulated OCM Phone (the dialer app) instead, optionally linked to the SMS phone on the same handset."""
    from rest_framework.test import APIClient

    if not settings.SMS_ENABLE_SIMULATOR:
        raise RuntimeError("SMS_ENABLE_SIMULATOR is off on this server; simulated phones are not allowed.")
    invite, token = enrollment.create_invite(user, name=name, office=office, options={"backfill_days": backfill_days, "mark_read_on_open": True},
                                             platform=app, companion=companion)
    key = ec.generate_private_key(ec.SECP256R1())
    spki = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    timestamp, nonce = int(time.time()), secrets.token_urlsafe(18)
    message = canonical("ENROLL", enrollment.hash_token(token), hashlib.sha256(spki).hexdigest(), str(timestamp), nonce)
    signature = base64.b64encode(key.sign(message, ec.ECDSA(hashes.SHA256()))).decode()
    sims = [{"subscription_id": 1, "slot": 0, "carrier": "Vodacom", "country_iso": "TZ", "number": "+255754000101", "is_default": True}]
    if dual_sim:
        sims.append({"subscription_id": 2, "slot": 1, "carrier": "Airtel", "country_iso": "TZ", "number": "+255684000202", "is_default": False})
    response = APIClient(HTTP_HOST=_host()).post("/api/v1/device/enroll/", {
        "token": token, "public_key": base64.b64encode(spki).decode(), "signature": signature, "timestamp": timestamp, "nonce": nonce,
        "app_version": _app_version(), "device": {"manufacturer": "Simulated", "model": "Pixel Demo", "android_version": "14", "sdk_int": 34},
        "sims": sims, "notice_accepted": True, "notice_text": SmsSettings.load().monitoring_notice, "app": app,
    }, format="json")
    if response.status_code != 201:
        raise RuntimeError(f"simulated enrollment refused: {response.status_code} {response.json()}")
    device = Device.objects.get(pk=response.json()["device_id"])
    Device.objects.filter(pk=device.pk).update(is_simulated=True, **({"is_default_dialer": True} if app == "calls" else {"is_default_sms_app": True}))
    device.refresh_from_db()
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    sim = SimulatedDevice.objects.create(device=device, encrypted_private_key=encrypt_text(pem), state={"token": response.json()["access_token"], "token_expires": time.time() + response.json()["expires_in"]})
    phone = SimulatedPhone(sim)
    phone.heartbeat()
    if app == "sms":
        phone.backfill(backfill_days, seed=seed)
    return device


def phone_for(device: Device) -> SimulatedPhone:
    sim = SimulatedDevice.objects.select_related("device").filter(device=device).first()
    if not sim:
        raise RuntimeError("This phone is not simulated.")
    return SimulatedPhone(sim)


def control(device: Device, action: str) -> None:
    phone = phone_for(device)
    if action == "offline":
        phone.sim.online = False
        phone._save()
        # Show it offline right away, as if the last heartbeat was long ago.
        Device.objects.filter(pk=device.pk).update(last_seen_at=timezone.now() - timedelta(hours=1))
        from modules.devices.services.health import refresh_all

        refresh_all()
    elif action == "online":
        phone.sim.online = True
        phone._save()
        phone.heartbeat()
    elif action == "tick":
        phone.tick(force=True)
    elif action == "inbound":
        if phone.sim.online:
            phone.receive()


def tick_all(force: bool = False) -> int:
    handled = 0
    for sim in SimulatedDevice.objects.select_related("device").filter(online=True, device__status=DeviceStatus.ACTIVE, device__app="sms"):
        try:
            handled += SimulatedPhone(sim).tick(force=force)
        except RuntimeError as exc:
            import logging

            logging.getLogger(__name__).warning("simulated phone %s: %s", sim.device.code, exc)
    return handled
