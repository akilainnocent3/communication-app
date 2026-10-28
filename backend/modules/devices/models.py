import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class DeviceStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    REVOKED = "revoked", "Revoked"


class Device(models.Model):
    """An enrolled company phone. `id` identifies it internally and `code` (DEV-7F3K-9Q2M) in the admin; neither is
    a credential. The phone proves who it is with a non-exportable Keystore key (`public_key`)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    office = models.ForeignKey("identity.Office", on_delete=models.PROTECT, related_name="devices")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_devices")
    status = models.CharField(max_length=16, choices=DeviceStatus.choices, default=DeviceStatus.ACTIVE, db_index=True)

    # Identity: SubjectPublicKeyInfo (DER, base64) of the Keystore EC P-256 key and its SHA-256.
    public_key = models.TextField()
    key_fingerprint = models.CharField(max_length=64, unique=True)
    hardware_backed = models.BooleanField(default=False)
    attestation = models.JSONField(default=dict, blank=True, help_text="Verified key attestation summary (no raw chain).")
    integrity = models.JSONField(default=dict, blank=True, help_text="Play Integrity verdict summary, when configured.")

    # Facts reported at enrollment (and refreshed by heartbeats).
    manufacturer = models.CharField(max_length=80, blank=True)
    model = models.CharField(max_length=80, blank=True)
    android_version = models.CharField(max_length=20, blank=True)
    sdk_int = models.PositiveSmallIntegerField(default=0)
    app_version = models.CharField(max_length=32, blank=True)

    # Options chosen at enrollment and editable by managers (admin signature, mark-read-on-open, backfill days…).
    options = models.JSONField(default=dict, blank=True)
    notice_text = models.TextField(blank=True, help_text="The monitoring notice the phone holder accepted.")
    notice_accepted_at = models.DateTimeField(null=True, blank=True)

    # Latest heartbeat (history in DeviceHeartbeat).
    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)
    battery = models.PositiveSmallIntegerField(null=True, blank=True)
    charging = models.BooleanField(default=False)
    network_type = models.CharField(max_length=16, blank=True)
    signal = models.SmallIntegerField(null=True, blank=True)
    is_default_sms_app = models.BooleanField(default=False)
    permissions = models.JSONField(default=dict, blank=True, help_text="Android permission → granted.")
    battery_optimised = models.BooleanField(default=False)
    background_restricted = models.BooleanField(default=False, help_text="ActivityManager.isBackgroundRestricted: background work is restricted for the app.")
    standby_bucket = models.PositiveSmallIntegerField(null=True, blank=True, help_text="UsageStatsManager standby bucket (10 active … 40 rare, 45 restricted).")
    pending_outbox = models.PositiveIntegerField(default=0)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    risk_signals = models.JSONField(default=dict, blank=True, help_text="Root / emulator / debugger signals. Reported, not blocking.")
    sync_progress = models.JSONField(default=dict, blank=True)
    sync_state = models.JSONField(default=dict, blank=True, help_text="Highest acknowledged event sequence and resync requests.")
    attention = models.JSONField(default=list, blank=True, help_text="Current alerts (codes) computed from the heartbeat.")

    # FCM registration token. Lets this server wake the phone; never serialised to the API or logged.
    push_token = models.TextField(blank=True)
    is_simulated = models.BooleanField(default=False)

    enrolled_at = models.DateTimeField(default=timezone.now)
    enrolled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    suspended_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["office__name", "name"]

    def __str__(self):
        return f"{self.code} {self.name}"

    @property
    def is_active(self) -> bool:
        return self.status == DeviceStatus.ACTIVE


class SimLine(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="sim_lines")
    subscription_id = models.IntegerField()
    slot = models.PositiveSmallIntegerField(default=0)
    carrier = models.CharField(max_length=80, blank=True)
    country_iso = models.CharField(max_length=2, blank=True)
    number = models.CharField(max_length=32, blank=True, help_text="E.164 when the SIM exposes it.")
    display_name = models.CharField(max_length=60, blank=True)
    colour = models.CharField(max_length=9, default="#3758f9")
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["slot", "subscription_id"]
        constraints = [models.UniqueConstraint(fields=["device", "subscription_id"], name="uniq_sim_line")]

    @property
    def label(self) -> str:
        return self.display_name or self.carrier or f"SIM {self.slot + 1}"


class EnrollmentInvite(models.Model):
    """Single-use enrollment token (QR or code). Only the SHA-256 is stored."""

    token_hash = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    office = models.ForeignKey("identity.Office", on_delete=models.CASCADE, related_name="+")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    options = models.JSONField(default=dict, blank=True)
    platform = models.CharField(max_length=20, default="sms")
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    device = models.OneToOneField(Device, null=True, blank=True, on_delete=models.SET_NULL, related_name="invite")
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    last_failure = models.CharField(max_length=64, blank=True)
    # Short code for typing (XXXX-XXXX, 40 bits): HMAC-SHA256 with the server secret (a bare SHA-256 of 40 bits could be
    # brute-forced from a database copy), 15 minutes, single use. Resolving it issues a second token for this invite
    # (only its hash is kept, valid for the code's lifetime after resolution).
    short_code_hash = models.CharField(max_length=64, blank=True, db_index=True)
    short_code_expires_at = models.DateTimeField(null=True, blank=True)
    short_code_used_at = models.DateTimeField(null=True, blank=True)
    resolved_token_hash = models.CharField(max_length=64, blank=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def state(self) -> str:
        if self.used_at:
            return "used"
        if self.revoked_at:
            return "revoked"
        if self.expires_at <= timezone.now():
            return "expired"
        return "active"


class DeviceToken(models.Model):
    """Short-lived opaque access token minted after a proof-of-possession signature. Only the SHA-256 is stored."""

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)


class DeviceHeartbeat(models.Model):
    """History of heartbeats (pruned by `devices.prune`). The latest state lives on Device."""

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="heartbeats")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    battery = models.PositiveSmallIntegerField(null=True, blank=True)
    charging = models.BooleanField(default=False)
    network_type = models.CharField(max_length=16, blank=True)
    signal = models.SmallIntegerField(null=True, blank=True)
    is_default_sms_app = models.BooleanField(default=False)
    pending_outbox = models.PositiveIntegerField(default=0)
    app_version = models.CharField(max_length=32, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["device", "-created_at"], name="heartbeat_device_recent")]


class DeviceCommand(models.Model):
    """Something the server asks a phone to do (mark a thread read, resync, block a number). Delivered with the
    outbox claim and acknowledged by the phone. Commands carry ids and numbers, never message text."""

    PENDING, DELIVERED, DONE, FAILED = "pending", "delivered", "done", "failed"

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="commands")
    kind = models.CharField(max_length=32)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=12, default=PENDING, choices=[(s, s.title()) for s in (PENDING, DELIVERED, DONE, FAILED)], db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["device", "status"], name="command_device_status")]
