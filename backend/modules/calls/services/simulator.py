"""Simulated phones also make and take calls (demo and E2E only; production refuses the simulator).

Built on the SMS simulator's phones (modules/sms/services/simulator.py): the same enrolled device, Keystore-style key
and outbox sequence. History is uploaded like a real phone's call-log backfill (`call_log_id`, newest first); new calls
arrive like the dialer's live events (`call_key`, then `call.event`s). Realistic shape: busy mornings and afternoons,
missed bursts, after-hours calls that go unanswered, call-backs within hours, the odd conference, outcomes on some
answered calls. Callback tasks are fetched, notified, and placed after a delay, as a staff member would.
"""

from __future__ import annotations

import math
import random
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.utils import timezone

from modules.devices.models import Device, DeviceStatus
from modules.sms.models import SimulatedDevice
from modules.sms.services.simulator import CONTACTS, UNSAVED, SimulatedPhone

from ..models import CallOutcome

EXTRA_CALLERS = ["+255767440913", "+255713882004", "+255658330721", "+255744120998", "+255786551203", "+255622903417"]
HOURLY_WEIGHT = [0, 0, 0, 0, 0, 0, 1, 3, 8, 10, 9, 7, 5, 6, 8, 9, 7, 5, 3, 2, 1, 1, 0, 0]  # local time


def _ms(at: datetime) -> int:
    return int(at.timestamp() * 1000)


def _key() -> str:
    return secrets.token_urlsafe(12)


def _talk(rng: random.Random) -> int:
    return int(min(1800, max(8, rng.lognormvariate(math.log(110), 0.9))))


