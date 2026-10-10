"""Google Workspace domain-wide delegation: same Gmail API, credentials impersonate the mailbox user.

A super admin uploads the service-account key once (Settings → Integrations → Google Workspace) and the
Workspace admin authorises its client id for the scopes. Every mailbox in the domain then connects with no
consent screen.
"""

from __future__ import annotations

from django.conf import settings

from common.crypto import decrypt_json

from ..models import WorkspaceDomain
from .base import AuthError, Capabilities
from .gmail_api import GmailApiProvider, translate_error


def delegated_credentials(domain: WorkspaceDomain, subject: str):
    from google.oauth2 import service_account

    info = decrypt_json(domain.encrypted_service_account)
    scopes = [s for s in settings.GOOGLE_OAUTH_SCOPES if s.startswith("https://")]
    return service_account.Credentials.from_service_account_info(info, scopes=scopes).with_subject(subject)


def delegation_scopes() -> str:
    """The exact comma-separated scope string to paste into Google Admin → Domain-wide delegation."""
    return ",".join(s for s in settings.GOOGLE_OAUTH_SCOPES if s.startswith("https://"))


class WorkspaceDelegationProvider(GmailApiProvider):
    key = "workspace_delegation"

    def capabilities(self) -> Capabilities:
        return Capabilities(revoke=False)

    def _domain(self) -> WorkspaceDomain:
        domain = self.mailbox.email.rsplit("@", 1)[-1].lower()
        row = WorkspaceDomain.objects.filter(domain=domain).first()
        if not row:
            raise AuthError(f"Domain-wide delegation is not configured for {domain}.")
        return row

    def credentials(self):
        return delegated_credentials(self._domain(), self.mailbox.email)

    def service(self):
        if self._service is None:
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            creds = self.credentials()
            try:
                creds.refresh(Request())
            except Exception as exc:  # noqa: BLE001
                raise translate_error(exc) from None
            self._service = build("gmail", "v1", credentials=creds, cache_discovery=False, static_discovery=True)
        return self._service

    def revoke(self) -> None:
        return None  # nothing per-mailbox to revoke; remove the delegation in Google Admin instead
