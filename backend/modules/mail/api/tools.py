import json

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.crypto import encrypt_json
from common.errors import ApiError
from common.permissions import IsSuperAdmin
from modules.audit.services import record

from ..models import MailSettings, WorkspaceDomain
from ..providers import get_provider
from ..providers.base import ProviderError, Unsupported
from ..providers.workspace_delegation import delegated_credentials, delegation_scopes
from ..services import access
from ..services.sanitize import sanitize_compose_html
from .permissions import CanManageMailboxes, CanUseMail
from .serializers import (
    FilterSerializer,
    MailSettingsSerializer,
    SendAsSerializer,
    SignatureWriteSerializer,
    VacationSerializer,
    WorkspaceDomainSerializer,
    WorkspaceDomainWriteSerializer,
    WorkspaceTestSerializer,
)


def _call(fn):
    try:
        return fn()
    except Unsupported as exc:
        raise ApiError("unsupported", str(exc), status.HTTP_400_BAD_REQUEST) from None
    except ProviderError as exc:
        raise ApiError(exc.code, str(exc), status.HTTP_503_SERVICE_UNAVAILABLE if exc.retryable else status.HTTP_400_BAD_REQUEST) from None


class SendAsView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(responses=SendAsSerializer(many=True), operation_id="mail_settings_send_as")
    def get(self, request, mailbox):
        box = access.get_mailbox(request.user, mailbox)
        return Response(_call(lambda: get_provider(box).list_send_as()))


class SignatureView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(responses=SendAsSerializer(many=True), operation_id="mail_settings_signature_list")
    def get(self, request, mailbox):
        box = access.get_mailbox(request.user, mailbox)
        return Response(_call(lambda: get_provider(box).list_send_as()))

    @extend_schema(request=SignatureWriteSerializer, responses=SendAsSerializer, operation_id="mail_settings_signature_update")
    def put(self, request, mailbox):
        box = access.get_mailbox(request.user, mailbox, access.MANAGE)
        data = SignatureWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        html = sanitize_compose_html(data.validated_data["signature"])
        result = _call(lambda: get_provider(box).update_signature(data.validated_data["send_as"], html))
        record("mail.signature_update", request=request, mailbox=box, target_type="send_as", target_id=data.validated_data["send_as"])
        return Response(result)


class VacationView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(responses=VacationSerializer, operation_id="mail_settings_vacation_get")
    def get(self, request, mailbox):
        box = access.get_mailbox(request.user, mailbox)
        return Response(_call(lambda: get_provider(box).vacation_get()))

    @extend_schema(request=VacationSerializer, responses=VacationSerializer, operation_id="mail_settings_vacation_set")
    def put(self, request, mailbox):
        box = access.get_mailbox(request.user, mailbox, access.MANAGE)
        data = VacationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        if values.get("start_time") and values.get("end_time") and values["end_time"] <= values["start_time"]:
            raise ApiError("validation_error", "The last day must be after the first day.", errors={"end_time": ["Must be after the first day."]})
        values["response_body_html"] = sanitize_compose_html(values.get("response_body_html") or "")
        for key in ("start_time", "end_time"):
            values[key] = values[key].isoformat() if values.get(key) else None
        result = _call(lambda: get_provider(box).vacation_set(values))
        record("mail.vacation_update", request=request, mailbox=box, target_type="mailbox", target_id=box.pk, metadata={"enabled": values["enable_auto_reply"]})
        return Response(result)


class FilterListView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(responses=FilterSerializer(many=True), operation_id="mail_settings_filters_list")
    def get(self, request, mailbox):
        box = access.get_mailbox(request.user, mailbox)
        return Response(_call(lambda: get_provider(box).filters_list()))

    @extend_schema(request=FilterSerializer, responses={201: FilterSerializer}, operation_id="mail_settings_filters_create")
    def post(self, request, mailbox):
        box = access.get_mailbox(request.user, mailbox, access.MANAGE)
        data = FilterSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        criteria = {k: v for k, v in data.validated_data["criteria"].items() if v not in ("", None, False)}
        action = {k: v for k, v in data.validated_data["action"].items() if v not in ("", None, [])}
        if not criteria:
            raise ApiError("validation_error", "Add at least one condition (for example From).")
        if not action:
            raise ApiError("validation_error", "Choose at least one action.")
        result = _call(lambda: get_provider(box).filters_create(criteria, action))
        record("mail.filter_create", request=request, mailbox=box, target_type="filter", target_id=result.get("id", ""), metadata={"criteria": criteria, "action": action})
        return Response(result, status=status.HTTP_201_CREATED)


class FilterDetailView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(responses={204: None}, operation_id="mail_settings_filters_destroy")
    def delete(self, request, mailbox, filter_id):
        box = access.get_mailbox(request.user, mailbox, access.MANAGE)
        _call(lambda: get_provider(box).filters_delete(filter_id))
        record("mail.filter_delete", request=request, mailbox=box, target_type="filter", target_id=filter_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Settings → Integrations ------------------------------------------------------------------------------


def _mail_settings_payload() -> dict:
    return {
        "connect_notice": MailSettings.load().connect_notice,
        "google_configured": bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET),
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "scopes": settings.GOOGLE_OAUTH_SCOPES,
        "fake_provider_enabled": settings.MAIL_ENABLE_FAKE_PROVIDER,
    }


