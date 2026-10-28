import re

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from modules.devices.api.serializers import device_status_payload
from modules.devices.services.health import ATTENTION_LABELS
from modules.devices.services.phone import address_kind, display_number

from ..models import Contact, ConversationNote, Message, QuickReply, SensitiveRule
from ..services.actions import ACTIONS
from ..services.crypto import decrypt_text
from ..services.text import mask_sensitive

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


# --- Shared pieces ---------------------------------------------------------------------------------------------


class SmsOfficeRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    colour = serializers.CharField()


class UserRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    display_name = serializers.CharField()


class SimRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    slot = serializers.IntegerField()
    colour = serializers.CharField()


class DeviceRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    colour = serializers.CharField()


class AlertSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()


class DevicePermissionsSerializer(serializers.Serializer):
    read = serializers.BooleanField()
    send = serializers.BooleanField()
    manage = serializers.BooleanField()
    reveal = serializers.BooleanField()


def user_ref(user):
    return {"id": user.pk, "display_name": user.display_name} if user else None


def sim_ref(line):
    return {"id": line.pk, "label": line.label, "slot": line.slot, "colour": line.colour} if line else None


def device_ref(device):
    return {"id": device.pk, "code": device.code, "name": device.name, "colour": device.office.colour}


# --- Devices ---------------------------------------------------------------------------------------------------


class SimLineSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    subscription_id = serializers.IntegerField()
    slot = serializers.IntegerField()
    carrier = serializers.CharField()
    country_iso = serializers.CharField()
    number = serializers.CharField()
    display_name = serializers.CharField()
    label = serializers.CharField()
    colour = serializers.CharField()
    is_default = serializers.BooleanField()
    is_active = serializers.BooleanField()


class DeviceSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    office = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    status = serializers.CharField()
    online = serializers.SerializerMethodField()
    last_seen_at = serializers.DateTimeField(allow_null=True)
    attention = serializers.SerializerMethodField()
    manufacturer = serializers.CharField()
    model = serializers.CharField()
    android_version = serializers.CharField()
    app_version = serializers.CharField()
    battery = serializers.IntegerField(allow_null=True)
    charging = serializers.BooleanField()
    network_type = serializers.CharField()
    signal = serializers.IntegerField(allow_null=True)
    is_default_sms_app = serializers.BooleanField()
    battery_optimised = serializers.BooleanField()
    background_restricted = serializers.BooleanField()
    standby_bucket = serializers.IntegerField(allow_null=True)
    background_help = serializers.SerializerMethodField(help_text="What to change on this phone (by manufacturer) when it is restricted.")
    pending_outbox = serializers.IntegerField()
    last_sync_at = serializers.DateTimeField(allow_null=True)
    sync_progress = serializers.DictField()
    hardware_backed = serializers.BooleanField()
    is_simulated = serializers.BooleanField()
    sims = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    unread = serializers.SerializerMethodField()
    enrolled_at = serializers.DateTimeField()

    @extend_schema_field(SmsOfficeRefSerializer)
    def get_office(self, obj):
        return {"id": obj.office_id, "name": obj.office.name, "colour": obj.office.colour}

    @extend_schema_field(UserRefSerializer(allow_null=True))
    def get_assigned_to(self, obj):
        return user_ref(obj.assigned_to)

    def get_online(self, obj) -> bool:
        return device_status_payload(obj)["online"]

    @extend_schema_field(AlertSerializer(many=True))
    def get_attention(self, obj):
        return [{"code": code, "label": ATTENTION_LABELS.get(code, code)} for code in obj.attention or []]

    def get_background_help(self, obj) -> list[str]:
        from modules.devices.services.health import background_guidance

        return background_guidance(obj)

    @extend_schema_field(SimLineSerializer(many=True))
    def get_sims(self, obj):
        return SimLineSerializer([s for s in obj.sim_lines.all() if s.is_active], many=True).data

    @extend_schema_field(DevicePermissionsSerializer)
    def get_permissions(self, obj):
        from ..services.access import permissions_for

        cache = self.context.setdefault("_perms", {})
        if obj.pk not in cache:
            cache[obj.pk] = permissions_for(self.context["request"].user, obj)
        return cache[obj.pk]

    def get_unread(self, obj) -> int:
        return getattr(obj, "unread", None) or 0


