"""Phone → server sync: idempotency, ordering, validation, cross-device isolation, contacts, deletes, media, crypto."""

import hashlib
import time

import pytest
from django.db import connection
from django.utils import timezone

from modules.devices.models import Device
from modules.sms.models import Contact, Conversation, Message, MessagePart
from modules.sms.services import media
from modules.sms.services.text import detect_sensitive, mask_sensitive, segment_info

pytestmark = pytest.mark.django_db


def test_events_create_conversations_and_are_idempotent(phone):
    first = phone.message(body="Habari, bei ya saruji?")
    response = phone.send_events(first, phone.message(direction="out", body="TSh 19,500", status="delivered"))
    assert response.status_code == 200, response.json()
    assert response.json() == {"acked_seq": 2, "processed": 2, "skipped": 0, "rejected": []}
    conversation = Conversation.objects.get()
    assert conversation.participants_key == "+255754210331" and conversation.message_count == 2 and conversation.thread_id == 7
    assert conversation.last_direction == "out" and conversation.awaiting_since is None
    # The same batch again (phone retried after a lost response): skipped by sequence.
    again = phone.send_events(first, seqs=[1])
    assert again.json()["skipped"] == 1 and Message.objects.count() == 2
    # The same message under a new sequence (resent after a crash): updated, not duplicated.
    phone.send_events({**first, "payload": {**first["payload"], "is_read": True}})
    assert Message.objects.count() == 2 and Message.objects.get(direction="in").is_read


def test_events_are_applied_in_sequence_order(phone):
    created = phone.message(body="Hello")
    read = {"type": "message.read", "payload": {k: created["payload"][k] for k in ("kind", "provider_id", "date")} | {"is_read": True}}
    phone.send_events(read, created, seqs=[2, 1])
    assert Message.objects.get().is_read is True


def test_unread_and_awaiting_reply(phone):
    phone.send_events(phone.message(body="Mzigo umefika?", is_read=False))
    conversation = Conversation.objects.get()
    assert conversation.unread_count == 1 and conversation.awaiting_since is not None


def test_malformed_events_are_rejected_but_acknowledged(phone):
    bad = phone.message(body="x" * 5001)
    future = phone.message(at_ms=int((time.time() + 3 * 86400) * 1000))
    too_many = phone.message(address=[f"+2557542{i:05d}" for i in range(21)])
    response = phone.send_events(bad, future, too_many, phone.message(body="fine"))
    body = response.json()
    assert body["acked_seq"] == 4 and body["processed"] == 1
    assert [r["code"] for r in body["rejected"]] == ["invalid_body", "invalid_date", "invalid_addresses"]


def test_batch_limits(phone):
    events = [{**phone.message(), "seq": i + 1} for i in range(201)]
    assert phone.post("sync/events/", {"events": events}).status_code == 400
    assert phone.post("sync/events/", {"events": [{"seq": 1, "type": "evil.event", "payload": {}}]}).status_code == 400


def test_a_phone_cannot_touch_another_phones_messages(phone, other_phone, client_for, admin):
    from modules.devices.models import Device

    other = Device.objects.get(pk=other_phone.device_id)
    sent = client_for(admin).post("/api/v1/sms/send/", {"device": str(other.pk), "to": ["+255754210331"], "body": "Hi", "undo_seconds": 0}, format="json").json()["message"]
    hijack = phone.message(direction="out", body="changed", client_uuid=sent["client_uuid"], status="sent")
    result = phone.send_events(hijack).json()
    assert result["rejected"] == [{"seq": 1, "code": "foreign_message"}]
    report = phone.post("outbox/status/", {"reports": [{"client_uuid": sent["client_uuid"], "status": "sending"}]}).json()
    assert report["results"][0]["result"] == "unknown_message"
    assert Message.objects.get(client_uuid=sent["client_uuid"]).status == "queued"
    # Conversations are always derived per phone.
    phone.send_events(phone.message(body="mine"))
    assert Conversation.objects.filter(device_id=phone.device_id).count() == 1


