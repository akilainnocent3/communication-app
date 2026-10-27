"""Demo data: 3 offices, 4 demo mailboxes with ~300 conversations, one user per role and (when the SMS simulator
is enabled) two simulated company phones, one of them dual-SIM.

    python manage.py seed_demo            # idempotent: skips what already exists
    python manage.py seed_demo --reset    # wipe demo mailboxes and recreate them
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from modules.identity.models import Office, Role, User
from modules.identity.services import assign_role, ensure_roles
from modules.mail.models import EmailTemplate, Mailbox, MailboxAccess, MailboxStatus
from modules.mail.services.demo import COMPANY_DOMAIN, seed_mailbox
from modules.mail.services.sync import sync_mailbox

OFFICES = [("Head Office — Dar es Salaam", "hq", "#3758f9"), ("Arusha Branch", "arusha", "#10b981"), ("Mwanza Branch", "mwanza", "#f59e0b")]
MAILBOXES = [
    ("info@" + COMPANY_DOMAIN, "Head Office", "hq", "#3758f9", 85),
    ("finance@" + COMPANY_DOMAIN, "Finance", "hq", "#8b5cf6", 75),
    ("arusha.office@gmail.example", "Arusha Office", "arusha", "#10b981", 70),
    ("mwanza.office@gmail.example", "Mwanza Office", "mwanza", "#f59e0b", 70),
]
USERS = [
    ("admin@" + COMPANY_DOMAIN, "Amina Juma", Role.SUPER_ADMIN, "hq"),
    ("manager@" + COMPANY_DOMAIN, "Halima Mrisho", Role.ADMIN, "hq"),
    ("arusha.manager@" + COMPANY_DOMAIN, "Salim Mollel", Role.OFFICE_MANAGER, "arusha"),
    ("viewer@" + COMPANY_DOMAIN, "Zawadi Nyerere", Role.VIEWER, "mwanza"),
]
DEMO_PASSWORD = "Demo-pass-2026!"
TEMPLATES = [
    ("Thank you for your enquiry", "Re: your enquiry", "<p>Dear {{first_name}},</p><p>Thank you for contacting Kilimanjaro Trading. We have received your enquiry and will reply within one working day.</p><p>Kind regards,</p>"),
    ("Payment received", "Payment received — thank you", "<p>Dear {{first_name}},</p><p>We confirm receipt of your payment. A receipt is attached.</p><p>Asante sana,</p>"),
    ("Out of stock", "", "<p>Hello {{first_name}},</p><p>Unfortunately this item is out of stock. We expect new stock in two weeks.</p>"),
]
PHONES = [("Arusha front desk", "arusha", True, 11), ("Head Office reception", "hq", False, 5)]
QUICK_REPLIES = [
    ("Asante", "Asante sana! Tutakujibu hivi punde."),
    ("Price list", "Thank you for your enquiry. Our latest price list is attached in our email; reply here with the quantity you need."),
    ("Payment received", "Tumepokea malipo yako. Asante kwa kufanya biashara nasi."),
    ("Office hours", "Our offices are open Monday to Friday 8:00–17:00 and Saturday 8:00–13:00."),
]


class Command(BaseCommand):
    help = "Create demo offices, users and fake mailboxes with realistic mail."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete and recreate the demo mailboxes.")

    def handle(self, *args, reset=False, **options):
        if not settings.MAIL_ENABLE_FAKE_PROVIDER:
            raise CommandError("MAIL_ENABLE_FAKE_PROVIDER is off on this server; demo mailboxes are not allowed.")
        ensure_roles()
        with transaction.atomic():
            offices = {}
            for name, code, colour in OFFICES:
                offices[code], _ = Office.objects.get_or_create(code=code, defaults={"name": name, "colour": colour})
            for email, name, role_slug, office in USERS:
                user = User.objects.filter(email=email).first()
                if not user:
                    user = User.objects.create_user(email=email, password=DEMO_PASSWORD, full_name=name, office=offices[office])
                assign_role(user, Role.objects.get(slug=role_slug))
            if reset:
                Mailbox.objects.filter(provider="fake").delete()
                from modules.devices.models import Device

                Device.objects.filter(is_simulated=True).delete()

        created = []
        for email, display, office, colour, threads in MAILBOXES:
            mailbox = Mailbox.objects.filter(email=email).first()
            if mailbox:
                continue
            mailbox = Mailbox.objects.create(
                office=offices[office], email=email, display_name=display, colour=colour, provider="fake",
                status=MailboxStatus.CONNECTED, connected_at=timezone.now(),
            )
            created.append((mailbox, threads))
        all_boxes = list(Mailbox.objects.filter(provider="fake").select_related("office"))
        for index, (mailbox, threads) in enumerate(created):
            peers = [m for m in all_boxes if m.pk != mailbox.pk][:2]
            count = seed_mailbox(mailbox, threads=threads, seed=1000 + index, internal_peers=peers)
            result = sync_mailbox(mailbox.pk, full=True)
            self.stdout.write(f"  {mailbox.email}: {count} messages ({result})")

        arusha = Mailbox.objects.filter(email=MAILBOXES[2][0]).first()
        mwanza = Mailbox.objects.filter(email=MAILBOXES[3][0]).first()
        manager = User.objects.get(email=USERS[2][0])
        viewer = User.objects.get(email=USERS[3][0])
        if arusha:
            MailboxAccess.objects.update_or_create(user=manager, mailbox=arusha, defaults={"can_read": True, "can_send": True, "can_delete": True, "can_manage": True})
        if mwanza:
            MailboxAccess.objects.update_or_create(user=viewer, mailbox=mwanza, defaults={"can_read": True, "can_send": False, "can_delete": False, "can_manage": False})
        admin = User.objects.get(email=USERS[0][0])
        for name, subject, body in TEMPLATES:
            EmailTemplate.objects.get_or_create(name=name, defaults={"subject": subject, "body_html": body, "created_by": admin})

        if settings.SMS_ENABLE_SIMULATOR:
            self._seed_phones(offices, admin, manager, viewer)

        self.stdout.write(self.style.SUCCESS("Demo ready. Sign in with any of:"))
        for email, name, role, _ in USERS:
            self.stdout.write(f"  {email:<45} {role:<15} password: {DEMO_PASSWORD}")

    def _seed_phones(self, offices, admin, manager, viewer):
        from modules.devices.models import Device
        from modules.sms.models import DeviceAccess, QuickReply
        from modules.sms.services import simulator

        for name, office, dual_sim, seed in PHONES:
            if Device.objects.filter(name=name, is_simulated=True).exists():
                continue
            device = simulator.create(name=name, office=offices[office], user=admin, dual_sim=dual_sim, backfill_days=45, seed=seed)
            self.stdout.write(f"  {device.code} {name}: simulated phone{' (dual SIM)' if dual_sim else ''}")
        arusha = Device.objects.filter(name=PHONES[0][0], is_simulated=True).first()
        hq = Device.objects.filter(name=PHONES[1][0], is_simulated=True).first()
        if arusha:
            DeviceAccess.objects.update_or_create(user=manager, device=arusha, defaults={"can_read": True, "can_send": True, "can_manage": True, "can_reveal_sensitive": False})
        if hq:
            DeviceAccess.objects.update_or_create(user=viewer, device=hq, defaults={"can_read": True, "can_send": False, "can_manage": False, "can_reveal_sensitive": False})
        for title, body in QUICK_REPLIES:
            QuickReply.objects.get_or_create(title=title, device=None, defaults={"body": body, "created_by": admin})
