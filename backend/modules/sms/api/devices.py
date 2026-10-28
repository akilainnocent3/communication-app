"""Admin endpoints for enrolled phones and enrollment invites (/api/v1/sms/devices/, /api/v1/sms/enrollments/)."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.errors import ApiError
from modules.audit.services import record
from modules.devices.models import DeviceStatus, EnrollmentInvite, SimLine
from modules.devices.services import enrollment, manage
from modules.identity.models import Office

from ..models import DeviceAccess
from ..services import access
from .permissions import CanManageDevices, CanUseSms
from .serializers import (
    DeviceAccessEntrySerializer,
    DeviceDetailSerializer,
    DeviceSerializer,
    DeviceStatusChangeSerializer,
    DeviceUpdateSerializer,
    EnrollmentCreatedSerializer,
    EnrollmentShortCodeSerializer,
    EnrollmentCreateSerializer,
    EnrollmentSerializer,
    HeartbeatHistorySerializer,
    SimLineSerializer,
    SimulatorActionSerializer,
    SimUpdateSerializer,
)

User = get_user_model()


def _with_unread(qs):
    return qs.prefetch_related("sim_lines").annotate(
        unread=Sum("sms_conversations__unread_count", filter=Q(sms_conversations__is_archived=False, sms_conversations__is_spam=False))
    )


def _detail(request, device):
    device = _with_unread(access.accessible_devices(request.user)).select_related("enrolled_by").get(pk=device.pk)
    return Response(DeviceDetailSerializer(device, context={"request": request}).data)


def _require_manage_devices(request):
    if not request.user.has_perm("sms.manage_devices"):
        raise ApiError("permission_denied", "Only admins who manage phones can do this.", status.HTTP_403_FORBIDDEN)


class DeviceListView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(responses=DeviceSerializer(many=True), operation_id="sms_devices_list")
    def get(self, request):
        qs = _with_unread(access.accessible_devices(request.user))
        if request.query_params.get("include_revoked") not in ("1", "true"):
            qs = qs.exclude(status=DeviceStatus.REVOKED)
        return Response(DeviceSerializer(qs, many=True, context={"request": request}).data)


class DeviceDetailView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(responses=DeviceDetailSerializer, operation_id="sms_devices_retrieve")
    def get(self, request, pk):
        return _detail(request, access.get_device(request.user, pk))

    @extend_schema(request=DeviceUpdateSerializer, responses=DeviceDetailSerializer, operation_id="sms_devices_update")
    def patch(self, request, pk):
        device = access.get_device(request.user, pk, access.MANAGE)
        data = DeviceUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        if "office" in values:
            values["office"] = Office.objects.filter(pk=values["office"]).first()
            if not values["office"]:
                raise ApiError("validation_error", "Choose an office.", errors={"office": ["Unknown office."]})
        if "assigned_to" in values and values["assigned_to"] is not None:
            values["assigned_to"] = User.objects.filter(pk=values["assigned_to"], is_active=True).first()
            if not values["assigned_to"]:
                raise ApiError("validation_error", "Choose an active user.", errors={"assigned_to": ["Unknown user."]})
        if "options" in values:
            values["options"] = dict(values["options"])
        manage.update(device, request.user, values, request=request)
        return _detail(request, device)


class DeviceStatusView(APIView):
    """suspend / resume / revoke. Revoking needs the device code typed back (confirm_code)."""

    permission_classes = [IsAuthenticated, CanManageDevices]
    action = ""

    @extend_schema(request=DeviceStatusChangeSerializer, responses=DeviceDetailSerializer, operation_id="sms_devices_status")
    def post(self, request, pk, action):
        device = access.get_device(request.user, pk, access.MANAGE)
        data = DeviceStatusChangeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        if device.status == DeviceStatus.REVOKED:
            raise ApiError("device_revoked", "This phone was removed. Enroll it again to use it.", status.HTTP_409_CONFLICT)
        if action == "suspend":
            manage.suspend(device, request.user, request=request, reason=values["reason"])
        elif action == "resume":
            manage.resume(device, request.user, request=request)
        elif action == "revoke":
            if values["confirm_code"].strip().upper() != device.code:
                raise ApiError("validation_error", "Type the device code to confirm.", errors={"confirm_code": ["Does not match the device code."]})
            manage.revoke(device, request.user, request=request, reason=values["reason"])
        else:
            raise ApiError("not_found", "Unknown action.", status.HTTP_404_NOT_FOUND)
        return _detail(request, device)


class DeviceResyncView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(request=None, responses={202: None}, operation_id="sms_devices_resync")
    def post(self, request, pk):
        device = access.get_device(request.user, pk, access.MANAGE)
        if device.status != DeviceStatus.ACTIVE:
            raise ApiError("device_inactive", "This phone is suspended or removed.", status.HTTP_409_CONFLICT)
        manage.request_resync(device, request.user, request=request)
        return Response(status=status.HTTP_202_ACCEPTED)


class DeviceHeartbeatsView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(responses=HeartbeatHistorySerializer(many=True), operation_id="sms_devices_heartbeats")
    def get(self, request, pk):
        device = access.get_device(request.user, pk)
        return Response(HeartbeatHistorySerializer(device.heartbeats.all()[:96], many=True).data)


class SimLineView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(request=SimUpdateSerializer, responses=SimLineSerializer, operation_id="sms_sims_update")
    def patch(self, request, pk, sim_id):
        device = access.get_device(request.user, pk, access.MANAGE)
        line = SimLine.objects.filter(device=device, pk=sim_id).first()
        if not line:
            raise ApiError("not_found", "This SIM was not found.", status.HTTP_404_NOT_FOUND)
        data = SimUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        manage.rename_sim(line, request.user, display_name=data.validated_data.get("display_name"), colour=data.validated_data.get("colour"), request=request)
        return Response(SimLineSerializer(line).data)


class DeviceAccessView(APIView):
    permission_classes = [IsAuthenticated, CanUseSms]

    @extend_schema(responses=DeviceAccessEntrySerializer(many=True), operation_id="sms_device_access_list")
    def get(self, request, pk):
        device = access.get_device(request.user, pk, access.MANAGE)
        rows = DeviceAccess.objects.filter(device=device).select_related("user").order_by("user__full_name", "user__email")
        return Response([DeviceAccessEntrySerializer.from_row(r) for r in rows])

    @extend_schema(request=DeviceAccessEntrySerializer(many=True), responses=DeviceAccessEntrySerializer(many=True), operation_id="sms_device_access_update")
    def put(self, request, pk):
        device = access.get_device(request.user, pk, access.MANAGE)
        data = DeviceAccessEntrySerializer(data=request.data, many=True)
        data.is_valid(raise_exception=True)
        entries = [dict(e) for e in data.validated_data]
        ids = {e["user"] for e in entries}
        if User.objects.filter(pk__in=ids, is_active=True).count() != len(ids):
            raise ApiError("validation_error", "One of the users does not exist or is inactive.")
        current = {r.user_id: r for r in DeviceAccess.objects.filter(device=device)}
        if not request.user.has_perm("sms.manage_devices"):
            # Phone managers can share access, but not hand out "manage" or "reveal sensitive".
            for entry in entries:
                row = current.get(entry["user"])
                for flag in ("can_manage", "can_reveal_sensitive"):
                    if entry.get(flag) and not (row and getattr(row, flag)):
                        raise ApiError("permission_denied", "Only admins can give 'manage' or 'reveal sensitive' access.", status.HTTP_403_FORBIDDEN)
        for entry in entries:
            if entry.get("can_send") or entry.get("can_manage") or entry.get("can_reveal_sensitive"):
                entry["can_read"] = True
        DeviceAccess.objects.filter(device=device).exclude(user_id__in=ids).delete()
        for entry in entries:
            DeviceAccess.objects.update_or_create(user_id=entry["user"], device=device, defaults={k: entry[k] for k in ("can_read", "can_send", "can_manage", "can_reveal_sensitive")})
        record("device.access_update", request=request, target_type="device", target_id=device.pk,
               metadata={"device": device.code, "entries": [{k: e[k] for k in ("user", "can_read", "can_send", "can_manage", "can_reveal_sensitive")} for e in entries]})
        rows = DeviceAccess.objects.filter(device=device).select_related("user").order_by("user__full_name", "user__email")
        return Response([DeviceAccessEntrySerializer.from_row(r) for r in rows])


class SimulatorView(APIView):
    """Demo phones only (SMS_ENABLE_SIMULATOR, refused in production): go online/offline, run a tick, receive a text."""

    permission_classes = [IsAuthenticated, CanManageDevices]

    @extend_schema(request=SimulatorActionSerializer, responses=DeviceDetailSerializer, operation_id="sms_devices_simulator")
    def post(self, request, pk):
        if not settings.SMS_ENABLE_SIMULATOR:
            raise ApiError("not_found", "Not found.", status.HTTP_404_NOT_FOUND)
        device = access.get_device(request.user, pk, access.MANAGE)
        if not device.is_simulated:
            raise ApiError("validation_error", "This is a real phone.")
        data = SimulatorActionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        from ..services import simulator

        simulator.control(device, data.validated_data["action"])
        return _detail(request, device)


# --- Enrollment --------------------------------------------------------------------------------------------------


def _enrollment_payload(invite, token: str, short_code: str) -> dict:
    from modules.mail.services.connect import qr_svg

    uri = enrollment.enroll_uri(token)
    return {**EnrollmentSerializer(invite).data, "code": token, "uri": uri, "qr_svg": qr_svg(uri), "short_code": enrollment.format_short_code(short_code)}


class EnrollmentListView(APIView):
    permission_classes = [IsAuthenticated, CanManageDevices]

    @extend_schema(responses=EnrollmentSerializer(many=True), operation_id="sms_enrollments_list")
    def get(self, request):
        rows = EnrollmentInvite.objects.filter(platform="sms").select_related("office", "created_by", "device", "device__office")[:30]
        return Response(EnrollmentSerializer(rows, many=True).data)

    @extend_schema(request=EnrollmentCreateSerializer, responses={201: EnrollmentCreatedSerializer}, operation_id="sms_enrollments_create")
    def post(self, request):
        data = EnrollmentCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        office = Office.objects.filter(pk=values["office"]).first()
        if not office:
            raise ApiError("validation_error", "Choose an office.", errors={"office": ["Unknown office."]})
        assigned = None
        if values.get("assigned_to"):
            assigned = User.objects.filter(pk=values["assigned_to"], is_active=True).first()
            if not assigned:
                raise ApiError("validation_error", "Choose an active user.", errors={"assigned_to": ["Unknown user."]})
        options = {k: values[k] for k in ("signature_enabled", "signature", "mark_read_on_open", "backfill_days")}
        invite, token = enrollment.create_invite(request.user, name=values["name"], office=office, assigned_to=assigned, options=options, request=request)
        short_code = enrollment.issue_short_code(invite, request.user, request=request)
        return Response(_enrollment_payload(invite, token, short_code), status=status.HTTP_201_CREATED)


class _EnrollmentBase(APIView):
    permission_classes = [IsAuthenticated, CanManageDevices]

    def _invite(self, pk):
        invite = EnrollmentInvite.objects.filter(pk=pk, platform="sms").select_related("office", "created_by", "device", "device__office").first()
        if not invite:
            raise ApiError("not_found", "This enrollment was not found.", status.HTTP_404_NOT_FOUND)
        return invite


class EnrollmentDetailView(_EnrollmentBase):
    @extend_schema(responses=EnrollmentSerializer, operation_id="sms_enrollments_retrieve")
    def get(self, request, pk):
        return Response(EnrollmentSerializer(self._invite(pk)).data)


class EnrollmentShortCodeView(_EnrollmentBase):
    """A new short code for an active invite (the previous one stops working); codes last 15 minutes, invites 24 h."""

    @extend_schema(request=None, responses=EnrollmentShortCodeSerializer, operation_id="sms_enrollments_short_code")
    def post(self, request, pk):
        invite = self._invite(pk)
        if invite.state != "active":
            raise ApiError("invite_inactive", "This enrollment was already used, revoked or has expired.", status.HTTP_409_CONFLICT)
        code = enrollment.issue_short_code(invite, request.user, request=request)
        return Response({"short_code": enrollment.format_short_code(code), "short_code_expires_at": invite.short_code_expires_at})


class EnrollmentRevokeView(_EnrollmentBase):
    @extend_schema(request=None, responses=EnrollmentSerializer, operation_id="sms_enrollments_revoke")
    def post(self, request, pk):
        invite = self._invite(pk)
        enrollment.revoke_invite(invite, request.user, request=request)
        invite.refresh_from_db()
        return Response(EnrollmentSerializer(invite).data)
