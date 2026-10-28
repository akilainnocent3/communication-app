"""The Calls platform: every call on an enrolled company phone, captured by the phone's dialer and synced.

Numbers, names, times and durations stay plaintext (lists, filters, analytics). Free text — call notes and callback
reasons — is encrypted with the device-data key ring (common/devicecrypto.py, SMS_DATA_KEYS). No call audio exists:
third-party apps cannot record calls (docs/calls-recording.md). USSD/MMI codes, DTMF digits and emergency calls are
never sent by the phone and refused by the server (docs/security.md).
"""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class CallsPlatform(models.Model):
    """Holds the platform-wide permissions."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("access", "Use the Calls platform"),
            ("access_all_devices", "Open every phone's calls without explicit access"),
            ("manage_settings", "Change Calls settings, outcomes, office hours, tariffs; enable Calls on phones"),
            ("export", "Export call logs"),
        ]


class DeviceAccess(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calls_device_access")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="calls_access")
    can_read = models.BooleanField(default=True)
    can_assign_callbacks = models.BooleanField(default=False)
    can_annotate = models.BooleanField(default=False)
    can_export = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "device"], name="uniq_calls_device_access")]


class Direction(models.TextChoices):
    IN = "in", "Incoming"
    OUT = "out", "Outgoing"


class Result(models.TextChoices):
    ANSWERED = "answered", "Answered"
    MISSED = "missed", "Missed"
    REJECTED = "rejected", "Declined"
    BLOCKED = "blocked", "Blocked"
    BUSY = "busy", "Busy"
    NO_ANSWER = "no_answer", "No answer"
    FAILED = "failed", "Failed"
    VOICEMAIL = "voicemail", "Voicemail"
    ANSWERED_ELSEWHERE = "answered_elsewhere", "Answered elsewhere"
    CANCELLED = "cancelled", "Cancelled"


# Incoming calls the company did not take: the "missed" family that needs a call back.
MISSED_RESULTS = (Result.MISSED, Result.REJECTED, Result.VOICEMAIL)
# Results that mean somebody talked.
CONNECTED_RESULTS = (Result.ANSWERED,)


class CallRecord(models.Model):
    """One call. Merged from the system call log (CallLog.Calls) and the dialer's live InCallService events."""

    PRESENTATION = [("allowed", "Allowed"), ("restricted", "Private number"), ("unknown", "Unknown"), ("payphone", "Payphone")]
    ENDED_BY = [("local", "This phone"), ("remote", "Other side"), ("system", "Network or system"), ("", "Unknown")]
    NETWORK = [("volte", "VoLTE"), ("wifi", "Wi-Fi calling"), ("cs", "Mobile network"), ("unknown", "Unknown")]
    ORIGIN = [("manual", "Dialled"), ("callback_task", "Callback task"), ("from_sms", "From a message"), ("redial", "Redial"), ("incoming", "Incoming")]

    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="calls")
    office = models.ForeignKey("identity.Office", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", help_text="The phone's office when the call happened.")
    sim_line = models.ForeignKey("devices.SimLine", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    customer = models.ForeignKey("directory.Customer", null=True, blank=True, on_delete=models.SET_NULL, related_name="calls")
    direction = models.CharField(max_length=3, choices=Direction.choices)
    result = models.CharField(max_length=20, choices=Result.choices)
    number_e164 = models.CharField(max_length=64, blank=True, help_text="Address key: E.164 for phone numbers, digits for short codes; empty when hidden.")
    raw_number = models.CharField(max_length=64, blank=True)
    presentation = models.CharField(max_length=12, choices=PRESENTATION, default="allowed")
    contact_name_on_phone = models.CharField(max_length=120, blank=True)
    started_at = models.DateTimeField(help_text="Ring start (incoming) or dial start (outgoing).")
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    ring_seconds = models.PositiveIntegerField(default=0)
    talk_seconds = models.PositiveIntegerField(default=0, help_text="answered → ended; stored for indexing and sums.")
    disconnect_cause_code = models.SmallIntegerField(null=True, blank=True)
    disconnect_cause_label = models.CharField(max_length=80, blank=True)
    ended_by = models.CharField(max_length=8, choices=ENDED_BY, blank=True)
    is_conference = models.BooleanField(default=False)
    conference_size = models.PositiveSmallIntegerField(default=0)
    is_video = models.BooleanField(default=False)
    network = models.CharField(max_length=8, choices=NETWORK, default="unknown")
    was_on_hold_seconds = models.PositiveIntegerField(default=0)
    origin = models.CharField(max_length=16, choices=ORIGIN, default="manual")
    callback_task = models.ForeignKey("CallbackTask", null=True, blank=True, on_delete=models.SET_NULL, related_name="calls")
    # A later answered call with this number (either direction) links back to the missed call it returned.
    returns_call = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="returned_calls")
    returned_at = models.DateTimeField(null=True, blank=True, help_text="Missed calls: when the number was next reached.")
    returned_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    is_after_hours = models.BooleanField(default=False)
    provider_call_log_id = models.BigIntegerField(null=True, blank=True, help_text="CallLog.Calls._ID on the phone.")
    android_call_key = models.CharField(max_length=64, null=True, blank=True, help_text="The dialer's own id for a live call.")
    is_final = models.BooleanField(default=False, help_text="Ended: counted in the rollups.")
    deleted_on_device_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["device", "provider_call_log_id"], condition=Q(provider_call_log_id__isnull=False), name="uniq_call_log_id"),
            models.UniqueConstraint(fields=["device", "android_call_key"], condition=Q(android_call_key__isnull=False), name="uniq_call_key"),
        ]
        indexes = [
            models.Index(fields=["device", "-started_at", "-id"], name="call_device_recent"),
            models.Index(fields=["-started_at", "-id"], name="call_recent"),
            models.Index(fields=["number_e164", "-started_at"], name="call_number_recent"),
            models.Index(fields=["result", "started_at"], name="call_result_date"),
            models.Index(fields=["customer", "-started_at"], name="call_customer_recent"),
            models.Index(fields=["direction", "result", "returned_at", "started_at"], name="call_unreturned"),
        ]

    @property
    def is_missed(self) -> bool:
        return self.direction == Direction.IN and self.result in MISSED_RESULTS


