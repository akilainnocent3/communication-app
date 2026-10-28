"""Admin-facing Calls serializers. Prefixed `Call…`/`Customer…` so drf-spectacular component names never collide with
SMS or Gmail ones."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from common.devicecrypto import decrypt_text
from modules.devices.services.phone import display_number

from ..models import CallAnnotation, CallbackTask, CallOutcome, CallRecord, CarrierTariff, OfficeHours, Result

RESULT_CHOICES = Result.values


class CallDeviceRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    office = serializers.CharField(source="office.name")
    colour = serializers.CharField(source="office.colour")


class CallSimRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    colour = serializers.CharField()


class CallOutcomeRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    colour = serializers.CharField()


class CallSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    device = CallDeviceRefSerializer()
    sim = serializers.SerializerMethodField()
    direction = serializers.CharField()
    result = serializers.CharField()
    number = serializers.CharField(source="number_e164")
    display_number = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    name_source = serializers.SerializerMethodField()
    customer_id = serializers.IntegerField(allow_null=True)
    presentation = serializers.CharField()
    started_at = serializers.DateTimeField()
    answered_at = serializers.DateTimeField(allow_null=True)
    ended_at = serializers.DateTimeField(allow_null=True)
    ring_seconds = serializers.IntegerField()
    talk_seconds = serializers.IntegerField()
    is_after_hours = serializers.BooleanField()
    is_conference = serializers.BooleanField()
    is_video = serializers.BooleanField()
    origin = serializers.CharField()
    returned_at = serializers.DateTimeField(allow_null=True)
    outcome = serializers.SerializerMethodField()
    deleted_on_device = serializers.SerializerMethodField()
    is_final = serializers.BooleanField()

    @extend_schema_field(CallSimRefSerializer(allow_null=True))
    def get_sim(self, obj):
        return {"id": obj.sim_line_id, "label": obj.sim_line.label, "colour": obj.sim_line.colour} if obj.sim_line_id else None

    def get_display_number(self, obj) -> str:
        return display_number(obj.number_e164) if obj.number_e164 else ""

    def get_name(self, obj) -> str:
        return obj.contact_name_on_phone or (obj.customer.display_name if obj.customer_id else "")

    def get_name_source(self, obj) -> str:
        """phone (saved in the phone's contacts), directory (company directory) or ""."""
        if obj.contact_name_on_phone:
            return "phone"
        return "directory" if obj.customer_id and obj.customer.display_name else ""

    @extend_schema_field(CallOutcomeRefSerializer(allow_null=True))
    def get_outcome(self, obj):
        annotations = getattr(obj, "prefetched_annotations", None)
        if annotations is None:
            annotations = list(obj.annotations.all())
        latest = next((a for a in reversed(annotations) if a.outcome_id), None)
        return {"id": latest.outcome_id, "name": latest.outcome.name, "colour": latest.outcome.colour} if latest else None

    def get_deleted_on_device(self, obj) -> bool:
        return obj.deleted_on_device_at is not None


class CallPageSerializer(serializers.Serializer):
    results = CallSummarySerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)


class CallEventSerializer(serializers.Serializer):
    kind = serializers.CharField()
    at = serializers.DateTimeField()
    data = serializers.DictField()


class CallAnnotationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    outcome = serializers.SerializerMethodField()
    note = serializers.SerializerMethodField()
    tags = serializers.ListField(child=serializers.CharField())
    author = serializers.SerializerMethodField()
    from_phone = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    @extend_schema_field(CallOutcomeRefSerializer(allow_null=True))
    def get_outcome(self, obj: CallAnnotation):
        return {"id": obj.outcome_id, "name": obj.outcome.name, "colour": obj.outcome.colour} if obj.outcome_id else None

    def get_note(self, obj) -> str:
        return decrypt_text(obj.encrypted_note)

    def get_author(self, obj) -> str:
        if obj.from_phone:
            return "On the phone"
        return obj.author.display_name if obj.author_id else ""


class CallAnnotationWriteSerializer(serializers.Serializer):
    outcome = serializers.IntegerField(required=False, allow_null=True, default=None)
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    tags = serializers.ListField(child=serializers.CharField(max_length=40), max_length=10, required=False, default=list)


class CallHistoryItemSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["call", "sms"])
    at = serializers.DateTimeField()
    direction = serializers.CharField()
    result = serializers.CharField(allow_blank=True)
    talk_seconds = serializers.IntegerField(allow_null=True)
    device = serializers.CharField()
    call_id = serializers.IntegerField(allow_null=True)
    conversation_id = serializers.IntegerField(allow_null=True)
    snippet = serializers.CharField(allow_blank=True)


