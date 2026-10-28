"""Calls tools: outcomes, tariffs, office hours, per-phone access, call-back views, customer delete, demo controls, tasks."""

from modules.audit.models import AuditEvent
from modules.calls import tasks
from modules.calls.models import CallbackTask, CallOutcome, CallRecord, CarrierTariff, DeviceAccess
from tests.calls_helpers import log_row, now_ms


def test_outcomes_tariffs_and_hours(client_for, admin, manager, office, calls_phone):
    client = client_for(admin)
    created = client.post("/api/v1/calls/outcomes/", {"name": "Quote sent", "colour": "#123456", "order": 5}, format="json").json()
    assert client.patch(f"/api/v1/calls/outcomes/{created['id']}/", {"name": "Quote"}, format="json").json()["name"] == "Quote"
    assert "Quote" in [o["name"] for o in client.get("/api/v1/calls/outcomes/").json()]
    assert client_for(manager).post("/api/v1/calls/outcomes/", {"name": "X"}, format="json").status_code == 403
    # Used outcomes are retired, not deleted (past notes keep their label).
    phone = calls_phone()
    phone.send_events(log_row(log_id=1))
    sale = CallOutcome.objects.get(name="Sale")
    client.post(f"/api/v1/calls/calls/{CallRecord.objects.get().pk}/annotations/", {"outcome": sale.pk}, format="json")
    assert client.delete(f"/api/v1/calls/outcomes/{sale.pk}/").status_code == 204 and CallOutcome.objects.get(pk=sale.pk).is_active is False
    assert client.delete(f"/api/v1/calls/outcomes/{created['id']}/").status_code == 204 and not CallOutcome.objects.filter(pk=created["id"]).exists()
    assert client.delete("/api/v1/calls/outcomes/99999/").status_code == 404
    # Tariffs feed the cost estimate.
    tariff = client.post("/api/v1/calls/tariffs/", {"carrier": "Vodacom", "per_minute": "40.00", "billing_increment_seconds": 60}, format="json").json()
    assert client.patch(f"/api/v1/calls/tariffs/{tariff['id']}/", {"per_minute": "35.00"}, format="json").json()["per_minute"] == "35.00"
    phone.send_events(log_row(direction="out", duration=90, log_id=2))
    cost = client.get("/api/v1/calls/stats/?range=7").json()["kpis"]["estimated_cost"]
    assert cost == [{"carrier": "Vodacom", "minutes": 2, "amount": "70.00", "currency": "TZS"}]
    assert client.delete(f"/api/v1/calls/tariffs/{tariff['id']}/").status_code == 204 and not CarrierTariff.objects.exists()
    hours = client.get("/api/v1/calls/office-hours/").json()
    assert hours[0]["configured"] is False and hours[0]["week"]["1"] == [["08:00", "17:00"]]
    assert client.put(f"/api/v1/calls/office-hours/{office.pk}/", {"timezone": "Mars/Base", "week": {}, "holidays": []}, format="json").status_code == 400


def test_device_access_and_callback_views(client_for, admin, manager, calls_phone):
    phone = calls_phone()
    client = client_for(admin)
    rows = client.put(f"/api/v1/calls/devices/{phone.device_id}/access/", [{"user": manager.pk, "can_annotate": True}], format="json").json()
    assert rows[0]["can_read"] and rows[0]["can_annotate"]  # any flag implies read
    assert client.get(f"/api/v1/calls/devices/{phone.device_id}/access/").json() == rows
    assert DeviceAccess.objects.filter(user=manager).exists() and AuditEvent.objects.filter(action="calls.access_update").exists()
    task = client.post("/api/v1/calls/callbacks/", {"device": phone.device_id, "number": "0754210331", "reason": "Order"}, format="json").json()
    assert [t["id"] for t in client.get("/api/v1/calls/callbacks/?view=mine").json()] == [task["id"]]
    assert client.get(f"/api/v1/calls/callbacks/{task['id']}/").json()["reason"] == "Order"
    assert client.patch(f"/api/v1/calls/callbacks/{task['id']}/", {"priority": "urgent", "reason": "Order of 40 bags"}, format="json").json()["priority"] == "urgent"
    client.post("/api/v1/calls/callbacks/bulk/", {"ids": [task["id"]], "action": "done"}, format="json")
    assert client.get("/api/v1/calls/callbacks/?view=open").json() == []
    assert [t["id"] for t in client.get("/api/v1/calls/callbacks/?view=done").json()] == [task["id"]]
    assert client.post("/api/v1/calls/callbacks/bulk/", {"ids": [task["id"]], "action": "assign"}, format="json").status_code == 400
    assert phone.get("calls/config/").json()["outcomes"]


def test_customer_delete_and_simulator_view(client_for, admin, office, calls_phone):
    from modules.directory.models import Customer
    from modules.sms.services import simulator

    phone = calls_phone()
    phone.send_events(log_row(log_id=1))
    customer = Customer.objects.get()
    client = client_for(admin)
    assert client.delete(f"/api/v1/calls/customers/{customer.pk}/").status_code == 204
    assert CallRecord.objects.get().customer_id is None and AuditEvent.objects.filter(action="directory.delete").exists()
    assert client.post(f"/api/v1/calls/devices/{phone.device_id}/simulator/", {"action": "missed"}, format="json").status_code == 400  # a real phone
    device = simulator.create(name="Demo", office=office, user=admin, backfill_days=1)
    client.post(f"/api/v1/calls/devices/{device.pk}/enable/", {"enabled": True}, format="json")
    assert client.post(f"/api/v1/calls/devices/{device.pk}/simulator/", {"action": "missed"}, format="json").status_code == 204
    assert CallRecord.objects.filter(device=device, result="missed").exists()
    client.post(f"/api/v1/calls/devices/{device.pk}/enable/", {"enabled": False}, format="json")
    assert AuditEvent.objects.filter(action="calls.device_disable").exists()


def test_tasks_run(calls_phone):
    phone = calls_phone()
    phone.send_events(log_row(at=now_ms(-60), log_id=1))
    assert tasks.repair_rollups() >= 1
    assert tasks.retention_purge() == 0
    assert tasks.expire_callbacks() == 0
    assert tasks.simulator_tick() == 0
    assert CallbackTask.objects.count() == 0
