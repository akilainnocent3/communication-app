"""Calls admin API: permission matrix, filters, detail + audit, notes, call-backs, export masking, directory, settings,
office hours, auto-SMS after missed calls, rollups == raw, retention."""

import io
import random
import zipfile
from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.utils import timezone

from modules.audit.models import AuditEvent
from modules.calls.models import CallbackTask, CallOutcome, CallRecord, CallSettings, CallStatHourly, OfficeHours, Result
from modules.calls.services import hours, rollups, stats
from modules.devices.models import Device
from modules.directory.models import Customer
from modules.platforms.models import Platform
from tests.calls_helpers import live, log_row, now_ms


@pytest.fixture
def two_phones(calls_phone, other_office):
    hq, arusha = calls_phone(name="HQ desk"), calls_phone(name="Arusha desk", target_office=other_office)
    # Each phone: an answered call, then a missed call from the same customer that nobody has returned yet.
    hq.send_events(log_row(log_id=1), log_row(result="missed", at=now_ms(-10), log_id=2), log_row(direction="out", at=now_ms(-60), log_id=3, number="+255713402118"))
    arusha.send_events(log_row(number="+255688120554", log_id=1), log_row(number="+255688120554", result="missed", at=now_ms(-5), log_id=2))
    return hq, arusha


def test_permission_matrix(client_for, admin, manager, viewer, two_phones, calls_grant):
    hq, arusha = two_phones
    hq_call = CallRecord.objects.filter(device_id=hq.device_id).first()
    arusha_call = CallRecord.objects.filter(device_id=arusha.device_id).first()
    admin_client = client_for(admin)
    assert len(admin_client.get("/api/v1/calls/calls/").json()["results"]) == 5
    # No access rows: nothing visible, objects answer 404 (existence not revealed).
    mgr = client_for(manager)
    assert mgr.get("/api/v1/calls/calls/").json()["results"] == []
    assert mgr.get(f"/api/v1/calls/calls/{hq_call.pk}/").status_code == 404
    assert mgr.get(f"/api/v1/calls/calls/?device={hq.device_id}").status_code == 404
    # Read access to one phone: its calls only; notes and call-backs need their own flags.
    calls_grant(manager, hq.device_id)
    assert {c["id"] for c in mgr.get("/api/v1/calls/calls/").json()["results"]} == set(CallRecord.objects.filter(device_id=hq.device_id).values_list("pk", flat=True))
    assert mgr.get(f"/api/v1/calls/calls/{arusha_call.pk}/").status_code == 404
    assert mgr.post(f"/api/v1/calls/calls/{hq_call.pk}/annotations/", {"note": "x"}, format="json").status_code == 403
    assert mgr.post("/api/v1/calls/callbacks/", {"device": hq.device_id, "number": "+255754210331"}, format="json").status_code == 403
    calls_grant(manager, hq.device_id, can_annotate=True, can_assign_callbacks=True)
    assert mgr.post(f"/api/v1/calls/calls/{hq_call.pk}/annotations/", {"note": "Asked for price"}, format="json").status_code == 201
    assert mgr.post("/api/v1/calls/callbacks/", {"device": hq.device_id, "number": "+255754210331"}, format="json").status_code == 201
    assert mgr.post("/api/v1/calls/callbacks/", {"device": arusha.device_id, "number": "+255754210331"}, format="json").status_code == 404
    # Settings, export and enabling phones are admin-only.
    assert mgr.patch("/api/v1/calls/settings/", {"unreturned_hours": 2}, format="json").status_code == 403
    assert mgr.get("/api/v1/calls/export/").status_code == 403
    assert mgr.post(f"/api/v1/calls/devices/{hq.device_id}/enable/", {"enabled": False}, format="json").status_code == 403
    # A role without calls.access sees no platform at all; a disabled platform refuses everyone.
    from modules.identity.services import assign_role

    assign_role(viewer, None)
    assert client_for(viewer).get("/api/v1/calls/calls/").status_code == 403
    from modules.platforms.services import sync_platform_rows

    sync_platform_rows()
    Platform.objects.filter(key="calls").update(is_enabled=False)
    assert admin_client.get("/api/v1/calls/calls/").status_code == 403
    assert admin_client.get("/api/v1/auth/me/").json()["platform_data"]["calls"]["devices"] == []


