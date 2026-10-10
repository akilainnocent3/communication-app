from urllib.parse import quote, urlencode

from django.conf import settings
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.errors import ApiError
from common.http import ClientIpScopedThrottle
from modules.identity.models import Office, User

from ..models import MailboxAccess, MailboxInvite, MailSettings
from ..services import access, connect, mailboxes
from ..tasks import sync_mailbox_task
from .permissions import CanUseMail, CanManageMailboxes
from .serializers import (
    AccessEntrySerializer,
    DetectionSerializer,
    DetectRequestSerializer,
    ImapSettingsSerializer,
    ImapTestResultSerializer,
    InviteCreatedSerializer,
    InviteSerializer,
    MailboxCreatedSerializer,
    MailboxCreateSerializer,
    MailboxSerializer,
    MailboxStatusSerializer,
    MailboxUpdateSerializer,
    OAuthStartSerializer,
    PublicInviteSerializer,
    UrlSerializer,
)


def _with_unread(qs):
    return qs.select_related("office", "connected_by").annotate(unread=Count("threads", filter=Q(threads__is_unread=True, threads__label_ids__contains=["INBOX"])))


def _managed_mailbox(request, pk):
    return access.get_mailbox(request.user, pk, access.MANAGE)


class MailboxListView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(responses=MailboxSerializer(many=True), operation_id="mail_mailboxes_list")
    def get(self, request):
        qs = _with_unread(access.accessible_mailboxes(request.user))
        return Response(MailboxSerializer(qs, many=True, context={"request": request}).data)

    @extend_schema(request=MailboxCreateSerializer, responses={201: MailboxCreatedSerializer}, operation_id="mail_mailboxes_create")
    def post(self, request):
        if not request.user.has_perm("mail.manage_mailboxes"):
            raise ApiError("permission_denied", "You don't have permission to add mailboxes.", status.HTTP_403_FORBIDDEN)
        data = MailboxCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        office = Office.objects.filter(pk=values["office"]).first()
        if not office:
            raise ApiError("validation_error", "Choose an office.", errors={"office": ["Unknown office."]})
        provider = values.get("provider")
        if provider == "fake" and not settings.MAIL_ENABLE_FAKE_PROVIDER:
            raise ApiError("validation_error", "Demo mailboxes are disabled on this server.")
        mailbox, detection = mailboxes.create_mailbox(
            request.user, office=office, email=values["email"], display_name=values["display_name"], colour=values["colour"],
            provider="fake" if provider == "fake" else None, request=request,
        )
        mailbox = _with_unread(access.accessible_mailboxes(request.user)).get(pk=mailbox.pk)
        return Response({"mailbox": MailboxSerializer(mailbox, context={"request": request}).data, "detection": detection}, status=status.HTTP_201_CREATED)