def test_contacts_only_for_numbers_in_conversations(phone):
    phone.send_events(phone.message(address="0754210331"))
    result = phone.send_events(
        {"type": "contact.upsert", "payload": {"address": "+255754210331", "display_name": "Neema Mushi"}},
        {"type": "contact.upsert", "payload": {"address": "+255700999888", "display_name": "Not in any conversation"}},
    ).json()
    assert result["processed"] == 2
    assert Contact.objects.get(address="+255754210331").display_name == "Neema Mushi"
    assert not Contact.objects.filter(address="+255700999888").exists()


def test_alphanumeric_and_short_code_senders(phone):
    phone.send_events(phone.message(address="M-PESA", body="QJK3XY Imethibitishwa. Umepokea Tsh50,000.00. Salio jipya la M-Pesa ni Tsh120,500.00."), phone.message(address="15300", body="Ofa!"))
    keys = set(Conversation.objects.values_list("participants_key", flat=True))
    assert keys == {"M-PESA", "15300"}
    assert Message.objects.get(address="M-PESA").sensitive_kind == "money"


def test_deletes_on_phone_keep_server_copy_unless_mirrored(phone, settings):
    created = phone.message(body="keep me")
    ref = {k: created["payload"][k] for k in ("kind", "provider_id", "date")}
    phone.send_events(created, {"type": "message.delete", "payload": ref})
    message = Message.objects.get()
    assert message.deleted_on_device_at is not None
    settings.SMS_MIRROR_DEVICE_DELETES = True
    second = phone.message(body="mirror me")
    phone.send_events(second, {"type": "thread.delete", "payload": {"thread_id": 7}})
    assert not Message.objects.exists() and not Conversation.objects.exists()


def test_block_events_and_backfill_progress(phone):
    phone.send_events({"type": "block.add", "payload": {"address": "+255700111222"}}, {"type": "backfill.progress", "payload": {"phase": "running", "done": 40, "total": 120}})
    assert Contact.objects.get(address="+255700111222").is_blocked
    assert Device.objects.get(pk=phone.device_id).sync_progress == {"phase": "running", "done": 40, "total": 120}


def test_bodies_and_snippets_are_encrypted_at_rest(phone):
    phone.send_events(phone.message(body="Siri kubwa ya biashara 12345"))
    with connection.cursor() as cursor:
        cursor.execute("SELECT encrypted_body FROM sms_message")
        raw = cursor.fetchone()[0]
        cursor.execute("SELECT encrypted_snippet FROM sms_conversation")
        snippet = cursor.fetchone()[0]
    assert "Siri" not in raw and "Siri" not in snippet and raw.startswith("gAAAA")


def test_rotate_sms_keys(phone, settings):
    from cryptography.fernet import Fernet
    from django.core.management import call_command

    from modules.sms.services.crypto import decrypt_text

    phone.send_events(phone.message(body="Rotate me"))
    old = Message.objects.get().encrypted_body
    new_key = Fernet.generate_key().decode()
    settings.SMS_DATA_KEYS = [new_key, *settings.SMS_DATA_KEYS]
    call_command("rotate_sms_keys")
    rotated = Message.objects.get().encrypted_body
    assert rotated != old
    settings.SMS_DATA_KEYS = [new_key]
    assert decrypt_text(rotated) == "Rotate me"


# --- MMS media ---------------------------------------------------------------------------------------------------


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200