class CallSimulator:
    def __init__(self, phone: SimulatedPhone, rng: random.Random | None = None):
        self.phone = phone
        self.rng = rng or random.Random()
        self.state = phone.sim.state.setdefault("calls", {"next_log_id": 5000, "pending": {}})

    @property
    def device(self) -> Device:
        return self.phone.device

    def _save(self) -> None:
        self.phone.sim.state["calls"] = self.state
        self.phone._save()

    def _log_id(self) -> int:
        self.state["next_log_id"] += 1
        return self.state["next_log_id"]

    def _sub(self):
        subs = self.phone.subs()
        return self.rng.choice(subs)

    def numbers(self) -> list[tuple[str, str]]:
        return [*CONTACTS, *[("", n) for n in UNSAVED + EXTRA_CALLERS]]

    # --- history (call-log backfill) ---------------------------------------------------------------------------

    def history_events(self, days: int, tz) -> list[dict]:
        rng, now = self.rng, timezone.now()
        events = []
        people = self.numbers()
        for offset in range(days, -1, -1):
            day = (now - timedelta(days=offset)).astimezone(tz).date()
            weekday = day.isoweekday()
            volume = rng.randint(6, 14) if weekday <= 5 else rng.randint(1, 5) if weekday == 6 else rng.randint(0, 2)
            for _ in range(volume):
                hour = rng.choices(range(24), weights=HOURLY_WEIGHT)[0]
                if rng.random() < 0.08:
                    hour = rng.choice([19, 20, 21, 6])  # after hours
                start = datetime(day.year, day.month, day.day, hour, rng.randint(0, 59), rng.randint(0, 59), tzinfo=tz)
                if start >= now - timedelta(minutes=5):
                    continue
                name, number = rng.choice(people)
                events.extend(self._history_call(start, name, number, after_hours=hour < 8 or hour >= 18))
        events.sort(key=lambda e: -e["payload"]["started_at"])  # newest first, like the phone's backfill
        return events

    def _history_call(self, start: datetime, name: str, number: str, after_hours: bool) -> list[dict]:
        rng = self.rng
        sub = self._sub()
        out = []
        if rng.random() < 0.6:  # incoming
            roll = rng.random()
            if after_hours:
                result = "missed" if roll < 0.75 else "answered"
            else:
                result = "answered" if roll < 0.7 else "missed" if roll < 0.88 else "rejected" if roll < 0.95 else "voicemail"
            out.append(self._log_row("in", result, number, name, start, sub))
            if result != "answered" and rng.random() < 0.65:
                # A call-back from the office, usually within a few hours.
                back = start + timedelta(minutes=rng.randint(10, 360))
                if back < timezone.now() - timedelta(minutes=2):
                    out.append(self._log_row("out", "answered" if rng.random() < 0.8 else "no_answer", number, name, back, sub))
            if result == "missed" and rng.random() < 0.25:
                out.append(self._log_row("in", "missed", number, name, start + timedelta(minutes=rng.randint(1, 6)), sub))  # a burst
        else:
            roll = rng.random()
            result = "answered" if roll < 0.75 else "no_answer" if roll < 0.9 else "busy" if roll < 0.97 else "failed"
            row = self._log_row("out", result, number, name, start, sub)
            if result == "answered" and rng.random() < 0.05:
                row["payload"].update(is_conference=True, conference_size=3)
            out.append(row)
        return out

    def _log_row(self, direction: str, result: str, number: str, name: str, start: datetime, sub) -> dict:
        talk = _talk(self.rng) if result == "answered" else 0
        ring = self.rng.randint(3, 25) if direction == "in" else self.rng.randint(5, 30)
        payload = {
            "call_log_id": self._log_id(), "direction": direction, "result": result, "number": number, "contact_name": name, "started_at": _ms(start),
            "duration": talk, "sub_id": sub, "presentation": "allowed",
        }
        if result == "answered":
            payload["answered_at"] = _ms(start + timedelta(seconds=ring))
        return {"type": "call.upsert", "payload": payload}

    def backfill(self, days: int = 45) -> int:
        from ..services.stats import tz_for

        events = self.history_events(days, tz_for(None))
        self.phone.push([{"type": "call_log.backfill", "payload": {"phase": "running", "done": 0, "total": len(events)}}])
        self.phone.push(events)
        self.phone.push([{"type": "call_log.backfill", "payload": {"phase": "done", "done": len(events), "total": len(events)}}])
        self._annotate_some()
        self._save()
        return len(events)

    def _annotate_some(self) -> None:
        from ..models import CallRecord

        outcomes = list(CallOutcome.objects.filter(is_active=True).values_list("pk", flat=True))
        if not outcomes:
            return
        events = []
        for call in CallRecord.objects.filter(device=self.device, result="answered").order_by("-started_at")[:40]:
            if self.rng.random() < 0.5:
                events.append({"type": "call.annotation", "payload": {"client_uuid": str(uuid.uuid4()), "call_log_id": call.provider_call_log_id,
                                                                      "outcome_id": self.rng.choice(outcomes), "note": ""}})
        if events:
            self.phone.push(events)

    # --- live behaviour -------------------------------------------------------------------------------------------

    def incoming(self, result: str | None = None) -> None:
        """A call rings now; it is answered (and ends a little later on a later tick) or missed."""
        rng, now = self.rng, timezone.now()
        name, number = rng.choice(self.numbers())
        key, sub = _key(), self._sub()
        result = result or ("answered" if rng.random() < 0.65 else "missed")
        ring = rng.randint(4, 20)
        events = [
            {"type": "call.upsert", "payload": {"call_key": key, "direction": "in", "result": "missed", "number": number, "contact_name": name,
                                                "started_at": _ms(now), "sub_id": sub}},
            {"type": "call.event", "payload": {"call_key": key, "kind": "ringing", "at": _ms(now)}},
        ]
        if result == "answered":
            answered = now + timedelta(seconds=ring)
            events.append({"type": "call.event", "payload": {"call_key": key, "kind": "active", "at": _ms(answered)}})
            self.state["pending"][key] = {"payload": {**events[0]["payload"], "result": "answered", "answered_at": _ms(answered)},
                                          "end": time.time() + rng.randint(20, 90), "talk": _talk(rng)}
        else:
            ended = now + timedelta(seconds=ring)
            events[0]["payload"].update(ended_at=_ms(ended), ended_by="remote")
            events.append({"type": "call.event", "payload": {"call_key": key, "kind": "ended", "at": _ms(ended)}})
        self.phone.push(events)
        self._save()

    def finish_due(self, force: bool = False) -> int:
        done = 0
        for key, item in list(self.state["pending"].items()):
            if not force and item["end"] > time.time():
                continue
            ended = datetime.fromtimestamp(item["payload"]["answered_at"] / 1000, tz=dt_timezone.utc) + timedelta(seconds=item["talk"])
            ended = min(ended, timezone.now())
            payload = {**item["payload"], "ended_at": _ms(ended), "ended_by": self.rng.choice(["local", "remote"])}
            self.phone.push([{"type": "call.upsert", "payload": payload}, {"type": "call.event", "payload": {"call_key": key, "kind": "ended", "at": _ms(ended)}}])
            self.state["pending"].pop(key)
            done += 1
        self._save()
        return done

    def work_callbacks(self, force: bool = False) -> int:
        """Fetch call-back tasks; notify new ones; place due ones after a short 'staff' delay (never instantly)."""
        tasks = self.phone.call("get", "calls/callbacks/")
        handled = 0
        seen = self.state.setdefault("tasks", {})
        now = time.time()
        for task in tasks:
            info = seen.setdefault(task["id"], {"notified": False, "dial_at": now + (0 if force else self.rng.randint(20, 120))})
            if not info["notified"]:
                self.phone.push([{"type": "callback.state", "payload": {"task": task["id"], "state": "notified", "at": int(now * 1000)}}])
                info["notified"] = True
                handled += 1
            if task["state"] in ("open", "notified") and info["dial_at"] <= now and task["due_at"] <= now * 1000 + 60_000:
                # Placed after the task became due (never "before" the missed call it answers), ending now.
                end = timezone.now()
                started = max(end - timedelta(seconds=80), datetime.fromtimestamp(task["due_at"] / 1000, tz=dt_timezone.utc) + timedelta(seconds=1))
                started = min(started, end - timedelta(seconds=3))
                answered = started + (end - started) / 4
                key = _key()
                self.phone.push([
                    {"type": "callback.state", "payload": {"task": task["id"], "state": "dialed", "at": _ms(started)}},
                    {"type": "call.upsert", "payload": {"call_key": key, "direction": "out", "result": "answered", "number": task["number"], "started_at": _ms(started),
                                                        "answered_at": _ms(answered), "ended_at": _ms(end), "ended_by": "local",
                                                        "origin": "callback_task", "callback_task": task["id"], "sub_id": self._sub()}},
                ])
                handled += 1
        self._save()
        return handled

    def tick(self, force: bool = False) -> int:
        handled = self.finish_due(force)
        handled += self.work_callbacks(force)
        if not force and self.rng.random() < 1 / 30:
            self.incoming()
            handled += 1
        return handled


