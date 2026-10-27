from rest_framework.permissions import BasePermission

from ..services.access import can_use_sms


class CanUseSms(BasePermission):
    """`sms.access` and the SMS platform switched on (a disabled platform refuses its whole API)."""

    message = "You don't have access to the SMS platform."

    def has_permission(self, request, view):
        return can_use_sms(request.user)


class CanManageDevices(BasePermission):
    message = "You don't have permission to manage phones."

    def has_permission(self, request, view):
        return can_use_sms(request.user) and request.user.has_perm("sms.manage_devices")
