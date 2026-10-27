"""Object-level mailbox permissions. Every mail endpoint goes through these helpers.

Admins (users with `mail.access_all_mailboxes`, and super admins) can do everything in every mailbox.
Everyone else needs a `MailboxAccess` row; its flags decide read / send / delete / manage.
"""

from __future__ import annotations

from django.db.models import Count, Q, QuerySet
from rest_framework import status

from common.errors import ApiError
from modules.platforms.services import is_platform_enabled

from ..models import Mailbox, MailboxAccess, Thread

READ, SEND, DELETE, MANAGE = "read", "send", "delete", "manage"
FLAGS = {READ: "can_read", SEND: "can_send", DELETE: "can_delete", MANAGE: "can_manage"}


def is_mail_admin(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_superuser or user.has_perm("mail.access_all_mailboxes")))


def can_use_mail(user) -> bool:
    return bool(user and user.is_authenticated and user.has_perm("mail.access") and is_platform_enabled("gmail"))


def accessible_mailboxes(user, perm: str = READ) -> QuerySet[Mailbox]:
    if not can_use_mail(user):
        return Mailbox.objects.none()
    qs = Mailbox.objects.select_related("office")
    if is_mail_admin(user):
        return qs
    return qs.filter(access__user=user, **{f"access__{FLAGS[perm]}": True}).distinct()


def permissions_for(user, mailbox: Mailbox) -> dict[str, bool]:
    if is_mail_admin(user):
        return {key: True for key in FLAGS}
    row = MailboxAccess.objects.filter(user=user, mailbox=mailbox).first() if can_use_mail(user) else None
    return {key: bool(row and getattr(row, flag)) for key, flag in FLAGS.items()}


def get_mailbox(user, mailbox_id, perm: str = READ) -> Mailbox:
    """The mailbox, or 404 when the user cannot read it (never reveal that it exists), or 403 for missing rights."""
    try:
        mailbox_id = int(mailbox_id)
    except (TypeError, ValueError):
        raise ApiError("not_found", "This mailbox was not found.", status.HTTP_404_NOT_FOUND) from None
    mailbox = accessible_mailboxes(user, READ).filter(pk=mailbox_id).first()
    if not mailbox:
        raise ApiError("not_found", "This mailbox was not found.", status.HTTP_404_NOT_FOUND)
    if perm != READ and not permissions_for(user, mailbox)[perm]:
        raise ApiError("permission_denied", PERM_MESSAGES[perm], status.HTTP_403_FORBIDDEN)
    return mailbox


PERM_MESSAGES = {
    SEND: "You don't have permission to send from this mailbox.",
    DELETE: "You don't have permission to delete mail in this mailbox.",
    MANAGE: "You don't have permission to manage this mailbox.",
    READ: "You don't have permission to read this mailbox.",
}


def accessible_threads(user) -> QuerySet[Thread]:
    return Thread.objects.filter(mailbox__in=accessible_mailboxes(user, READ).values("pk"))


def get_threads(user, thread_ids: list[int], perm: str = READ) -> list[Thread]:
    """Threads the user may act on. Any id they cannot see makes the whole request fail (no partial leaks)."""
    ids = {int(t) for t in thread_ids}
    threads = list(accessible_threads(user).filter(pk__in=ids).select_related("mailbox", "mailbox__office"))
    if len(threads) != len(ids):
        raise ApiError("not_found", "Some conversations were not found. Refresh and try again.", status.HTTP_404_NOT_FOUND)
    if perm != READ:
        for mailbox in {t.mailbox for t in threads}:
            if not permissions_for(user, mailbox)[perm]:
                raise ApiError("permission_denied", PERM_MESSAGES[perm], status.HTTP_403_FORBIDDEN)
    return threads


def mailbox_summaries(user) -> list[dict]:
    """Small mailbox list for the switcher, with inbox unread counts."""
    mailboxes = accessible_mailboxes(user).annotate(
        unread=Count("threads", filter=Q(threads__is_unread=True, threads__label_ids__contains=["INBOX"]))
    )
    admin = is_mail_admin(user)
    rows = {row.mailbox_id: row for row in MailboxAccess.objects.filter(user=user)} if not admin else {}
    result = []
    for mailbox in mailboxes:
        if admin:
            perms = {key: True for key in FLAGS}
        else:
            row = rows.get(mailbox.pk)
            perms = {key: bool(row and getattr(row, flag)) for key, flag in FLAGS.items()}
        result.append(
            {
                "id": mailbox.pk,
                "email": mailbox.email,
                "name": mailbox.name,
                "office": {"id": mailbox.office_id, "name": mailbox.office.name, "colour": mailbox.office.colour},
                "colour": mailbox.colour,
                "provider": mailbox.provider,
                "status": mailbox.status,
                "unread": mailbox.unread,
                "permissions": perms,
            }
        )
    return result