class CallDetailSerializer(CallSummarySerializer):
    disconnect_cause_label = serializers.CharField()
    ended_by = serializers.CharField()
    network = serializers.CharField()
    conference_size = serializers.IntegerField()
    was_on_hold_seconds = serializers.IntegerField()
    returns_call_id = serializers.IntegerField(allow_null=True)
    returned_by_id = serializers.IntegerField(allow_null=True)
    callback_task_id = serializers.IntegerField(allow_null=True)
    events = CallEventSerializer(many=True)
    annotations = CallAnnotationSerializer(many=True)
    history = CallHistoryItemSerializer(many=True)
    permissions = serializers.DictField(child=serializers.BooleanField())
    outcome_required = serializers.BooleanField()


class CallbackSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    device = CallDeviceRefSerializer()
    number = serializers.CharField(source="number_e164")
    display_number = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    customer_id = serializers.IntegerField(allow_null=True)
    source_call_id = serializers.IntegerField(allow_null=True)
    call_id = serializers.IntegerField(allow_null=True)
    assigned_by = serializers.SerializerMethodField()
    assignee = serializers.SerializerMethodField()
    due_at = serializers.DateTimeField()
    priority = serializers.CharField()
    reason = serializers.SerializerMethodField()
    state = serializers.CharField()
    attempts = serializers.IntegerField()
    notified_at = serializers.DateTimeField(allow_null=True)
    dialed_at = serializers.DateTimeField(allow_null=True)
    done_at = serializers.DateTimeField(allow_null=True)
    snoozed_until = serializers.DateTimeField(allow_null=True)
    expires_at = serializers.DateTimeField()
    created_at = serializers.DateTimeField()

    def get_display_number(self, obj) -> str:
        return display_number(obj.number_e164)

    def get_name(self, obj: CallbackTask) -> str:
        return obj.customer.display_name if obj.customer_id else ""

    def get_assigned_by(self, obj) -> str:
        return obj.assigned_by.display_name if obj.assigned_by_id else ""

    def get_assignee(self, obj) -> str:
        return obj.assignee.display_name if obj.assignee_id else ""

    def get_reason(self, obj) -> str:
        return decrypt_text(obj.encrypted_reason)


class CallbackCreateSerializer(serializers.Serializer):
    device = serializers.UUIDField()
    number = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    call = serializers.IntegerField(required=False, allow_null=True, default=None)
    customer = serializers.IntegerField(required=False, allow_null=True, default=None)
    due_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    priority = serializers.ChoiceField(choices=[p for p, _ in CallbackTask.PRIORITIES], required=False, default="normal")
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class CallbackUpdateSerializer(serializers.Serializer):
    device = serializers.UUIDField(required=False)
    due_at = serializers.DateTimeField(required=False)
    priority = serializers.ChoiceField(choices=[p for p, _ in CallbackTask.PRIORITIES], required=False)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    state = serializers.ChoiceField(choices=["done"], required=False)


class CallbackBulkSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=200)
    action = serializers.ChoiceField(choices=["assign", "cancel", "done"])
    device = serializers.UUIDField(required=False)
    due_at = serializers.DateTimeField(required=False)


class CallOutcomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallOutcome
        fields = ["id", "name", "colour", "order", "is_active"]


class CarrierTariffSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarrierTariff
        fields = ["id", "carrier", "per_minute", "currency", "billing_increment_seconds"]


class OfficeHoursSerializer(serializers.Serializer):
    office = serializers.IntegerField()
    office_name = serializers.CharField(read_only=True)
    timezone = serializers.CharField(max_length=64)
    week = serializers.DictField(child=serializers.ListField(child=serializers.ListField(child=serializers.CharField(max_length=5))))
    holidays = serializers.ListField(child=serializers.CharField(max_length=10), max_length=200)
    configured = serializers.BooleanField(read_only=True)


class CallSettingsSerializer(serializers.Serializer):
    unreturned_hours = serializers.IntegerField(min_value=1, max_value=168)
    outcome_required_after_seconds = serializers.IntegerField(min_value=0, max_value=36000)
    post_call_card = serializers.BooleanField()
    auto_sms_enabled = serializers.BooleanField()
    auto_sms_template = serializers.CharField(max_length=300)
    auto_sms_after_hours_only = serializers.BooleanField()
    auto_sms_per_number_per_day = serializers.IntegerField(min_value=1, max_value=5)
    auto_sms_cooldown_hours = serializers.IntegerField(min_value=0, max_value=168)
    callback_expiry_hours = serializers.IntegerField(min_value=1, max_value=720)
    retention_days = serializers.IntegerField(min_value=0, max_value=3650, allow_null=True)
    effective_retention_days = serializers.IntegerField(read_only=True)


class CallDeviceSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    office = serializers.CharField(source="office.name")
    colour = serializers.CharField(source="office.colour")
    status = serializers.CharField()
    calls_enabled = serializers.SerializerMethodField()
    online = serializers.SerializerMethodField()
    last_seen_at = serializers.DateTimeField(allow_null=True)
    is_default_dialer = serializers.BooleanField()
    full_screen_intent_allowed = serializers.BooleanField(allow_null=True)
    call_state = serializers.CharField()
    attention = serializers.SerializerMethodField()
    holder = serializers.SerializerMethodField()
    calls_backfill = serializers.SerializerMethodField()

    def get_calls_enabled(self, obj) -> bool:
        return obj.has("calls")

    def get_online(self, obj) -> bool:
        from modules.devices.services.health import is_online

        return is_online(obj)

    def get_holder(self, obj) -> str:
        return obj.assigned_to.display_name if obj.assigned_to_id else ""

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_attention(self, obj):
        from modules.devices.services.health import ATTENTION_LABELS

        return [{"code": c, "label": ATTENTION_LABELS.get(c, c)} for c in obj.attention or []]

    def get_calls_backfill(self, obj) -> dict:
        return (obj.sync_progress or {}).get("calls") or {}


class CallDeviceAccessSerializer(serializers.Serializer):
    user = serializers.IntegerField()
    name = serializers.CharField(read_only=True)
    email = serializers.CharField(read_only=True)
    can_read = serializers.BooleanField(default=True)
    can_assign_callbacks = serializers.BooleanField(default=False)
    can_annotate = serializers.BooleanField(default=False)
    can_export = serializers.BooleanField(default=False)


class CustomerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    key = serializers.CharField()
    display_number = serializers.SerializerMethodField()
    display_name = serializers.CharField()
    organisation = serializers.CharField()
    tags = serializers.ListField(child=serializers.CharField())
    owner = serializers.SerializerMethodField()
    owner_id = serializers.IntegerField(allow_null=True)
    caller_id_all_phones = serializers.BooleanField()
    auto_sms_opt_out = serializers.BooleanField()
    first_seen_call = serializers.DateTimeField(allow_null=True)
    last_seen_call = serializers.DateTimeField(allow_null=True)
    first_seen_sms = serializers.DateTimeField(allow_null=True)
    last_seen_sms = serializers.DateTimeField(allow_null=True)

    def get_display_number(self, obj) -> str:
        return display_number(obj.key)

    def get_owner(self, obj) -> str:
        return obj.owner.display_name if obj.owner_id else ""


class CustomerPageSerializer(serializers.Serializer):
    results = CustomerSerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)


class CustomerDetailSerializer(CustomerSerializer):
    notes = serializers.CharField()
    can_edit = serializers.BooleanField()
    aliases = serializers.ListField(child=serializers.CharField())
    stats = serializers.DictField()


class CustomerWriteSerializer(serializers.Serializer):
    number = serializers.CharField(max_length=64, required=False)
    display_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    organisation = serializers.CharField(max_length=120, required=False, allow_blank=True)
    tags = serializers.ListField(child=serializers.CharField(max_length=40), max_length=20, required=False)
    notes = serializers.CharField(max_length=4000, required=False, allow_blank=True)
    owner = serializers.IntegerField(required=False, allow_null=True)
    caller_id_all_phones = serializers.BooleanField(required=False)
    auto_sms_opt_out = serializers.BooleanField(required=False)


class CustomerMergeSerializer(serializers.Serializer):
    target = serializers.IntegerField()
    sources = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=20)


class CallStatsSerializer(serializers.Serializer):
    range_days = serializers.IntegerField()
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    unreturned_hours = serializers.IntegerField()
    kpis = serializers.DictField()
    series = serializers.ListField(child=serializers.DictField())
    heatmap = serializers.ListField(child=serializers.ListField(child=serializers.IntegerField()))
    by_result = serializers.ListField(child=serializers.DictField())
    per_device = serializers.ListField(child=serializers.DictField())
    per_office = serializers.ListField(child=serializers.DictField())
    per_sim = serializers.ListField(child=serializers.DictField())
    staff = serializers.ListField(child=serializers.DictField())
    callers = serializers.DictField()
    top_callers = serializers.ListField(child=serializers.DictField())
    outcomes = serializers.ListField(child=serializers.DictField())
    unreturned_list = serializers.ListField(child=serializers.DictField())


class CallLiveSerializer(serializers.Serializer):
    server_time = serializers.DateTimeField()
    phones = serializers.ListField(child=serializers.DictField())
    totals = serializers.DictField()


class CallBadgesSerializer(serializers.Serializer):
    unreturned = serializers.IntegerField()
    open_callbacks = serializers.IntegerField()
    my_callbacks = serializers.IntegerField()
    attention = serializers.IntegerField()


class CallSimulatorActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["incoming", "missed", "tick"])


class CallEnableSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()


def office_hours_payload(office, row: OfficeHours | None) -> dict:
    from ..services.hours import DEFAULT_TZ, DEFAULT_WEEK

    return {"office": office.pk, "office_name": office.name, "timezone": row.timezone if row else DEFAULT_TZ,
            "week": row.week if row else DEFAULT_WEEK, "holidays": row.holidays if row else [], "configured": row is not None}


__all__ = ["CallRecord"]
