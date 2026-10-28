import io

import pyotp
import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.db.models import Q
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.auth import enforce_csrf
from common.crypto import decrypt_json, encrypt_json
from common.errors import ApiError
from common.http import ClientIpScopedThrottle
from common.permissions import HasPerm
from modules.audit.services import record
from modules.platforms.registry import registry
from modules.platforms.services import platforms_for

from ..models import Office, Role, User, default_preferences
from ..services import assign_role, clear_login_failures, login_locked, note_login_failure, permission_codes
from .serializers import (
    LoginSerializer,
    OfficeSerializer,
    PreferencesSerializer,
    RoleSerializer,
    RoleWriteSerializer,
    TotpCodeSerializer,
    UserSerializer,
    UserWriteSerializer,
)

MeSerializer = inline_serializer(
    "Me",
    {
        "user": inline_serializer(
            "MeUser",
            {
                "id": serializers.IntegerField(),
                "email": serializers.EmailField(),
                "full_name": serializers.CharField(),
                "display_name": serializers.CharField(),
                "timezone": serializers.CharField(),
                "preferences": serializers.DictField(),
                "totp_enabled": serializers.BooleanField(),
            },
        ),
        "role": inline_serializer("MeRole", {"slug": serializers.CharField(), "name": serializers.CharField()}, allow_null=True),
        "permissions": serializers.ListField(child=serializers.CharField()),
        "platforms": serializers.ListField(child=serializers.DictField()),
        "platform_data": serializers.DictField(),
        "company_name": serializers.CharField(),
    },
)


def me_payload(user: User) -> dict:
    preferences = {**default_preferences(), **(user.preferences or {})}
    platform_data = {}
    for spec in registry.all():
        if spec.session_data and user.has_perm(spec.permission):
            platform_data[spec.key] = spec.session_data(user)
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "display_name": user.display_name,
            "timezone": user.timezone,
            "preferences": preferences,
            "totp_enabled": user.totp_enabled,
        },
        "role": UserSerializer().get_role(user),
        "permissions": permission_codes(user),
        "platforms": platforms_for(user),
        "platform_data": platform_data,
        "company_name": settings.COMPANY_NAME,
    }


class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @method_decorator(ensure_csrf_cookie)
    @extend_schema(responses=inline_serializer("Csrf", {"csrf_token": serializers.CharField()}), operation_id="auth_csrf")
    def get(self, request):
        return Response({"csrf_token": get_token(request)})


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ClientIpScopedThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses=MeSerializer, operation_id="auth_login")
    def post(self, request):
        enforce_csrf(request)  # login CSRF: a third-party page must not sign the browser into another account
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        email = data.validated_data["email"].strip().lower()
        if login_locked(email):
            raise ApiError("login_locked", "Too many failed sign-in attempts. Try again in 15 minutes.", status.HTTP_429_TOO_MANY_REQUESTS)
        user = authenticate(request, email=email, password=data.validated_data["password"])
        if user is None:
            note_login_failure(email)
            record("auth.login_failed", request=request, metadata={"email": email})
            raise ApiError("invalid_credentials", "The email or password is not correct.", status.HTTP_400_BAD_REQUEST)
        if user.totp_enabled:
            code = (data.validated_data.get("otp") or "").strip()
            if not code:
                raise ApiError("otp_required", "Enter the 6-digit code from your authenticator app.", status.HTTP_400_BAD_REQUEST)
            secret = decrypt_json(user.totp_secret).get("secret", "")
            if not pyotp.TOTP(secret).verify(code, valid_window=1):
                note_login_failure(email)
                raise ApiError("otp_invalid", "That code is not correct. Try the newest code.", status.HTTP_400_BAD_REQUEST)
        clear_login_failures(email)
        login(request, user)
        record("auth.login", request=request, actor=user)
        return Response(me_payload(user))


class LogoutView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={204: None}, operation_id="auth_logout")
    def post(self, request):
        if request.user.is_authenticated:
            record("auth.logout", request=request)
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(responses=MeSerializer, operation_id="auth_me")
    def get(self, request):
        return Response(me_payload(request.user))


