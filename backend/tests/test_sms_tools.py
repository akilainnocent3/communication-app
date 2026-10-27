"""SMS tools: quick replies, sensitive-message rules, settings, contacts and blocks, list filters and pagination,
outbox views, stars, notes, assignees, media housekeeping and the phone config endpoint."""

import time
from datetime import timedelta

import pytest
from django.utils import timezone

from modules.audit.models import AuditEvent
from modules.sms.models import Contact, Conversation, Message, QuickReply, SmsSettings

pytestmark = pytest.mark.django_db
TO = "+255754210331"


def test_quick_replies_crud_and_phone_sync(client_for, admin, manager, device_grant, phone):
    client = client_for(admin)
    created = client.post("/api/v1/sms/quick-replies/", {"title": "Asante", "body": "Asante sana!"}, format="json")
    assert created.status_code == 201
    reply = created.json()
    assert client.patch(f"/api/v1/sms/quick-replies/{reply['id']}/", {"body": "Asante sana, karibu."}, format="json").json()["body"] == "Asante sana, karibu."
    # Phone-specific reply needs manage on that phone; global ones need sms.manage_devices.
    device_grant(manager, phone.device_id, can_send=True)
    assert client_for(manager).post("/api/v1/sms/quick-replies/", {"title": "x", "body": "y"}, format="json").status_code == 403
    assert client_for(manager).post("/api/v1/sms/quick-replies/", {"title": "x", "body": "y", "device": phone.device_id}, format="json").status_code == 403
    device_grant(manager, phone.device_id, can_send=True, can_manage=True)
    own = client_for(manager).post("/api/v1/sms/quick-replies/", {"title": "Desk", "body": "We are open.", "device": phone.device_id}, format="json")
    assert own.status_code == 201
    assert {r["title"] for r in client_for(manager).get("/api/v1/sms/quick-replies/").json()} == {"Asante", "Desk"}
    config = phone.get("config/").json()
    assert {r["title"] for r in config["quick_replies"]} == {"Asante", "Desk"} and config["poll_seconds"] == 20
    assert client_for(manager).delete(f"/api/v1/sms/quick-replies/{reply['id']}/").status_code == 403
    assert client.delete(f"/api/v1/sms/quick-replies/{reply['id']}/").status_code == 204
    assert QuickReply.objects.count() == 1


def test_sensitive_rules(client_for, admin, viewer, device_grant, phone):
    client = client_for(admin)
    assert client.post("/api/v1/sms/rules/", {"name": "Bad", "kind": "otp", "body_pattern": "("}, format="json").status_code == 400
    assert client.post("/api/v1/sms/rules/", {"name": "Empty", "kind": "otp"}, format="json").status_code == 400
    rule = client.post("/api/v1/sms/rules/", {"name": "Payroll", "kind": "money", "body_pattern": "(?i)payslip"}, format="json").json()
    assert client.patch(f"/api/v1/sms/rules/{rule['id']}/", {"is_enabled": False}, format="json").json()["is_enabled"] is False
    device_grant(viewer, phone.device_id)
    assert client_for(viewer).get("/api/v1/sms/rules/").status_code == 200
    assert client_for(viewer).post("/api/v1/sms/rules/", {"name": "x", "kind": "otp", "body_pattern": "x"}, format="json").status_code == 403
    assert client.delete(f"/api/v1/sms/rules/{rule['id']}/").status_code == 204
    assert AuditEvent.objects.filter(action__startswith="sms.rule_").count() == 3


def test_settings_and_monitoring_notice(client_for, admin, manager, invite_token):
    client = client_for(admin)
    current = client.get("/api/v1/sms/settings/").json()
    assert current["retention_days"] == 365 and current["simulator_enabled"] is True and current["push_configured"] is False
    updated = client.put("/api/v1/sms/settings/", {"monitoring_notice": "Company phone. Messages are copied and logged.", "default_signature": "- Mauzo"}, format="json").json()
    assert updated["default_signature"] == "- Mauzo"
    assert client_for(manager).put("/api/v1/sms/settings/", {"monitoring_notice": "x", "default_signature": ""}, format="json").status_code == 403
    _, token = invite_token()
    assert client_for(None).get(f"/api/v1/device/enroll/info/?token={token}").json()["notice"] == "Company phone. Messages are copied and logged."
    assert SmsSettings.load().monitoring_notice.startswith("Company phone")


