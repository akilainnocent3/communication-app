"""Realistic demo mail for the fake provider (dev, demos, end-to-end tests). Deterministic for a given seed.

The company is fictional (Kilimanjaro Trading Co.) and every address uses the reserved `.example` domain, so
nothing here can reach a real person.
"""

from __future__ import annotations

import base64
import random
import secrets
import struct
import zlib
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from ..models import FakeHistory, FakeMessage, FakeServerState, Mailbox

COMPANY_DOMAIN = "kilimanjaro-trading.example"

PEOPLE = [
    ("Neema Mushi", "neema.mushi@azania-logistics.example", "client"),
    ("Baraka Mwakyusa", "baraka@mwakyusa-hardware.example", "supplier"),
    ("Rehema Kimaro", "rehema.kimaro@serengeti-foods.example", "client"),
    ("Juma Hassan", "juma.hassan@pwani-transport.example", "supplier"),
    ("Grace Massawe", "grace@massawe-consult.example", "client"),
    ("Emmanuel Lyimo", "e.lyimo@kibo-insurance.example", "partner"),
    ("Fatma Said", "fatma.said@zanzibar-spices.example", "client"),
    ("Daudi Mrema", "daudi.mrema@mrema-builders.example", "client"),
    ("Upendo Shayo", "upendo@shayo-accounting.example", "partner"),
    ("Joseph Kariuki", "joseph.k@nairobi-imports.example", "supplier"),
    ("Aisha Mohamed", "aisha.mohamed@tanga-cement.example", "supplier"),
    ("Peter Swai", "peter.swai@swai-electronics.example", "client"),
]
AUTOMATED = [
    ("TRA e-Filing", "no-reply@tra-efiling.example", "updates"),
    ("CRDB Bank Alerts", "alerts@crdb-bank.example", "updates"),
    ("NMB Business", "statements@nmb-business.example", "updates"),
    ("Vodacom M-Pesa Business", "mpesa-business@vodacom.example", "updates"),
    ("LinkedIn", "notifications@linkedin.example", "social"),
    ("Facebook", "notification@facebook.example", "social"),
    ("Jumia Business", "deals@jumia-business.example", "promotions"),
    ("Precision Air", "offers@precisionair.example", "promotions"),
    ("Office Supplies TZ", "newsletter@officesupplies-tz.example", "promotions"),
]