def test_list_filters_and_detail_audit(client_for, admin, two_phones):
    hq, _ = two_phones
    client = client_for(admin)
    missed = client.get("/api/v1/calls/calls/?folder=missed").json()["results"]
    assert {c["result"] for c in missed} == {"missed"} and len(missed) == 2
    assert len(client.get(f"/api/v1/calls/calls/?device={hq.device_id}&folder=outgoing").json()["results"]) == 1
    assert len(client.get("/api/v1/calls/calls/?q=0713402118").json()["results"]) == 1
    assert len(client.get("/api/v1/calls/calls/?min_duration=30").json()["results"]) == 3
    assert client.get("/api/v1/calls/calls/?folder=unreturned").json()["results"][0]["returned_at"] is None
    call = CallRecord.objects.filter(device_id=hq.device_id, result="answered").first()
    detail = client.get(f"/api/v1/calls/calls/{call.pk}/").json()
    assert detail["permissions"]["annotate"] and detail["history"]  # the customer's missed call on the same number
    assert AuditEvent.objects.filter(action="calls.call_open", target_id=str(call.pk)).count() == 1
    client.get(f"/api/v1/calls/calls/{call.pk}/?peek=1")
    assert AuditEvent.objects.filter(action="calls.call_open").count() == 1


def test_annotations_by_admin(client_for, admin, manager, two_phones):
    call = CallRecord.objects.filter(result="answered").first()
    client = client_for(admin)
    outcome = CallOutcome.objects.get(name="Sale")
    created = client.post(f"/api/v1/calls/calls/{call.pk}/annotations/", {"outcome": outcome.pk, "note": "40 bags", "tags": ["cement"]}, format="json").json()
    assert created["outcome"]["name"] == "Sale" and created["note"] == "40 bags"
    assert client.get(f"/api/v1/calls/calls/?outcome={outcome.pk}").json()["results"][0]["outcome"]["name"] == "Sale"
    assert client.patch(f"/api/v1/calls/annotations/{created['id']}/", {"note": "50 bags"}, format="json").json()["note"] == "50 bags"
    assert client.post(f"/api/v1/calls/calls/{call.pk}/annotations/", {}, format="json").status_code == 400
    assert client.delete(f"/api/v1/calls/annotations/{created['id']}/").status_code == 204
    assert AuditEvent.objects.filter(action__startswith="calls.annotation_").count() == 3


def test_callback_lifecycle(client_for, admin, two_phones):
    hq, _ = two_phones
    client = client_for(admin)
    missed = CallRecord.objects.get(device_id=hq.device_id, result="missed")
    task = client.post("/api/v1/calls/callbacks/", {"device": hq.device_id, "call": missed.pk, "reason": "Price of cement", "priority": "high"}, format="json").json()
    assert task["state"] == "open" and task["number"] == missed.number_e164 and task["reason"] == "Price of cement"
    on_phone = hq.get("calls/callbacks/").json()
    assert [t["number"] for t in on_phone] == [missed.number_e164] and on_phone[0]["requested_by"] and on_phone[0]["reason"] == "Price of cement"
    uuid = on_phone[0]["id"]
    hq.send_events({"type": "callback.state", "payload": {"task": uuid, "state": "notified", "at": now_ms()}})
    assert CallbackTask.objects.get().state == "notified"
    # The staff member taps Call: the call carries the task and, once answered, completes it and returns the missed call.
    hq.send_events(live(number=missed.number_e164, direction="out", at=now_ms(-2), talk_s=30, callback_task=uuid, origin="callback_task"))
    task_row = CallbackTask.objects.get()
    call = CallRecord.objects.get(callback_task=task_row)
    assert task_row.state == "done" and task_row.call == call and call.origin == "callback_task"
    assert CallRecord.objects.get(pk=missed.pk).returned_by == call
    assert hq.get("calls/callbacks/").json() == []
    # Cancel and expiry.
    second = client.post("/api/v1/calls/callbacks/", {"device": hq.device_id, "number": "0754000999"}, format="json").json()
    assert client.post(f"/api/v1/calls/callbacks/{second['id']}/cancel/").json()["state"] == "cancelled"
    assert client.post(f"/api/v1/calls/callbacks/{second['id']}/cancel/").status_code == 409
    third = client.post("/api/v1/calls/callbacks/", {"device": hq.device_id, "number": "0754000998"}, format="json").json()
    from modules.calls.services.callbacks import expire

    assert expire(timezone.now() + timedelta(days=10)) == 1 and CallbackTask.objects.get(pk=third["id"]).state == "expired"
    assert client.post("/api/v1/calls/callbacks/", {"device": hq.device_id, "number": "*150#"}, format="json").status_code == 400
    assert {e.action for e in AuditEvent.objects.filter(action__startswith="calls.callback")} == {"calls.callback_create", "calls.callback_cancel"}