def enable(device: Device) -> None:
    capabilities = {**(device.capabilities or {}), "calls": True}
    Device.objects.filter(pk=device.pk).update(capabilities=capabilities, is_default_dialer=True)
    device.capabilities, device.is_default_dialer = capabilities, True


def simulator_for(device: Device, rng=None) -> CallSimulator:
    sim = SimulatedDevice.objects.select_related("device").filter(device=device).first()
    if not sim:
        raise RuntimeError("This phone is not simulated.")
    return CallSimulator(SimulatedPhone(sim), rng)


def seed(device: Device, days: int = 45, seed_value: int = 7) -> int:
    if not settings.SMS_ENABLE_SIMULATOR:
        raise RuntimeError("SMS_ENABLE_SIMULATOR is off on this server; simulated phones are not allowed.")
    enable(device)
    return simulator_for(device, random.Random(seed_value)).backfill(days)


def control(device: Device, action: str) -> None:
    simulator = simulator_for(device)
    if action == "incoming":
        simulator.incoming()
    elif action == "missed":
        simulator.incoming("missed")
    elif action == "tick":
        simulator.tick(force=True)


def tick_all(force: bool = False) -> int:
    handled = 0
    for sim in SimulatedDevice.objects.select_related("device").filter(online=True, device__status=DeviceStatus.ACTIVE, device__capabilities__calls=True):
        try:
            handled += CallSimulator(SimulatedPhone(sim)).tick(force=force)
        except RuntimeError as exc:
            import logging

            logging.getLogger(__name__).warning("simulated phone %s (calls): %s", sim.device.code, exc)
    return handled
