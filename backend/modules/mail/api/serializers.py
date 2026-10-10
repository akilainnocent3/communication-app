import re

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ..models import EmailTemplate, Label, Mailbox, MailboxAccess, MailboxInvite, Message, ScheduledEmail, Thread, ThreadNote

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class AddressSerializer(serializers.Serializer):
    email = serializers.CharField()
    name = serializers.CharField(allow_blank=True, required=False, default="")


class OfficeRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    colour = serializers.CharField()


class MailboxPermissionsSerializer(serializers.Serializer):
    read = serializers.BooleanField()
    send = serializers.BooleanField()
    delete = serializers.BooleanField()
    manage = serializers.BooleanField()


class CapabilitiesSerializer(serializers.Serializer):
    labels = serializers.BooleanField()
    categories = serializers.BooleanField()
    filters = serializers.BooleanField()
    vacation = serializers.BooleanField()
    signatures = serializers.BooleanField()
    send_as = serializers.BooleanField()
    important = serializers.BooleanField()
    server_search = serializers.BooleanField()
    revoke = serializers.BooleanField()


class MailboxSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)
    office = serializers.SerializerMethodField()
    provider_label = serializers.CharField(source="get_provider_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    connected_by = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    unread = serializers.SerializerMethodField()

    class Meta:
        model = Mailbox
        fields = [
            "id", "email", "display_name", "name", "colour", "office", "provider", "provider_label", "status", "status_label",
            "sync_progress", "last_synced_at", "sync_error", "connected_at", "connected_by", "granted_scopes", "capabilities",
            "permissions", "unread", "created_at",
        ]

    @extend_schema_field(OfficeRefSerializer)
    def get_office(self, obj):
        return {"id": obj.office_id, "name": obj.office.name, "colour": obj.office.colour}

    def get_connected_by(self, obj) -> str | None:
        return obj.connected_by.email if obj.connected_by_id and obj.connected_by else None

    @extend_schema_field(CapabilitiesSerializer)
    def get_capabilities(self, obj):
        from ..providers.base import Capabilities

        if obj.provider == "imap_smtp":
            return Capabilities(labels=False, categories=False, filters=False, vacation=False, signatures=False, send_as=False, important=False, revoke=False).as_dict()
        return Capabilities(revoke=obj.provider == "gmail_oauth").as_dict()

    @extend_schema_field(MailboxPermissionsSerializer)
    def get_permissions(self, obj):
        from ..services.access import permissions_for

        cache = self.context.setdefault("_perms", {})
        if obj.pk not in cache:
            cache[obj.pk] = permissions_for(self.context["request"].user, obj)
        return cache[obj.pk]

    def get_unread(self, obj) -> int:
        value = getattr(obj, "unread", None)
        if value is None:
            value = obj.threads.filter(is_unread=True, label_ids__contains=["INBOX"]).count()
        return value


class MailboxCreateSerializer(serializers.Serializer):
    office = serializers.IntegerField()
    email = serializers.EmailField()
    display_name = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    colour = serializers.CharField(max_length=7, required=False, allow_blank=True, default="")
    provider = serializers.ChoiceField(choices=["auto", "fake"], required=False, default="auto")

    def validate_colour(self, value):
        if value and not HEX.match(value):
            raise serializers.ValidationError("Use a hex colour like #3758f9.")
        return value.lower()


class MailboxUpdateSerializer(serializers.Serializer):
    office = serializers.IntegerField(required=False)
    display_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    colour = serializers.CharField(max_length=7, required=False)

    def validate_colour(self, value):
        if not HEX.match(value):
            raise serializers.ValidationError("Use a hex colour like #3758f9.")
        return value.lower()


class DetectRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ImapDefaultsSerializer(serializers.Serializer):
    imap_host = serializers.CharField()
    imap_port = serializers.IntegerField()
    imap_security = serializers.CharField()
    smtp_host = serializers.CharField()
    smtp_port = serializers.IntegerField()
    smtp_security = serializers.CharField()


class DetectionSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=["gmail_oauth", "workspace_delegation", "imap_smtp", "unsupported", "fake"])
    reason = serializers.CharField()
    domain = serializers.CharField()
    mx = serializers.ListField(child=serializers.CharField())
    supported = serializers.BooleanField()
    imap_defaults = ImapDefaultsSerializer(allow_null=True)


class MailboxCreatedSerializer(serializers.Serializer):
    mailbox = MailboxSerializer()
    detection = DetectionSerializer()


