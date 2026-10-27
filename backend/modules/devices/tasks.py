from celery import shared_task


@shared_task(name="devices.push", ignore_result=True)
def push_task(device_id: str, kind: str = "sync") -> bool:
    from .services.push import wake

    return wake(device_id, kind)


@shared_task(name="devices.refresh_health", ignore_result=True)
def refresh_health() -> int:
    from .services.health import refresh_all

    return refresh_all()


@shared_task(name="devices.prune", ignore_result=True)
def prune() -> dict:
    from .services.health import prune as run

    return run()
