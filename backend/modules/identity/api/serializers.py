from django.contrib.auth.models import Permission
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from ..models import Office, Role, User


class OfficeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Office
        fields = ["id", "name", "code", "colour", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_colour(self, value):
        import re

        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise serializers.ValidationError("Use a hex colour like #3758f9.")
        return value.lower()


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ["id", "slug", "name", "description", "rank", "is_system", "permissions", "user_count"]

    def get_permissions(self, role) -> list[str]:
        return sorted(f"{p.content_type.app_label}.{p.codename}" for p in role.group.permissions.select_related("content_type"))

    def get_user_count(self, role) -> int:
        return role.users.count()


class RoleWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80)
    description = serializers.CharField(max_length=255, allow_blank=True, required=False, default="")
    permissions = serializers.ListField(child=serializers.CharField(), required=False, default=list)

    def validate_permissions(self, codes):
        perms = []
        for code in codes:
            if "." not in code:
                raise serializers.ValidationError(f"Unknown permission '{code}'.")
            app_label, codename = code.split(".", 1)
            perm = Permission.objects.filter(content_type__app_label=app_label, codename=codename).first()
            if not perm:
                raise serializers.ValidationError(f"Unknown permission '{code}'.")
            perms.append(perm)
        return perms


class UserSummarySerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "display_name"]


class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    role = serializers.SerializerMethodField()
    office = OfficeSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "display_name", "role", "office", "is_active", "totp_enabled", "date_joined", "last_login"]

    def get_role(self, user) -> dict | None:
        if user.is_superuser:
            return {"slug": Role.SUPER_ADMIN, "name": "Super admin"}
        return {"slug": user.role.slug, "name": user.role.name} if user.role_id else None


class UserWriteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=150, allow_blank=True, required=False, default="")
    role = serializers.SlugRelatedField(slug_field="slug", queryset=Role.objects.all(), allow_null=True, required=False)
    office = serializers.PrimaryKeyRelatedField(queryset=Office.objects.all(), allow_null=True, required=False)
    is_active = serializers.BooleanField(required=False, default=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, style={"input_type": "password"})

    def validate_email(self, value):
        value = value.strip().lower()
        qs = User.objects.filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value):
        if value:
            validate_password(value)
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(style={"input_type": "password"})
    otp = serializers.CharField(required=False, allow_blank=True, max_length=10)


class PreferencesSerializer(serializers.Serializer):
    shortcuts = serializers.BooleanField(required=False)
    density = serializers.ChoiceField(choices=["comfortable", "compact"], required=False)
    reading_pane = serializers.ChoiceField(choices=["right", "none"], required=False)
    swipe_right = serializers.ChoiceField(choices=["archive", "trash", "read", "none"], required=False)
    swipe_left = serializers.ChoiceField(choices=["archive", "trash", "read", "none"], required=False)
    undo_send_seconds = serializers.ChoiceField(choices=[0, 5, 10, 20, 30], required=False)
    timezone = serializers.CharField(required=False, max_length=64)

    def validate_timezone(self, value):
        import zoneinfo

        if value not in zoneinfo.available_timezones():
            raise serializers.ValidationError("Unknown time zone.")
        return value


class TotpCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=10)
