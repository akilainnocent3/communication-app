"""The SMS permission matrix: who can see and change which phone, and the two API surfaces."""

import pytest

from modules.devices.models import Device
from modules.platforms.models import Platform
from modules.sms.models import Conversation, Message, MessagePart

pytestmark = pytest.mark.django_db
TO = "+255754210331"


@pytest.fixture
def data(phone, other_phone):
    import hashlib

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
    phone.send_events(phone.message(body="Habari", is_read=False), phone.message(kind="mms", address="+255713402118", body="Picha",
                      parts=[{"seq": 0, "content_type": "image/png", "size": len(png), "sha256": hashlib.sha256(png).hexdigest()}]))
    other_phone.send_events(other_phone.message(body="Arusha customer"))
    from modules.sms.services import media

    media.store(MessagePart.objects.get(), png)
    return {
        "device": Device.objects.get(pk=phone.device_id), "other": Device.objects.get(pk=other_phone.device_id),
        "conversation": Conversation.objects.get(device_id=phone.device_id, participants_key=TO),
        "other_conversation": Conversation.objects.get(device_id=other_phone.device_id),
        "part": MessagePart.objects.get(),
    }


def test_admin_sees_every_phone(client_for, admin, data):
    devices = client_for(admin).get("/api/v1/sms/devices/").json()
    assert {d["code"] for d in devices} == {data["device"].code, data["other"].code}


def test_no_access_is_404_everywhere(client_for, viewer, data):
    client = client_for(viewer)
    device, conversation, part = data["device"], data["conversation"], data["part"]
    message = conversation.messages.first()
    assert client.get("/api/v1/sms/devices/").json() == []
    assert client.get("/api/v1/sms/conversations/?device=all").json()["total"] == 0
    for url in (
        f"/api/v1/sms/devices/{device.pk}/", f"/api/v1/sms/conversations/?device={device.pk}", f"/api/v1/sms/conversations/{conversation.pk}/",
        f"/api/v1/sms/conversations/{conversation.pk}/messages/", f"/api/v1/sms/conversations/{conversation.pk}/notes/",
        f"/api/v1/sms/messages/{part.message_id}/media/{part.pk}/", f"/api/v1/sms/devices/{device.pk}/heartbeats/", f"/api/v1/sms/stats/?device={device.pk}",
    ):
        assert client.get(url).status_code == 404, url
    assert client.post(f"/api/v1/sms/messages/{message.pk}/reveal/").status_code == 404
    assert client.post("/api/v1/sms/send/", {"device": str(device.pk), "to": [TO], "body": "x"}, format="json").status_code == 404


def test_read_only_cannot_send_block_assign_or_organise(client_for, viewer, device_grant, data):
    device, conversation = data["device"], data["conversation"]
    device_grant(viewer, device.pk)
    client = client_for(viewer)
    assert client.get(f"/api/v1/sms/conversations/{conversation.pk}/").status_code == 200
    assert client.post("/api/v1/sms/conversations/actions/", {"action": "read", "conversation_ids": [conversation.pk]}, format="json").status_code == 200
    for action in ("archive", "assign", "spam", "pin", "block"):
        response = client.post("/api/v1/sms/conversations/actions/", {"action": action, "conversation_ids": [conversation.pk], "assignee": viewer.pk}, format="json")
        assert response.status_code == 403, action
    assert client.post("/api/v1/sms/send/", {"device": str(device.pk), "conversation": conversation.pk, "body": "x"}, format="json").status_code == 403
    assert client.post("/api/v1/sms/blocked/", {"device": str(device.pk), "address": TO}, format="json").status_code == 403
    assert client.patch(f"/api/v1/sms/devices/{device.pk}/", {"name": "X"}, format="json").status_code == 403
    assert client.get(f"/api/v1/sms/devices/{device.pk}/access/").status_code == 403


def test_can_send_can_send(client_for, manager, device_grant, data):
    device_grant(manager, data["device"].pk, can_send=True)
    response = client_for(manager).post("/api/v1/sms/send/", {"device": str(data["device"].pk), "conversation": data["conversation"].pk, "body": "Karibu", "undo_seconds": 0}, format="json")
    assert response.status_code == 202
    assert client_for(manager).post("/api/v1/sms/conversations/actions/", {"action": "archive", "conversation_ids": [data["conversation"].pk]}, format="json").status_code == 200