class CallEvent(models.Model):
    """Append-only timeline of one call, from the dialer's InCallService."""

    KINDS = ["ringing", "dialing", "active", "hold", "unhold", "conference_add", "ended"]

    call = models.ForeignKey(CallRecord, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=16, choices=[(k, k.replace("_", " ").title()) for k in KINDS])
    at = models.DateTimeField()
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["at", "id"]
        constraints = [models.UniqueConstraint(fields=["call", "kind", "at"], name="uniq_call_event")]


class CallOutcome(models.Model):
    """Company-defined dispositions (Sale, Support, Complaint…)."""

    name = models.CharField(max_length=60, unique=True)
    colour = models.CharField(max_length=9, default="#3758f9")
    order = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]


class CallAnnotation(models.Model):
    call = models.ForeignKey(CallRecord, on_delete=models.CASCADE, related_name="annotations")
    outcome = models.ForeignKey(CallOutcome, null=True, blank=True, on_delete=models.SET_NULL, related_name="annotations")
    encrypted_note = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    from_phone = models.BooleanField(default=False, help_text="Written by the staff member on the phone (post-call card).")
    client_uuid = models.UUIDField(null=True, blank=True, unique=True, help_text="Idempotency key from the phone.")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]


class CallbackTask(models.Model):
    """An admin asks the phone holder to call a customer. The phone shows it; the holder taps Call. Never auto-dialled."""

    OPEN, NOTIFIED, DIALED, DONE, CANCELLED, EXPIRED = "open", "notified", "dialed", "done", "cancelled", "expired"
    STATES = [(OPEN, "Open"), (NOTIFIED, "On the phone"), (DIALED, "Called"), (DONE, "Done"), (CANCELLED, "Cancelled"), (EXPIRED, "Expired")]
    ACTIVE_STATES = (OPEN, NOTIFIED, DIALED)
    PRIORITIES = [("low", "Low"), ("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, help_text="Stable id the phone uses.")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="callback_tasks")
    customer = models.ForeignKey("directory.Customer", null=True, blank=True, on_delete=models.SET_NULL, related_name="callback_tasks")
    number_e164 = models.CharField(max_length=64)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="callbacks_assigned")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="callbacks_assigned_to_me",
                                 help_text="Who holds the phone (defaults to the phone's assigned user).")
    source_call = models.ForeignKey(CallRecord, null=True, blank=True, on_delete=models.SET_NULL, related_name="callback_requests")
    due_at = models.DateTimeField()
    priority = models.CharField(max_length=8, choices=PRIORITIES, default="normal")
    encrypted_reason = models.TextField(blank=True)
    state = models.CharField(max_length=10, choices=STATES, default=OPEN, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    call = models.ForeignKey(CallRecord, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", help_text="The call placed for it.")
    notified_at = models.DateTimeField(null=True, blank=True)
    dialed_at = models.DateTimeField(null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    snoozed_until = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_at", "id"]
        indexes = [
            models.Index(fields=["device", "state", "due_at"], name="callback_device_state"),
            models.Index(fields=["assignee", "state"], name="callback_assignee"),
        ]


class OfficeHours(models.Model):
    """Opening hours of one office, in its own time zone. `week` maps ISO weekday (1 = Monday) to [["08:00", "17:00"], …]."""

    office = models.OneToOneField("identity.Office", on_delete=models.CASCADE, related_name="call_hours")
    timezone = models.CharField(max_length=64, default="Africa/Dar_es_Salaam")
    week = models.JSONField(default=dict, blank=True)
    holidays = models.JSONField(default=list, blank=True, help_text="Closed all day: ISO dates (YYYY-MM-DD).")
    updated_at = models.DateTimeField(auto_now=True)


class CarrierTariff(models.Model):
    """Price of outgoing minutes per carrier, for cost estimates (the bill itself comes from the carrier)."""

    carrier = models.CharField(max_length=80, unique=True, help_text="As the SIM reports it (SimLine.carrier), case-insensitive.")
    per_minute = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="TZS")
    billing_increment_seconds = models.PositiveSmallIntegerField(default=60)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["carrier"]


class CallSettings(models.Model):
    """Singleton for platform-wide Calls settings."""

    unreturned_hours = models.PositiveSmallIntegerField(default=4, help_text="A missed call is unreturned if nobody reaches the number within this time.")
    outcome_required_after_seconds = models.PositiveIntegerField(default=0, help_text="0 = the post-call card is optional.")
    post_call_card = models.BooleanField(default=True)
    auto_sms_enabled = models.BooleanField(default=False)
    auto_sms_template = models.CharField(max_length=300, default="Sorry we missed your call. We will call you back as soon as possible. - {company}")
    auto_sms_after_hours_only = models.BooleanField(default=False)
    auto_sms_per_number_per_day = models.PositiveSmallIntegerField(default=1)
    auto_sms_cooldown_hours = models.PositiveSmallIntegerField(default=24)
    callback_expiry_hours = models.PositiveSmallIntegerField(default=72)
    retention_days = models.PositiveIntegerField(null=True, blank=True, help_text="Overrides CALLS_RETENTION_DAYS when set.")
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def load(cls) -> "CallSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AutoSmsLog(models.Model):
    """Automatic missed-call messages sent, for the per-number limits."""

    number_e164 = models.CharField(max_length=64)
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="+")
    call = models.OneToOneField(CallRecord, on_delete=models.CASCADE, related_name="auto_sms")
    message_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["number_e164", "created_at"], name="autosms_number")]