class PreferencesView(APIView):
    @extend_schema(request=PreferencesSerializer, responses=MeSerializer, operation_id="auth_preferences")
    def patch(self, request):
        data = PreferencesSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        user = request.user
        if "timezone" in values:
            user.timezone = values.pop("timezone")
        user.preferences = {**default_preferences(), **(user.preferences or {}), **values}
        user.save(update_fields=["preferences", "timezone"])
        return Response(me_payload(user))


def _qr_svg(text: str) -> str:
    image = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue().decode()


class TotpSetupView(APIView):
    """Start TOTP enrolment: returns a fresh secret and QR; it is enabled only after /totp/enable/ verifies a code."""

    @extend_schema(
        request=None,
        responses=inline_serializer("TotpSetup", {"secret": serializers.CharField(), "otpauth_uri": serializers.CharField(), "qr_svg": serializers.CharField()}),
        operation_id="auth_totp_setup",
    )
    def post(self, request):
        user = request.user
        if user.totp_enabled:
            raise ApiError("totp_enabled", "Two-step sign-in is already on.")
        secret = pyotp.random_base32()
        user.totp_secret = encrypt_json({"secret": secret})
        user.save(update_fields=["totp_secret"])
        uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="OCM")
        return Response({"secret": secret, "otpauth_uri": uri, "qr_svg": _qr_svg(uri)})


class TotpEnableView(APIView):
    @extend_schema(request=TotpCodeSerializer, responses=MeSerializer, operation_id="auth_totp_enable")
    def post(self, request):
        data = TotpCodeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = request.user
        secret = decrypt_json(user.totp_secret).get("secret") if user.totp_secret else None
        if not secret or not pyotp.TOTP(secret).verify(data.validated_data["code"], valid_window=1):
            raise ApiError("otp_invalid", "That code is not correct. Try the newest code.")
        user.totp_enabled = True
        user.save(update_fields=["totp_enabled"])
        record("auth.totp_enabled", request=request)
        return Response(me_payload(user))


class TotpDisableView(APIView):
    @extend_schema(request=TotpCodeSerializer, responses=MeSerializer, operation_id="auth_totp_disable")
    def post(self, request):
        data = TotpCodeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = request.user
        secret = decrypt_json(user.totp_secret).get("secret") if user.totp_secret else None
        if not user.totp_enabled or not secret or not pyotp.TOTP(secret).verify(data.validated_data["code"], valid_window=1):
            raise ApiError("otp_invalid", "That code is not correct. Try the newest code.")
        user.totp_enabled = False
        user.totp_secret = ""
        user.save(update_fields=["totp_enabled", "totp_secret"])
        record("auth.totp_disabled", request=request)
        return Response(me_payload(user))


# --- Settings: users, roles, offices -------------------------------------------------------------------

ManageUsers = HasPerm.of("identity.manage_users")


class UserListView(APIView):
    permission_classes = [IsAuthenticated, ManageUsers]

    @extend_schema(parameters=[OpenApiParameter("q", str)], responses=UserSerializer(many=True), operation_id="settings_users_list")
    def get(self, request):
        users = User.objects.select_related("role", "office").order_by("full_name", "email")
        q = request.query_params.get("q", "").strip()
        if q:
            users = users.filter(Q(email__icontains=q) | Q(full_name__icontains=q))
        return Response(UserSerializer(users[:500], many=True).data)

    @extend_schema(request=UserWriteSerializer, responses=UserSerializer, operation_id="settings_users_create")
    def post(self, request):
        data = UserWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        role = values.get("role")
        _guard_role_change(request.user, role)
        if not values.get("password"):
            raise ApiError("validation_error", "Set a password for the new user.", errors={"password": ["Required."]})
        with transaction.atomic():
            user = User.objects.create_user(
                email=values["email"], password=values["password"], full_name=values.get("full_name", ""),
                office=values.get("office"), is_active=values.get("is_active", True),
            )
            assign_role(user, role)
        record("users.create", request=request, target_type="user", target_id=user.pk, metadata={"email": user.email, "role": role.slug if role else None})
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