def test_contacts_and_unblock(client_for, admin, phone):
    phone.send_events(phone.message(), phone.message(direction="out", body="x"), {"type": "contact.upsert", "payload": {"address": TO, "display_name": "Neema Mushi"}})
    client = client_for(admin)
    rows = client.get("/api/v1/sms/contacts/").json()["results"]
    assert rows[0]["name"] == "Neema Mushi" and rows[0]["messages"] == 2 and rows[0]["conversation"]
    assert client.get("/api/v1/sms/contacts/?q=0754210").json()["results"][0]["address"] == TO
    assert client.get("/api/v1/sms/contacts/?q=nobody").json()["results"] == []
    client.post("/api/v1/sms/blocked/", {"device": phone.device_id, "address": TO}, format="json")
    blocked = client.get("/api/v1/sms/contacts/?blocked=true").json()["results"]
    assert [b["address"] for b in blocked] == [TO]
    assert client.delete(f"/api/v1/sms/blocked/{blocked[0]['id']}/").status_code == 204
    assert not Contact.objects.get(address=TO).is_blocked
    assert {"sms.block", "sms.unblock"} <= set(AuditEvent.objects.values_list("action", flat=True))


def test_conversation_actions_block_spam(client_for, admin, phone):
    phone.send_events(phone.message())
    conversation = Conversation.objects.get()
    client = client_for(admin)
    client.post("/api/v1/sms/conversations/actions/", {"action": "block", "conversation_ids": [conversation.pk]}, format="json")
    conversation.refresh_from_db()
    assert conversation.is_spam and Contact.objects.get(address=TO).is_blocked
    assert client.get("/api/v1/sms/conversations/?folder=spam").json()["total"] == 1
    client.post("/api/v1/sms/conversations/actions/", {"action": "unblock", "conversation_ids": [conversation.pk]}, format="json")
    assert client.get("/api/v1/sms/conversations/?folder=inbox").json()["total"] == 1