class CallStatHourly(models.Model):
    """Incremental rollup (one row per hour bucket and dimension combination). Dashboards read only these.

    `hour` is the UTC hour start. Maintained on ingest (services/rollups.py) and recomputed nightly for recent days."""

    hour = models.DateTimeField()
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="+")
    sim_line_id = models.BigIntegerField(null=True, blank=True)
    office_id = models.BigIntegerField(null=True, blank=True)
    direction = models.CharField(max_length=3)
    result = models.CharField(max_length=20)
    after_hours = models.BooleanField(default=False)
    calls = models.IntegerField(default=0)
    talk_seconds = models.BigIntegerField(default=0)
    ring_seconds = models.BigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["hour", "device", "sim_line_id", "office_id", "direction", "result", "after_hours"],
                                               name="uniq_call_stat_hour", nulls_distinct=False)]
        indexes = [models.Index(fields=["hour", "device"], name="callstat_hour_device")]


class CallerDaily(models.Model):
    """Calls per number per phone per UTC day (rollup): unique callers, top and repeat callers without raw scans."""

    day = models.DateField()
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="+")
    number_e164 = models.CharField(max_length=64)
    incoming = models.IntegerField(default=0)
    outgoing = models.IntegerField(default=0)
    missed = models.IntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["day", "device", "number_e164"], name="uniq_caller_day")]
        indexes = [models.Index(fields=["day", "device"], name="callerday_day_device")]