def _guard_role_change(actor: User, role: Role | None):
    if role and role.slug == Role.SUPER_ADMIN and not actor.is_superuser:
        raise ApiError("permission_denied", "Only a super admin can make someone a super admin.", status.HTTP_403_FORBIDDEN)


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated, ManageUsers]

    def _get(self, pk):
        user = User.objects.select_related("role", "office").filter(pk=pk).first()
        if not user:
            raise ApiError("not_found", "This user was not found.", status.HTTP_404_NOT_FOUND)
        return user

    @extend_schema(request=UserWriteSerializer, responses=UserSerializer, operation_id="settings_users_update")
    def patch(self, request, pk):
        user = self._get(pk)
        if user.is_superuser and not request.user.is_superuser:
            raise ApiError("permission_denied", "Only a super admin can change a super admin.", status.HTTP_403_FORBIDDEN)
        data = UserWriteSerializer(user, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        changes = {}
        with transaction.atomic():
            for field in ("email", "full_name", "office", "is_active"):
                if field in values and getattr(user, field) != values[field]:
                    changes[field] = str(values[field]) if field == "office" else values[field]
                    setattr(user, field, values[field])
            if user.pk == request.user.pk and values.get("is_active") is False:
                raise ApiError("validation_error", "You cannot deactivate your own account.")
            if values.get("password"):
                user.set_password(values["password"])
                changes["password"] = "changed"
            user.save()
            if "role" in values:
                role = values["role"]
                _guard_role_change(request.user, role)
                if user.pk == request.user.pk and user.is_superuser and (not role or role.slug != Role.SUPER_ADMIN):
                    raise ApiError("validation_error", "You cannot remove your own super admin role.")
                if user.role_slug != (role.slug if role else ""):
                    changes["role"] = role.slug if role else None
                assign_role(user, role)
        if changes:
            record("users.update", request=request, target_type="user", target_id=user.pk, metadata={"email": user.email, "changes": changes})
        return Response(UserSerializer(user).data)


class RoleListView(APIView):
    permission_classes = [IsAuthenticated, ManageUsers]

    @extend_schema(responses=RoleSerializer(many=True), operation_id="settings_roles_list")
    def get(self, request):
        return Response(RoleSerializer(Role.objects.select_related("group"), many=True).data)

    @extend_schema(request=RoleWriteSerializer, responses=RoleSerializer, operation_id="settings_roles_create")
    def post(self, request):
        from django.contrib.auth.models import Group
        from django.utils.text import slugify

        data = RoleWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        slug = slugify(data.validated_data["name"])[:40] or "role"
        if Role.objects.filter(slug=slug).exists():
            raise ApiError("validation_error", "A role with this name already exists.", errors={"name": ["Already exists."]})
        with transaction.atomic():
            group = Group.objects.create(name=f"role:{slug}")
            group.permissions.set(data.validated_data["permissions"])
            role = Role.objects.create(slug=slug, name=data.validated_data["name"], description=data.validated_data["description"], rank=50, group=group)
        record("roles.create", request=request, target_type="role", target_id=role.pk, metadata={"slug": slug})
        return Response(RoleSerializer(role).data, status=status.HTTP_201_CREATED)


class RoleDetailView(APIView):
    permission_classes = [IsAuthenticated, ManageUsers]

    @extend_schema(request=RoleWriteSerializer, responses=RoleSerializer, operation_id="settings_roles_update")
    def patch(self, request, pk):
        role = Role.objects.filter(pk=pk).first()
        if not role:
            raise ApiError("not_found", "This role was not found.", status.HTTP_404_NOT_FOUND)
        if role.slug == Role.SUPER_ADMIN:
            raise ApiError("validation_error", "The super admin role always has every permission.")
        data = RoleWriteSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        if "name" in data.validated_data:
            role.name = data.validated_data["name"]
        if "description" in data.validated_data:
            role.description = data.validated_data["description"]
        role.save()
        if "permissions" in request.data:
            role.group.permissions.set(data.validated_data["permissions"])
        record("roles.update", request=request, target_type="role", target_id=role.pk, metadata={"slug": role.slug, "permissions": request.data.get("permissions")})
        return Response(RoleSerializer(role).data)

    @extend_schema(responses={204: None}, operation_id="settings_roles_delete")
    def delete(self, request, pk):
        role = Role.objects.filter(pk=pk).first()
        if not role:
            raise ApiError("not_found", "This role was not found.", status.HTTP_404_NOT_FOUND)
        if role.is_system:
            raise ApiError("validation_error", "Built-in roles cannot be deleted.")
        if role.users.exists():
            raise ApiError("validation_error", "Move the users in this role to another role first.")
        group = role.group
        role.delete()
        group.delete()
        record("roles.delete", request=request, target_type="role", target_id=pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PermissionCatalogView(APIView):
    """Permissions an admin can grant to custom roles (only this product's, not Django internals)."""

    permission_classes = [IsAuthenticated, ManageUsers]

    @extend_schema(responses=inline_serializer("PermissionItem", {"code": serializers.CharField(), "name": serializers.CharField()}, many=True), operation_id="settings_permissions_list")
    def get(self, request):
        from django.contrib.auth.models import Permission

        from modules.platforms.registry import registry

        # Every registered platform's access permission is grantable, so new platforms need no change here.
        codes = {"mail.access_all_mailboxes", "mail.manage_mailboxes", "audit.view_auditevent", "identity.manage_users", "platforms.manage_platforms"}
        codes |= {spec.permission for spec in registry.all()}
        apps = {code.split(".", 1)[0] for code in codes}
        perms = Permission.objects.filter(content_type__app_label__in=apps).select_related("content_type").order_by("content_type__app_label", "codename")
        items = [{"code": f"{p.content_type.app_label}.{p.codename}", "name": p.name} for p in perms]
        return Response([item for item in items if item["code"] in codes])


class OfficeListView(APIView):
    def get_permissions(self):
        return [IsAuthenticated()] if self.request.method == "GET" else [IsAuthenticated(), ManageUsers()]

    @extend_schema(responses=OfficeSerializer(many=True), operation_id="settings_offices_list")
    def get(self, request):
        return Response(OfficeSerializer(Office.objects.all(), many=True).data)

    @extend_schema(request=OfficeSerializer, responses=OfficeSerializer, operation_id="settings_offices_create")
    def post(self, request):
        data = OfficeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        office = data.save()
        record("offices.create", request=request, target_type="office", target_id=office.pk, metadata={"name": office.name})
        return Response(OfficeSerializer(office).data, status=status.HTTP_201_CREATED)


class OfficeDetailView(APIView):
    permission_classes = [IsAuthenticated, ManageUsers]

    @extend_schema(request=OfficeSerializer, responses=OfficeSerializer, operation_id="settings_offices_update")
    def patch(self, request, pk):
        office = Office.objects.filter(pk=pk).first()
        if not office:
            raise ApiError("not_found", "This office was not found.", status.HTTP_404_NOT_FOUND)
        data = OfficeSerializer(office, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        office = data.save()
        record("offices.update", request=request, target_type="office", target_id=office.pk, metadata={"name": office.name})
        return Response(OfficeSerializer(office).data)

    @extend_schema(responses={204: None}, operation_id="settings_offices_delete")
    def delete(self, request, pk):
        office = Office.objects.filter(pk=pk).first()
        if not office:
            raise ApiError("not_found", "This office was not found.", status.HTTP_404_NOT_FOUND)
        from django.db.models import ProtectedError

        try:
            office.delete()
        except ProtectedError as exc:
            raise ApiError("office_in_use", "Move or remove this office's mailboxes first.") from exc
        record("offices.delete", request=request, target_type="office", target_id=pk)
        return Response(status=status.HTTP_204_NO_CONTENT)

