"""Admin reply → phone sends it: queue, undo, schedule, claim leases, at-most-once, expiry, cancel, retry, unknown,
rate limits and caps, recipient rules, signature, sensitive reveal, conversation API and analytics."""

import uuid
from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone

from modules.audit.models import AuditEvent
from modules.devices.models import Device, DeviceCommand
from modules.sms.models import Conversation, Message
from modules.sms.services import outbound
from modules.sms.services.crypto import decrypt_text

pytestmark = pytest.mark.django_db
TO = "+255754210331"


def send(client, phone, body="Asante, tumepokea.", **extra):
    payload = {"device": phone.device_id, "to": [TO], "body": body, "undo_seconds": 0, **extra}
    return client.post("/api/v1/sms/send/", payload, format="json")


def due(message_id):
    Message.objects.filter(pk=message_id).update(send_at=timezone.now() - timedelta(seconds=1))


def test_send_queues_audits_and_wakes_the_phone(client_for, admin, phone):
    with mock.patch("modules.devices.tasks.push_task.delay") as wake:
        response = send(client_for(admin), phone)
    assert response.status_code == 202, response.json()
    message = response.json()["message"]
    assert message["status"] == "queued" and message["origin"] == "admin" and message["sent_by"]["display_name"]
    assert message["segments"] == 1 and message["direction"] == "out"
    wake.assert_called_with(phone.device_id, "outbox")
    row = Message.objects.get()
    assert decrypt_text(row.encrypted_body) == "Asante, tumepokea." and row.provider_id is None
    event = AuditEvent.objects.get(action="sms.send")
    assert event.metadata["recipients"] == ["+2557•••••331"] and "Asante" not in str(event.metadata)


def test_full_lifecycle_claim_sending_sent_delivered(client_for, admin, phone):
    sent = send(client_for(admin), phone).json()["message"]
    claim = phone.post("outbox/claim/", {}).json()
    assert [m["client_uuid"] for m in claim["messages"]] == [sent["client_uuid"]]
    item = claim["messages"][0]
    assert item["body"] == "Asante, tumepokea." and item["addresses"] == [TO] and item["subscription_id"] == 1 and item["sent_by"]
    assert Message.objects.get().status == "dispatched"
    # Re-claiming within the lease returns nothing.
    assert phone.post("outbox/claim/", {}).json()["messages"] == []
    for status in ("sending", "sent", "delivered"):
        result = phone.post("outbox/status/", {"reports": [{"client_uuid": sent["client_uuid"], "status": status, "parts": 1}]}).json()
        assert result["results"][0]["result"] == "ok"
    message = Message.objects.get()
    assert message.status == "delivered" and message.sent_at and message.delivered_at
    assert [h["status"] for h in message.status_history] == ["queued", "dispatched", "sending", "sent", "delivered"]
    # A late "sent" never hides "delivered".
    late = phone.post("outbox/status/", {"reports": [{"client_uuid": sent["client_uuid"], "status": "sent"}]}).json()
    assert late["results"][0]["result"] == "ignored" and Message.objects.get().status == "delivered"
    # The phone writes it to its store: linked by client_uuid, no duplicate.
    phone.send_events(phone.message(direction="out", body="Asante, tumepokea.", client_uuid=sent["client_uuid"], status="delivered"))
    assert Message.objects.count() == 1 and Message.objects.get().provider_id is not None
    detail = client_for(admin).get(f"/api/v1/sms/conversations/{sent['conversation']}/messages/").json()["results"][0]
    assert detail["status"] == "delivered" and detail["origin"] == "admin"