def test_callback_bulk_reassign(client_for, admin, two_phones):
    hq, arusha = two_phones
    client = client_for(admin)
    ids = [client.post("/api/v1/calls/callbacks/", {"device": hq.device_id, "number": n}, format="json").json()["id"] for n in ("0754000101", "0754000102")]
    moved = client.post("/api/v1/calls/callbacks/bulk/", {"ids": ids, "action": "assign", "device": arusha.device_id}, format="json").json()
    assert {t["device"]["id"] for t in moved} == {arusha.device_id}
    assert len(arusha.get("calls/callbacks/").json()) == 2 and hq.get("calls/callbacks/").json() == []


def test_export_masks_numbers_without_can_export(client_for, admin, manager, two_phones, calls_grant):
    hq, _ = two_phones
    from django.contrib.auth.models import Permission

    manager.user_permissions.add(Permission.objects.get(codename="export", content_type__app_label="calls"))
    calls_grant(manager, hq.device_id)
    from modules.identity.models import User

    manager = User.objects.get(pk=manager.pk)
    masked = client_for(manager).get("/api/v1/calls/export/").content.decode()
    assert "•" in masked and "+255 754 210 331" not in masked
    calls_grant(manager, hq.device_id, can_export=True)
    full = client_for(User.objects.get(pk=manager.pk)).get("/api/v1/calls/export/").content.decode()
    assert "+255 754 210 331" in full and "Arusha desk" not in full  # still only the phones they can read
    xlsx = client_for(admin).get("/api/v1/calls/export/?file_format=xlsx")
    assert xlsx["Content-Type"].startswith("application/vnd.openxmlformats")
    sheet = zipfile.ZipFile(io.BytesIO(xlsx.content)).read("xl/worksheets/sheet1.xml").decode()
    assert "+255 688 120 554" in sheet and "Arusha desk" in sheet
    assert AuditEvent.objects.filter(action="calls.export").count() == 3


def test_csv_formula_injection_is_neutralised():
    from modules.calls.services.export import to_csv

    assert b"'=HYPERLINK" in to_csv([["=HYPERLINK(\"x\")"]])
    # A digit after the sign does not make a formula harmless; only phone numbers are left unquoted.
    for formula in ("=1+cmd|' /C calc'!A0", "@1SUM(A1)", "+1+HYPERLINK(\"x\")", "-2+3"):
        assert to_csv([[formula]]).decode().splitlines()[-1].strip('"').startswith("'"), formula
    for number in ("+255 754 210 331", "+2557•••••331", "+255754210331"):
        assert to_csv([[number]]).decode().splitlines()[-1] == number


