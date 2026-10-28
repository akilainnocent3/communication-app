from rest_framework.permissions import AllowAny
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from common.errors import ApiError
from common.http import ClientIpScopedThrottle, SecurityStoreThrottle

from ..services.health import touch
from ..services.versions import is_supported
from .auth import DeviceTokenAuthentication, IsDevice

APP_VERSION_HEADER = "HTTP_X_CM_APP_VERSION"


class DeviceThrottle(SecurityStoreThrottle, SimpleRateThrottle):
    """Per-device rate (scope `device`), keyed on the authenticated device, not the IP (phones share carrier NAT)."""

    scope = "device"

    def get_cache_key(self, request, view):
        device = getattr(request.user, "device", None)
        return self.cache_format % {"scope": self.scope, "ident": str(device.pk) if device else self.get_ident(request)}


def check_app_version(request) -> None:
    version = request.META.get(APP_VERSION_HEADER, "")
    if not is_supported(version):
        raise ApiError("upgrade_required", "This app version is no longer supported. Install the latest version.", 426)


class DeviceAPIView(APIView):
    """Base for every authenticated phone endpoint. Never mix with session-auth views."""

    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [IsDevice]
    throttle_classes = [DeviceThrottle]

    def initial(self, request, *args, **kwargs):
        check_app_version(request)
        super().initial(request, *args, **kwargs)
        touch(request.user.device)

    @property
    def device(self):
        return self.request.user.device


class PublicDeviceAPIView(APIView):
    """Enrollment and token minting: no auth, throttled per client IP."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ClientIpScopedThrottle]