def test_at_most_once_leases(client_for, admin, phone):
    sent = send(client_for(admin), phone).json()["message"]
    phone.post("outbox/claim/", {})
    # The lease expires before the phone acknowledged: offered again (it was never started).
    Message.objects.update(lease_expires_at=timezone.now() - timedelta(seconds=1))
    assert len(phone.post("outbox/claim/", {}).json()["messages"]) == 1
    phone.post("outbox/status/", {"reports": [{"client_uuid": sent["client_uuid"], "status": "sending"}]})
    # Acknowledged: never offered again, even long after.
    Message.objects.update(lease_expires_at=timezone.now() - timedelta(hours=1))
    assert phone.post("outbox/claim/", {}).json()["messages"] == []
    # The app died mid-send: it reports unknown; a person decides.
    phone.post("outbox/status/", {"reports": [{"client_uuid": sent["client_uuid"], "status": "unknown"}]})
    message = Message.objects.get()
    assert message.status == "unknown" and "Check with the customer" in message.error_detail


def test_undo_window_and_cancel(client_for, admin, phone):
    client = client_for(admin)
    sent = send(client, phone, undo_seconds=10).json()["message"]
    assert phone.post("outbox/claim/", {}).json()["messages"] == []  # still in the undo window
    cancelled = client.post(f"/api/v1/sms/messages/{sent['id']}/cancel/").json()
    assert cancelled["status"] == "cancelled"
    due(sent["id"])
    assert phone.post("outbox/claim/", {}).json()["messages"] == []
    assert client.post(f"/api/v1/sms/messages/{sent['id']}/cancel/").status_code == 409
    # Cannot cancel once the phone has it.
    other = send(client, phone).json()["message"]
    phone.post("outbox/claim/", {})
    assert client.post(f"/api/v1/sms/messages/{other['id']}/cancel/").status_code == 409


def test_undo_uses_the_users_preference(client_for, admin, phone):
    admin.preferences = {**admin.preferences, "undo_send_seconds": 20}
    admin.save()
    response = client_for(admin).post("/api/v1/sms/send/", {"device": phone.device_id, "to": [TO], "body": "x"}, format="json").json()["message"]
    assert (timezone.datetime.fromisoformat(response["send_at"]) - timezone.now()).total_seconds() > 15


def test_scheduled_send(client_for, admin, phone):
    client = client_for(admin)
    at = timezone.now() + timedelta(hours=2)
    sent = send(client, phone, send_at=at.isoformat()).json()["message"]
    assert sent["is_scheduled"] and sent["status"] == "queued"
    assert [m["id"] for m in client.get("/api/v1/sms/outbox/?view=scheduled").json()] == [sent["id"]]
    assert phone.post("outbox/claim/", {}).json()["messages"] == []
    due(sent["id"])
    with mock.patch("modules.devices.tasks.push_task.delay") as wake:
        assert outbound.dispatch_due() == 1
    wake.assert_called_once()
    assert len(phone.post("outbox/claim/", {}).json()["messages"]) == 1
    assert send(client, phone, send_at=(timezone.now() + timedelta(seconds=5)).isoformat()).status_code == 400
    assert AuditEvent.objects.filter(action="sms.schedule").exists()


def test_offline_phone_keeps_queue_then_expires(client_for, admin, phone, settings):
    sent = send(client_for(admin), phone).json()["message"]
    outbox = client_for(admin).get("/api/v1/sms/outbox/").json()
    assert [m["id"] for m in outbox] == [sent["id"]]
    Message.objects.update(send_at=timezone.now() - timedelta(hours=settings.SMS_OUTBOUND_TTL_HOURS + 1))
    assert phone.post("outbox/claim/", {}).json()["messages"] == []  # too old to send
    assert outbound.expire_stale()["expired"] == 1
    message = Message.objects.get()
    assert message.status == "expired" and "offline" in message.error_detail
    problems = client_for(admin).get("/api/v1/sms/outbox/?view=problems").json()
    assert problems[0]["status"] == "expired"


