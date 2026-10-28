from celery import shared_task


@shared_task(name="calls.retention_purge", ignore_result=True)
def retention_purge() -> int:
    from .services.retention import purge

    return purge()


@shared_task(name="calls.repair_rollups", ignore_result=True)
def repair_rollups() -> int:
    from .services.rollups import repair_recent

    return repair_recent()


@shared_task(name="calls.expire_callbacks", ignore_result=True)
def expire_callbacks() -> int:
    from .services.callbacks import expire

    return expire()


@shared_task(name="calls.simulator_tick", ignore_result=True)
def simulator_tick() -> int:
    from django.conf import settings

    if not settings.SMS_ENABLE_SIMULATOR:
        return 0
    from .services.simulator import tick_all

    return tick_all()
