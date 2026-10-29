"""The automatic SMS after a missed call ("Sorry we missed your call…"), off by default (CallSettings.auto_sms_enabled).

Sent by the phone that missed the call, through the SMS outbound queue (sms.services.outbound.queue_automatic), so every
SMS rule applies: no short codes, sender IDs or premium numbers, blocked numbers skipped, the phone's rate and daily cap.
On top: only for calls that just happened (never for history), optionally only after hours, at most N per number per
day, a cool-down per number, never to a customer who opted out, never once the call was already returned.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from common.errors import ApiError
from modules.devices.services.phone import mask

from ..models import AutoSmsLog, CallRecord, CallSettings

log = logging.getLogger(__name__)

FRESH = timedelta(minutes=30)


def skip_reason(call: CallRecord, config: CallSettings, now=None) -> str | None:
    now = now or timezone.now()
    if not config.auto_sms_enabled:
        return "disabled"
    if not call.is_missed or not call.number_e164.startswith("+"):
        return "not_applicable"
    if call.ended_at is None or now - call.ended_at > FRESH:
        return "not_fresh"
    if call.returned_at is not None:
        return "returned"
    if sms_device(call) is None:
        return "no_sms_phone"
    if config.auto_sms_after_hours_only and not call.is_after_hours:
        return "office_hours"
    if call.customer_id and call.customer.auto_sms_opt_out:
        return "opted_out"
    recent = AutoSmsLog.objects.filter(number_e164=call.number_e164)
    if recent.filter(created_at__gte=now - timedelta(days=1)).count() >= config.auto_sms_per_number_per_day:
        return "daily_limit"
    if config.auto_sms_cooldown_hours and recent.filter(created_at__gte=now - timedelta(hours=config.auto_sms_cooldown_hours)).exists():
        return "cooldown"
    return None


def sms_device(call: CallRecord):
    """The phone that sends the SMS: OCM Messages on the same handset as the OCM Phone that missed the call (its
    companion), or the call's own device when it is an SMS phone (simulated or older data)."""
    from modules.devices.models import DeviceStatus

    device = call.device
    if not device.has("sms"):
        device = device.companion if device.companion_id else None
    if device is None or device.status != DeviceStatus.ACTIVE or not device.has("sms"):
        return None
    return device


def maybe_send(call: CallRecord) -> bool:
    config = CallSettings.load()
    reason = skip_reason(call, config)
    if reason:
        return False
    from modules.sms.services.outbound import queue_automatic

    body = config.auto_sms_template.replace("{company}", settings.COMPANY_NAME)
    try:
        with transaction.atomic():
            sender = sms_device(call)
            entry = AutoSmsLog.objects.create(number_e164=call.number_e164, device=sender, call=call)
            message = queue_automatic(sender, call.number_e164, body, reason="missed_call")
            AutoSmsLog.objects.filter(pk=entry.pk).update(message_id=message.pk)
    except IntegrityError:
        return False  # already sent for this call
    except ApiError as exc:
        log.info("missed-call SMS to %s not sent: %s", mask(call.number_e164), exc.code)
        return False
    return True
