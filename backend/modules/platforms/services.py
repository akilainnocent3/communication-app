from .models import Platform
from .registry import registry


def sync_platform_rows() -> None:
    """Make sure every registered platform has a row (new platforms get their default enablement)."""
    existing = set(Platform.objects.values_list("key", flat=True))
    Platform.objects.bulk_create(
        [Platform(key=spec.key, is_enabled=spec.default_enabled, order=spec.order) for spec in registry.all() if spec.key not in existing]
    )


def platforms_for(user, include_disabled: bool = False) -> list[dict]:
    sync_platform_rows()
    rows = {row.key: row for row in Platform.objects.all()}
    result = []
    for spec in registry.all():
        row = rows[spec.key]
        if not include_disabled and not row.is_enabled:
            continue
        if not include_disabled and not user.has_perm(spec.permission):
            continue
        result.append({"key": spec.key, "name": spec.name, "permission": spec.permission, "is_enabled": row.is_enabled, "order": row.order})
    return sorted(result, key=lambda item: (item["order"], item["key"]))