def test_directory_crud_merge_visibility_and_phone_delta(client_for, admin, manager, two_phones, calls_grant):
    hq, arusha = two_phones
    client = client_for(admin)
    a = Customer.objects.get(key="+255754210331")
    created = client.post("/api/v1/calls/customers/", {"number": "0713402119", "display_name": "Neema Mushi (2nd)", "tags": ["vip"]}, format="json").json()
    assert client.post("/api/v1/calls/customers/", {"number": "+255713402119"}, format="json").status_code == 409
    updated = client.patch(f"/api/v1/calls/customers/{a.pk}/", {"display_name": "Neema Mushi", "notes": "Prefers Swahili", "tags": ["vip", "VIP"]}, format="json").json()
    assert updated["notes"] == "Prefers Swahili" and updated["tags"] == ["vip"]
    assert "Prefers" not in Customer.objects.get(pk=a.pk).encrypted_notes
    # Caller ID delta for the HQ phone: only customers in contact with it, names only.
    delta = hq.get("calls/directory/").json()
    assert {e["number"] for e in delta["entries"] if not e["removed"]} == {"+255754210331"} and delta["complete"]
    assert "+255688120554" not in {e["number"] for e in arusha.get("calls/directory/").json()["entries"] if not e["removed"]}
    again = hq.get(f"calls/directory/?cursor={delta['next_cursor']}").json()
    assert again["entries"] == []
    # Merge moves the calls; the merged number keeps resolving to the survivor.
    merged = client.post("/api/v1/calls/customers/merge/", {"target": a.pk, "sources": [created["id"]]}, format="json").json()
    assert merged["aliases"] == ["+255713402119"] and merged["tags"] == ["vip"]
    hq.send_events(log_row(number="+255713402119", log_id=50))
    assert CallRecord.objects.get(device_id=hq.device_id, provider_call_log_id=50).customer_id == a.pk
    # Visibility: an office manager sees customers of the phones they can read, and cannot edit without annotate.
    mgr = client_for(manager)
    assert mgr.get("/api/v1/calls/customers/").json()["results"] == []
    calls_grant(manager, arusha.device_id)
    assert [c["key"] for c in mgr.get("/api/v1/calls/customers/").json()["results"]] == ["+255688120554"]
    assert mgr.get(f"/api/v1/calls/customers/{a.pk}/").status_code == 404
    arusha_customer = Customer.objects.get(key="+255688120554")
    assert mgr.patch(f"/api/v1/calls/customers/{arusha_customer.pk}/", {"display_name": "X"}, format="json").status_code == 403
    timeline = client.get(f"/api/v1/calls/customers/{a.pk}/timeline/").json()
    assert {item["kind"] for item in timeline} == {"call"}
    assert AuditEvent.objects.filter(action__startswith="directory.").count() >= 3


def test_settings_office_hours_and_tariffs(client_for, admin, office):
    client = client_for(admin)
    assert client.patch("/api/v1/calls/settings/", {"unreturned_hours": 2, "auto_sms_enabled": True}, format="json").json()["unreturned_hours"] == 2
    assert AuditEvent.objects.filter(action="calls.settings_update").exists()
    bad = client.put(f"/api/v1/calls/office-hours/{office.pk}/", {"timezone": "Africa/Dar_es_Salaam", "week": {"1": [["17:00", "08:00"]]}, "holidays": []}, format="json")
    assert bad.status_code == 400
    ok = client.put(f"/api/v1/calls/office-hours/{office.pk}/", {"timezone": "Africa/Nairobi", "week": {"1": [["08:00", "12:00"], ["13:00", "17:00"]]}, "holidays": ["2026-12-25"]}, format="json")
    assert ok.status_code == 200 and ok.json()["configured"]
    tariff = client.post("/api/v1/calls/tariffs/", {"carrier": "Vodacom", "per_minute": "35.00"}, format="json")
    assert tariff.status_code == 201


def test_office_hours_with_time_zones_and_holidays(office):
    OfficeHours.objects.create(office=office, timezone="Africa/Dar_es_Salaam", week=hours.clean_week({"1": [["08:00", "12:00"], ["13:00", "17:00"]]}), holidays=["2026-12-28"])
    eat = dt_timezone(timedelta(hours=3))
    monday = datetime(2026, 11, 2, tzinfo=eat)
    assert not hours.is_after_hours(monday.replace(hour=9), office.pk)
    assert hours.is_after_hours(monday.replace(hour=12, minute=30), office.pk)  # lunch
    assert hours.is_after_hours(monday.replace(hour=17), office.pk)
    assert hours.is_after_hours(datetime(2026, 11, 3, 9, tzinfo=eat), office.pk)  # Tuesday: no hours configured
    assert hours.is_after_hours(datetime(2026, 12, 28, 9, tzinfo=eat), office.pk)  # holiday (a Monday)
    # 06:30 UTC is 09:30 in Dar es Salaam: office time decides, not server time.
    assert not hours.is_after_hours(datetime(2026, 11, 2, 6, 30, tzinfo=dt_timezone.utc), office.pk)
    # No hours configured: the default week (Mon–Fri 08–17, Sat 08–13).
    assert not hours.is_after_hours(datetime(2026, 11, 7, 10, tzinfo=eat), None)
    assert hours.is_after_hours(datetime(2026, 11, 8, 10, tzinfo=eat), None)


