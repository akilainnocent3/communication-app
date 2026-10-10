from django.conf import settings

from .base import MailProvider, ProviderError


def get_provider(mailbox) -> MailProvider:
    """The provider implementation for a mailbox. Imports are lazy so Google libraries load only when used."""
    if mailbox.provider == "fake":
        if not settings.MAIL_ENABLE_FAKE_PROVIDER:
            raise ProviderError("provider_disabled", "Demo mailboxes are disabled on this server.")
        from .fake import FakeMailProvider

        return FakeMailProvider(mailbox)
    if mailbox.provider == "gmail_oauth":
        from .gmail_api import GmailApiProvider

        return GmailApiProvider(mailbox)
    if mailbox.provider == "workspace_delegation":
        from .workspace_delegation import WorkspaceDelegationProvider

        return WorkspaceDelegationProvider(mailbox)
    if mailbox.provider == "imap_smtp":
        from .imap_smtp import ImapSmtpProvider

        return ImapSmtpProvider(mailbox)
    raise ProviderError("unknown_provider", f"Unknown mail provider '{mailbox.provider}'.")
