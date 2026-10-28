"""Customers: resolving numbers on ingest, visibility, edits, merges and the cross-channel timeline.

Only real phone numbers create a customer automatically. Short codes and sender IDs ("M-PESA", "15300") are linked when
an admin has created an entry for them, never created by traffic (they are services, not customers).

Visibility: directory managers and admins with every-phone access see every customer; everyone else sees customers
that have been in contact with a phone they can read (SMS or Calls). Anything else answers 404.
"""

from __future__ import annotations

from datetime import datetime

from django.db import transaction
from django.db.models import Q, QuerySet
from rest_framework import status

from common.devicecrypto import decrypt_text, encrypt_text
from common.errors import ApiError
from modules.audit.services import record
from modules.devices.services.phone import address_kind, address_key, display_number, mask

from ..models import Customer, CustomerDevice

CHANNELS = ("sms", "call")
MAX_TAGS = 20


def resolve(customer: Customer | None) -> Customer | None:
    """Follow merges to the surviving entry (bounded: merge chains are flattened on merge)."""
    hops = 0
    while customer is not None and customer.merged_into_id and hops < 5:
        customer = customer.merged_into
        hops += 1
    return customer


def key_for(raw: str, region: str | None = None) -> tuple[str, str]:
    """(address key, kind) for a raw number as a phone reports it."""
    return address_key(raw, region), address_kind(raw)


def touch(raw: str, *, channel: str, at: datetime, device, region: str | None = None) -> Customer | None:
    """The customer for a number seen on `device` at `at` (created for real numbers), with its first/last seen and the
    device link updated. Called on ingest of SMS conversations and calls."""
    key, kind = key_for(raw, region)
    if not key:
        return None
    if kind == "number" and key.startswith("+"):
        customer, _ = Customer.objects.get_or_create(key=key, defaults={"number_e164": key, "raw_sender": (raw or "")[:64]})
    else:
        customer = Customer.objects.filter(key=key).select_related("merged_into").first()
        if customer is None:
            return None
    customer = resolve(customer)
    seen(customer, channel=channel, at=at, device=device)
    return customer


def seen(customer: Customer, *, channel: str, at: datetime, device) -> None:
    """Widen first/last seen for one channel and the device link. Filtered updates: no read-modify-write races."""
    first, last = f"first_seen_{channel}", f"last_seen_{channel}"
    Customer.objects.filter(pk=customer.pk).filter(Q(**{f"{first}__isnull": True}) | Q(**{f"{first}__gt": at})).update(**{first: at})
    Customer.objects.filter(pk=customer.pk).filter(Q(**{f"{last}__isnull": True}) | Q(**{f"{last}__lt": at})).update(**{last: at})
    link, created = CustomerDevice.objects.get_or_create(customer=customer, device=device, defaults={"first_seen": at, "last_seen": at})
    if not created:
        CustomerDevice.objects.filter(pk=link.pk, first_seen__gt=at).update(first_seen=at)
        CustomerDevice.objects.filter(pk=link.pk, last_seen__lt=at).update(last_seen=at)


# --- Visibility --------------------------------------------------------------------------------------------------


def sees_everything(user) -> bool:
    return bool(user and user.is_authenticated and (
        user.is_superuser or user.has_perm("directory.manage_customers")
        or user.has_perm("calls.access_all_devices") or user.has_perm("sms.access_all_devices")
    ))


def readable_device_ids(user) -> set:
    """Phones this user can read in any phone platform (SMS or Calls)."""
    ids: set = set()
    from modules.sms.services.access import accessible_devices as sms_devices

    ids.update(sms_devices(user).values_list("pk", flat=True))
    try:
        from modules.calls.services.access import accessible_devices as call_devices
    except ImportError:  # pragma: no cover - Calls not installed
        return ids
    ids.update(call_devices(user).values_list("pk", flat=True))
    return ids


def can_use_directory(user) -> bool:
    if not (user and user.is_authenticated):
        return False
    from modules.platforms.services import is_platform_enabled

    platforms = [key for key in ("sms", "calls") if user.has_perm(f"{key}.access") and is_platform_enabled(key)]
    return bool(platforms)


def accessible_customers(user) -> QuerySet[Customer]:
    if not can_use_directory(user):
        return Customer.objects.none()
    qs = Customer.objects.filter(merged_into__isnull=True)
    if sees_everything(user):
        return qs
    return qs.filter(device_links__device_id__in=readable_device_ids(user)).distinct()


def get_customer(user, customer_id) -> Customer:
    try:
        customer_id = int(customer_id)
    except (TypeError, ValueError):
        customer_id = 0
    customer = accessible_customers(user).select_related("owner").filter(pk=customer_id).first()
    if not customer:
        raise ApiError("not_found", "This customer was not found.", status.HTTP_404_NOT_FOUND)
    return customer


def can_edit(user, customer: Customer) -> bool:
    """Directory managers edit everything; Calls users who may annotate on a linked phone edit that customer."""
    if user.is_superuser or user.has_perm("directory.manage_customers"):
        return True
    try:
        from modules.calls.services.access import devices_with
    except ImportError:  # pragma: no cover
        return False
    linked = set(customer.device_links.values_list("device_id", flat=True))
    return bool(linked & set(devices_with(user, "annotate").values_list("pk", flat=True)))


def require_edit(user, customer: Customer) -> None:
    if not can_edit(user, customer):
        raise ApiError("permission_denied", "You don't have permission to edit this customer.", status.HTTP_403_FORBIDDEN)


def require_manage(user) -> None:
    if not (user.is_superuser or user.has_perm("directory.manage_customers")):
        raise ApiError("permission_denied", "Only directory managers can do this.", status.HTTP_403_FORBIDDEN)


