from django.apps import AppConfig


class DevicesConfig(AppConfig):
    """Company phones enrolled into Communication Manager: identity, enrollment, device auth, heartbeat and push.

    Shared by every phone-based platform (SMS today, Calls later). Platform data lives in the platform's own app.
    """

    name = "modules.devices"
    label = "devices"
    verbose_name = "Devices"

    def ready(self):
        from . import schema  # noqa: F401 - registers the OpenAPI auth extension