class MailboxDetailView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(responses=MailboxSerializer, operation_id="mail_mailboxes_retrieve")
    def get(self, request, pk):
        access.get_mailbox(request.user, pk)
        mailbox = _with_unread(access.accessible_mailboxes(request.user)).get(pk=pk)
        return Response(MailboxSerializer(mailbox, context={"request": request}).data)

    @extend_schema(request=MailboxUpdateSerializer, responses=MailboxSerializer, operation_id="mail_mailboxes_update")
    def patch(self, request, pk):
        mailbox = _managed_mailbox(request, pk)
        data = MailboxUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        if "office" in values:
            office = Office.objects.filter(pk=values["office"]).first()
            if not office:
                raise ApiError("validation_error", "Choose an office.", errors={"office": ["Unknown office."]})
            mailbox.office = office
        for key in ("display_name", "colour"):
            if key in values:
                setattr(mailbox, key, values[key])
        mailbox.save()
        from modules.audit.services import record

        record("mailbox.update", request=request, mailbox=mailbox, target_type="mailbox", target_id=mailbox.pk, metadata={k: str(v) for k, v in values.items()})
        return self.get(request, pk)

    @extend_schema(responses={204: None}, operation_id="mail_mailboxes_destroy")
    def delete(self, request, pk):
        mailbox = _managed_mailbox(request, pk)
        mailboxes.delete_mailbox(request.user, mailbox, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DetectView(APIView):
    permission_classes = [IsAuthenticated, CanManageMailboxes]

    @extend_schema(request=DetectRequestSerializer, responses=DetectionSerializer, operation_id="mail_mailboxes_detect")
    def post(self, request, pk=None):
        if pk is not None:
            email = _managed_mailbox(request, pk).email
        else:
            data = DetectRequestSerializer(data=request.data)
            data.is_valid(raise_exception=True)
            email = data.validated_data["email"]
        return Response(connect.detect(email).as_dict())


class RedetectView(DetectView):
    """Run detection again for an existing mailbox (e.g. after the company moved its mail hosting)."""

    @extend_schema(request=None, responses=DetectionSerializer, operation_id="mail_mailboxes_redetect")
    def post(self, request, pk=None):
        return super().post(request, pk)


class ConnectView(APIView):
    """'Connect now': the Google consent URL for this mailbox (or an instant Workspace connection)."""

    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(request=None, responses=UrlSerializer, operation_id="mail_mailboxes_connect")
    def post(self, request, pk):
        mailbox = _managed_mailbox(request, pk)
        if mailbox.provider == "workspace_delegation":
            mailboxes.connect_workspace(request.user, mailbox, request=request)
            return Response({"url": f"/gmail/mailboxes?connected={mailbox.pk}"})
        if mailbox.provider not in ("gmail_oauth",):
            raise ApiError("validation_error", "This mailbox connects with its server settings, not Google sign-in.")
        return Response({"url": connect.oauth_url(mailbox, user=request.user)})


class InviteListView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(responses=InviteSerializer(many=True), operation_id="mail_invites_list")
    def get(self, request, pk):
        mailbox = _managed_mailbox(request, pk)
        return Response(InviteSerializer(mailbox.invites.select_related("created_by")[:20], many=True).data)

    @extend_schema(request=None, responses={201: InviteCreatedSerializer}, operation_id="mail_invites_create")
    def post(self, request, pk):
        mailbox = _managed_mailbox(request, pk)
        if mailbox.provider not in ("gmail_oauth",):
            raise ApiError("validation_error", "Connect links are for Google mailboxes. Use the server settings form for this mailbox.")
        invite, token = connect.create_invite(mailbox, request.user, request=request)
        url = connect.connect_url(token)
        message = f"Hello! Please connect the mailbox {mailbox.email} to {settings.COMPANY_NAME}'s Communication Manager. Open this link and tap 'Connect with Google': {url}"
        return Response(
            {**InviteSerializer(invite).data, "url": url, "whatsapp_url": f"https://wa.me/?text={quote(message)}", "qr_svg": connect.qr_svg(url)},
            status=status.HTTP_201_CREATED,
        )


class InviteRevokeView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(request=None, responses=InviteSerializer, operation_id="mail_invites_revoke")
    def post(self, request, pk, invite_id):
        mailbox = _managed_mailbox(request, pk)
        invite = MailboxInvite.objects.filter(pk=invite_id, mailbox=mailbox).first()
        if not invite:
            raise ApiError("not_found", "This link was not found.", status.HTTP_404_NOT_FOUND)
        connect.revoke_invite(invite, request.user, request=request)
        invite.refresh_from_db()
        return Response(InviteSerializer(invite).data)


class SyncView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(request=None, parameters=[OpenApiParameter("full", bool)], responses={202: MailboxStatusSerializer}, operation_id="mail_mailboxes_sync")
    def post(self, request, pk):
        mailbox = access.get_mailbox(request.user, pk)
        full = request.query_params.get("full") in ("1", "true")
        if full and not access.permissions_for(request.user, mailbox)["manage"]:
            raise ApiError("permission_denied", "You don't have permission to resync this mailbox.", status.HTTP_403_FORBIDDEN)
        sync_mailbox_task.delay(mailbox.pk, full)
        mailbox.refresh_from_db()
        return Response(_status_payload(mailbox), status=status.HTTP_202_ACCEPTED)


def _status_payload(mailbox) -> dict:
    invite = mailbox.invites.select_related("created_by").first()
    return {
        "id": mailbox.pk, "status": mailbox.status, "sync_progress": mailbox.sync_progress or {}, "last_synced_at": mailbox.last_synced_at,
        "sync_error": mailbox.sync_error, "latest_invite": InviteSerializer(invite).data if invite else None,
    }


class StatusView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(responses=MailboxStatusSerializer, operation_id="mail_mailboxes_status")
    def get(self, request, pk):
        return Response(_status_payload(access.get_mailbox(request.user, pk)))


class ImapTestView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(request=ImapSettingsSerializer, responses=ImapTestResultSerializer, operation_id="mail_mailboxes_test_imap")
    def post(self, request, pk):
        mailbox = _managed_mailbox(request, pk)
        data = ImapSettingsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        from ..providers.imap_smtp import test_connection

        values = dict(data.validated_data)
        password, username = values.pop("password"), values.pop("username") or mailbox.email
        result = test_connection(values, username, password)
        return Response({"ok": result["imap"]["ok"] and result["smtp"]["ok"], **result})


class ImapSaveView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(request=ImapSettingsSerializer, responses=ImapTestResultSerializer, operation_id="mail_mailboxes_save_imap")
    def post(self, request, pk):
        mailbox = _managed_mailbox(request, pk)
        data = ImapSettingsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        password, username = values.pop("password"), values.pop("username")
        result = mailboxes.save_imap(request.user, mailbox, server=values, username=username, password=password, request=request)
        if not result["ok"]:
            raise ApiError("connection_failed", "Couldn't connect with these settings. Check the password and server details.", errors=result)
        return Response(result)


class DisconnectView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(request=None, responses=MailboxSerializer, operation_id="mail_mailboxes_disconnect")
    def post(self, request, pk):
        mailbox = _managed_mailbox(request, pk)
        mailboxes.disconnect(request.user, mailbox, request=request)
        return MailboxDetailView().get(request, pk)


class AccessView(APIView):
    permission_classes = [IsAuthenticated, CanUseMail]

    @extend_schema(responses=AccessEntrySerializer(many=True), operation_id="mail_access_list")
    def get(self, request, pk):
        mailbox = _managed_mailbox(request, pk)
        rows = MailboxAccess.objects.filter(mailbox=mailbox).select_related("user").order_by("user__full_name", "user__email")
        return Response([AccessEntrySerializer.from_row(r) for r in rows])

    @extend_schema(request=AccessEntrySerializer(many=True), responses=AccessEntrySerializer(many=True), operation_id="mail_access_update")
    def put(self, request, pk):
        mailbox = _managed_mailbox(request, pk)
        data = AccessEntrySerializer(data=request.data, many=True)
        data.is_valid(raise_exception=True)
        entries = [dict(e) for e in data.validated_data]
        ids = {e["user"] for e in entries}
        if User.objects.filter(pk__in=ids, is_active=True).count() != len(ids):
            raise ApiError("validation_error", "One of the users does not exist or is inactive.")
        if not request.user.has_perm("mail.manage_mailboxes"):
            # Mailbox managers can share access but not hand out "manage".
            current = {r.user_id: r.can_manage for r in MailboxAccess.objects.filter(mailbox=mailbox)}
            for entry in entries:
                if entry.get("can_manage") and not current.get(entry["user"]):
                    raise ApiError("permission_denied", "Only admins can give 'manage' access.", status.HTTP_403_FORBIDDEN)
        rows = mailboxes.set_access(request.user, mailbox, entries, request=request)
        return Response([AccessEntrySerializer.from_row(r) for r in rows])


# --- Public connect flow (no login) -----------------------------------------------------------------------


class PublicInviteView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ClientIpScopedThrottle]
    throttle_scope = "public_connect"

    @extend_schema(responses=PublicInviteSerializer, operation_id="mail_connect_info")
    def get(self, request, token):
        invite = connect.invite_for_token(token)
        if not invite:
            raise ApiError("not_found", "This connect link is not valid. Ask your administrator for a new one.", status.HTTP_404_NOT_FOUND)
        mailbox = invite.mailbox
        return Response({
            "state": "connected" if invite.state == "used" else invite.state,
            "company_name": settings.COMPANY_NAME,
            "mailbox_email": mailbox.email,
            "mailbox_name": mailbox.name,
            "notice": MailSettings.load().connect_notice,
            "expires_at": invite.expires_at,
            "google_configured": bool(settings.GOOGLE_OAUTH_CLIENT_ID),
        })


