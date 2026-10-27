"""Simulated company phones for demos and E2E tests (refused when SMS_ENABLE_SIMULATOR is off, as in production).

    python manage.py simulate_sms_device --create "Demo phone" --office hq [--dual-sim]
    python manage.py simulate_sms_device DEV-XXXX-XXXX --offline | --online | --inbound | --tick
    python manage.py simulate_sms_device --run [--interval 3]      # keep every online simulated phone working
"""

import random
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from modules.devices.models import Device
from modules.identity.models import Office
from modules.sms.services import simulator


class Command(BaseCommand):
    help = "Create and drive simulated SMS phones (demo and tests only)."

    def add_arguments(self, parser):
        parser.add_argument("device", nargs="?", help="Device code (DEV-XXXX-XXXX) for --offline/--online/--inbound/--tick.")
        parser.add_argument("--create", metavar="NAME")
        parser.add_argument("--office", default="hq", help="Office code for --create.")
        parser.add_argument("--dual-sim", action="store_true")
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--offline", action="store_true")
        parser.add_argument("--online", action="store_true")
        parser.add_argument("--inbound", action="store_true")
        parser.add_argument("--tick", action="store_true")
        parser.add_argument("--run", action="store_true", help="Loop: heartbeats, outbox, occasional inbound messages.")
        parser.add_argument("--interval", type=float, default=3.0)

    def handle(self, *args, **options):
        if not settings.SMS_ENABLE_SIMULATOR:
            raise CommandError("SMS_ENABLE_SIMULATOR is off on this server; simulated phones are not allowed.")
        if options["create"]:
            office = Office.objects.filter(code=options["office"]).first()
            if not office:
                raise CommandError(f"Unknown office code '{options['office']}'.")
            device = simulator.create(name=options["create"], office=office, dual_sim=options["dual_sim"], backfill_days=options["days"])
            self.stdout.write(self.style.SUCCESS(f"Created {device.code} ({device.name})"))
            return
        if options["run"]:
            self.stdout.write("Simulating phones. Ctrl+C to stop.")
            rng = random.Random()
            while True:
                handled = simulator.tick_all()
                if handled:
                    self.stdout.write(f"  {handled} status reports")
                time.sleep(options["interval"] * rng.uniform(0.8, 1.2))
        if not options["device"]:
            raise CommandError("Give a device code, --create or --run.")
        device = Device.objects.filter(code=options["device"].upper(), is_simulated=True).first()
        if not device:
            raise CommandError("No simulated phone with this code.")
        for action in ("offline", "online", "inbound", "tick"):
            if options[action]:
                simulator.control(device, action)
                self.stdout.write(self.style.SUCCESS(f"{device.code}: {action}"))
