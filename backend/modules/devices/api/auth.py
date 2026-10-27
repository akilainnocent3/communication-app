"""Authentication for the phone-facing API (`/api/v1/device/…`).

Only `Authorization: Bearer <device access token>` is accepted there: no cookies, therefore no CSRF. Admin
endpoints use session auth only, so a device token sent to them is ignored (401), and a browser session sent
here is ignored too (401). The two surfaces live in separate URL modules and base views.
"""

from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.permissions import BasePermission

from ..models import DeviceToken
from ..services.auth import DeviceAuthError, authenticate


class DevicePrincipal:
    """`request.user` for a phone. Authenticated, but holds no Django permissions and is never a staff user."""

    is_authenticated = True
    is_anonymous = False
    is_active = True
    is_staff = False
    is_superuser = False
    pk = None
    id = None
    email = ""

    def __init__(self, device):
        self.device = device

    def has_perm(self, perm, obj=None) -> bool:
        return False

    def has_perms(self, perms, obj=None) -> bool:
        return False

    def get_all_permissions(self, obj=None) -> set:
        return set()

    def __str__(self):
        return self.device.code


class DeviceAuthFailed(exceptions.AuthenticationFailed):
    def __init__(self, error: DeviceAuthError):
        super().__init__(detail=error.message, code=error.code)
        self.status_code = error.status


class DeviceTokenAuthentication(BaseAuthentication):
    keyword = b"bearer"

    def authenticate(self, request):
        header = get_authorization_header(request).split()
        if not header or header[0].lower() != self.keyword:
            return None
        if len(header) != 2:
            raise DeviceAuthFailed(DeviceAuthError("invalid_token", "The device token is not valid."))
        try:
            row = authenticate(header[1].decode("latin-1"))
        except DeviceAuthError as exc:
            raise DeviceAuthFailed(exc) from None
        return DevicePrincipal(row.device), row

    def authenticate_header(self, request):
        return 'Bearer realm="device"'


class IsDevice(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.auth, DeviceToken) and isinstance(request.user, DevicePrincipal)
