"""Calls ingest: idempotency, call-log + live merge, returns, privacy (USSD, emergency), capability and platform gates."""

from datetime import timedelta

import pytest
from django.utils import timezone

from modules.calls.models import CallEvent, CallRecord, Result
from modules.devices.models import Device
from modules.directory.models import Customer, CustomerDevice
from modules.platforms.models import Platform
from tests.calls_helpers import MINUTE, live, log_row, now_ms


@pytest.fixture
def cphone(calls_phone):
    return calls_phone()


def test_call_log_row_is_idempotent(cphone):
    event = log_row(log_id=77)
    first = cphone.send_events(event).json()
    assert first["processed"] == 1 and first["rejected"] == []
    # The same sequence again is skipped; the same row under a new sequence updates instead of duplicating.
    assert cphone.send_events(event, seqs=[cphone.seq]).json()["skipped"] == 1
    assert cphone.send_events(event).json()["processed"] == 1
    assert CallRecord.objects.count() == 1
    call = CallRecord.objects.get()
    assert call.provider_call_log_id == 77 and call.is_final and call.talk_seconds == 60 and call.ring_seconds == 5


def test_live_events_and_call_log_merge_into_one_call(cphone):
    started = now_ms(-3)
    ringing = live(result="missed", at=started, ended=False, key="live-key-0001")
    assert cphone.send_events(ringing, {"type": "call.event", "payload": {"call_key": "live-key-0001", "kind": "ringing", "at": started}}).json()["processed"] == 2
    call = CallRecord.objects.get()
    assert not call.is_final and Device.objects.get(pk=cphone.device_id).call_state == "ringing"
    answered = live(result="answered", at=started, ring_s=7, talk_s=125, key="live-key-0001", ended_by="remote", hold_seconds=12)
    cphone.send_events(answered, {"type": "call.event", "payload": {"call_key": "live-key-0001", "kind": "ended", "at": started + 132_000}})
    # The system call log reports the same call a few seconds apart: it must merge, not duplicate.
    cphone.send_events(log_row(at=started + 2000, duration=124, log_id=901))
    assert CallRecord.objects.count() == 1
    call.refresh_from_db()
    assert call.android_call_key == "live-key-0001" and call.provider_call_log_id == 901
    assert call.result == Result.ANSWERED and call.talk_seconds == 125 and call.ring_seconds == 7  # live values win
    assert call.ended_by == "remote" and call.was_on_hold_seconds == 12 and call.is_final
    assert list(CallEvent.objects.filter(call=call).values_list("kind", flat=True)) == ["ringing", "ended"]
    assert Device.objects.get(pk=cphone.device_id).call_state == "idle"


def test_log_refines_a_generic_missed_result(cphone):
    started = now_ms(-15)
    cphone.send_events(live(result="missed", at=started, key="live-key-0002"))
    cphone.send_events(log_row(result="voicemail", at=started + 1000, log_id=5))
    assert CallRecord.objects.get().result == Result.VOICEMAIL


def test_calls_on_different_sims_or_numbers_do_not_merge(cphone):
    started = now_ms(-15)
    cphone.send_events(live(at=started), log_row(number="+255713402118", at=started + 1000))
    assert CallRecord.objects.count() == 2


def test_returns_link_both_ways_including_late_backfill(cphone, calls_phone):
    other = calls_phone(name="Second phone")
    missed_at = now_ms(-180)
    cphone.send_events(log_row(result="missed", at=missed_at, log_id=1), log_row(result="missed", at=missed_at + 2 * MINUTE, log_id=2))
    # Another phone of the company calls back and reaches the customer: both open missed calls are returned.
    other.send_events(log_row(direction="out", at=missed_at + 30 * MINUTE, log_id=10))
    back = CallRecord.objects.get(provider_call_log_id=10)
    missed = CallRecord.objects.filter(result=Result.MISSED)
    assert all(m.returned_by_id == back.pk for m in missed) and back.returns_call_id == CallRecord.objects.get(provider_call_log_id=2).pk
    # Backfill is newest first: a missed call that arrives after its return is linked too.
    cphone.send_events(log_row(number="+255688120554", direction="out", at=now_ms(-60), log_id=20),
                       log_row(number="+255688120554", result="missed", at=now_ms(-90), log_id=21))
    late = CallRecord.objects.get(provider_call_log_id=21)
    assert late.returned_by_id == CallRecord.objects.get(provider_call_log_id=20).pk
    # An unanswered call-back attempt does not count as reaching the customer.
    cphone.send_events(log_row(number="+255765330912", result="missed", at=now_ms(-50), log_id=30),
                       log_row(number="+255765330912", direction="out", result="no_answer", at=now_ms(-40), log_id=31))
    assert CallRecord.objects.get(provider_call_log_id=30).returned_at is None


