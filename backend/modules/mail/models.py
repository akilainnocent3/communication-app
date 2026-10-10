from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils import timezone


class Provider(models.TextChoices):
    GMAIL_OAUTH = "gmail_oauth", "Google"
    WORKSPACE_DELEGATION = "workspace_delegation", "Google Workspace"
    IMAP_SMTP = "imap_smtp", "IMAP / SMTP"
    FAKE = "fake", "Demo"


class MailboxStatus(models.TextChoices):
    PENDING = "pending", "Waiting for connection"
    CONNECTED = "connected", "Connected"
    NEEDS_RECONNECT = "needs_reconnect", "Needs reconnect"
    SYNCING = "syncing", "Syncing"
    ERROR = "error", "Error"
    DISABLED = "disabled", "Disabled"


class Mailbox(models.Model):
    office = models.ForeignKey("identity.Office", on_delete=models.PROTECT, related_name="mailboxes")
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=120, blank=True)
    colour = models.CharField(max_length=9, default="#3758f9")
    provider = models.CharField(max_length=32, choices=Provider.choices)
    status = models.CharField(max_length=32, choices=MailboxStatus.choices, default=MailboxStatus.PENDING, db_index=True)
    # Encrypted JSON (MultiFernet): refresh token / IMAP password. Never serialised to the API.
    encrypted_credentials = models.TextField(blank=True)
    # Non-secret connection settings (IMAP host/port, detected MX, Workspace domain).
    server_settings = models.JSONField(default=dict, blank=True)
    granted_scopes = models.JSONField(default=list, blank=True)
    history_id = models.CharField(max_length=64, blank=True, help_text="Provider sync cursor (Gmail historyId).")
    sync_state = models.JSONField(default=dict, blank=True, help_text="Provider-specific sync state (IMAP UIDs).")
    sync_progress = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    sync_error = models.TextField(blank=True)
    connected_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    connected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["office__name", "email"]
        permissions = [
            ("access", "Use the Gmail platform"),
            ("access_all_mailboxes", "Open every mailbox without explicit access"),
            ("manage_mailboxes", "Connect, edit and disconnect mailboxes"),
        ]

    def __str__(self):
        return self.email

    @property
    def name(self) -> str:
        return self.display_name or self.office.name


class MailboxInvite(models.Model):
    mailbox = models.ForeignKey(Mailbox, on_delete=models.CASCADE, related_name="invites")
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
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


class MailboxAccess(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mailbox_access")
    mailbox = models.ForeignKey(Mailbox, on_delete=models.CASCADE, related_name="access")
    can_read = models.BooleanField(default=True)
    can_send = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_manage = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "mailbox"], name="uniq_mailbox_access")]


class Label(models.Model):
    SYSTEM = "system"
    USER = "user"

    mailbox = models.ForeignKey(Mailbox, on_delete=models.CASCADE, related_name="labels")
    provider_label_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=10, choices=[(SYSTEM, "System"), (USER, "User")], default=USER)
    colour = models.CharField(max_length=9, blank=True)
    text_colour = models.CharField(max_length=9, blank=True)
    messages_unread = models.PositiveIntegerField(default=0)
    messages_total = models.PositiveIntegerField(default=0)
    threads_unread = models.PositiveIntegerField(default=0)
    threads_total = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["mailbox", "provider_label_id"], name="uniq_label")]


class Thread(models.Model):
    mailbox = models.ForeignKey(Mailbox, on_delete=models.CASCADE, related_name="threads")
    provider_thread_id = models.CharField(max_length=255)
    subject = models.TextField(blank=True)
    snippet = models.TextField(blank=True)
    participants = models.JSONField(default=list, blank=True)
    last_message_at = models.DateTimeField(db_index=True)
    message_count = models.PositiveIntegerField(default=0)
    has_attachments = models.BooleanField(default=False)
    label_ids = ArrayField(models.CharField(max_length=255), default=list, blank=True)
    is_unread = models.BooleanField(default=False)
    is_starred = models.BooleanField(default=False)
    is_important = models.BooleanField(default=False)
    is_muted = models.BooleanField(default=False)
    search_vector = SearchVectorField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_message_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["mailbox", "provider_thread_id"], name="uniq_thread")]
        indexes = [
            models.Index(fields=["mailbox", "-last_message_at", "-id"], name="thread_mailbox_recent"),
            models.Index(fields=["-last_message_at", "-id"], name="thread_recent"),
            models.Index(fields=["mailbox", "is_unread"], name="thread_mailbox_unread"),
            GinIndex(fields=["label_ids"], name="thread_label_ids"),
            GinIndex(fields=["search_vector"], name="thread_search"),
        ]


