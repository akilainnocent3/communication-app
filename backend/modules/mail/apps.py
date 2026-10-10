from django.apps import AppConfig


def _session_data(user) -> dict:
    """Extra data for GET /auth/me/: the mailboxes this user can open (for the mailbox switcher)."""
    from .services.access import mailbox_summaries

    return {"mailboxes": mailbox_summaries(user)}


class MailConfig(AppConfig):
    name = "modules.mail"
    label = "mail"
    verbose_name = "Gmail"

    def ready(self):
        from modules.platforms.registry import PlatformSpec, registry

        registry.register(PlatformSpec(key="gmail", name="Gmail", permission="mail.access", order=10, session_data=_session_data))