class AttestationSerializer(serializers.Serializer):
    present = serializers.BooleanField()
    chain_valid = serializers.BooleanField()
    root_trusted = serializers.BooleanField()
    challenge_ok = serializers.BooleanField()
    security_level = serializers.CharField()
    hardware_backed = serializers.BooleanField()


class DeviceOptionsSerializer(serializers.Serializer):
    signature_enabled = serializers.BooleanField(required=False)
    signature = serializers.CharField(max_length=40, required=False, allow_blank=True)
    mark_read_on_open = serializers.BooleanField(required=False)
    backfill_days = serializers.IntegerField(min_value=0, max_value=730, required=False, allow_null=True)


class DeviceDetailSerializer(DeviceSerializer):
    sdk_int = serializers.IntegerField()
    options = serializers.DictField()
    permissions_granted = serializers.DictField(source="permissions")
    risk_signals = serializers.DictField()
    attestation = serializers.SerializerMethodField()
    notice_accepted_at = serializers.DateTimeField(allow_null=True)
    notice_text = serializers.CharField()
    suspended_at = serializers.DateTimeField(allow_null=True)
    revoked_at = serializers.DateTimeField(allow_null=True)
    enrolled_by = serializers.SerializerMethodField()
    push_enabled = serializers.SerializerMethodField()
    capabilities = serializers.DictField(child=serializers.BooleanField())
    is_default_dialer = serializers.BooleanField()

    @extend_schema_field(AttestationSerializer)
    def get_attestation(self, obj):
        data = obj.attestation or {}
        return {key: data.get(key, False) if key != "security_level" else data.get(key, "software") for key in AttestationSerializer().fields}

    @extend_schema_field(UserRefSerializer(allow_null=True))
    def get_enrolled_by(self, obj):
        return user_ref(obj.enrolled_by)

    def get_push_enabled(self, obj) -> bool:
        return bool(obj.push_token)


class DeviceUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, required=False)
    office = serializers.IntegerField(required=False)
    assigned_to = serializers.IntegerField(required=False, allow_null=True)
    options = DeviceOptionsSerializer(required=False)


class DeviceStatusChangeSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    confirm_code = serializers.CharField(max_length=16, required=False, allow_blank=True, default="")


class SimUpdateSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=60, required=False, allow_blank=True)
    colour = serializers.CharField(max_length=7, required=False)

    def validate_colour(self, value):
        if not HEX.match(value):
            raise serializers.ValidationError("Use a hex colour like #10b981.")
        return value.lower()


class HeartbeatHistorySerializer(serializers.Serializer):
    created_at = serializers.DateTimeField()
    battery = serializers.IntegerField(allow_null=True)
    charging = serializers.BooleanField()
    network_type = serializers.CharField()
    signal = serializers.IntegerField(allow_null=True)
    is_default_sms_app = serializers.BooleanField()
    pending_outbox = serializers.IntegerField()
    app_version = serializers.CharField()


class DeviceAccessEntrySerializer(serializers.Serializer):
    user = serializers.IntegerField()
    email = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    can_read = serializers.BooleanField(default=True)
    can_send = serializers.BooleanField(default=False)
    can_manage = serializers.BooleanField(default=False)
    can_reveal_sensitive = serializers.BooleanField(default=False)

    @staticmethod
    def from_row(row) -> dict:
        return {
            "user": row.user_id, "email": row.user.email, "display_name": row.user.display_name, "can_read": row.can_read,
            "can_send": row.can_send, "can_manage": row.can_manage, "can_reveal_sensitive": row.can_reveal_sensitive,
        }


class SimulatorActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["online", "offline", "tick", "inbound"])


class EnrollmentCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    office = serializers.IntegerField()
    assigned_to = serializers.IntegerField(required=False, allow_null=True, default=None)
    backfill_days = serializers.IntegerField(min_value=0, max_value=730, required=False, allow_null=True, default=None)
    signature_enabled = serializers.BooleanField(required=False, default=False)
    signature = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    mark_read_on_open = serializers.BooleanField(required=False, default=True)
    platforms = serializers.ListField(child=serializers.ChoiceField(choices=["sms", "calls"]), required=False, default=list, max_length=2,
                                      help_text='Phone platforms to enroll for; default ["sms"]. "calls" needs calls.manage_settings.')


class EnrollmentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    office = serializers.SerializerMethodField()
    state = serializers.CharField()
    expires_at = serializers.DateTimeField()
    used_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    created_by = serializers.SerializerMethodField()
    device = serializers.SerializerMethodField()
    failed_attempts = serializers.IntegerField()
    last_failure = serializers.CharField()
    platforms = serializers.ListField(child=serializers.CharField())
    short_code_expires_at = serializers.DateTimeField(allow_null=True)
    short_code_used = serializers.SerializerMethodField()

    @extend_schema_field(SmsOfficeRefSerializer)
    def get_office(self, obj):
        return {"id": obj.office_id, "name": obj.office.name, "colour": obj.office.colour}

    def get_short_code_used(self, obj) -> bool:
        return obj.short_code_used_at is not None

    def get_created_by(self, obj) -> str | None:
        return obj.created_by.email if obj.created_by_id and obj.created_by else None

    @extend_schema_field(DeviceRefSerializer(allow_null=True))
    def get_device(self, obj):
        return device_ref(obj.device) if obj.device_id else None


class EnrollmentCreatedSerializer(EnrollmentSerializer):
    code = serializers.CharField()
    uri = serializers.CharField()
    qr_svg = serializers.CharField()
    short_code = serializers.CharField(help_text="XXXX-XXXX, single use, valid until short_code_expires_at.")


class EnrollmentShortCodeSerializer(serializers.Serializer):
    short_code = serializers.CharField()
    short_code_expires_at = serializers.DateTimeField()


# --- Conversations ---------------------------------------------------------------------------------------------


class SmsParticipantSerializer(serializers.Serializer):
    address = serializers.CharField()
    display = serializers.CharField()
    name = serializers.CharField()
    kind = serializers.CharField()
    is_blocked = serializers.BooleanField()


def contact_map(conversations) -> dict:
    devices = {c.device_id for c in conversations}
    addresses = {a for c in conversations for a in c.addresses}
    return {(c.device_id, c.address): c for c in Contact.objects.filter(device_id__in=devices, address__in=addresses)}


class ConversationSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    device = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    is_group = serializers.BooleanField()
    snippet = serializers.SerializerMethodField()
    snippet_sensitive = serializers.BooleanField()
    last_message_at = serializers.DateTimeField()
    last_direction = serializers.CharField()
    last_status = serializers.CharField()
    unread_count = serializers.IntegerField()
    message_count = serializers.IntegerField()
    is_pinned = serializers.BooleanField()
    is_archived = serializers.BooleanField()
    is_muted = serializers.BooleanField()
    is_spam = serializers.BooleanField()
    is_starred = serializers.BooleanField()
    state = serializers.CharField()
    assigned_to = serializers.SerializerMethodField()
    sim = serializers.SerializerMethodField()
    has_mms = serializers.BooleanField()
    awaiting_since = serializers.DateTimeField(allow_null=True)
    deleted_on_device_at = serializers.DateTimeField(allow_null=True)

    def _contacts(self):
        return self.context.get("contacts", {})

    @extend_schema_field(DeviceRefSerializer)
    def get_device(self, obj):
        return device_ref(obj.device)

    @extend_schema_field(SmsParticipantSerializer(many=True))
    def get_participants(self, obj):
        contacts = self._contacts()
        result = []
        for address in obj.addresses:
            contact = contacts.get((obj.device_id, address))
            result.append({"address": address, "display": display_number(address), "name": contact.display_name if contact else "", "kind": address_kind(address), "is_blocked": bool(contact and contact.is_blocked)})
        return result

    def get_title(self, obj) -> str:
        contacts = self._contacts()
        names = []
        for address in obj.addresses[:4]:
            contact = contacts.get((obj.device_id, address))
            names.append(contact.display_name if contact and contact.display_name else display_number(address))
        title = ", ".join(names)
        return title + (f" +{len(obj.addresses) - 4}" if len(obj.addresses) > 4 else "")

    def get_snippet(self, obj) -> str:
        return decrypt_text(obj.encrypted_snippet)

    @extend_schema_field(UserRefSerializer(allow_null=True))
    def get_assigned_to(self, obj):
        return user_ref(obj.assigned_to)

    @extend_schema_field(SimRefSerializer(allow_null=True))
    def get_sim(self, obj):
        return sim_ref(obj.sim_line)


class ConversationPageSerializer(serializers.Serializer):
    results = ConversationSummarySerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)
    total = serializers.IntegerField(allow_null=True)