class Message(models.Model):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="messages")
    mailbox = models.ForeignKey(Mailbox, on_delete=models.CASCADE, related_name="messages")
    provider_message_id = models.CharField(max_length=255)
    rfc_message_id = models.CharField(max_length=998, blank=True)
    in_reply_to = models.CharField(max_length=998, blank=True)
    references = models.TextField(blank=True)
    from_addr = models.JSONField(default=dict, blank=True)
    to = models.JSONField(default=list, blank=True)
    cc = models.JSONField(default=list, blank=True)
    bcc = models.JSONField(default=list, blank=True)
    reply_to = models.JSONField(default=list, blank=True)
    subject = models.TextField(blank=True)
    date = models.DateTimeField(db_index=True)
    snippet = models.TextField(blank=True)
    label_ids = ArrayField(models.CharField(max_length=255), default=list, blank=True)
    size = models.PositiveIntegerField(default=0)
    has_attachments = models.BooleanField(default=False)
    attachments = models.JSONField(default=list, blank=True)
    list_unsubscribe = models.TextField(blank=True)
    list_unsubscribe_post = models.CharField(max_length=255, blank=True)
    is_outgoing = models.BooleanField(default=False)
    # Sanitised body cache, filled when the thread is opened, evicted after MAIL_BODY_CACHE_DAYS.
    body_html = models.TextField(null=True, blank=True)
    body_text = models.TextField(null=True, blank=True)
    body_meta = models.JSONField(default=dict, blank=True)
    body_cached_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["date", "id"]
        constraints = [models.UniqueConstraint(fields=["mailbox", "provider_message_id"], name="uniq_message")]
        indexes = [
            models.Index(fields=["thread", "date"], name="message_thread_date"),
            models.Index(fields=["mailbox", "date"], name="message_mailbox_date"),
            models.Index(fields=["body_cached_at"], name="message_body_cached"),
        ]


class Draft(models.Model):
    """Local index of provider drafts (the provider is the source of truth)."""

    mailbox = models.ForeignKey(Mailbox, on_delete=models.CASCADE, related_name="drafts")
    provider_draft_id = models.CharField(max_length=255)
    provider_message_id = models.CharField(max_length=255, blank=True)
    thread = models.ForeignKey(Thread, null=True, blank=True, on_delete=models.SET_NULL, related_name="drafts")
    to = models.JSONField(default=list, blank=True)
    cc = models.JSONField(default=list, blank=True)
    bcc = models.JSONField(default=list, blank=True)
    subject = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    snippet = models.TextField(blank=True)
    mode = models.CharField(max_length=16, default="new")
    in_reply_to_message = models.ForeignKey(Message, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    attachment_ids = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=["mailbox", "provider_draft_id"], name="uniq_draft")]


class Contact(models.Model):
    mailbox = models.ForeignKey(Mailbox, on_delete=models.CASCADE, related_name="contacts")
    email = models.EmailField()
    name = models.CharField(max_length=255, blank=True)
    last_seen = models.DateTimeField(default=timezone.now)
    frequency = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["mailbox", "email"], name="uniq_contact")]
        indexes = [models.Index(fields=["mailbox", "-frequency"], name="contact_rank")]


class OutgoingAttachment(models.Model):
    """A file uploaded for compose. Private storage, streamed back only through permission-checked views."""

    mailbox = models.ForeignKey(Mailbox, on_delete=models.CASCADE, related_name="+")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=255, default="application/octet-stream")
    size = models.PositiveIntegerField()
    content = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)


