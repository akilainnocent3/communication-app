from celery import shared_task


@shared_task(name="sms.dispatch_due", ignore_result=True)
def dispatch_due() -> int:
    from .services.outbound import dispatch_due as run

    return run()


@shared_task(name="sms.expire_outbound", ignore_result=True)
def expire_outbound() -> dict:
    from .services.outbound import expire_stale

    return expire_stale()


@shared_task(name="sms.retention_purge", ignore_result=True)
def retention_purge() -> int:
    from .services.retention import purge

    return purge()


@shared_task(name="sms.media_cleanup", ignore_result=True)
def media_cleanup() -> int:
    from .services.media import cleanup_orphans

    return cleanup_orphans()


@shared_task(name="sms.simulator_tick", ignore_result=True)
def simulator_tick() -> int:
    from django.conf import settings

    if not settings.SMS_ENABLE_SIMULATOR:
        return 0
    from .services.simulator import tick_all

    return tick_all()