def test_list_filters_and_pinned_pagination(client_for, admin, phone, monkeypatch):
    from modules.sms.api import conversations

    monkeypatch.setattr(conversations, "PAGE_SIZE", 3)
    now = int(time.time() * 1000)
    events = [phone.message(address=f"+25575421{i:04d}", body=f"m{i}", at_ms=now - i * 60_000, direction="in" if i % 2 else "out") for i in range(8)]
    phone.send_events(*events)
    pinned = Conversation.objects.get(participants_key="+255754210007")
    client = client_for(admin)
    client.post("/api/v1/sms/conversations/actions/", {"action": "pin", "conversation_ids": [pinned.pk]}, format="json")
    seen, cursor = [], None
    while True:
        page = client.get("/api/v1/sms/conversations/" + (f"?cursor={cursor}" if cursor else "")).json()
        seen += [r["id"] for r in page["results"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert seen[0] == pinned.pk and len(seen) == len(set(seen)) == 8
    assert all(r["last_direction"] == "in" for r in client.get("/api/v1/sms/conversations/?direction=in&folder=all").json()["results"])
    today = timezone.localdate().isoformat()
    assert client.get(f"/api/v1/sms/conversations/?after={today}&before={today}").json()["total"] == 8
    assert client.get("/api/v1/sms/conversations/?has_mms=1").json()["total"] == 0
    sim = phone.get("config/").json()["sims"]
    assert sim and client.get("/api/v1/sms/conversations/?sim=abc").json()["total"] == 0


def test_message_pagination_star_and_search(client_for, admin, phone, monkeypatch):
    from modules.sms.api import conversations

    monkeypatch.setattr(conversations, "MESSAGE_PAGE", 2)
    now = int(time.time() * 1000)
    phone.send_events(*[phone.message(body=f"ujumbe {i}", at_ms=now - i * 1000) for i in range(5)])
    conversation = Conversation.objects.get()
    client = client_for(admin)
    first = client.get(f"/api/v1/sms/conversations/{conversation.pk}/messages/").json()
    second = client.get(f"/api/v1/sms/conversations/{conversation.pk}/messages/?cursor={first['next_cursor']}").json()
    assert [m["body"] for m in first["results"]] == ["ujumbe 0", "ujumbe 1"] and [m["body"] for m in second["results"]] == ["ujumbe 2", "ujumbe 3"]
    assert [m["body"] for m in client.get(f"/api/v1/sms/conversations/{conversation.pk}/messages/?q=UJUMBE 4").json()["results"]] == ["ujumbe 4"]
    message = first["results"][0]["id"]
    assert client.post(f"/api/v1/sms/messages/{message}/star/", {"starred": True}, format="json").json()["is_starred"]
    assert client.get("/api/v1/sms/conversations/?folder=starred").json()["total"] == 1


def test_notes_assignees_and_segments(client_for, admin, manager, device_grant, phone):
    phone.send_events(phone.message())
    conversation = Conversation.objects.get()
    device_grant(manager, phone.device_id, can_send=True)
    note = client_for(admin).post(f"/api/v1/sms/conversations/{conversation.pk}/notes/", {"body": "Paid by cash"}, format="json").json()
    assert client_for(manager).delete(f"/api/v1/sms/conversations/{conversation.pk}/notes/{note['id']}/").status_code == 403
    assert client_for(admin).delete(f"/api/v1/sms/conversations/{conversation.pk}/notes/{note['id']}/").status_code == 204
    assert client_for(admin).post(f"/api/v1/sms/conversations/{conversation.pk}/notes/", {"body": "  "}, format="json").status_code == 400
    names = {a["email"] for a in client_for(admin).get(f"/api/v1/sms/assignees/?device={phone.device_id}").json()}
    assert {admin.email, manager.email} <= names
    assert client_for(admin).get("/api/v1/sms/segments/?text=" + "a" * 161).json()["segments"] == 2


def test_outbox_pending_view_and_device_list(client_for, admin, phone, other_phone):
    client = client_for(admin)
    client.post("/api/v1/sms/send/", {"device": phone.device_id, "to": [TO], "body": "x", "undo_seconds": 0}, format="json")
    pending = client.get(f"/api/v1/sms/outbox/?device={phone.device_id}").json()
    assert len(pending) == 1 and pending[0]["conversation_title"] == "+255 754 210 331"
    client.post(f"/api/v1/sms/devices/{other_phone.device_id}/revoke/", {"confirm_code": client.get(f"/api/v1/sms/devices/{other_phone.device_id}/").json()["code"]}, format="json")
    assert len(client.get("/api/v1/sms/devices/").json()) == 1
    assert len(client.get("/api/v1/sms/devices/?include_revoked=1").json()) == 2
    assert client.post(f"/api/v1/sms/devices/{other_phone.device_id}/resume/", format="json").status_code == 409


def test_heartbeat_history_and_enrollment_list(client_for, admin, phone):
    phone.post("heartbeat/", {"is_default_sms_app": True, "battery": 80})
    client = client_for(admin)
    assert client.get(f"/api/v1/sms/devices/{phone.device_id}/heartbeats/").json()[0]["battery"] == 80
    enrollments = client.get("/api/v1/sms/enrollments/").json()
    assert enrollments[0]["state"] == "used" and enrollments[0]["device"]["id"] == phone.device_id


def test_media_cleanup_removes_orphans(phone, settings):
    import os

    from modules.sms.services import media

    root = media._root()
    orphan = root / "orphan.bin"
    orphan.write_bytes(b"x")
    old = time.time() - 7200
    os.utime(orphan, (old, old))
    partial = root / "partial" / "999999"
    partial.mkdir(parents=True)
    (partial / "0000000000").write_bytes(b"x")
    assert media.cleanup_orphans() == 2
    assert not orphan.exists() and not partial.exists()


def test_expire_marks_stuck_sending_unknown(client_for, admin, phone, settings):
    from modules.sms.services import outbound

    sent = client_for(admin).post("/api/v1/sms/send/", {"device": phone.device_id, "to": [TO], "body": "x", "undo_seconds": 0}, format="json").json()["message"]
    phone.post("outbox/claim/", {})
    phone.post("outbox/status/", {"reports": [{"client_uuid": sent["client_uuid"], "status": "sending"}]})
    Message.objects.update(dispatched_at=timezone.now() - timedelta(hours=settings.SMS_OUTBOUND_TTL_HOURS + 1))
    assert outbound.expire_stale()["unknown"] == 1
    assert Message.objects.get().status == "unknown"