class OAuthStartView(APIView):
    """Start Google consent from a connect link (`token`) or, for a signed-in admin, a mailbox id."""

    permission_classes = [AllowAny]
    throttle_classes = [ClientIpScopedThrottle]
    throttle_scope = "public_connect"

    @extend_schema(request=OAuthStartSerializer, responses=UrlSerializer, operation_id="mail_oauth_start")
    def post(self, request):
        data = OAuthStartSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        token = data.validated_data.get("token")
        if token:
            invite = connect.invite_for_token(token)
            if not invite or invite.state != "active":
                raise ApiError("invite_inactive", "This connect link was already used, revoked or has expired. Ask your administrator for a new one.", status.HTTP_410_GONE)
            return Response({"url": connect.oauth_url(invite.mailbox, invite=invite, invite_token=token)})
        if not request.user.is_authenticated:
            raise ApiError("not_authenticated", "Your session has ended. Sign in again.", status.HTTP_401_UNAUTHORIZED)
        mailbox = _managed_mailbox(request, data.validated_data.get("mailbox"))
        return Response({"url": connect.oauth_url(mailbox, user=request.user)})


class OAuthCallbackView(APIView):
    """Google redirects the browser here. We answer with a redirect to a friendly page."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ClientIpScopedThrottle]
    throttle_scope = "public_connect"

    @extend_schema(parameters=[OpenApiParameter("code", str), OpenApiParameter("state", str), OpenApiParameter("error", str)], responses={302: None}, operation_id="mail_oauth_callback")
    def get(self, request):
        state = request.query_params.get("state", "")
        try:
            data = connect.read_state(state)
        except connect.OAuthFailure as failure:
            return HttpResponseRedirect(f"/connect/result?{urlencode({'result': failure.code})}")
        target = f"/connect/{data['token']}" if data.get("token") else f"/gmail/mailboxes/{data['m']}"
        error = request.query_params.get("error")
        if error:
            return HttpResponseRedirect(f"{target}?{urlencode({'result': 'denied' if error == 'access_denied' else 'error'})}")
        try:
            connect.complete_oauth(request.query_params.get("code", ""), state, request=request)
        except connect.OAuthFailure as failure:
            params = {"result": failure.code}
            if failure.context.get("signed_in_as"):
                params["signed_in_as"] = failure.context["signed_in_as"]
            if failure.context.get("missing"):
                params["missing"] = ",".join(failure.context["missing"])
            return HttpResponseRedirect(f"{target}?{urlencode(params)}")
        return HttpResponseRedirect(f"{target}?result=connected")
