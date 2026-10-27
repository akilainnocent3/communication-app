from django.apps import AppConfig


def _session_data(user) -> dict:
    """Extra data for GET /auth/me/: the phones this user can open (for the device switcher)."""
    from .services.access import device_summaries

    return {"devices": device_summaries(user)}


class SmsConfig(AppConfig):
    name = "modules.sms"
    label = "sms"
    verbose_name = "SMS"

    def ready(self):
        from modules.platforms.registry import PlatformSpec, registry

        registry.register(PlatformSpec(key="sms", name="SMS", permission="sms.access", order=20, session_data=_session_data))