def test_failed_and_retry(client_for, admin, phone):
    client = client_for(admin)
    sent = send(client, phone).json()["message"]
    phone.post("outbox/claim/", {})
    phone.post("outbox/status/", {"reports": [{"client_uuid": sent["client_uuid"], "status": "sending"}, {"client_uuid": sent["client_uuid"], "status": "failed", "error_code": 4}]})
    failed = Message.objects.get(pk=sent["id"])
    assert failed.status == "failed" and failed.error_detail == "The phone has no mobile service."
    retried = client.post(f"/api/v1/sms/messages/{sent['id']}/retry/").json()["message"]
    assert retried["client_uuid"] != sent["client_uuid"] and retried["retry_of"] == sent["id"] and retried["status"] == "queued"
    assert AuditEvent.objects.filter(action="sms.retry").exists()
    assert client.post(f"/api/v1/sms/messages/{retried['id']}/retry/").status_code == 400


def test_double_submit_with_same_client_uuid(client_for, admin, phone):
    client_uuid = str(uuid.uuid4())
    first = send(client_for(admin), phone, client_uuid=client_uuid).json()["message"]
    second = send(client_for(admin), phone, client_uuid=client_uuid).json()["message"]
    assert first["id"] == second["id"] and Message.objects.count() == 1


@pytest.mark.parametrize("recipient, code", [("M-PESA", "invalid_recipient"), ("15300", "short_code_refused"), ("12", "short_code_refused"), ("+2557", "invalid_recipient")])
def test_recipient_rules(client_for, admin, phone, recipient, code):
    response = send(client_for(admin), phone, to=[recipient])
    assert response.status_code == 400 and response.json()["code"] == code


def test_short_codes_when_allowed(client_for, admin, phone, settings):
    settings.SMS_ALLOW_SHORT_CODES = True
    assert send(client_for(admin), phone, to=["15300"]).status_code == 202


def test_rate_limits_and_daily_cap(client_for, admin, phone, settings):
    settings.SMS_DEVICE_RATE_PER_MINUTE = 2
    client = client_for(admin)
    assert send(client, phone).status_code == 202 and send(client, phone).status_code == 202
    limited = send(client, phone)
    assert limited.status_code == 429 and limited.json()["code"] == "rate_limited"
    settings.SMS_DEVICE_RATE_PER_MINUTE = 100
    settings.SMS_DEVICE_DAILY_CAP = 2
    capped = send(client, phone)
    assert capped.status_code == 429 and capped.json()["code"] == "daily_cap"


def test_signature_and_segments(client_for, admin, phone):
    Device.objects.filter(pk=phone.device_id).update(options={"signature_enabled": True, "signature": "- Head Office", "mark_read_on_open": True})
    message = send(client_for(admin), phone, body="a" * 150).json()["message"]
    assert message["body"].endswith("\n- Head Office") and message["segments"] == 2 and message["encoding"] == "gsm7"
    # An em dash is not in GSM-7: the whole message becomes UCS-2 and needs three segments (the counter shows it).
    Device.objects.filter(pk=phone.device_id).update(options={"signature_enabled": True, "signature": "— Head Office", "mark_read_on_open": True})
    message = send(client_for(admin), phone, body="a" * 150).json()["message"]
    assert message["encoding"] == "ucs2" and message["segments"] == 3


def test_blocked_number_and_suspended_phone(client_for, admin, phone):
    client = client_for(admin)
    assert client.post("/api/v1/sms/blocked/", {"device": phone.device_id, "address": TO}, format="json").status_code == 204
    assert DeviceCommand.objects.filter(kind="block", payload__address=TO).exists()
    assert send(client, phone).json()["code"] == "recipient_blocked"
    Device.objects.filter(pk=phone.device_id).update(status="suspended")
    assert send(client, phone, to=["+255713402118"]).json()["code"] == "device_inactive"


# --- Conversations API -------------------------------------------------------------------------------------------


def seed(phone):
    phone.send_events(
        phone.message(body="Habari, mzigo umefika?", is_read=False),
        phone.message(address="+255713402118", body="Invoice please", is_read=False),
        phone.message(address="GOOGLE", body="G-482913 is your Google verification code.", is_read=False),
        {"type": "contact.upsert", "payload": {"address": TO, "display_name": "Neema Mushi"}},
    )


