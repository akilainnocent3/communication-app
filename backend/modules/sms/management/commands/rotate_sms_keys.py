"""Re-encrypt SMS bodies, snippets and MMS files with the newest key in SMS_DATA_KEYS (put the new key first)."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from modules.sms.models import Conversation, Message, MessagePart, SimulatedDevice
from modules.sms.services.crypto import rotate_bytes, rotate_text


class Command(BaseCommand):
    help = "Rotate encrypted SMS data to the newest SMS_DATA_KEYS key. Safe to re-run."

    def handle(self, *args, **options):
        counts = {"messages": 0, "conversations": 0, "media": 0, "simulators": 0}
        for row in Message.objects.exclude(encrypted_body="").only("pk", "encrypted_body").iterator(chunk_size=1000):
            Message.objects.filter(pk=row.pk).update(encrypted_body=rotate_text(row.encrypted_body))
            counts["messages"] += 1
        for row in Conversation.objects.exclude(encrypted_snippet="").only("pk", "encrypted_snippet").iterator(chunk_size=1000):
            Conversation.objects.filter(pk=row.pk).update(encrypted_snippet=rotate_text(row.encrypted_snippet))
            counts["conversations"] += 1
        root = Path(settings.SMS_MEDIA_ROOT)
        for part in MessagePart.objects.exclude(storage_name="").only("storage_name").iterator():
            path = root / part.storage_name
            if path.exists():
                tmp = path.with_suffix(".rotating")
                tmp.write_bytes(rotate_bytes(path.read_bytes()))
                tmp.replace(path)  # atomic on POSIX
                counts["media"] += 1
        for row in SimulatedDevice.objects.all():
            SimulatedDevice.objects.filter(pk=row.pk).update(encrypted_private_key=rotate_text(row.encrypted_private_key))
            counts["simulators"] += 1
        self.stdout.write(self.style.SUCCESS(f"Rotated: {counts}"))
