"""Call-back tasks: an admin asks the holder of a phone to call a customer.

The server can never place a carrier call. A task is pushed to the phone (FCM wake-up "callbacks", then the phone
pulls GET calls/callbacks/), shown as a notification and in the app's list, and placed only when the staff member taps
Call (origin=callback_task). States: open → notified → dialed → done, or cancelled / expired.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import status

from common.devicecrypto import decrypt_text, encrypt_text
from common.errors import ApiError
from modules.audit.services import record
from modules.devices.models import DeviceStatus
from modules.devices.services.phone import address_key, mask

from ..models import CallbackTask, CallRecord, CallSettings
from . import access

MAX_DUE_DAYS = 30


def reason(task: CallbackTask) -> str:
    return decrypt_text(task.encrypted_reason)


def _wake(device_id) -> None:
    from modules.devices.tasks import push_task

    transaction.on_commit(lambda: push_task.delay(str(device_id), "callbacks"))


def create(user, *, device_id, number: str = "", call_id=None, customer_id=None, due_at=None, priority: str = "normal", reason_text: str = "",
           request=None) -> CallbackTask:
    device = access.get_device(user, device_id, access.ASSIGN)
    if device.status != DeviceStatus.ACTIVE:
        raise ApiError("device_inactive", "This phone is suspended or removed.", status.HTTP_409_CONFLICT)
    source = access.get_call(user, call_id) if call_id else None
    customer = None
    if customer_id:
        from modules.directory.services.customers import get_customer

        customer = get_customer(user, customer_id)
    raw = number or (source.number_e164 if source else "") or (customer.number_e164 if customer else "")
    key = address_key(raw) if raw else ""
    if not key or "*" in raw or "#" in raw:
        raise ApiError("validation_error", "Enter the number to call back.", errors={"number": ["A phone number is required."]})
    if customer is None:
        from modules.directory.models import Customer

        customer = Customer.objects.filter(key=key, merged_into__isnull=True).first() or (source.customer if source else None)
    now = timezone.now()
    due_at = due_at or now
    if due_at > now + timedelta(days=MAX_DUE_DAYS):
        raise ApiError("validation_error", f"Choose a time within {MAX_DUE_DAYS} days.", errors={"due_at": ["Too far ahead."]})
    expiry = timedelta(hours=CallSettings.load().callback_expiry_hours)
    task = CallbackTask.objects.create(
        device=device, customer=customer, number_e164=key, assigned_by=user, assignee=device.assigned_to, source_call=source,
        due_at=due_at, priority=priority, encrypted_reason=encrypt_text(reason_text.strip()[:500]), expires_at=max(due_at, now) + expiry,
    )
    record("calls.callback_create", request=request, actor=user, target_type="callback", target_id=task.pk,
           metadata={"device": device.code, "number": mask(key), "priority": priority, "due_at": due_at.isoformat()})
    _wake(device.pk)
    return task


def cancel(user, task: CallbackTask, request=None) -> CallbackTask:
    if not access.permissions_for(user, task.device)[access.ASSIGN]:
        raise ApiError("permission_denied", access.PERM_MESSAGES[access.ASSIGN], status.HTTP_403_FORBIDDEN)
    if task.state not in CallbackTask.ACTIVE_STATES:
        raise ApiError("conflict", "This call-back is already finished.", status.HTTP_409_CONFLICT)
    task.state, task.cancelled_at = CallbackTask.CANCELLED, timezone.now()
    task.save(update_fields=["state", "cancelled_at", "updated_at"])
    record("calls.callback_cancel", request=request, actor=user, target_type="callback", target_id=task.pk, metadata={"device": task.device.code})
    _wake(task.device_id)
    return task


def update(user, task: CallbackTask, values: dict, request=None) -> CallbackTask:
    """Reassign to another phone, reschedule, change the priority or reason, or mark done from the admin."""
    if not access.permissions_for(user, task.device)[access.ASSIGN]:
        raise ApiError("permission_denied", access.PERM_MESSAGES[access.ASSIGN], status.HTTP_403_FORBIDDEN)
    if task.state not in CallbackTask.ACTIVE_STATES:
        raise ApiError("conflict", "This call-back is already finished.", status.HTTP_409_CONFLICT)
    changed, old_device = {}, task.device_id
    if values.get("device") and str(values["device"]) != str(task.device_id):
        device = access.get_device(user, values["device"], access.ASSIGN)
        task.device, task.assignee, task.state, task.notified_at = device, device.assigned_to, CallbackTask.OPEN, None
        changed["device"] = device.code
    if "due_at" in values and values["due_at"]:
        task.due_at = values["due_at"]
        changed["due_at"] = task.due_at.isoformat()
    if values.get("priority"):
        task.priority = changed["priority"] = values["priority"]
    if "reason" in values:
        task.encrypted_reason = encrypt_text((values["reason"] or "").strip()[:500])
        changed["reason"] = "changed"
    if values.get("state") == CallbackTask.DONE:
        task.state, task.done_at = CallbackTask.DONE, timezone.now()
        changed["state"] = "done"
    task.save()
    if changed:
        record("calls.callback_update", request=request, actor=user, target_type="callback", target_id=task.pk, metadata=changed)
        _wake(task.device_id)
        if old_device != task.device_id:
            _wake(old_device)
    return task


def bulk(user, ids: list[int], action: str, values: dict, request=None) -> list[CallbackTask]:
    tasks = [access.get_callback(user, pk) for pk in ids]
    result = []
    for task in tasks:
        result.append(cancel(user, task, request=request) if action == "cancel" else update(user, task, values, request=request))
    return result


def for_phone(device, now=None) -> list[CallbackTask]:
    """What the phone shows: active tasks that are due (or due within a day), newest due first."""
    now = now or timezone.now()
    return list(CallbackTask.objects.filter(device=device, state__in=CallbackTask.ACTIVE_STATES, due_at__lte=now + timedelta(days=1))
                .select_related("customer", "assigned_by").order_by("due_at")[:100])


def expire(now=None) -> int:
    now = now or timezone.now()
    stale = CallbackTask.objects.filter(state__in=CallbackTask.ACTIVE_STATES, expires_at__lt=now)
    device_ids = set(stale.values_list("device_id", flat=True))
    count = stale.update(state=CallbackTask.EXPIRED)
    for device_id in device_ids:
        from modules.devices.tasks import push_task

        push_task.delay(str(device_id), "callbacks")
    return count


def suggest_for(call: CallRecord) -> dict:
    return {"number": call.number_e164, "device": str(call.device_id), "customer": call.customer_id}
