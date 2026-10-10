from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from .models import Mailbox, MailboxStatus, Message


@shared_task(name="mail.sync_mailbox", ignore_result=True)
def sync_mailbox_task(mailbox_id: int, full: bool = False) -> str:
    from .services.sync import sync_mailbox

    return sync_mailbox(mailbox_id, full=full)


@shared_task(name="mail.sync_all_mailboxes", ignore_result=True)
def sync_all_mailboxes() -> int:
    ids = list(Mailbox.objects.filter(status__in=[MailboxStatus.CONNECTED, MailboxStatus.ERROR, MailboxStatus.SYNCING]).values_list("pk", flat=True))
    for mailbox_id in ids:
        sync_mailbox_task.delay(mailbox_id)
    return len(ids)


@shared_task(name="mail.send_scheduled", ignore_result=True)
def send_scheduled_task(item_id: int) -> str:
    from .services.send import send_now

    return send_now(item_id)


@shared_task(name="mail.dispatch_due_sends", ignore_result=True)
def dispatch_due_sends() -> int:
    from .services.send import dispatch_due

    return dispatch_due()


@shared_task(name="mail.wake_snoozed_threads", ignore_result=True)
def wake_snoozed_threads() -> int:
    from .services.actions import wake_snoozed

    return wake_snoozed()


@shared_task(name="mail.evict_cached_bodies", ignore_result=True)
def evict_cached_bodies() -> int:
    from datetime import timedelta

    from django.conf import settings

    cutoff = timezone.now() - timedelta(days=settings.MAIL_BODY_CACHE_DAYS)
    return Message.objects.filter(Q(body_cached_at__lt=cutoff)).update(body_html=None, body_text=None, body_meta={}, body_cached_at=None)