# --- Edits ---------------------------------------------------------------------------------------------------------


def clean_tags(tags) -> list[str]:
    seen_tags, result = set(), []
    for tag in tags or []:
        text = str(tag).strip()[:40]
        if text and text.lower() not in seen_tags:
            seen_tags.add(text.lower())
            result.append(text)
    return result[:MAX_TAGS]


def notes(customer: Customer) -> str:
    return decrypt_text(customer.encrypted_notes)


def create(user, values: dict, request=None) -> Customer:
    require_manage(user)
    raw = (values.get("number") or "").strip()
    key, kind = key_for(raw)
    if not key:
        raise ApiError("validation_error", "Enter a phone number, short code or sender name.", errors={"number": ["Required."]})
    if Customer.objects.filter(key=key).exists():
        raise ApiError("conflict", "This number is already in the directory.", status.HTTP_409_CONFLICT, errors={"number": ["Already in the directory."]})
    customer = Customer.objects.create(
        key=key, number_e164=key if kind == "number" and key.startswith("+") else "", raw_sender=raw[:64], created_by=user,
        **_fields(values),
    )
    record("directory.create", request=request, actor=user, target_type="customer", target_id=customer.pk, metadata={"number": mask(key)})
    return customer


def _fields(values: dict) -> dict:
    result = {}
    for name in ("display_name", "organisation"):
        if name in values:
            result[name] = (values[name] or "").strip()[:120]
    if "tags" in values:
        result["tags"] = clean_tags(values["tags"])
    if "notes" in values:
        result["encrypted_notes"] = encrypt_text((values["notes"] or "").strip()[:4000])
    for flag in ("caller_id_all_phones", "auto_sms_opt_out"):
        if flag in values:
            result[flag] = bool(values[flag])
    if "owner" in values:
        result["owner"] = values["owner"]
    return result


def update(user, customer: Customer, values: dict, request=None) -> Customer:
    require_edit(user, customer)
    fields = _fields(values)
    if "caller_id_all_phones" in fields and fields["caller_id_all_phones"] != customer.caller_id_all_phones:
        require_manage(user)  # sends the name to every phone
    changed = [name for name, value in fields.items() if getattr(customer, name) != value]
    for name in changed:
        setattr(customer, name, fields[name])
    if changed:
        customer.save(update_fields=[*changed, "updated_at"])
        record("directory.update", request=request, actor=user, target_type="customer", target_id=customer.pk,
               metadata={"number": mask(customer.key), "fields": sorted("notes" if n == "encrypted_notes" else n for n in changed)})
    return customer


def delete(user, customer: Customer, request=None) -> None:
    require_manage(user)
    record("directory.delete", request=request, actor=user, target_type="customer", target_id=customer.pk, metadata={"number": mask(customer.key)})
    customer.delete()


@transaction.atomic
def merge(user, target: Customer, sources: list[Customer], request=None) -> Customer:
    """Fold `sources` into `target`: every SMS conversation, call, callback and phone link moves; tags are joined, notes
    appended, seen times widened. Sources stay as aliases (`merged_into`) so their numbers keep resolving to `target`."""
    require_manage(user)
    sources = [s for s in sources if s.pk != target.pk]
    if not sources:
        raise ApiError("validation_error", "Choose at least one other customer to merge.")
    ids = [s.pk for s in sources]
    from modules.sms.models import Conversation

    Conversation.objects.filter(customer_id__in=ids).update(customer=target)
    try:
        from modules.calls.models import CallbackTask, CallRecord
    except ImportError:  # pragma: no cover
        pass
    else:
        CallRecord.objects.filter(customer_id__in=ids).update(customer=target)
        CallbackTask.objects.filter(customer_id__in=ids).update(customer=target)
    for link in CustomerDevice.objects.filter(customer_id__in=ids):
        seen_at = [link.first_seen, link.last_seen]
        existing = CustomerDevice.objects.filter(customer=target, device_id=link.device_id).first()
        if existing:
            CustomerDevice.objects.filter(pk=existing.pk).update(first_seen=min(existing.first_seen, seen_at[0]), last_seen=max(existing.last_seen, seen_at[1]))
            link.delete()
        else:
            CustomerDevice.objects.filter(pk=link.pk).update(customer=target)
    texts = [notes(target)] + [f"[{s.display_name or display_number(s.key)}] {notes(s)}" for s in sources if s.encrypted_notes]
    target.encrypted_notes = encrypt_text("\n\n".join(t for t in texts if t)[:8000])
    target.tags = clean_tags([*target.tags, *(tag for s in sources for tag in s.tags)])
    target.display_name = target.display_name or next((s.display_name for s in sources if s.display_name), "")
    target.organisation = target.organisation or next((s.organisation for s in sources if s.organisation), "")
    for channel in CHANNELS:
        for attr, pick in ((f"first_seen_{channel}", min), (f"last_seen_{channel}", max)):
            values = [v for v in [getattr(target, attr), *(getattr(s, attr) for s in sources)] if v]
            setattr(target, attr, pick(values) if values else None)
    target.save()
    # Flatten: anything merged into a source now points straight at the target.
    Customer.objects.filter(merged_into_id__in=ids).update(merged_into=target)
    Customer.objects.filter(pk__in=ids).update(merged_into=target, encrypted_notes="")
    record("directory.merge", request=request, actor=user, target_type="customer", target_id=target.pk,
           metadata={"merged": ids, "numbers": [mask(s.key) for s in sources]})
    return target


def numbers_of(customer: Customer) -> list[str]:
    """The customer's own key and those of the entries merged into it."""
    return [customer.key, *Customer.objects.filter(merged_into=customer).values_list("key", flat=True)]