class InviteSerializer(serializers.ModelSerializer):
    state = serializers.CharField(read_only=True)
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = MailboxInvite
        fields = ["id", "state", "expires_at", "used_at", "revoked_at", "created_at", "created_by"]

    def get_created_by(self, obj) -> str | None:
        return obj.created_by.email if obj.created_by_id else None


class InviteCreatedSerializer(InviteSerializer):
    url = serializers.CharField()
    whatsapp_url = serializers.CharField()
    qr_svg = serializers.CharField()

    class Meta(InviteSerializer.Meta):
        fields = [*InviteSerializer.Meta.fields, "url", "whatsapp_url", "qr_svg"]


class MailboxStatusSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    sync_progress = serializers.DictField()
    last_synced_at = serializers.DateTimeField(allow_null=True)
    sync_error = serializers.CharField(allow_blank=True)
    latest_invite = InviteSerializer(allow_null=True)


class ImapSettingsSerializer(serializers.Serializer):
    imap_host = serializers.CharField(max_length=253)
    imap_port = serializers.IntegerField(min_value=1, max_value=65535)
    imap_security = serializers.ChoiceField(choices=["ssl", "starttls"])
    smtp_host = serializers.CharField(max_length=253)
    smtp_port = serializers.IntegerField(min_value=1, max_value=65535)
    smtp_security = serializers.ChoiceField(choices=["ssl", "starttls"])
    username = serializers.CharField(max_length=254, required=False, allow_blank=True, default="")
    password = serializers.CharField(max_length=500, style={"input_type": "password"})

    def validate(self, attrs):
        for key in ("imap_host", "smtp_host"):
            if not re.fullmatch(r"[A-Za-z0-9.-]+", attrs[key]):
                raise serializers.ValidationError({key: ["Enter a server name like mail.example.com."]})
        return attrs


class ImapTestResultSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    imap = serializers.DictField()
    smtp = serializers.DictField()


class AccessEntrySerializer(serializers.Serializer):
    user = serializers.IntegerField()
    email = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    can_read = serializers.BooleanField(default=True)
    can_send = serializers.BooleanField(default=False)
    can_delete = serializers.BooleanField(default=False)
    can_manage = serializers.BooleanField(default=False)

    @staticmethod
    def from_row(row: MailboxAccess) -> dict:
        return {"user": row.user_id, "email": row.user.email, "display_name": row.user.display_name, "can_read": row.can_read, "can_send": row.can_send, "can_delete": row.can_delete, "can_manage": row.can_manage}


class PublicInviteSerializer(serializers.Serializer):
    state = serializers.CharField()
    company_name = serializers.CharField()
    mailbox_email = serializers.CharField()
    mailbox_name = serializers.CharField()
    notice = serializers.CharField()
    expires_at = serializers.DateTimeField()
    google_configured = serializers.BooleanField()


class OAuthStartSerializer(serializers.Serializer):
    token = serializers.CharField(required=False, allow_blank=True)
    mailbox = serializers.IntegerField(required=False)


class UrlSerializer(serializers.Serializer):
    url = serializers.CharField()


# --- Labels -----------------------------------------------------------------------------------------------


class LabelSerializer(serializers.ModelSerializer):
    label_id = serializers.CharField(source="provider_label_id", read_only=True)
    mailbox = serializers.IntegerField(source="mailbox_id", read_only=True)

    class Meta:
        model = Label
        fields = ["id", "label_id", "mailbox", "name", "type", "colour", "text_colour", "threads_total", "threads_unread"]


class LabelWriteSerializer(serializers.Serializer):
    mailbox = serializers.IntegerField(required=False)
    name = serializers.CharField(max_length=225)
    colour = serializers.CharField(max_length=7, required=False, allow_blank=True, default="")
    text_colour = serializers.CharField(max_length=7, required=False, allow_blank=True, default="")

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Enter a name.")
        if value.upper() in {"INBOX", "SENT", "SPAM", "TRASH", "DRAFT", "DRAFTS", "STARRED", "IMPORTANT", "UNREAD", "CHAT"}:
            raise serializers.ValidationError("This name is reserved. Choose another.")
        return value


# --- Threads & messages -----------------------------------------------------------------------------------


class MailboxRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.CharField()
    name = serializers.CharField()
    colour = serializers.CharField()
    office = serializers.CharField()


class LabelChipSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    colour = serializers.CharField(allow_blank=True)
    text_colour = serializers.CharField(allow_blank=True)


class ParticipantSerializer(serializers.Serializer):
    email = serializers.CharField()
    name = serializers.CharField(allow_blank=True)
    unread = serializers.BooleanField(required=False)
    is_me = serializers.BooleanField(required=False)


