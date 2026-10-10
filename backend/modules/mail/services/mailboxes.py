"""Adding, connecting (IMAP, Workspace), disconnecting and removing mailboxes; access management."""

from __future__ import annotations

import random

from django.db import transaction
from django.utils import timezone
from rest_framework import status

from common.crypto import encrypt_json
from common.errors import ApiError
from modules.audit.services import record

from ..models import Draft, Label, Mailbox, MailboxAccess, MailboxStatus, Thread, WorkspaceDomain
from ..providers import get_provider
from ..providers.base import ProviderError
from . import connect

PALETTE = ["#3758f9", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316", "#6366f1"]


def create_mailbox(user, *, office, email: str, display_name: str = "", colour: str = "", provider: str | None = None, request=None) -> tuple[Mailbox, dict]:
    email = email.strip().lower()
    if Mailbox.objects.filter(email__iexact=email).exists():
        raise ApiError("mailbox_exists", "This mailbox is already added.", status.HTTP_409_CONFLICT, errors={"email": ["Already added."]})
    detection = connect.detect(email)
    if provider == "fake":
        detection = connect.Detection("fake", "Demo mailbox with sample mail.", email.rsplit("@", 1)[-1], [])
    elif not detection.supported:
        raise ApiError("unsupported_provider", detection.reason, errors={"email": [detection.reason]})
    mailbox = Mailbox.objects.create(
        office=office, email=email, display_name=display_name.strip(), colour=colour or random.choice(PALETTE),
        provider=detection.provider, status=MailboxStatus.PENDING,
        server_settings={"mx": detection.mx, **({"imap_defaults": detection.imap_defaults} if detection.imap_defaults else {})},
    )
    record("mailbox.create", request=request, actor=user, mailbox=mailbox, target_type="mailbox", target_id=mailbox.pk, metadata={"provider": mailbox.provider, "office": office.name})
    if mailbox.provider == "workspace_delegation":
        connect_workspace(user, mailbox, request=request)
    elif mailbox.provider == "fake":
        from .demo import seed_mailbox

        seed_mailbox(mailbox, threads=40)
        Mailbox.objects.filter(pk=mailbox.pk).update(status=MailboxStatus.CONNECTED, connected_at=timezone.now(), connected_by=user)
        _start_sync(mailbox, full=True)
    mailbox.refresh_from_db()
    return mailbox, detection.as_dict()


def _start_sync(mailbox: Mailbox, full: bool = False) -> None:
    from ..tasks import sync_mailbox_task

    transaction.on_commit(lambda: sync_mailbox_task.delay(mailbox.pk, full))


def connect_workspace(user, mailbox: Mailbox, request=None) -> Mailbox:
    domain = mailbox.email.rsplit("@", 1)[-1].lower()
    if not WorkspaceDomain.objects.filter(domain=domain).exists():
        raise ApiError("workspace_not_configured", f"Company-wide access is not set up for {domain}.")
    mailbox.provider = "workspace_delegation"
    try:
        profile = get_provider(mailbox).get_profile()
    except ProviderError as exc:
        Mailbox.objects.filter(pk=mailbox.pk).update(provider="gmail_oauth", sync_error=str(exc))
        raise ApiError("workspace_failed", f"Google Workspace refused access to {mailbox.email}: {exc}. Use 'Connect with Google' instead.") from exc
    if (profile.get("emailAddress") or "").lower() != mailbox.email:
        raise ApiError("workspace_failed", "Google Workspace opened a different mailbox. Check the address.")
    Mailbox.objects.filter(pk=mailbox.pk).update(provider="workspace_delegation", status=MailboxStatus.CONNECTED, sync_error="", connected_by=user, connected_at=timezone.now())
    record("mailbox.connect", request=request, actor=user, mailbox=mailbox, target_type="mailbox", target_id=mailbox.pk, metadata={"via": "workspace_delegation"})
    _start_sync(mailbox, full=True)
    mailbox.refresh_from_db()
    return mailbox


def save_imap(user, mailbox: Mailbox, *, server: dict, username: str, password: str, request=None) -> dict:
    """Test the settings, then store them (password encrypted) and start syncing."""
    from ..providers.imap_smtp import test_connection

    result = test_connection(server, username or mailbox.email, password)
    if not (result["imap"]["ok"] and result["smtp"]["ok"]):
        return {"ok": False, **result}
    with transaction.atomic():
        Mailbox.objects.filter(pk=mailbox.pk).update(
            provider="imap_smtp", server_settings={**(mailbox.server_settings or {}), **server},
            encrypted_credentials=encrypt_json({"username": username or mailbox.email, "password": password}),
            status=MailboxStatus.CONNECTED, sync_error="", history_id="", connected_by=user, connected_at=timezone.now(),
        )
        record("mailbox.connect", request=request, actor=user, mailbox=mailbox, target_type="mailbox", target_id=mailbox.pk, metadata={"via": "imap", "host": server.get("imap_host")})
        _start_sync(mailbox, full=True)
    return {"ok": True, **result}


@transaction.atomic
def disconnect(user, mailbox: Mailbox, request=None) -> Mailbox:
    """Revoke the provider credential, forget it and the synced mail. The mailbox stays so it can be reconnected."""
    try:
        get_provider(mailbox).revoke()
    except ProviderError:
        pass
    Thread.objects.filter(mailbox=mailbox).delete()
    Label.objects.filter(mailbox=mailbox).delete()
    Draft.objects.filter(mailbox=mailbox).delete()
    Mailbox.objects.filter(pk=mailbox.pk).update(
        encrypted_credentials="", granted_scopes=[], history_id="", sync_state={}, sync_progress={}, sync_error="",
        status=MailboxStatus.PENDING, last_synced_at=None, connected_at=None,
    )
    record("mailbox.disconnect", request=request, actor=user, mailbox=mailbox, target_type="mailbox", target_id=mailbox.pk)
    mailbox.refresh_from_db()
    return mailbox


@transaction.atomic
def delete_mailbox(user, mailbox: Mailbox, request=None) -> None:
    try:
        get_provider(mailbox).revoke()
    except ProviderError:
        pass
    record("mailbox.delete", request=request, actor=user, mailbox=mailbox, target_type="mailbox", target_id=mailbox.pk)
    mailbox.delete()


@transaction.atomic
def set_access(user, mailbox: Mailbox, entries: list[dict], request=None) -> list[MailboxAccess]:
    """Replace the explicit access list of a mailbox."""
    keep = []
    for entry in entries:
        row, _ = MailboxAccess.objects.update_or_create(
            user_id=entry["user"], mailbox=mailbox,
            defaults={k: bool(entry.get(k, False)) for k in ("can_read", "can_send", "can_delete", "can_manage")} | {"can_read": True},
        )
        keep.append(row.pk)
    MailboxAccess.objects.filter(mailbox=mailbox).exclude(pk__in=keep).delete()
    record("mailbox.access_update", request=request, actor=user, mailbox=mailbox, target_type="mailbox", target_id=mailbox.pk, metadata={"entries": entries})
    return list(MailboxAccess.objects.filter(mailbox=mailbox).select_related("user"))