def test_list_titles_search_and_folders(client_for, admin, phone):
    seed(phone)
    client = client_for(admin)
    page = client.get("/api/v1/sms/conversations/").json()
    assert page["total"] == 3
    titles = {row["title"] for row in page["results"]}
    assert {"Neema Mushi", "+255 713 402 118", "GOOGLE"} == titles
    otp = next(row for row in page["results"] if row["title"] == "GOOGLE")
    assert otp["snippet_sensitive"] and "482913" not in otp["snippet"]
    assert [r["title"] for r in client.get("/api/v1/sms/conversations/?q=neema").json()["results"]] == ["Neema Mushi"]
    assert [r["title"] for r in client.get("/api/v1/sms/conversations/?q=0713402").json()["results"]] == ["+255 713 402 118"]
    assert client.get("/api/v1/sms/conversations/?folder=unread").json()["total"] == 3
    assert client.get("/api/v1/sms/conversations/?folder=awaiting").json()["total"] == 3
    assert client.get("/api/v1/sms/conversations/?device=not-a-uuid").status_code == 404


def test_open_conversation_marks_read_audits_and_commands_phone(client_for, admin, phone):
    seed(phone)
    conversation = Conversation.objects.get(participants_key=TO)
    client = client_for(admin)
    peek = client.get(f"/api/v1/sms/conversations/{conversation.pk}/?peek=1").json()
    assert peek["unread_count"] == 1 and not AuditEvent.objects.filter(action="sms.conversation_open").exists()
    opened = client.get(f"/api/v1/sms/conversations/{conversation.pk}/").json()
    assert opened["unread_count"] == 0 and opened["permissions"]["send"] and opened["stats"]["inbound"] == 1
    assert AuditEvent.objects.filter(action="sms.conversation_open", target_id=str(conversation.pk)).exists()
    command = DeviceCommand.objects.get(kind="mark_read")
    assert command.payload == {"thread_id": 7}
    claim = phone.post("outbox/claim/", {}).json()
    assert claim["commands"][0]["kind"] == "mark_read"
    phone.post("outbox/status/", {"command_acks": [{"id": command.pk, "ok": True}]})
    assert DeviceCommand.objects.get().status == "done"


def test_sensitive_messages_are_masked_and_reveal_is_audited(client_for, admin, viewer, device_grant, phone):
    seed(phone)
    conversation = Conversation.objects.get(participants_key="GOOGLE")
    message = conversation.messages.get()
    body = client_for(admin).get(f"/api/v1/sms/conversations/{conversation.pk}/messages/").json()["results"][0]
    assert body["is_masked"] and "482913" not in body["body"]
    device_grant(viewer, phone.device_id)
    assert client_for(viewer).post(f"/api/v1/sms/messages/{message.pk}/reveal/").status_code == 403
    device_grant(viewer, phone.device_id, can_reveal_sensitive=True)
    revealed = client_for(viewer).post(f"/api/v1/sms/messages/{message.pk}/reveal/").json()
    assert "482913" in revealed["body"]
    assert AuditEvent.objects.filter(action="sms.reveal_sensitive", actor=viewer).exists()
    # Searching inside a conversation never matches masked text.
    assert client_for(admin).get(f"/api/v1/sms/conversations/{conversation.pk}/messages/?q=482913").json()["results"] == []


