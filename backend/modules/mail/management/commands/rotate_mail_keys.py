"""Re-encrypt every stored credential with the newest key in MAIL_TOKEN_KEYS (put the new key first)."""

from django.core.management.base import BaseCommand
from django.db import transaction

from common.crypto import rotate
from modules.identity.models import User
from modules.mail.models import Mailbox, WorkspaceDomain


class Command(BaseCommand):
    help = "Rotate encrypted mailbox credentials, service-account keys and TOTP secrets to the newest key."

    @transaction.atomic
    def handle(self, *args, **options):
        counts = {"mailboxes": 0, "workspace": 0, "totp": 0}
        for mailbox in Mailbox.objects.exclude(encrypted_credentials=""):
            Mailbox.objects.filter(pk=mailbox.pk).update(encrypted_credentials=rotate(mailbox.encrypted_credentials))
            counts["mailboxes"] += 1
        for row in WorkspaceDomain.objects.all():
            WorkspaceDomain.objects.filter(pk=row.pk).update(encrypted_service_account=rotate(row.encrypted_service_account))
            counts["workspace"] += 1
        for user in User.objects.exclude(totp_secret=""):
            User.objects.filter(pk=user.pk).update(totp_secret=rotate(user.totp_secret))
            counts["totp"] += 1
        self.stdout.write(self.style.SUCCESS(f"Rotated: {counts}"))