class ConversationStatsSerializer(serializers.Serializer):
    first_contact_at = serializers.DateTimeField(allow_null=True)
    inbound = serializers.IntegerField()
    outbound = serializers.IntegerField()
    avg_response_minutes = serializers.IntegerField(allow_null=True)


class ConversationDetailSerializer(ConversationSummarySerializer):
    thread_id = serializers.IntegerField(allow_null=True)
    permissions = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()
    device_status = serializers.SerializerMethodField()

    @extend_schema_field(DevicePermissionsSerializer)
    def get_permissions(self, obj):
        from ..services.access import permissions_for

        return permissions_for(self.context["request"].user, obj.device)

    @extend_schema_field(ConversationStatsSerializer)
    def get_stats(self, obj):
        return self.context.get("stats", {})

    @extend_schema_field(serializers.DictField())
    def get_device_status(self, obj):
        payload = device_status_payload(obj.device)
        return {"status": obj.device.status, "online": payload["online"], "last_seen_at": payload["last_seen_at"], "is_default_sms_app": obj.device.is_default_sms_app or obj.device.is_simulated}


class PartSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    seq = serializers.IntegerField()
    content_type = serializers.CharField()
    filename = serializers.CharField()
    size = serializers.IntegerField()
    available = serializers.BooleanField()


class StatusEntrySerializer(serializers.Serializer):
    status = serializers.CharField()
    at = serializers.DateTimeField()


class SmsMessageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    conversation = serializers.IntegerField(source="conversation_id")
    kind = serializers.CharField()
    direction = serializers.CharField()
    origin = serializers.CharField()
    address = serializers.CharField()
    body = serializers.SerializerMethodField()
    is_masked = serializers.SerializerMethodField()
    is_sensitive = serializers.BooleanField()
    sensitive_kind = serializers.CharField()
    segments = serializers.IntegerField()
    encoding = serializers.CharField()
    subject = serializers.CharField()
    at = serializers.DateTimeField(source="provider_date")
    status = serializers.CharField()
    status_label = serializers.CharField(source="get_status_display")
    status_history = StatusEntrySerializer(many=True)
    sent_by = serializers.SerializerMethodField()
    sim = serializers.SerializerMethodField()
    error_code = serializers.IntegerField(allow_null=True)
    error_detail = serializers.CharField()
    is_read = serializers.BooleanField()
    is_starred = serializers.BooleanField()
    deleted_on_device_at = serializers.DateTimeField(allow_null=True)
    send_at = serializers.DateTimeField(allow_null=True)
    is_scheduled = serializers.BooleanField()
    sent_at = serializers.DateTimeField(allow_null=True)
    delivered_at = serializers.DateTimeField(allow_null=True)
    client_uuid = serializers.UUIDField(allow_null=True)
    retry_of = serializers.IntegerField(source="retry_of_id", allow_null=True)
    parts = serializers.SerializerMethodField()

    def _revealed(self, obj) -> bool:
        return obj.pk in self.context.get("revealed", set())

    def get_body(self, obj) -> str:
        body = decrypt_text(obj.encrypted_body)
        return mask_sensitive(body) if obj.is_sensitive and not self._revealed(obj) else body

    def get_is_masked(self, obj) -> bool:
        return obj.is_sensitive and not self._revealed(obj)

    @extend_schema_field(UserRefSerializer(allow_null=True))
    def get_sent_by(self, obj):
        return user_ref(obj.sent_by)

    @extend_schema_field(SimRefSerializer(allow_null=True))
    def get_sim(self, obj):
        return sim_ref(obj.sim_line)

    @extend_schema_field(PartSerializer(many=True))
    def get_parts(self, obj):
        if obj.kind != Message.MMS:
            return []
        return [{"id": p.pk, "seq": p.seq, "content_type": p.content_type or p.declared_type, "filename": p.filename, "size": p.size, "available": bool(p.storage_name)} for p in obj.parts.all()]


class SmsMessagePageSerializer(serializers.Serializer):
    results = SmsMessageSerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)


class OutboxItemSerializer(SmsMessageSerializer):
    device = serializers.SerializerMethodField()
    conversation_title = serializers.SerializerMethodField()

    @extend_schema_field(DeviceRefSerializer)
    def get_device(self, obj):
        return device_ref(obj.device)

    def get_conversation_title(self, obj) -> str:
        names = self.context.get("names", {})
        return ", ".join(names.get((obj.device_id, a)) or display_number(a) for a in obj.conversation.addresses[:3])


class SmsActionRequestSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=sorted(ACTIONS))
    conversation_ids = serializers.ListField(child=serializers.IntegerField(), max_length=500)
    assignee = serializers.IntegerField(required=False, allow_null=True, default=None)


class SmsActionResultSerializer(serializers.Serializer):
    conversations = ConversationSummarySerializer(many=True)


class SmsNoteSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = ConversationNote
        fields = ["id", "body", "author", "created_at"]
        read_only_fields = ["id", "author", "created_at"]

    @extend_schema_field(UserRefSerializer(allow_null=True))
    def get_author(self, obj):
        return user_ref(obj.author)


class RevealSerializer(serializers.Serializer):
    body = serializers.CharField()


class StarSerializer(serializers.Serializer):
    starred = serializers.BooleanField()


# --- Compose ---------------------------------------------------------------------------------------------------


class SmsComposeSerializer(serializers.Serializer):
    device = serializers.UUIDField()
    conversation = serializers.IntegerField(required=False, allow_null=True, default=None)
    to = serializers.ListField(child=serializers.CharField(max_length=40), required=False, default=list, max_length=20)
    body = serializers.CharField(max_length=5000, trim_whitespace=False)
    sim_line = serializers.IntegerField(required=False, allow_null=True, default=None)
    send_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    undo_seconds = serializers.IntegerField(min_value=0, max_value=30, required=False, allow_null=True, default=None)
    client_uuid = serializers.UUIDField(required=False, allow_null=True, default=None)


class SmsComposeResultSerializer(serializers.Serializer):
    message = SmsMessageSerializer()
    conversation = serializers.IntegerField()


class SegmentInfoSerializer(serializers.Serializer):
    encoding = serializers.CharField()
    units = serializers.IntegerField()
    segments = serializers.IntegerField()
    per_segment = serializers.IntegerField()
    remaining = serializers.IntegerField()


# --- Contacts, quick replies, rules, settings -------------------------------------------------------------------


class ContactRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    device = DeviceRefSerializer()
    address = serializers.CharField()
    display = serializers.CharField()
    name = serializers.CharField()
    kind = serializers.CharField()
    is_blocked = serializers.BooleanField()
    messages = serializers.IntegerField()
    last_contact_at = serializers.DateTimeField(allow_null=True)
    conversation = serializers.IntegerField(allow_null=True)


class ContactPageSerializer(serializers.Serializer):
    results = ContactRowSerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)


class BlockRequestSerializer(serializers.Serializer):
    device = serializers.UUIDField()
    address = serializers.CharField(max_length=40)


class QuickReplySerializer(serializers.ModelSerializer):
    device = serializers.UUIDField(source="device_id", required=False, allow_null=True)

    class Meta:
        model = QuickReply
        fields = ["id", "title", "body", "device", "updated_at"]
        read_only_fields = ["id", "updated_at"]


class SensitiveRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensitiveRule
        fields = ["id", "name", "kind", "sender_pattern", "body_pattern", "is_enabled", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        import re as regex

        for key in ("sender_pattern", "body_pattern"):
            pattern = attrs.get(key) or ""
            if pattern:
                try:
                    regex.compile(pattern)
                except regex.error as exc:
                    raise serializers.ValidationError({key: f"Not a valid pattern: {exc}"}) from None
        if not (attrs.get("sender_pattern") or attrs.get("body_pattern") or (self.instance and (self.instance.sender_pattern or self.instance.body_pattern))):
            raise serializers.ValidationError("Set a sender or text pattern.")
        return attrs


class SmsSettingsSerializer(serializers.Serializer):
    monitoring_notice = serializers.CharField(max_length=2000)
    default_signature = serializers.CharField(max_length=40, allow_blank=True)
    retention_days = serializers.IntegerField(read_only=True)
    mirror_device_deletes = serializers.BooleanField(read_only=True)
    outbound_ttl_hours = serializers.IntegerField(read_only=True)
    daily_cap = serializers.IntegerField(read_only=True)
    allow_short_codes = serializers.BooleanField(read_only=True)
    push_configured = serializers.BooleanField(read_only=True)
    simulator_enabled = serializers.BooleanField(read_only=True)


class SmsAssigneeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.CharField()
    display_name = serializers.CharField()

