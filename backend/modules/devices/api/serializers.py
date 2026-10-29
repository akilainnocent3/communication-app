from rest_framework import serializers

from ..services.health import ATTENTION_LABELS, is_online


class SimSerializer(serializers.Serializer):
    subscription_id = serializers.IntegerField()
    slot = serializers.IntegerField(min_value=0, max_value=7, required=False, default=0)
    carrier = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    country_iso = serializers.CharField(max_length=2, required=False, allow_blank=True, default="")
    number = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    is_default = serializers.BooleanField(required=False, default=False)


class DeviceFactsSerializer(serializers.Serializer):
    manufacturer = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    model = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    android_version = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    sdk_int = serializers.IntegerField(min_value=0, max_value=100, required=False, default=0)


class EnrollInfoSerializer(serializers.Serializer):
    state = serializers.CharField()
    company_name = serializers.CharField()
    device_name = serializers.CharField()
    office = serializers.CharField()
    notice = serializers.CharField()
    platform = serializers.ChoiceField(choices=["sms", "calls"], help_text="The app this code is for: sms (OCM Messages) or calls (OCM Phone).")
    expires_at = serializers.DateTimeField()
    server_time = serializers.IntegerField()


class EnrollRequestSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=100)
    public_key = serializers.CharField(max_length=1024)
    signature = serializers.CharField(max_length=256)
    timestamp = serializers.IntegerField()
    nonce = serializers.CharField(max_length=64)
    attestation_chain = serializers.ListField(child=serializers.CharField(max_length=8192), max_length=8, required=False, default=list)
    integrity_token = serializers.CharField(max_length=8192, required=False, allow_blank=True, default="")
    app_version = serializers.CharField(max_length=32)
    device = DeviceFactsSerializer(required=False, default=dict)
    sims = SimSerializer(many=True, required=False, default=list, max_length=4)
    notice_accepted = serializers.BooleanField()
    notice_text = serializers.CharField(max_length=4000, required=False, allow_blank=True, default="")
    app = serializers.ChoiceField(choices=["sms", "calls"], required=False, default="sms",
                                  help_text="Which OCM app is enrolling: sms (OCM Messages) or calls (OCM Phone). Must match the code.")


class TokenResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    token_type = serializers.CharField()
    expires_in = serializers.IntegerField()


class EnrollResponseSerializer(TokenResponseSerializer):
    device_id = serializers.UUIDField()
    device_code = serializers.CharField()
    name = serializers.CharField()
    office = serializers.CharField()
    options = serializers.DictField()
    hardware_backed = serializers.BooleanField()


class TokenRequestSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=40)
    timestamp = serializers.IntegerField()
    nonce = serializers.CharField(max_length=64)
    signature = serializers.CharField(max_length=256)


class HeartbeatSerializer(serializers.Serializer):
    battery = serializers.IntegerField(min_value=0, max_value=100, required=False, allow_null=True, default=None)
    charging = serializers.BooleanField(required=False, default=False)
    network_type = serializers.ChoiceField(choices=["wifi", "cellular", "ethernet", "none", "other", ""], required=False, default="")
    signal = serializers.IntegerField(min_value=-1, max_value=4, required=False, allow_null=True, default=None)
    is_default_sms_app = serializers.BooleanField(required=False, default=False, help_text="OCM Messages: holds the SMS role. OCM Phone leaves it out.")
    is_default_dialer = serializers.BooleanField(required=False, default=False)
    full_screen_intent_allowed = serializers.BooleanField(required=False, allow_null=True)
    call_state = serializers.ChoiceField(choices=["idle", "ringing", "active", "held", ""], required=False, default="")
    permissions = serializers.DictField(child=serializers.BooleanField(), required=False, default=dict)
    battery_optimised = serializers.BooleanField(required=False, default=False)
    background_restricted = serializers.BooleanField(required=False, default=False)
    standby_bucket = serializers.IntegerField(min_value=0, max_value=100, required=False, allow_null=True, default=None)
    manufacturer = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    pending_outbox = serializers.IntegerField(min_value=0, max_value=10_000_000, required=False, default=0)
    app_version = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    android_version = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    last_sync_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    risk_signals = serializers.DictField(child=serializers.BooleanField(), required=False, default=dict)
    sims = SimSerializer(many=True, required=False, allow_null=True, default=None, max_length=4)

    def validate_permissions(self, value):
        if len(value) > 40:
            raise serializers.ValidationError("Too many entries.")
        return value


class HeartbeatResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    capabilities = serializers.DictField(child=serializers.BooleanField(), help_text="Phone platforms enabled for this phone (the app runs their onboarding).")
    attention = serializers.ListField(child=serializers.CharField())
    server_time = serializers.IntegerField()
    poll_seconds = serializers.IntegerField()


class ShortCodeRequestSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=16)


class ShortCodeResponseSerializer(serializers.Serializer):
    token = serializers.CharField()
    expires_in = serializers.IntegerField(help_text="Seconds the resolved token can be used to enroll.")


class PushTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=4096, allow_blank=True)


def device_status_payload(device, now=None) -> dict:
    """Admin-facing health summary (used by the SMS device views)."""
    return {
        "online": is_online(device, now),
        "last_seen_at": device.last_seen_at,
        "attention": [{"code": code, "label": ATTENTION_LABELS.get(code, code)} for code in device.attention or []],
    }