def test_auto_sms_after_missed_call(calls_phone, enrolled):
    from modules.sms.models import Message

    sms_phone = enrolled(name="Front desk")
    lonely = calls_phone(name="No SMS app")
    phone = calls_phone(companion=sms_phone)  # OCM Phone on the same handset as OCM Messages
    config = CallSettings.load()
    phone.send_events(live(result="missed", at=now_ms(-1)))
    assert not Message.objects.filter(origin="auto").exists()  # off by default
    config.auto_sms_enabled = True
    config.save()
    phone.send_events(live(result="missed", at=now_ms(-1)))
    message = Message.objects.get(origin="auto")
    assert message.status == "queued" and message.address == "+255754210331"
    # Queued on the SMS phone of the same handset, which claims and sends it; the dialer has no SMS outbox.
    assert str(message.conversation.device_id) == sms_phone.device_id
    assert [m["client_uuid"] for m in sms_phone.post("outbox/claim/", {"limit": 10}).json()["messages"]] == [str(message.client_uuid)]
    lonely.send_events(live(result="missed", at=now_ms(-1), number="+255765330912"))  # no OCM Messages on that handset: nothing sent
    phone.send_events(live(result="missed", at=now_ms(-1)))  # cool-down: one per number per day
    phone.send_events(log_row(result="missed", at=now_ms(-600), number="+255713402118"))  # history: never
    phone.send_events(live(result="missed", at=now_ms(-1), number="15300"))  # short code: never
    Customer.objects.filter(key="+255688120554").delete()
    Customer.objects.create(key="+255688120554", number_e164="+255688120554", auto_sms_opt_out=True)
    phone.send_events(live(result="missed", at=now_ms(-1), number="+255688120554"))  # opted out
    assert Message.objects.filter(origin="auto").count() == 1


def test_rollups_match_raw_aggregation(calls_phone, admin, client_for):
    phone = calls_phone()
    rng = random.Random(3)
    events = []
    for index in range(300):
        at = now_ms(-rng.randint(1, 60 * 24 * 20))
        result = rng.choice(["answered", "answered", "missed", "rejected", "voicemail", "no_answer", "busy"])
        direction = "out" if result in ("no_answer", "busy") or rng.random() < 0.3 else "in"
        if direction == "out" and result in ("missed", "rejected", "voicemail"):
            result = "answered"
        events.append(log_row(number=rng.choice(["+255754210331", "+255713402118", "+255688120554", "+255765330912"]), direction=direction, result=result,
                              at=at, duration=rng.randint(5, 400), log_id=index))
    for start in range(0, len(events), 150):
        phone.send_events(*events[start:start + 150])
    # A late refinement of a final call changes its contribution (subtract old, add new).
    phone.send_events(live(result="missed", at=now_ms(-5), key="refine-key-01"))
    phone.send_events(log_row(result="voicemail", at=now_ms(-5) + 1000, log_id=9999))
    start, end, _ = stats.period(admin, 30)
    device_ids = [phone.device_id]
    raw = stats.raw_totals(device_ids, start, end)
    dashboard = client_for(admin).get("/api/v1/calls/stats/?range=30").json()
    kpis = dashboard["kpis"]
    assert (kpis["total"], kpis["incoming"], kpis["outgoing"], kpis["missed"], kpis["answered_incoming"]) == (raw["total"], raw["incoming"], raw["outgoing"], raw["missed"], raw["answered_in"])
    assert kpis["talk_minutes"] == round((raw["talk"] or 0) / 60)
    # Dashboard "missed" == the Missed folder of the call log with the same dates.
    today = timezone.now().astimezone(stats.tz_for(admin)).date()
    after = (today - timedelta(days=29)).isoformat()
    missed_list, cursor = [], None
    while True:
        page = client_for(admin).get(f"/api/v1/calls/calls/?folder=missed&after={after}&before={today.isoformat()}" + (f"&cursor={cursor}" if cursor else "")).json()
        missed_list += page["results"]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(missed_list) == kpis["missed"]
    # The nightly repair rebuilds exactly what ingest maintained.
    before = sorted(CallStatHourly.objects.values_list("hour", "direction", "result", "calls", "talk_seconds", "ring_seconds"))
    rollups.rebuild(timezone.now() - timedelta(days=40), timezone.now())
    assert sorted(CallStatHourly.objects.values_list("hour", "direction", "result", "calls", "talk_seconds", "ring_seconds")) == before
    assert sum(r["count"] for r in dashboard["by_result"]) == raw["total"]
    assert sum(sum(row) for row in dashboard["heatmap"]) == raw["incoming"]