CLIENT_TOPICS = [
    ("Quotation request: {item}", "Hello,\n\nCould you please send us a quotation for {qty} units of {item}? We need delivery to {city} before the end of the month.\n\nKind regards,\n{name}"),
    ("Order confirmation #{num}", "Dear team,\n\nWe confirm order #{num} for {qty} {item}. Please share the proforma invoice and the expected delivery date.\n\nThank you,\n{name}"),
    ("Delivery delay to {city}?", "Hi,\n\nOur shipment of {item} to {city} has not arrived yet. Could you check with the transporter and update us today?\n\nAsante,\n{name}"),
    ("Meeting next week about the {item} contract", "Habari,\n\nCan we meet on Tuesday at 10:00 at your {city} office to review the {item} contract? I will bring the signed copies.\n\nBest,\n{name}"),
    ("Payment for invoice INV-{num}", "Dear Finance,\n\nPlease find attached the bank slip for invoice INV-{num} (TZS {amount}). Kindly confirm receipt.\n\nRegards,\n{name}"),
]
SUPPLIER_TOPICS = [
    ("Price list update — {month}", "Dear customer,\n\nAttached is our updated price list for {month}. Prices for {item} change from the 1st.\n\nRegards,\n{name}"),
    ("Proforma invoice PI-{num}", "Hello,\n\nPlease find proforma invoice PI-{num} for {qty} {item}. Payment terms: 50% deposit, balance on delivery.\n\nThank you,\n{name}"),
    ("Stock available: {item}", "Hi,\n\nWe have {qty} units of {item} in our Dar es Salaam warehouse. Let us know if you want us to reserve them.\n\n{name}"),
]
AUTOMATED_TOPICS = {
    "updates": [
        ("Your VAT return for {month} is due", "<p>Dear Taxpayer,</p><p>This is a reminder that your <b>VAT return for {month}</b> is due on the 20th. File online to avoid penalties.</p><p>TRA e-Filing</p>"),
        ("Account statement for {month}", "<p>Dear Customer,</p><p>Your account statement for {month} is attached. Closing balance: <b>TZS {amount}</b>.</p>"),
        ("Payment received TZS {amount}", "<p>You have received <b>TZS {amount}</b> from {name}. Reference {num}.</p>"),
    ],
    "social": [
        ("{name} wants to connect", "<p>{name} would like to join your professional network.</p><p><a href=\"https://linkedin.example/in/someone\">View profile</a></p>"),
        ("You have 3 new notifications", "<p>See what you missed on your page this week.</p>"),
    ],
    "promotions": [
        ("Up to 40% off office furniture this week", "<table width=\"100%\"><tr><td align=\"center\"><img src=\"https://images.example/banner-office.jpg\" width=\"560\" alt=\"Office furniture sale\"><h2 style=\"color:#1f2937\">Big office sale</h2><p>Chairs, desks and filing cabinets from TZS 120,000.</p><p><a href=\"https://deals.example/office\" style=\"background:#f97316;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none\">Shop now</a></p></td></tr></table>"),
        ("Fly Dar es Salaam ↔ Mwanza from TZS 180,000", "<p><img src=\"https://images.example/plane.png\" width=\"480\" alt=\"Plane\"></p><p>Book before Friday for our lowest business fares.</p>"),
        ("Your monthly stationery deals", "<p>Printer paper, toner and more. <a href=\"https://officesupplies.example/deals\">See the deals</a>.</p><p><img src=\"https://images.example/stationery.jpg\" width=\"400\" alt=\"\"></p>"),
    ],
}
ITEMS = ["cement bags", "roofing sheets", "solar panels", "maize flour", "cooking oil", "laptops", "office chairs", "steel bars", "water tanks", "printer toner"]
CITIES = ["Dar es Salaam", "Arusha", "Mwanza", "Dodoma", "Mbeya", "Tanga", "Moshi", "Morogoro", "Zanzibar"]
MONTHS = ["July", "August", "September", "October"]
REPLIES = [
    "Thank you, {first}. We have received this and will get back to you by tomorrow.",
    "Dear {first},\n\nNoted with thanks. Our team is checking and we will update you shortly.",
    "Hi {first},\n\nPlease see the attached document. Let me know if anything is missing.",
    "Asante {first}. Confirmed — we will proceed as discussed.",
]
USER_LABELS = [("Clients", "#16a765", "#ffffff"), ("Suppliers", "#4986e7", "#ffffff"), ("Tax / TRA", "#f691b2", "#000000"), ("Urgent", "#cc3a21", "#ffffff"), ("Receipts", "#ffad47", "#000000")]


def _pdf(title: str) -> bytes:
    """A tiny valid one-page PDF with a line of text."""
    text = title.replace("(", "[").replace(")", "]")[:80]
    stream = f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % index + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def _png(width: int, height: int, colour: tuple[int, int, int]) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    row = b"\x00" + bytes(colour) * width
    raw = row * height
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def _attachment(filename: str, mime: str, data: bytes, part: str) -> dict:
    return {"id": part, "filename": filename, "mime_type": mime, "size": len(data), "content_id": "", "inline": False, "data": base64.b64encode(data).decode()}


def _html(text: str) -> str:
    paragraphs = [p.replace("\n", "<br>") for p in text.split("\n\n")]
    return "".join(f"<p>{p}</p>" for p in paragraphs)


class _Builder:
    def __init__(self, mailbox: Mailbox, rng: random.Random):
        self.mailbox = mailbox
        self.rng = rng
        self.rows: list[FakeMessage] = []
        self.me = {"email": mailbox.email, "name": mailbox.display_name or mailbox.office.name}
        self.labels = {}

    def message(self, *, thread_id, sender, to, subject, html, when, labels, attachments=(), in_reply_to="", references="", extra_headers=None, text=""):
        message_id = secrets.token_hex(8)
        rfc_id = f"<{message_id}@{sender['email'].split('@')[1]}>"
        headers = {
            "subject": subject, "from": sender, "to": to, "cc": [], "bcc": [], "message_id": rfc_id,
            "in_reply_to": in_reply_to, "references": references, **(extra_headers or {}),
        }
        self.rows.append(FakeMessage(
            mailbox=self.mailbox, message_id=message_id, thread_id=thread_id, label_ids=labels, headers=headers,
            body_html=html, body_text=text, attachments=list(attachments), internal_date=when,
        ))
        return rfc_id


