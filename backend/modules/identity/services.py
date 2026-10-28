"""Users, roles and offices: business rules kept out of the views."""

from django.contrib.auth.models import Group, Permission
from django.db import transaction

from common import stores

from .models import Role, User

# Permissions each seeded role carries ("app_label.codename"). Super admins are Django superusers and get
# everything implicitly; the group still carries the list so demoting is a role change, nothing more.
ROLE_PERMISSIONS: dict[str, list[str]] = {
    Role.SUPER_ADMIN: ["*"],
    Role.ADMIN: [
        "mail.access",
        "mail.access_all_mailboxes",
        "mail.manage_mailboxes",
        "sms.access",
        "sms.access_all_devices",
        "sms.manage_devices",
        "calls.access",
        "calls.access_all_devices",
        "calls.manage_settings",
        "calls.export",
        "directory.manage_customers",
        "audit.view_auditevent",
        "identity.manage_users",
    ],
    # Office managers and viewers reach phones only through DeviceAccess rows (sms and calls).
    Role.OFFICE_MANAGER: ["mail.access", "sms.access", "calls.access"],
    Role.VIEWER: ["mail.access", "sms.access", "calls.access"],
}

SEEDED_ROLES = [
    (Role.SUPER_ADMIN, "Super admin", "Everything, including platforms, integrations and roles.", 0),
    (Role.ADMIN, "Admin", "Every mailbox and phone, connecting mailboxes, enrolling phones, users and the audit log.", 10),
    (Role.OFFICE_MANAGER, "Office manager", "Works in the mailboxes and phones they are given access to.", 20),
    (Role.VIEWER, "Viewer", "Reads the mailboxes and phones they are given access to.", 30),
]


def _permissions(codes: list[str]):
    if codes == ["*"]:
        return Permission.objects.all()
    found = []
    for code in codes:
        app_label, codename = code.split(".", 1)
        perm = Permission.objects.filter(content_type__app_label=app_label, codename=codename).first()
        if perm:
            found.append(perm)
    return found


@transaction.atomic
def ensure_roles() -> None:
    """Create the four system roles (idempotent). Runs after every migrate."""
    for slug, name, description, rank in SEEDED_ROLES:
        group, _ = Group.objects.get_or_create(name=f"role:{slug}")
        Role.objects.get_or_create(
            slug=slug, defaults={"name": name, "description": description, "rank": rank, "group": group, "is_system": True}
        )
        # Add (never remove) the baseline: permissions of apps migrated later get picked up on the next run,
        # and extra permissions an admin granted survive.
        group.permissions.add(*_permissions(ROLE_PERMISSIONS[slug]))


def assign_role(user: User, role: Role | None) -> None:
    user.role = role
    user.is_superuser = bool(role and role.slug == Role.SUPER_ADMIN)
    user.is_staff = user.is_superuser
    user.save(update_fields=["role", "is_superuser", "is_staff"])
    user.groups.set([role.group] if role else [])
    # has_perm caches per instance; drop it so the change applies immediately.
    for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        user.__dict__.pop(attr, None)


def permission_codes(user: User) -> list[str]:
    if not user.is_authenticated:
        return []
    if user.is_superuser:
        codes = {f"{p.content_type.app_label}.{p.codename}" for p in Permission.objects.select_related("content_type")}
    else:
        codes = set(user.get_all_permissions())
    return sorted(codes)


# --- Login throttling: per email address, independent of the per-IP DRF throttle --------------------------
LOGIN_FAILURE_LIMIT = 8
LOGIN_LOCK_SECONDS = 15 * 60


def _key(email: str) -> str:
    return f"login-failures:{email.strip().lower()}"


# Counters live in the security store (never evicted); a store error raises SecurityStoreUnavailable (sign-in refused).
def login_locked(email: str) -> bool:
    return (stores.read(_key(email), 0) or 0) >= LOGIN_FAILURE_LIMIT


def note_login_failure(email: str) -> None:
    stores.bump(_key(email), LOGIN_LOCK_SECONDS)


def clear_login_failures(email: str) -> None:
    stores.delete(_key(email))