def test_unreturned_metric(calls_phone, admin):
    phone = calls_phone()
    config = CallSettings.load()
    config.unreturned_hours = 4
    config.save()
    phone.send_events(
        log_row(number="+255754210331", result="missed", at=now_ms(-600), log_id=1), log_row(number="+255754210331", direction="out", at=now_ms(-570), log_id=2),  # in time
        log_row(number="+255713402118", result="missed", at=now_ms(-600), log_id=3), log_row(number="+255713402118", direction="out", at=now_ms(-200), log_id=4),  # late
        log_row(number="+255688120554", result="missed", at=now_ms(-600), log_id=5),  # never
        log_row(number="+255765330912", result="missed", at=now_ms(-30), log_id=6),  # still open
    )
    start, end, _ = stats.period(admin, 7)
    summary = stats.unreturned_summary([phone.device_id], start, end, 4, timezone.now())
    assert (summary["returned_in_time"], summary["unreturned"], summary["open"]) == (1, 2, 1)
    assert summary["median_minutes"] == round((30 + 400) / 2)


def test_live_board_and_badges(client_for, admin, two_phones):
    hq, _ = two_phones
    hq.post("heartbeat/", {"is_default_sms_app": True, "is_default_dialer": True, "call_state": "active"})
    live_board = client_for(admin).get("/api/v1/calls/live/").json()
    states = {p["name"]: p["state"] for p in live_board["phones"]}
    assert states["HQ desk"] == "active" and live_board["totals"]["on_call"] == 1
    badges = client_for(admin).get("/api/v1/calls/badges/").json()
    assert badges["unreturned"] == 2


def test_ocm_phone_enrolls_on_its_own_and_links_to_the_sms_phone(client_for, admin, office, phone):
    """Decision 80: OCM Phone is its own app with its own code, key and device; OCM Messages never takes calls."""
    from tests.phone import Phone

    client = client_for(admin)
    assert [d["id"] for d in client.get("/api/v1/calls/devices/?candidates=1").json()] == [phone.device_id]
    assert client.post(f"/api/v1/calls/devices/{phone.device_id}/enable/", {"enabled": True}, format="json").json()["code"] == "wrong_app"
    assert phone.send_events(log_row()).json()["rejected"][0]["code"] == "platform_not_enabled"

    created = client.post("/api/v1/calls/enrollments/", {"name": "Front desk", "office": office.pk, "companion": phone.device_id}, format="json")
    assert created.status_code == 201 and created.json()["uri"].startswith("ocmphone://enroll?") and created.json()["platforms"] == ["calls"]
    token = created.json()["code"]
    info = Phone().client.get(f"/api/v1/device/enroll/info/?token={token}").json()
    assert info["platform"] == "calls" and "never the conversation" in info["notice"]
    # The SMS app cannot use an OCM Phone code (and the attempt does not burn it).
    wrong = Phone().enroll(token)
    assert wrong.status_code == 409 and wrong.json()["code"] == "wrong_app"
    dialer = Phone()
    assert dialer.enroll(token, app="calls").status_code == 201
    device = Device.objects.get(pk=dialer.device_id)
    assert device.app == "calls" and device.capabilities == {"sms": False, "calls": True}
    assert str(device.companion_id) == phone.device_id and str(Device.objects.get(pk=phone.device_id).companion_id) == dialer.device_id
    heartbeat = dialer.post("heartbeat/", {"is_default_dialer": True}).json()
    assert heartbeat["capabilities"] == {"sms": False, "calls": True} and "not_default_sms_app" not in heartbeat["attention"]
    assert dialer.send_events(log_row()).json()["processed"] == 1
    assert dialer.send_events(dialer.message()).json()["rejected"][0]["code"] == "platform_not_enabled"
    listed = client.get("/api/v1/calls/devices/").json()
    assert [(d["id"], d["app"], d["companion"]["id"]) for d in listed] == [(dialer.device_id, "calls", phone.device_id)]
    # The admin can switch Calls off and on for OCM Phone.
    assert not client.post(f"/api/v1/calls/devices/{dialer.device_id}/enable/", {"enabled": False}, format="json").json()["calls_enabled"]
    assert AuditEvent.objects.filter(action="calls.device_disable").exists()