class AssignmentSerializer(serializers.Serializer):
    assignee = serializers.DictField()
    status = serializers.CharField()


class ThreadSummarySerializer(serializers.ModelSerializer):
    mailbox = serializers.SerializerMethodField()
    participants = ParticipantSerializer(many=True)
    labels = serializers.SerializerMethodField()
    snoozed_until = serializers.SerializerMethodField()
    assignment = serializers.SerializerMethodField()

    class Meta:
        model = Thread
        fields = [
            "id", "mailbox", "subject", "snippet", "participants", "last_message_at", "message_count", "has_attachments", "label_ids",
            "labels", "is_unread", "is_starred", "is_important", "is_muted", "snoozed_until", "assignment",
        ]

    @extend_schema_field(MailboxRefSerializer)
    def get_mailbox(self, obj):
        m = obj.mailbox
        return {"id": m.pk, "email": m.email, "name": m.name, "colour": m.colour, "office": m.office.name}

    @extend_schema_field(LabelChipSerializer(many=True))
    def get_labels(self, obj):
        labels = self.context.get("labels", {}).get(obj.mailbox_id, {})
        return [labels[label] for label in obj.label_ids if label in labels]

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_snoozed_until(self, obj):
        snooze = getattr(obj, "snooze", None)
        return snooze.until if snooze else None

    @extend_schema_field(AssignmentSerializer(allow_null=True))
    def get_assignment(self, obj):
        try:
            assignment = obj.assignment
        except Exception:  # noqa: BLE001 - RelatedObjectDoesNotExist
            return None
        return {"assignee": {"id": assignment.assignee_id, "display_name": assignment.assignee.display_name, "email": assignment.assignee.email}, "status": assignment.status}


class AttachmentSerializer(serializers.Serializer):
    id = serializers.CharField()
    filename = serializers.CharField()
    mime_type = serializers.CharField()
    size = serializers.IntegerField()
    inline = serializers.BooleanField()
    url = serializers.CharField()


class MessageSerializer(serializers.ModelSerializer):
    from_addr = AddressSerializer(allow_null=True)
    to = AddressSerializer(many=True)
    cc = AddressSerializer(many=True)
    bcc = AddressSerializer(many=True)
    reply_to = AddressSerializer(many=True)
    attachments = serializers.SerializerMethodField()
    body_html = serializers.SerializerMethodField()
    remote_images = serializers.SerializerMethodField()
    images_shown = serializers.SerializerMethodField()
    link_warnings = serializers.SerializerMethodField()
    is_unread = serializers.SerializerMethodField()
    can_unsubscribe = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id", "from_addr", "to", "cc", "bcc", "reply_to", "subject", "date", "snippet", "label_ids", "is_outgoing", "is_unread",
            "attachments", "body_html", "remote_images", "images_shown", "link_warnings", "can_unsubscribe", "rfc_message_id",
        ]

    def _allowed(self, obj) -> bool:
        from ..services.threads import images_allowed

        return images_allowed(obj, self.context.get("show_images", False), self.context.get("trusted", set()))

    @extend_schema_field(AttachmentSerializer(many=True))
    def get_attachments(self, obj):
        return [{**{k: a[k] for k in ("id", "filename", "mime_type", "size")}, "inline": a.get("inline", False), "url": f"/api/v1/mail/messages/{obj.pk}/attachments/{a['id']}/"} for a in obj.attachments if not a.get("inline")]

    def get_body_html(self, obj) -> str:
        from ..services.threads import body_for

        return body_for(obj, self._allowed(obj))

    def get_remote_images(self, obj) -> int:
        return int((obj.body_meta or {}).get("remote_images", 0))

    def get_images_shown(self, obj) -> bool:
        return self._allowed(obj)

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_link_warnings(self, obj):
        return (obj.body_meta or {}).get("link_warnings", [])

    def get_is_unread(self, obj) -> bool:
        return "UNREAD" in obj.label_ids

    def get_can_unsubscribe(self, obj) -> bool:
        return bool(obj.list_unsubscribe)


