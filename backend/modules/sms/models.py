"""The SMS platform: conversations and messages copied from enrolled company phones, and the outbound queue.

Message bodies, snippets and MMS files are encrypted at rest with SMS_DATA_KEYS (`services/crypto.py`). Numbers,
contact names and timestamps stay in plaintext so lists, search by contact and analytics work without decrypting.
"""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class SmsPlatform(models.Model):
    """Holds the platform-wide permissions."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("access", "Use the SMS platform"),
            ("access_all_devices", "Open every phone without explicit access"),
            ("manage_devices", "Enroll, suspend and revoke phones"),
        ]


class DeviceAccess(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sms_device_access")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="sms_access")
    can_read = models.BooleanField(default=True)
    can_send = models.BooleanField(default=False)
    can_manage = models.BooleanField(default=False)
    can_reveal_sensitive = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "device"], name="uniq_sms_device_access")]


class Contact(models.Model):
    """Name from the phone's address book, only for numbers that appear in synced conversations (data minimisation)."""

    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="sms_contacts")
    address = models.CharField(max_length=64, help_text="Address key: E.164, short code or sender ID.")
    display_name = models.CharField(max_length=120, blank=True)
    photo_hash = models.CharField(max_length=64, blank=True)
    is_blocked = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["device", "address"], name="uniq_sms_contact")]
        indexes = [models.Index(fields=["device", "display_name"], name="sms_contact_name")]


class Conversation(models.Model):
    OPEN, DONE = "open", "done"

    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="sms_conversations")
    thread_id = models.BigIntegerField(null=True, blank=True, help_text="Android Telephony thread id.")
    participants_key = models.CharField(max_length=700, help_text="Sorted address keys joined by ','.")
    addresses = models.JSONField(default=list, blank=True)
    is_group = models.BooleanField(default=False)
    last_message_at = models.DateTimeField(db_index=True)
    encrypted_snippet = models.TextField(blank=True)
    snippet_sensitive = models.BooleanField(default=False)
    last_direction = models.CharField(max_length=3, blank=True)
    last_status = models.CharField(max_length=16, blank=True)
    has_mms = models.BooleanField(default=False)
    unread_count = models.PositiveIntegerField(default=0)
    message_count = models.PositiveIntegerField(default=0)
    is_pinned = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    is_muted = models.BooleanField(default=False)
    is_spam = models.BooleanField(default=False)
    is_starred = models.BooleanField(default=False)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sms_assigned")
    state = models.CharField(max_length=8, choices=[(OPEN, "Open"), (DONE, "Done")], default=OPEN)
    first_message_at = models.DateTimeField(null=True, blank=True)
    last_inbound_at = models.DateTimeField(null=True, blank=True)
    last_outbound_at = models.DateTimeField(null=True, blank=True)
    # Set while the newest message is inbound and unanswered: "Awaiting reply" is a plain indexed filter.
    awaiting_since = models.DateTimeField(null=True, blank=True, db_index=True)
    sim_line = models.ForeignKey("devices.SimLine", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    # The company directory entry of a one-to-one conversation (set when the conversation is created).
    customer = models.ForeignKey("directory.Customer", null=True, blank=True, on_delete=models.SET_NULL, related_name="sms_conversations")
    deleted_on_device_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_message_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["device", "participants_key"], name="uniq_sms_conversation")]
        indexes = [
            models.Index(fields=["device", "-last_message_at", "-id"], name="sms_conv_device_recent"),
            models.Index(fields=["-last_message_at", "-id"], name="sms_conv_recent"),
            models.Index(fields=["device", "thread_id"], name="sms_conv_thread"),
        ]


class MessageStatus(models.TextChoices):
    RECEIVED = "received", "Received"
    QUEUED = "queued", "Queued"
    DISPATCHED = "dispatched", "Sent to phone"
    SENDING = "sending", "Sending"
    SENT = "sent", "Sent"
    DELIVERED = "delivered", "Delivered"
    FAILED = "failed", "Failed"
    EXPIRED = "expired", "Expired"
    CANCELLED = "cancelled", "Cancelled"
    UNKNOWN = "unknown", "Delivery unknown"