def test_sms_codes_are_for_ocm_messages_only(client_for, admin, office):
    from tests.phone import Phone

    created = client_for(admin).post("/api/v1/sms/enrollments/", {"name": "Desk", "office": office.pk, "platforms": ["sms", "calls"]}, format="json").json()
    assert created["platforms"] == ["sms"] and created["uri"].startswith("cmsms://enroll?")
    assert Phone().enroll(created["code"], app="calls").json()["code"] == "wrong_app"


def test_only_calls_admins_make_ocm_phone_codes(client_for, manager, office):
    assert client_for(manager).post("/api/v1/calls/enrollments/", {"name": "Desk", "office": office.pk}, format="json").status_code == 403


def test_retention_purge(calls_phone, settings):
    phone = calls_phone()
    phone.send_events(log_row(at=now_ms(-60 * 24 * 400), log_id=1), log_row(at=now_ms(-60), log_id=2))
    settings.CALLS_RETENTION_DAYS = 365
    from modules.calls.services.retention import purge

    assert purge() == 1 and list(CallRecord.objects.values_list("provider_call_log_id", flat=True)) == [2]
    assert AuditEvent.objects.filter(action="calls.retention_purge").exists()


def test_rotate_keys_covers_calls_and_directory(calls_phone, settings):
    from cryptography.fernet import Fernet
    from django.core.management import call_command

    from common.devicecrypto import decrypt_text, encrypt_text
    from modules.calls.models import CallAnnotation

    phone = calls_phone()
    phone.send_events(log_row(log_id=1))
    note = CallAnnotation.objects.create(call=CallRecord.objects.get(), encrypted_note=encrypt_text("secret note"))
    old = note.encrypted_note
    settings.SMS_DATA_KEYS = [Fernet.generate_key().decode(), *settings.SMS_DATA_KEYS]
    call_command("rotate_sms_keys", stdout=io.StringIO())
    note.refresh_from_db()
    assert note.encrypted_note != old
    settings.SMS_DATA_KEYS = settings.SMS_DATA_KEYS[:1]
    assert decrypt_text(note.encrypted_note) == "secret note"


def test_simulated_phone_makes_calls(admin, office):
    from modules.calls.services import simulator as calls_simulator
    from modules.sms.services import simulator

    device = simulator.create(name="Demo", office=office, user=admin, backfill_days=3)
    count = calls_simulator.seed(device, days=5, seed_value=4)
    assert count == CallRecord.objects.filter(device=device).count() > 0
    calls_simulator.control(device, "missed")
    calls_simulator.control(device, "incoming")
    task = CallbackTask.objects.create(device=device, number_e164="+255754210331", due_at=timezone.now(), expires_at=timezone.now() + timedelta(days=1))
    calls_simulator.control(device, "tick")
    task.refresh_from_db()
    assert task.state == "done" and task.call is not None
    assert Result.MISSED in set(CallRecord.objects.filter(device=device).values_list("result", flat=True))
