from django.apps import AppConfig


def _session_data(user) -> dict:
    """Extra data for GET /auth/me/: the phones this user can open in Calls (for the device switcher)."""
    from .services.access import device_summaries

    return {"devices": device_summaries(user)}


class CallsConfig(AppConfig):
    name = "modules.calls"
    label = "calls"
    verbose_name = "Calls"

    def ready(self):
        from modules.platforms.registry import PlatformSpec, registry

        from . import events  # noqa: F401 - registers the call.* sync event types

        registry.register(PlatformSpec(key="calls", name="Calls", permission="calls.access", order=30, session_data=_session_data))