class IntegrationsView(APIView):
    permission_classes = [IsAuthenticated, CanManageMailboxes]

    @extend_schema(responses=MailSettingsSerializer, operation_id="settings_integrations_get")
    def get(self, request):
        return Response(_mail_settings_payload())

    @extend_schema(request=MailSettingsSerializer, responses=MailSettingsSerializer, operation_id="settings_integrations_update")
    def put(self, request):
        data = MailSettingsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = MailSettings.load()
        row.connect_notice = data.validated_data["connect_notice"].strip()
        row.save()
        record("settings.connect_notice_update", request=request)
        return Response(_mail_settings_payload())


def _domain_payload(row: WorkspaceDomain) -> dict:
    return {
        "id": row.pk, "domain": row.domain, "client_id": row.client_id, "service_account_email": row.service_account_email, "scopes": delegation_scopes(),
        "last_test_at": row.last_test_at, "last_test_ok": row.last_test_ok, "last_test_error": row.last_test_error, "created_at": row.created_at,
    }


class WorkspaceDomainListView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(responses=WorkspaceDomainSerializer(many=True), operation_id="settings_workspace_list")
    def get(self, request):
        return Response([_domain_payload(r) for r in WorkspaceDomain.objects.order_by("domain")])

    @extend_schema(request=WorkspaceDomainWriteSerializer, responses={201: WorkspaceDomainSerializer}, operation_id="settings_workspace_create")
    def post(self, request):
        data = WorkspaceDomainWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            info = json.loads(data.validated_data["service_account_json"])
        except json.JSONDecodeError:
            raise ApiError("validation_error", "This is not a valid JSON key file.", errors={"service_account_json": ["Invalid JSON."]}) from None
        if info.get("type") != "service_account" or not info.get("client_id") or not info.get("private_key") or not info.get("client_email"):
            raise ApiError("validation_error", "Upload the JSON key of a Google service account.", errors={"service_account_json": ["Not a service-account key."]})
        domain = data.validated_data["domain"].strip().lower().lstrip("@")
        row, _ = WorkspaceDomain.objects.update_or_create(
            domain=domain,
            defaults={"encrypted_service_account": encrypt_json(info), "client_id": str(info["client_id"]), "service_account_email": info["client_email"], "created_by": request.user, "last_test_ok": False, "last_test_error": ""},
        )
        record("settings.workspace_domain_save", request=request, target_type="workspace_domain", target_id=domain, metadata={"client_id": row.client_id})
        return Response(_domain_payload(row), status=status.HTTP_201_CREATED)


class WorkspaceDomainDetailView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(responses={204: None}, operation_id="settings_workspace_destroy")
    def delete(self, request, pk):
        row = WorkspaceDomain.objects.filter(pk=pk).first()
        if not row:
            raise ApiError("not_found", "This domain was not found.", status.HTTP_404_NOT_FOUND)
        record("settings.workspace_domain_delete", request=request, target_type="workspace_domain", target_id=row.domain)
        row.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceDomainTestView(APIView):
    """Try to impersonate a mailbox in the domain and read its profile."""

    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(request=WorkspaceTestSerializer, responses=WorkspaceDomainSerializer, operation_id="settings_workspace_test")
    def post(self, request, pk):
        row = WorkspaceDomain.objects.filter(pk=pk).first()
        if not row:
            raise ApiError("not_found", "This domain was not found.", status.HTTP_404_NOT_FOUND)
        data = WorkspaceTestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        email = data.validated_data["email"].lower()
        if not email.endswith("@" + row.domain):
            raise ApiError("validation_error", f"Use an address in {row.domain}.", errors={"email": ["Wrong domain."]})
        ok, error = True, ""
        try:
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            creds = delegated_credentials(row, email)
            creds.refresh(Request())
            profile = build("gmail", "v1", credentials=creds, cache_discovery=False, static_discovery=True).users().getProfile(userId="me").execute()
            ok = profile.get("emailAddress", "").lower() == email
            error = "" if ok else "Google opened a different mailbox."
        except Exception as exc:  # noqa: BLE001 - show the admin what Google said, without secrets
            ok = False
            text = str(exc)
            if "unauthorized_client" in text:
                error = "Google says the client is not authorised. Add the Client ID and scopes in Google Admin → Security → API controls → Domain-wide delegation (it can take a few minutes)."
            elif "invalid_grant" in text:
                error = "Google refused to impersonate this address. Check that the mailbox exists and the scopes match exactly."
            else:
                error = "The test failed. Check the key, the Client ID and the scopes in Google Admin."
        row.last_test_at, row.last_test_ok, row.last_test_error = timezone.now(), ok, error
        row.save(update_fields=["last_test_at", "last_test_ok", "last_test_error"])
        record("settings.workspace_domain_test", request=request, target_type="workspace_domain", target_id=row.domain, metadata={"ok": ok})
        return Response(_domain_payload(row))