def test_ussd_and_emergency_calls_are_never_stored(cphone):
    result = cphone.send_events(
        log_row(number="*150*00#", direction="out", log_id=1), live(number="*#06#", direction="out"),
        log_row(number="112", direction="out", log_id=2), live(number="911", direction="out"), log_row(number="+255754210331", log_id=3),
    ).json()
    codes = sorted(r["code"] for r in result["rejected"])
    assert codes == ["emergency_not_stored", "emergency_not_stored", "mmi_not_stored", "mmi_not_stored"]
    assert result["acked_seq"] == cphone.seq  # acknowledged: never retried, never stored
    assert list(CallRecord.objects.values_list("number_e164", flat=True)) == ["+255754210331"]
    assert not Customer.objects.filter(key__in=["112", "911", "*150*00#"]).exists()


def test_strict_validation(cphone):
    bad = [
        log_row(at=0),  # 1970
        log_row(at=now_ms(60 * 24 * 3)),  # three days ahead
        live(at=now_ms(-10), answered_at=now_ms(-20)),  # answered before it rang
        log_row(number="+2557<script>"),
        {"type": "call.upsert", "payload": {"direction": "in", "result": "missed", "number": "+255754210331", "started_at": now_ms(-1)}},  # no id
        live(talk_s=25 * 3600),  # over 24 h
        {"type": "call.event", "payload": {"call_key": "no-such-call", "kind": "ringing", "at": now_ms(-1)}},
    ]
    result = cphone.send_events(*bad).json()
    assert len(result["rejected"]) == len(bad) and CallRecord.objects.count() == 0


def test_phone_without_calls_capability_cannot_store_calls(enrolled):
    sms_only = enrolled()
    result = sms_only.send_events(log_row()).json()
    assert result["rejected"] == [{"seq": 1, "code": "platform_not_enabled"}] and CallRecord.objects.count() == 0
    assert sms_only.get("calls/config/").status_code == 403


def test_disabled_calls_platform_keeps_events_on_the_phone(cphone):
    from modules.platforms.services import sync_platform_rows

    sync_platform_rows()
    Platform.objects.filter(key="calls").update(is_enabled=False)
    blocked = cphone.send_events(log_row())
    assert blocked.status_code == 403 and blocked.json()["code"] == "platform_disabled"
    # SMS before the call event still goes through; the call event and everything after it wait on the phone.
    mixed = cphone.send_events(cphone.message(), log_row(), cphone.message()).json()
    assert mixed["processed"] == 1 and mixed["disabled_platform"] == "calls" and mixed["acked_seq"] == cphone.seq - 2
    assert CallRecord.objects.count() == 0


def test_directory_customers_from_calls_and_sms(cphone):
    cphone.send_events(log_row(number="0754210331", log_id=1), cphone.message(address="+255754210331"), log_row(number="M-PESA", log_id=2))
    customer = Customer.objects.get(key="+255754210331")
    assert customer.first_seen_call and customer.first_seen_sms
    assert CallRecord.objects.get(provider_call_log_id=1).customer == customer
    assert CustomerDevice.objects.filter(customer=customer, device_id=cphone.device_id).exists()
    assert not Customer.objects.filter(key="M-PESA").exists()  # sender IDs are services, not customers


def test_backfill_progress_and_heartbeat_fields(cphone):
    cphone.send_events({"type": "call_log.backfill", "payload": {"phase": "running", "done": 10, "total": 50}})
    device = Device.objects.get(pk=cphone.device_id)
    assert device.sync_progress["calls"] == {"phase": "running", "done": 10, "total": 50}
    response = cphone.post("heartbeat/", {"is_default_sms_app": True, "is_default_dialer": False, "full_screen_intent_allowed": False,
                                          "permissions": {"READ_CALL_LOG": False}, "call_state": "idle"})
    assert response.json()["capabilities"] == {"sms": True, "calls": True}
    assert {"not_default_dialer", "call_permissions_missing", "fsi_denied"} <= set(response.json()["attention"])


def test_annotation_from_phone_is_idempotent(cphone):
    from modules.calls.models import CallAnnotation, CallOutcome

    cphone.send_events(log_row(log_id=9))
    outcome = CallOutcome.objects.first()
    note = {"type": "call.annotation", "payload": {"client_uuid": "5b0c5c1e-6d1f-4e4c-9f1b-1b2c3d4e5f60", "call_log_id": 9, "outcome_id": outcome.pk, "note": "Wants 40 bags"}}
    cphone.send_events(note)
    cphone.send_events({**note, "payload": {**note["payload"], "note": "Wants 50 bags"}})
    annotation = CallAnnotation.objects.get()
    from common.devicecrypto import decrypt_text

    assert annotation.from_phone and annotation.outcome == outcome and decrypt_text(annotation.encrypted_note) == "Wants 50 bags"
    assert "50 bags" not in annotation.encrypted_note  # encrypted at rest


def test_deleted_on_phone_keeps_the_server_copy(cphone):
    cphone.send_events(log_row(log_id=4))
    cphone.send_events(log_row(log_id=4, deleted=True))
    call = CallRecord.objects.get()
    assert call.deleted_on_device_at is not None and call.deleted_on_device_at <= timezone.now() + timedelta(seconds=1)
