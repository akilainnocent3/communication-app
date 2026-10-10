from rest_framework.permissions import BasePermission

from ..services.access import can_use_mail


class CanUseMail(BasePermission):
    message = "You don't have access to the Gmail platform."

    def has_permission(self, request, view):
        return can_use_mail(request.user)


class CanManageMailboxes(BasePermission):
    message = "You don't have permission to manage mailboxes."

    def has_permission(self, request, view):
        return can_use_mail(request.user) and request.user.has_perm("mail.manage_mailboxes")