class ThreadDetailSerializer(ThreadSummarySerializer):
    messages = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    notes_count = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()

    class Meta(ThreadSummarySerializer.Meta):
        fields = [*ThreadSummarySerializer.Meta.fields, "messages", "permissions", "notes_count", "capabilities"]

    @extend_schema_field(MessageSerializer(many=True))
    def get_messages(self, obj):
        return MessageSerializer(self.context["messages"], many=True, context=self.context).data

    @extend_schema_field(MailboxPermissionsSerializer)
    def get_permissions(self, obj):
        from ..services.access import permissions_for

        return permissions_for(self.context["request"].user, obj.mailbox)

    def get_notes_count(self, obj) -> int:
        return obj.notes.count()

    @extend_schema_field(CapabilitiesSerializer)
    def get_capabilities(self, obj):
        return MailboxSerializer(context=self.context).get_capabilities(obj.mailbox)


class ThreadPageSerializer(serializers.Serializer):
    results = ThreadSummarySerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)
    total = serializers.IntegerField(allow_null=True)


class SelectionQuerySerializer(serializers.Serializer):
    mailbox = serializers.CharField()
    label = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField(required=False, allow_blank=True)
    q = serializers.CharField(required=False, allow_blank=True)
    unread = serializers.BooleanField(required=False, allow_null=True, default=None)
    starred = serializers.BooleanField(required=False, allow_null=True, default=None)
    has_attachment = serializers.BooleanField(required=False, allow_null=True, default=None)


class ActionRequestSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=[])
    thread_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list, max_length=5000)
    select_all = SelectionQuerySerializer(required=False, allow_null=True, default=None)
    label_ids = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    until = serializers.DateTimeField(required=False, allow_null=True, default=None)
    assignee = serializers.IntegerField(required=False, allow_null=True, default=None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from ..services.actions import ACTIONS

        self.fields["action"].choices = ACTIONS


class ActionResultSerializer(serializers.Serializer):
    threads = ThreadSummarySerializer(many=True)
    deleted_ids = serializers.ListField(child=serializers.IntegerField())
    undo_token = serializers.CharField(allow_null=True)


class UndoRequestSerializer(serializers.Serializer):
    undo_token = serializers.CharField()


# --- Compose ---------------------------------------------------------------------------------------------


class ComposeSerializer(serializers.Serializer):
    mailbox = serializers.IntegerField()
    send_as = serializers.EmailField(required=False, allow_blank=True)
    to = AddressSerializer(many=True, required=False, default=list)
    cc = AddressSerializer(many=True, required=False, default=list)
    bcc = AddressSerializer(many=True, required=False, default=list)
    subject = serializers.CharField(required=False, allow_blank=True, default="", max_length=900)
    html = serializers.CharField(required=False, allow_blank=True, default="")
    mode = serializers.ChoiceField(choices=["new", "reply", "reply_all", "forward"], default="new")
    in_reply_to_message = serializers.IntegerField(required=False, allow_null=True, default=None)
    attachment_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    forward_attachment_ids = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    draft_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    send_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    undo_seconds = serializers.ChoiceField(choices=[0, 5, 10, 20, 30], required=False, allow_null=True, default=None)

    def validate(self, attrs):
        for key in ("to", "cc", "bcc"):
            for item in attrs.get(key, []):
                serializers.EmailField().run_validation(item["email"])
        return attrs


class QueuedSerializer(serializers.ModelSerializer):
    mailbox = serializers.IntegerField(source="mailbox_id")
    subject = serializers.SerializerMethodField()
    to = serializers.SerializerMethodField()
    payload = serializers.SerializerMethodField()

    class Meta:
        model = ScheduledEmail
        fields = ["id", "mailbox", "kind", "send_at", "status", "error", "subject", "to", "payload", "created_at"]

    def get_subject(self, obj) -> str:
        return obj.payload.get("subject", "")

    @extend_schema_field(AddressSerializer(many=True))
    def get_to(self, obj):
        return obj.payload.get("to", [])

    @extend_schema_field(serializers.DictField())
    def get_payload(self, obj):
        return {k: obj.payload.get(k) for k in ("to", "cc", "bcc", "subject", "html", "mode", "in_reply_to_message", "attachment_ids", "draft_id")} | {"send_as": obj.payload.get("from", {}).get("email")}


class RescheduleSerializer(serializers.Serializer):
    send_at = serializers.DateTimeField()


class DraftSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    mailbox = serializers.IntegerField(source="mailbox_id")
    thread = serializers.IntegerField(source="thread_id", allow_null=True)
    to = AddressSerializer(many=True)
    cc = AddressSerializer(many=True)
    bcc = AddressSerializer(many=True)
    subject = serializers.CharField(allow_blank=True)
    body_html = serializers.CharField(allow_blank=True)
    snippet = serializers.CharField(allow_blank=True)
    mode = serializers.CharField()
    in_reply_to_message = serializers.IntegerField(source="in_reply_to_message_id", allow_null=True)
    attachment_ids = serializers.ListField(child=serializers.IntegerField())
    updated_at = serializers.DateTimeField()


class DraftWriteSerializer(ComposeSerializer):
    mailbox = serializers.IntegerField(required=False)


class UploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    mailbox = serializers.IntegerField()


class UploadedSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    filename = serializers.CharField()
    content_type = serializers.CharField()
    size = serializers.IntegerField()


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = ["id", "name", "subject", "body_html", "mailbox", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class NoteSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = ThreadNote
        fields = ["id", "body", "author", "created_at"]
        read_only_fields = ["id", "author", "created_at"]

    @extend_schema_field(serializers.DictField())
    def get_author(self, obj):
        return {"id": obj.author_id, "display_name": obj.author.display_name if obj.author else "Deleted user"}


class ContactSuggestionSerializer(serializers.Serializer):
    email = serializers.CharField()
    name = serializers.CharField(allow_blank=True)


class AssigneeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.CharField()
    display_name = serializers.CharField()


# --- Mailbox settings -------------------------------------------------------------------------------------


class SendAsSerializer(serializers.Serializer):
    email = serializers.CharField()
    display_name = serializers.CharField(allow_blank=True)
    is_default = serializers.BooleanField()
    is_primary = serializers.BooleanField()
    signature = serializers.CharField(allow_blank=True)


class SignatureWriteSerializer(serializers.Serializer):
    send_as = serializers.EmailField()
    signature = serializers.CharField(allow_blank=True, max_length=10000)


class VacationSerializer(serializers.Serializer):
    enable_auto_reply = serializers.BooleanField()
    response_subject = serializers.CharField(allow_blank=True, required=False, default="", allow_null=True)
    response_body_html = serializers.CharField(allow_blank=True, required=False, default="", allow_null=True)
    restrict_to_contacts = serializers.BooleanField(required=False, default=False, allow_null=True)
    restrict_to_domain = serializers.BooleanField(required=False, default=False, allow_null=True)
    start_time = serializers.DateTimeField(required=False, allow_null=True, default=None)
    end_time = serializers.DateTimeField(required=False, allow_null=True, default=None)


class FilterCriteriaSerializer(serializers.Serializer):
    from_ = serializers.CharField(required=False, allow_blank=True)
    to = serializers.CharField(required=False, allow_blank=True)
    subject = serializers.CharField(required=False, allow_blank=True)
    query = serializers.CharField(required=False, allow_blank=True)
    hasAttachment = serializers.BooleanField(required=False)

    def get_fields(self):
        fields = super().get_fields()
        fields["from"] = fields.pop("from_")
        return fields


class FilterActionSerializer(serializers.Serializer):
    addLabelIds = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    removeLabelIds = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    forward = serializers.EmailField(required=False, allow_blank=True)


class FilterSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    criteria = FilterCriteriaSerializer()
    action = FilterActionSerializer()


# --- Stats & integrations ---------------------------------------------------------------------------------


class StatsSerializer(serializers.Serializer):
    range_days = serializers.IntegerField()
    kpis = serializers.DictField()
    series = serializers.ListField(child=serializers.DictField())
    mailboxes = serializers.ListField(child=serializers.DictField())
    top_senders = serializers.ListField(child=serializers.DictField())
    unanswered = serializers.ListField(child=serializers.DictField())


class MailSettingsSerializer(serializers.Serializer):
    connect_notice = serializers.CharField(max_length=2000)
    google_configured = serializers.BooleanField(read_only=True)
    redirect_uri = serializers.CharField(read_only=True)
    scopes = serializers.ListField(child=serializers.CharField(), read_only=True)
    fake_provider_enabled = serializers.BooleanField(read_only=True)


class WorkspaceDomainSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    domain = serializers.CharField(read_only=True)
    client_id = serializers.CharField(read_only=True)
    service_account_email = serializers.CharField(read_only=True)
    scopes = serializers.CharField(read_only=True)
    last_test_at = serializers.DateTimeField(read_only=True, allow_null=True)
    last_test_ok = serializers.BooleanField(read_only=True)
    last_test_error = serializers.CharField(read_only=True, allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)


class WorkspaceDomainWriteSerializer(serializers.Serializer):
    domain = serializers.CharField(max_length=253)
    service_account_json = serializers.CharField(max_length=20000, style={"base_template": "textarea.html"})


class WorkspaceTestSerializer(serializers.Serializer):
    email = serializers.EmailField()