class Message(models.Model):
    SMS, MMS = "sms", "mms"
    IN, OUT = "in", "out"
    ORIGIN_PHONE, ORIGIN_ADMIN, ORIGIN_AUTO = "phone", "admin", "auto"
    GSM7, UCS2 = "gsm7", "ucs2"
    # Admin messages the phone may still pick up or is working on.
    PENDING_STATUSES = (MessageStatus.QUEUED, MessageStatus.DISPATCHED, MessageStatus.SENDING)

    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="sms_messages")
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sim_line = models.ForeignKey("devices.SimLine", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    kind = models.CharField(max_length=3, choices=[(SMS, "SMS"), (MMS, "MMS")], default=SMS)
    direction = models.CharField(max_length=3, choices=[(IN, "Inbound"), (OUT, "Outbound")])
    address = models.CharField(max_length=64, help_text="Sender (inbound) or first recipient (outbound), address key.")
    addresses = models.JSONField(default=list, blank=True, help_text="Raw addresses as the phone reported them.")
    encrypted_body = models.TextField(blank=True)
    body_length = models.PositiveIntegerField(default=0)
    segments = models.PositiveSmallIntegerField(default=1)
    encoding = models.CharField(max_length=4, choices=[(GSM7, "GSM-7"), (UCS2, "UCS-2")], default=GSM7)
    subject = models.CharField(max_length=200, blank=True)
    provider_id = models.BigIntegerField(null=True, blank=True, help_text="Android provider _id.")
    provider_date = models.DateTimeField(db_index=True, help_text="When the message was received/sent on the phone (or queued).")
    received_at = models.DateTimeField(default=timezone.now, help_text="When this server learned of the message.")
    is_read = models.BooleanField(default=True)
    status = models.CharField(max_length=16, choices=MessageStatus.choices, default=MessageStatus.RECEIVED, db_index=True)
    status_history = models.JSONField(default=list, blank=True)
    origin = models.CharField(max_length=8, choices=[(ORIGIN_PHONE, "Phone"), (ORIGIN_ADMIN, "Admin"), (ORIGIN_AUTO, "Rule")], default=ORIGIN_PHONE)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sms_sent")
    client_uuid = models.UUIDField(null=True, blank=True, unique=True)
    send_at = models.DateTimeField(null=True, blank=True, help_text="Admin messages: earliest time the phone may send (undo window / schedule).")
    is_scheduled = models.BooleanField(default=False)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    error_code = models.IntegerField(null=True, blank=True)
    error_detail = models.CharField(max_length=200, blank=True)
    retry_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="retries")
    deleted_on_device_at = models.DateTimeField(null=True, blank=True)
    is_sensitive = models.BooleanField(default=False)
    sensitive_kind = models.CharField(max_length=16, blank=True)
    is_starred = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["provider_date", "id"]
        constraints = [
            models.UniqueConstraint(fields=["device", "kind", "provider_id", "provider_date"], condition=Q(provider_id__isnull=False), name="uniq_sms_provider_message"),
        ]
        indexes = [
            models.Index(fields=["conversation", "provider_date", "id"], name="sms_msg_conv_date"),
            models.Index(fields=["device", "provider_date"], name="sms_msg_device_date"),
            models.Index(fields=["device", "status", "send_at"], name="sms_msg_outbox"),
        ]

    def set_status(self, status: str, at=None) -> None:
        at = at or timezone.now()
        self.status = status
        self.status_history = [*(self.status_history or []), {"status": status, "at": at.isoformat()}][-20:]


class MessagePart(models.Model):
    """One MMS attachment. The file is encrypted (SMS_DATA_KEYS) in SMS_MEDIA_ROOT, never under a public URL."""

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="parts")
    seq = models.PositiveSmallIntegerField()
    declared_type = models.CharField(max_length=100, blank=True)
    content_type = models.CharField(max_length=100, blank=True, help_text="Detected from the file's magic bytes.")
    filename = models.CharField(max_length=120, blank=True)
    size = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(max_length=64)
    storage_name = models.CharField(max_length=80, blank=True)
    received_bytes = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["seq"]
        constraints = [models.UniqueConstraint(fields=["message", "seq"], name="uniq_sms_part")]


class ConversationNote(models.Model):
    """Internal note. Never sent to the phone."""

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class QuickReply(models.Model):
    """Reply templates, synced to the phones as quick replies. `device` null = every phone."""

    title = models.CharField(max_length=80)
    body = models.TextField(max_length=1000)
    device = models.ForeignKey("devices.Device", null=True, blank=True, on_delete=models.CASCADE, related_name="quick_replies")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]


class SensitiveRule(models.Model):
    """Pattern that marks a message sensitive (one-time codes, banking and mobile-money messages)."""

    OTP, MONEY = "otp", "money"

    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=16, choices=[(OTP, "One-time code"), (MONEY, "Banking / mobile money")])
    sender_pattern = models.CharField(max_length=200, blank=True, help_text="Regex on the sender address (optional).")
    body_pattern = models.CharField(max_length=300, blank=True, help_text="Regex on the text (optional).")
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind", "name"]


class SmsSettings(models.Model):
    """Singleton for platform-wide SMS settings (Settings → Integrations)."""

    monitoring_notice = models.TextField(
        default=(
            "This is a company phone. Its text messages will be copied to the company's OCM (Office Communication Management), and "
            "authorised administrators will be able to read them and send messages from this phone. All access is logged."
        )
    )
    default_signature = models.CharField(max_length=40, default="- Head Office")
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def load(cls) -> "SmsSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SimulatedDevice(models.Model):
    """State of a simulated phone (demo and E2E only; production refuses the simulator)."""

    device = models.OneToOneField("devices.Device", on_delete=models.CASCADE, related_name="simulator")
    encrypted_private_key = models.TextField()
    online = models.BooleanField(default=True)
    next_seq = models.BigIntegerField(default=1)
    next_provider_id = models.BigIntegerField(default=1000)
    state = models.JSONField(default=dict, blank=True)