def _mms(phone, data=PNG, declared="image/png"):
    event = phone.message(kind="mms", body="Picha", parts=[{"seq": 0, "content_type": declared, "filename": "photo.png", "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}])
    phone.send_events(event)
    return event["payload"]


def _chunk(phone, payload, offset, data):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return phone.post("sync/media/", {"provider_id": payload["provider_id"], "date": payload["date"], "seq": 0, "offset": offset, "chunk": SimpleUploadedFile("c", data)}, fmt=None)


def test_mms_resumable_upload_checksum_and_sniffing(phone, client_for, admin):
    payload = _mms(phone, declared="text/html")
    assert _chunk(phone, payload, 0, PNG[:100]).json() == {"received_bytes": 100, "complete": False}
    stale = _chunk(phone, payload, 0, PNG[:100])
    assert stale.status_code == 409 and stale.json()["errors"]["received_bytes"] == ["100"]
    assert _chunk(phone, payload, 100, PNG[100:]).json() == {"received_bytes": len(PNG), "complete": True}
    part = MessagePart.objects.get()
    assert part.content_type == "image/png" and part.declared_type == "text/html"  # magic bytes win
    stored = (media._root() / part.storage_name).read_bytes()
    assert PNG not in stored and not (media._root() / "partial" / str(part.pk)).exists()
    message = part.message
    response = client_for(admin).get(f"/api/v1/sms/messages/{message.pk}/media/{part.pk}/")
    assert response.status_code == 200 and response.content == PNG and response["Content-Type"] == "image/png"
    assert "sandbox" in response["Content-Security-Policy"] and response["X-Content-Type-Options"] == "nosniff"


def test_mms_checksum_mismatch_restarts_upload(phone):
    payload = _mms(phone)
    bad = b"\x89PNG\r\n\x1a\n" + b"\x01" * 200
    response = _chunk(phone, payload, 0, bad)
    assert response.status_code == 422 and response.json()["code"] == "checksum_mismatch"
    assert MessagePart.objects.get().received_bytes == 0
    assert _chunk(phone, payload, 0, PNG).json()["complete"] is True


def test_mms_upload_needs_declared_part_on_this_phone(phone, other_phone):
    payload = _mms(phone)
    assert _chunk(other_phone, payload, 0, PNG).status_code == 404


def test_sniffing():
    assert media.sniff(b"\xff\xd8\xff\xe0rest") == "image/jpeg"
    assert media.sniff(b"\x00\x00\x00\x18ftyp3gp4") == "video/3gpp"
    assert media.sniff(b"#!AMR\n") == "audio/amr"
    assert media.sniff(b"BEGIN:VCARD\r\n") == "text/x-vcard"
    assert media.sniff(b"<html><script>") == "text/plain"
    assert media.sniff(b"\x00\x01\x02\xff\xfe") == "application/octet-stream"


# --- Text rules ----------------------------------------------------------------------------------------------


def test_segment_counter():
    assert segment_info("a" * 160).segments == 1 and segment_info("a" * 161).segments == 2
    assert segment_info("a" * 306).segments == 2 and segment_info("a" * 307).segments == 3
    assert segment_info("€" * 80).units == 160 and segment_info("€" * 80).encoding == "gsm7"
    swahili = segment_info("Habari 😊")
    assert swahili.encoding == "ucs2" and swahili.units == 9 and swahili.per_segment == 70
    assert segment_info("ш" * 71).segments == 2 and segment_info("ш" * 71).per_segment == 67


def test_sensitive_detection_and_masking():
    assert detect_sensitive("GOOGLE", "G-482913 is your Google verification code.") == "otp"
    assert detect_sensitive("WhatsApp", "Your WhatsApp code: 123-456. Don't share it.") == "otp"
    assert detect_sensitive("+255754000000", "Msimbo wako ni 4821") == "otp"
    assert detect_sensitive("CRDB BANK", "Your account was credited") == "money"
    assert detect_sensitive("+255754210331", "Habari, tuonane saa 4") == ""
    assert mask_sensitive("G-482913 is your code") == "•••••••• is your code"


def test_custom_rule(phone):
    from modules.sms.models import SensitiveRule

    SensitiveRule.objects.create(name="Payroll", kind="money", body_pattern=r"(?i)salary slip")
    phone.send_events(phone.message(body="Your salary slip for October is ready"))
    assert Message.objects.get().is_sensitive


def test_retention_purge(phone, settings):
    from modules.audit.models import AuditEvent
    from modules.sms.services.retention import purge

    old = int((time.time() - 400 * 86400) * 1000)
    phone.send_events(phone.message(at_ms=old, body="old"), phone.message(body="new", address="+255713402118"))
    settings.SMS_RETENTION_DAYS = 365
    assert purge() == 1
    assert list(Message.objects.values_list("address", flat=True)) == ["+255713402118"]
    assert Conversation.objects.count() == 1 and AuditEvent.objects.filter(action="sms.retention_purge").exists()
    settings.SMS_RETENTION_DAYS = 0
    assert purge(now=timezone.now() + timezone.timedelta(days=5000)) == 0