def test_mixed_selection_with_inaccessible_conversation_fails_entirely(client_for, manager, device_grant, data):
    device_grant(manager, data["device"].pk, can_send=True)
    mine, theirs = data["conversation"], data["other_conversation"]
    response = client_for(manager).post("/api/v1/sms/conversations/actions/", {"action": "archive", "conversation_ids": [mine.pk, theirs.pk]}, format="json")
    assert response.status_code == 404
    mine.refresh_from_db()
    assert not mine.is_archived


def test_unified_view_spans_only_accessible_phones(client_for, manager, device_grant, data):
    device_grant(manager, data["other"].pk)
    results = client_for(manager).get("/api/v1/sms/conversations/?device=all").json()["results"]
    assert results and {r["device"]["id"] for r in results} == {str(data["other"].pk)}
    stats = client_for(manager).get("/api/v1/sms/stats/").json()
    assert [d["code"] for d in stats["per_device"]] == [data["other"].code]
    me = client_for(manager).get("/api/v1/auth/me/").json()
    assert [d["code"] for d in me["platform_data"]["sms"]["devices"]] == [data["other"].code]


def test_phone_manager_cannot_hand_out_manage_or_reveal(client_for, manager, viewer, device_grant, data):
    device_grant(manager, data["device"].pk, can_manage=True)
    client = client_for(manager)
    url = f"/api/v1/sms/devices/{data['device'].pk}/access/"
    payload = [{"user": manager.pk, "can_manage": True}, {"user": viewer.pk, "can_reveal_sensitive": True}]
    assert client.put(url, payload, format="json").status_code == 403
    payload[1] = {"user": viewer.pk, "can_send": True}
    rows = client.put(url, payload, format="json").json()
    assert {r["user"]: r["can_read"] for r in rows} == {manager.pk: True, viewer.pk: True}
    # Managing a phone is not managing devices: suspend/revoke/enroll stay with admins.
    assert client.post(f"/api/v1/sms/devices/{data['device'].pk}/suspend/", {}, format="json").status_code == 403


def test_disabled_platform_refuses_admin_and_phone_apis(client_for, admin, phone, data):
    from modules.platforms.services import sync_platform_rows

    sync_platform_rows()
    Platform.objects.filter(key="sms").update(is_enabled=False)
    assert client_for(admin).get("/api/v1/sms/conversations/").status_code == 403
    assert client_for(admin).get("/api/v1/sms/devices/").status_code == 403
    me = client_for(admin).get("/api/v1/auth/me/").json()
    assert "sms" not in [p["key"] for p in me["platforms"]] and me["platform_data"]["sms"]["devices"] == []
    blocked = phone.send_events(phone.message())
    assert blocked.status_code == 403 and blocked.json()["code"] == "platform_disabled"
    # Device identity still works (the phone keeps its queue and retries later).
    assert phone.post("heartbeat/", {"is_default_sms_app": True}).status_code == 200


def test_disabled_gmail_platform_refuses_mail_api(client_for, admin, mailbox):
    from modules.platforms.services import sync_platform_rows

    sync_platform_rows()
    Platform.objects.filter(key="gmail").update(is_enabled=False)
    assert client_for(admin).get("/api/v1/mail/threads/").status_code == 403


def test_user_without_sms_access_is_refused(client_for, roles):
    from tests.conftest import make_user

    nobody = make_user("nobody@test.example", None, roles)
    assert client_for(nobody).get("/api/v1/sms/conversations/").status_code == 403
    assert client_for(None).get("/api/v1/sms/conversations/").status_code == 401


def test_a_device_reads_and_writes_only_its_own_data(phone, other_phone, client_for, admin, data):
    # The other phone's admin message is never offered to this phone.
    client_for(admin).post("/api/v1/sms/send/", {"device": str(data["other"].pk), "to": [TO], "body": "Hi", "undo_seconds": 0}, format="json")
    assert phone.post("outbox/claim/", {}).json()["messages"] == []
    assert len(other_phone.post("outbox/claim/", {}).json()["messages"]) == 1
    # Events that point at another phone's message never touch it.
    target = Message.objects.filter(device=data["other"], direction="in").first()
    before = target.is_read
    ref = {"kind": "sms", "provider_id": target.provider_id, "date": int(target.provider_date.timestamp() * 1000)}
    phone.send_events({"type": "message.read", "payload": {**ref, "is_read": not before}}, {"type": "message.delete", "payload": ref})
    target.refresh_from_db()
    assert target.is_read == before and target.deleted_on_device_at is None