def _when(rng: random.Random, now, max_days: int = 60):
    # Denser recent mail: square the uniform draw.
    days = (rng.random() ** 2) * max_days
    return now - timedelta(days=days, minutes=rng.randint(0, 600))


def seed_mailbox(mailbox: Mailbox, threads: int = 75, seed: int | None = None, internal_peers: list[Mailbox] | None = None) -> int:
    """Fill a fake mailbox with `threads` conversations. Returns the number of messages created."""
    rng = random.Random(seed if seed is not None else mailbox.pk)
    now = timezone.now()
    b = _Builder(mailbox, rng)
    state, _ = FakeServerState.objects.get_or_create(mailbox=mailbox)
    labels = []
    for name, colour, text_colour in USER_LABELS:
        labels.append({"id": f"Label_{secrets.token_hex(4)}", "name": name, "colour": colour, "text_colour": text_colour})
    state.labels = labels
    by_name = {item["name"]: item["id"] for item in labels}

    for index in range(threads):
        thread_id = secrets.token_hex(8)
        when = _when(rng, now)
        kind = rng.random()
        values = {
            "item": rng.choice(ITEMS), "qty": rng.choice([20, 50, 120, 300, 1000]), "city": rng.choice(CITIES),
            "num": rng.randint(1000, 9999), "amount": f"{rng.randint(150, 9800) * 1000:,}", "month": rng.choice(MONTHS),
        }
        if kind < 0.55:
            name, email, role = rng.choice(PEOPLE)
            sender = {"email": email, "name": name}
            topics = CLIENT_TOPICS if role in ("client", "partner") else SUPPLIER_TOPICS
            subject_t, body_t = rng.choice(topics)
            subject = subject_t.format(**values)
            body = body_t.format(name=name, **values)
            extra = [by_name["Clients" if role != "supplier" else "Suppliers"]]
            if "INV-" in subject or "PI-" in subject:
                extra.append(by_name["Receipts"])
            if rng.random() < 0.12:
                extra.append(by_name["Urgent"])
            attachments = []
            if rng.random() < 0.35:
                attachments.append(_attachment(f"{subject.split(':')[0].strip().replace(' ', '_')[:30]}.pdf", "application/pdf", _pdf(subject), "2"))
            if rng.random() < 0.12:
                attachments.append(_attachment("site_photo.png", "image/png", _png(64, 40, (rng.randint(40, 200), rng.randint(80, 200), rng.randint(80, 220))), "3"))
            unread = when > now - timedelta(days=4) and rng.random() < 0.6
            base = ["INBOX", "CATEGORY_PERSONAL"] + (["UNREAD"] if unread else []) + (["IMPORTANT"] if rng.random() < 0.4 else []) + (["STARRED"] if rng.random() < 0.1 else []) + extra
            if rng.random() < 0.15:
                base = [x for x in base if x != "INBOX"]  # archived
            rfc = b.message(thread_id=thread_id, sender=sender, to=[b.me], subject=subject, html=_html(body), text=body, when=when, labels=base, attachments=attachments)
            # Replies back and forth.
            replies = rng.choice([0, 0, 1, 1, 2, 3])
            refs = rfc
            reply_when = when
            for r in range(replies):
                reply_when = reply_when + timedelta(hours=rng.randint(1, 30))
                if reply_when > now:
                    break
                ours = r % 2 == 0
                text = rng.choice(REPLIES).format(first=name.split()[0]) if ours else f"Thank you. Noted.\n\n{name}"
                reply_labels = ["SENT"] if ours else ["INBOX", "CATEGORY_PERSONAL"] + (["UNREAD"] if reply_when > now - timedelta(days=2) else []) + extra
                if ours and "INBOX" in base:
                    reply_labels = ["SENT", "INBOX"]
                rfc = b.message(
                    thread_id=thread_id, sender=b.me if ours else sender, to=[sender] if ours else [b.me], subject=f"Re: {subject}",
                    html=_html(text) + f"<blockquote>On {when:%d %b %Y}, {name} wrote:<br>{_html(body)}</blockquote>", text=text, when=reply_when,
                    labels=reply_labels, in_reply_to=rfc, references=refs,
                )
                refs = f"{refs} {rfc}"
        elif kind < 0.92:
            name, email, category = rng.choice(AUTOMATED)
            subject_t, html_t = rng.choice(AUTOMATED_TOPICS[category])
            person = rng.choice(PEOPLE)[0]
            subject = subject_t.format(name=person, **values)
            html = html_t.format(name=person, **values)
            labels_ = ["INBOX", f"CATEGORY_{category.upper()}"] + (["UNREAD"] if rng.random() < 0.5 else [])
            if "VAT" in subject:
                labels_ += [by_name["Tax / TRA"], "IMPORTANT"]
            attachments = [_attachment(f"Statement_{values['month']}.pdf", "application/pdf", _pdf(subject), "2")] if "statement" in subject.lower() else []
            extra_headers = {}
            if category == "promotions":
                extra_headers = {"list_unsubscribe": f"<mailto:unsubscribe@{email.split('@')[1]}?subject=unsubscribe>, <https://{email.split('@')[1]}/unsubscribe?u={index}>", "list_unsubscribe_post": "List-Unsubscribe=One-Click"}
            b.message(thread_id=thread_id, sender={"email": email, "name": name}, to=[b.me], subject=subject, html=html, when=when, labels=labels_, attachments=attachments, extra_headers=extra_headers)
        elif kind < 0.95:
            # A phishing attempt (link text and destination differ) sitting in Spam.
            b.message(
                thread_id=thread_id, sender={"email": "security@crdb-bank-verify.example", "name": "CRDB Security"}, to=[b.me],
                subject="Urgent: verify your account", when=when, labels=["SPAM", "UNREAD"],
                html='<p>Your account will be suspended. Verify now at <a href="https://login-verify.example/crdb">https://crdb-bank.example/login</a>.</p>',
            )
        elif kind < 0.97:
            b.message(thread_id=thread_id, sender={"email": "old.newsletter@promo.example", "name": "Old Newsletter"}, to=[b.me], subject="Weekly digest", when=when, labels=["TRASH"], html="<p>Last week's digest.</p>")
        else:
            # Something we sent that has no reply yet.
            name, email, _ = rng.choice(PEOPLE)
            subject = f"Follow-up: {values['item']} delivery schedule"
            text = f"Dear {name.split()[0]},\n\nFollowing our call, please confirm the delivery schedule for the {values['item']}.\n\nRegards,\n{b.me['name']}"
            b.message(thread_id=thread_id, sender=b.me, to=[{"email": email, "name": name}], subject=subject, html=_html(text), text=text, when=when, labels=["SENT"])

    # Internal conversations with the other offices' mailboxes.
    for peer in internal_peers or []:
        thread_id = secrets.token_hex(8)
        when = _when(rng, now, 10)
        sender = {"email": peer.email, "name": peer.display_name or peer.office.name}
        subject = f"Weekly report — {peer.office.name}"
        body = f"Hello,\n\nPlease find this week's sales report for {peer.office.name} attached.\n\nRegards,\n{sender['name']}"
        b.message(thread_id=thread_id, sender=sender, to=[b.me], subject=subject, html=_html(body), text=body, when=when, labels=["INBOX", "CATEGORY_PERSONAL", "UNREAD", "IMPORTANT"],
                  attachments=[_attachment("weekly_report.pdf", "application/pdf", _pdf(subject), "2")])

    with transaction.atomic():
        FakeMessage.objects.bulk_create(b.rows, batch_size=500)
        state.history_id += 1
        state.save()
        FakeHistory.objects.filter(mailbox=mailbox).delete()
    return len(b.rows)