def test_actions_assign_notes_and_undo(client_for, admin, manager, device_grant, phone):
    seed(phone)
    ids = list(Conversation.objects.values_list("pk", flat=True))
    client = client_for(admin)
    for action in ("pin", "archive", "unarchive", "done", "reopen", "mute", "star", "read", "unread"):
        assert client.post("/api/v1/sms/conversations/actions/", {"action": action, "conversation_ids": ids}, format="json").status_code == 200
    assert client.post("/api/v1/sms/conversations/actions/", {"action": "assign", "conversation_ids": ids[:1], "assignee": manager.pk}, format="json").status_code == 403
    device_grant(manager, phone.device_id)
    assigned = client.post("/api/v1/sms/conversations/actions/", {"action": "assign", "conversation_ids": ids[:1], "assignee": manager.pk}, format="json").json()
    assert assigned["conversations"][0]["assigned_to"]["id"] == manager.pk
    assert client_for(manager).get("/api/v1/sms/conversations/?folder=assigned").json()["total"] == 1
    note = client.post(f"/api/v1/sms/conversations/{ids[0]}/notes/", {"body": "Called back"}, format="json")
    assert note.status_code == 201 and client.get(f"/api/v1/sms/conversations/{ids[0]}/notes/").json()[0]["body"] == "Called back"


def test_new_inbound_message_reopens_archived(client_for, admin, phone):
    phone.send_events(phone.message(body="one"))
    conversation = Conversation.objects.get()
    Conversation.objects.filter(pk=conversation.pk).update(is_archived=True, state="done")
    phone.send_events(phone.message(body="two"))
    conversation.refresh_from_db()
    assert not conversation.is_archived and conversation.state == "open"


def test_dashboard_numbers_are_metadata_only(client_for, admin, phone):
    seed(phone)
    sent = send(client_for(admin), phone).json()["message"]
    phone.post("outbox/claim/", {})
    phone.post("outbox/status/", {"reports": [{"client_uuid": sent["client_uuid"], "status": "sending"}, {"client_uuid": sent["client_uuid"], "status": "delivered"}]})
    stats = client_for(admin).get("/api/v1/sms/stats/?range=7").json()
    kpis = stats["kpis"]
    assert kpis["received"] == 3 and kpis["sent"] == 1 and kpis["delivery_success_rate"] == 100.0 and kpis["failed"] == 0
    assert kpis["median_first_response_minutes"] is not None
    assert len(stats["series"]) == 7 and sum(sum(row) for row in stats["heatmap"]) == 3
    assert {s["address"] for s in stats["top_senders"]} == {TO, "+255713402118", "GOOGLE"}
    assert stats["per_device"][0]["code"] and stats["per_sim"]


def test_simulator_end_to_end(admin, office, client_for):
    from modules.sms.services import simulator

    device = simulator.create(name="Demo", office=office, user=admin, dual_sim=True, backfill_days=20, seed=3)
    assert device.is_simulated and device.sim_lines.count() == 2
    assert Conversation.objects.filter(device=device).count() >= 8
    assert Message.objects.filter(device=device, kind="mms").exists()
    client = client_for(admin)
    sent = client.post("/api/v1/sms/send/", {"device": str(device.pk), "to": [TO], "body": "Karibu", "undo_seconds": 0}, format="json").json()["message"]
    client.post(f"/api/v1/sms/devices/{device.pk}/simulator/", {"action": "offline"}, format="json")
    client.post(f"/api/v1/sms/devices/{device.pk}/simulator/", {"action": "tick"}, format="json")
    assert Message.objects.get(pk=sent["id"]).status == "queued"
    client.post(f"/api/v1/sms/devices/{device.pk}/simulator/", {"action": "online"}, format="json")
    client.post(f"/api/v1/sms/devices/{device.pk}/simulator/", {"action": "tick"}, format="json")
    assert Message.objects.get(pk=sent["id"]).status == "sent"
    client.post(f"/api/v1/sms/devices/{device.pk}/simulator/", {"action": "tick"}, format="json")
    message = Message.objects.get(pk=sent["id"])
    assert message.status == "delivered" and message.provider_id is not None
    failing = client.post("/api/v1/sms/send/", {"device": str(device.pk), "to": ["+255754123000"], "body": "x", "undo_seconds": 0}, format="json").json()["message"]
    client.post(f"/api/v1/sms/devices/{device.pk}/simulator/", {"action": "tick"}, format="json")
    assert Message.objects.get(pk=failing["id"]).status == "failed"
