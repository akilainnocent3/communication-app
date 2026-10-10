from rest_framework.permissions import BasePermission


def has_perm(user, codename: str) -> bool:
    return bool(user and user.is_authenticated and user.has_perm(codename))


class HasPerm(BasePermission):
    """`permission_classes = [HasPerm.of("app.codename")]`"""

    perm = ""

    @classmethod
    def of(cls, perm: str):
        return type(f"HasPerm_{perm.replace('.', '_')}", (cls,), {"perm": perm})

    def has_permission(self, request, view):
        return has_perm(request.user, self.perm)


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)