class ScheduledEmail(models.Model):
    """A send waiting for its time: the undo-send window (kind=undo) or a scheduled send."""

    UNDO = "undo"
    SCHEDULED = "scheduled"
    PENDING, SENDING, SENT, CANCELLED, FAILED = "pending", "sending", "sent", "cancelled", "failed"

    mailbox = models.ForeignKey(Mailbox, on_delete=models.CASCADE, related_name="scheduled")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    kind = models.CharField(max_length=16, choices=[(UNDO, "Undo window"), (SCHEDULED, "Scheduled")])
    send_at = models.DateTimeField(db_index=True)
    payload = models.JSONField()
    status = models.CharField(
        max_length=16,
        choices=[(s, s.title()) for s in (PENDING, SENDING, SENT, CANCELLED, FAILED)],
        default=PENDING,
        db_index=True,
    )
    error = models.TextField(blank=True)
    sent_message_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["send_at"]
        indexes = [models.Index(fields=["status", "send_at"], name="scheduled_due")]


class SnoozedThread(models.Model):
    thread = models.OneToOneField(Thread, on_delete=models.CASCADE, related_name="snooze")
    until = models.DateTimeField(db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)


class EmailTemplate(models.Model):
    name = models.CharField(max_length=120)
    subject = models.CharField(max_length=255, blank=True)
    body_html = models.TextField()
    mailbox = models.ForeignKey(Mailbox, null=True, blank=True, on_delete=models.CASCADE, related_name="templates")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]


class ThreadNote(models.Model):
    """Internal note on a thread. Never sent to the provider."""

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class ThreadAssignment(models.Model):
    OPEN, DONE = "open", "done"

    thread = models.OneToOneField(Thread, on_delete=models.CASCADE, related_name="assignment")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assigned_threads")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=8, choices=[(OPEN, "Open"), (DONE, "Done")], default=OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["assignee", "status"], name="assignment_assignee")]


class TrustedSender(models.Model):
    """'Always show images from this sender' (per user)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    email = models.EmailField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "email"], name="uniq_trusted_sender")]


class UndoToken(models.Model):
    """Reverses a bulk action: the label changes needed to restore the previous state."""

    token = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    changes = models.JSONField()
    expires_at = models.DateTimeField()


class WorkspaceDomain(models.Model):
    domain = models.CharField(max_length=253, unique=True)
    encrypted_service_account = models.TextField()
    client_id = models.CharField(max_length=64)
    service_account_email = models.EmailField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    last_test_at = models.DateTimeField(null=True, blank=True)
    last_test_ok = models.BooleanField(default=False)
    last_test_error = models.TextField(blank=True)


class MailSettings(models.Model):
    """Singleton for platform-wide mail settings (editable in Settings → Integrations)."""

    connect_notice = models.TextField(
        default=(
            "Authorised company administrators will be able to read, send and manage email in this mailbox. "
            "All access is logged."
        )
    )
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def load(cls) -> "MailSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# --- Fake provider store ------------------------------------------------------------------------------
# The fake provider behaves like a tiny Gmail server backed by these tables, so sync, actions and sends
# round-trip exactly like the real thing (including history ids). Used for dev, demos and tests.


class FakeServerState(models.Model):
    mailbox = models.OneToOneField(Mailbox, on_delete=models.CASCADE, related_name="fake_state")
    history_id = models.PositiveBigIntegerField(default=1000)
    labels = models.JSONField(default=list)
    settings = models.JSONField(default=dict)


class FakeMessage(models.Model):
    mailbox = models.ForeignKey(Mailbox, on_delete=models.CASCADE, related_name="+")
    message_id = models.CharField(max_length=64)
    thread_id = models.CharField(max_length=64, db_index=True)
    draft_id = models.CharField(max_length=64, blank=True)
    label_ids = ArrayField(models.CharField(max_length=255), default=list)
    headers = models.JSONField(default=dict)
    body_html = models.TextField(blank=True)
    body_text = models.TextField(blank=True)
    attachments = models.JSONField(default=list)
    internal_date = models.DateTimeField()
    history_id = models.PositiveBigIntegerField(default=0, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["mailbox", "message_id"], name="uniq_fake_message")]


class FakeHistory(models.Model):
    mailbox = models.ForeignKey(Mailbox, on_delete=models.CASCADE, related_name="+")
    history_id = models.PositiveBigIntegerField(db_index=True)
    thread_id = models.CharField(max_length=64)
    deleted = models.BooleanField(default=False)
