"""`manage.py check --deploy`: the Redis roles are configured as decision 59 requires."""

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register


def _redis_config(url: str) -> dict:
    import redis

    client = redis.Redis.from_url(url, socket_connect_timeout=3, socket_timeout=3)
    return {**client.config_get("maxmemory-policy"), **client.config_get("appendonly")}


@register(Tags.caches, deploy=True)
def check_redis_roles(app_configs, **kwargs):
    if not settings.REDIS_URL:
        return [Error("REDIS_URL is not set: nonces, lockouts and the task queue would live in each process's memory.", id="cm.E001")]
    problems = []
    try:
        config = _redis_config(settings.REDIS_URL)
    except Exception as exc:  # noqa: BLE001
        return [Error(f"Cannot read the broker/security Redis configuration ({type(exc).__name__}).", id="cm.E002")]
    if config.get("maxmemory-policy") != "noeviction":
        problems.append(Error(
            f"The broker/security Redis evicts keys (maxmemory-policy={config.get('maxmemory-policy')}): queued tasks and replay nonces could be dropped.",
            hint="Run it with --maxmemory-policy noeviction (docker-compose.yml).", id="cm.E003"))
    if config.get("appendonly") != "yes":
        problems.append(Warning("The broker/security Redis has no AOF: queued tasks are lost on a restart.", hint="Run it with --appendonly yes.", id="cm.W001"))
    if not settings.REDIS_CACHE_URL:
        problems.append(Warning("REDIS_CACHE_URL is not set: cache data shares the noeviction Redis and can fill it.", hint="Point it at the allkeys-lru instance.", id="cm.W002"))
    return problems
