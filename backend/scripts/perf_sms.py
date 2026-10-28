"""SMS performance check: one phone with 100 000 messages, then time the admin and phone endpoints.

Uses its own database (cm_perf, dropped and recreated) so the dev database stays as the demo left it.

    cd backend && .venv/bin/python scripts/perf_sms.py [--messages 100000] [--conversations 2500] [--runs 7]

Prints a Markdown table: p50, p95 (nearest rank) and worst time per endpoint, and the number of SQL queries. A p95
over --slow-ms (300 ms, the admin budget) is flagged; for those it also prints the plan of the slowest query.
"""

from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
import time
import uuid
from datetime import timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

parser = argparse.ArgumentParser()
parser.add_argument("--messages", type=int, default=100_000)
parser.add_argument("--conversations", type=int, default=2_500)
parser.add_argument("--runs", type=int, default=20)
parser.add_argument("--slow-ms", type=float, default=300)
parser.add_argument("--keep", action="store_true", help="Reuse an existing cm_perf database instead of rebuilding it.")
args = parser.parse_args()

base_url = os.environ.get("PERF_DATABASE_URL", "postgres://cm:cm@127.0.0.1:5432/cm_perf")
os.environ["DATABASE_URL"] = base_url
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
os.environ["DJANGO_ALLOWED_HOSTS"] = "testserver,localhost"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "false"

import psycopg  # noqa: E402

admin_dsn = base_url.rsplit("/", 1)[0] + "/postgres"
db_name = base_url.rsplit("/", 1)[1]
if not args.keep:
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{db_name}"')

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402
from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402
from django.utils import timezone  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

call_command("migrate", verbosity=0)

from modules.devices.models import Device  # noqa: E402
from modules.devices.services.enrollment import create_invite  # noqa: E402
from modules.identity.models import Office, Role, User  # noqa: E402
from modules.identity.services import assign_role, ensure_roles  # noqa: E402
from modules.sms.models import Contact, Conversation, Message, MessageStatus  # noqa: E402
from modules.sms.services.crypto import encrypt_text  # noqa: E402
from tests.phone import Phone  # noqa: E402

random.seed(7)


def build() -> tuple[User, Phone]:
    ensure_roles()
    office, _ = Office.objects.get_or_create(name="Perf office", defaults={"code": "perf"})
    user = User.objects.filter(email="perf@example.com").first()
    if not user:
        user = User.objects.create_user(email="perf@example.com", password="perf-perf-perf", full_name="Perf Admin")
        assign_role(user, Role.objects.get(slug=Role.SUPER_ADMIN))
        user = User.objects.get(pk=user.pk)
    phone = Phone()
    phone.client = APIClient()
    if args.keep and Device.objects.exists():
        sys.exit("--keep needs the phone key; rebuild instead.")
    _, token = create_invite(user, name="Perf phone", office=office, options={})
    assert phone.enroll(token).status_code == 201
    device = Device.objects.get(pk=phone.device_id)

    started = time.perf_counter()
    now = timezone.now()
    # A few huge threads (M-PESA, a busy customer), the rest a long tail: like a real front-desk phone.
    weights = [random.paretovariate(1.2) for _ in range(args.conversations)]
    weights[0] *= 400
    weights[1] *= 150
    total = sum(weights)
    counts = [max(1, int(args.messages * w / total)) for w in weights]
    counts[0] += args.messages - sum(counts)

    numbers = [f"+2557{random.randint(10_000_000, 99_999_999)}" for _ in range(args.conversations)]
    numbers[0] = "MPESA"
    conversations = [
        Conversation(device=device, thread_id=index + 1, participants_key=number, addresses=[number], last_message_at=now)
        for index, number in enumerate(numbers)
    ]
    Conversation.objects.bulk_create(conversations, batch_size=2_000)
    Contact.objects.bulk_create(
        [Contact(device=device, address=number, display_name=f"Customer {index}") for index, number in enumerate(numbers[1:], 1) if index % 3],
        batch_size=2_000,
    )

    bodies = [encrypt_text(f"Habari, oda namba {n} iko tayari? Asante sana.") for n in range(200)]
    provider_id = 1_000
    rows: list[Message] = []
    for conversation, count in zip(conversations, counts):
        at = now - timedelta(days=random.randint(0, 360))
        for index in range(count):
            at += timedelta(minutes=random.randint(1, 600) // max(1, count // 200))
            direction = Message.IN if random.random() < 0.6 else Message.OUT
            provider_id += 1
            rows.append(Message(
                device=device, conversation=conversation, kind=Message.SMS, direction=direction, address=conversation.participants_key,
                addresses=[conversation.participants_key], encrypted_body=random.choice(bodies), body_length=45, provider_id=provider_id,
                provider_date=min(at, now), is_read=not (direction == Message.IN and index >= count - 2 and random.random() < 0.3),
                status=MessageStatus.RECEIVED if direction == Message.IN else MessageStatus.DELIVERED,
                is_sensitive=conversation.participants_key == "MPESA",
            ))
        if len(rows) >= 20_000:
            Message.objects.bulk_create(rows, batch_size=5_000)
            rows = []
    # A small admin outbox: queued, failed and scheduled messages.
    for index in range(60):
        rows.append(Message(
            device=device, conversation=conversations[index + 2], kind=Message.SMS, direction=Message.OUT, origin=Message.ORIGIN_ADMIN,
            sent_by=user, address=conversations[index + 2].participants_key, encrypted_body=bodies[0], provider_date=now, client_uuid=uuid.uuid4(),
            status=[MessageStatus.QUEUED, MessageStatus.FAILED, MessageStatus.QUEUED][index % 3], send_at=now + timedelta(hours=index % 3),
            is_scheduled=index % 3 == 2,
        ))
    Message.objects.bulk_create(rows, batch_size=5_000)

    # Conversation summaries the way refresh_conversation computes them, in one statement.
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE sms_conversation c SET
              last_message_at = s.last_at, first_message_at = s.first_at, message_count = s.n, unread_count = s.unread,
              last_inbound_at = s.last_in, last_outbound_at = s.last_out, encrypted_snippet = %s,
              last_direction = CASE WHEN s.last_in >= coalesce(s.last_out, s.last_in) THEN 'in' ELSE 'out' END,
              awaiting_since = CASE WHEN s.last_in > coalesce(s.last_out, s.last_in - interval '1 second') THEN s.last_in END
            FROM (SELECT conversation_id, max(provider_date) last_at, min(provider_date) first_at, count(*) n,
                         count(*) FILTER (WHERE NOT is_read AND direction = 'in') unread,
                         max(provider_date) FILTER (WHERE direction = 'in') last_in, max(provider_date) FILTER (WHERE direction = 'out') last_out
                  FROM sms_message GROUP BY conversation_id) s
            WHERE s.conversation_id = c.id
        """, [bodies[0]])
        cursor.execute("ANALYZE")
    print(f"Built {Message.objects.count():,} messages in {Conversation.objects.count():,} conversations "
          f"({time.perf_counter() - started:.0f} s). Biggest thread: {max(counts):,} messages.\n")
    return user, phone


def measure(label: str, call) -> dict:
    call()  # warm-up (connection, caches)
    times, queries, status = [], 0, None
    for _ in range(args.runs):
        with CaptureQueriesContext(connection) as ctx:
            started = time.perf_counter()
            response = call()
            times.append((time.perf_counter() - started) * 1000)
        queries, status = len(ctx.captured_queries), response.status_code
        selects = [q for q in ctx.captured_queries if q["sql"].lstrip().upper().startswith("SELECT")]
        slowest = max(selects, key=lambda q: float(q["time"]), default=None)
    ordered = sorted(times)
    p95 = ordered[max(0, -(-95 * len(ordered) // 100) - 1)]  # nearest rank
    return {"label": label, "median": statistics.median(times), "p95": p95, "max": max(times), "queries": queries, "status": status, "slowest": slowest}


def main() -> None:
    user, phone = build()
    admin = APIClient()
    admin.force_authenticate(user)
    admin.force_login(user)
    device = phone.device_id
    big = Conversation.objects.order_by("-message_count").first()
    mid = Conversation.objects.filter(message_count__gte=20).order_by("message_count").first()
    message = Message.objects.filter(conversation=big).order_by("-provider_date").first()
    cursor = admin.get("/api/v1/sms/conversations/", {"device": device}).json().get("next_cursor")
    older = admin.get(f"/api/v1/sms/conversations/{big.pk}/messages/").json().get("next_cursor")
    seq = iter(range(1, 10_000_000))

    def sync_batch():
        events = [phone.message(address=f"+2557{random.randint(10_000_000, 99_999_999)}", at_ms=int(time.time() * 1000) - 1_000) for _ in range(200)]
        return phone.send_events(*events, seqs=[next(seq) for _ in events])

    cases = [
        ("Conversations, all phones (inbox)", lambda: admin.get("/api/v1/sms/conversations/")),
        ("Conversations, one phone", lambda: admin.get("/api/v1/sms/conversations/", {"device": device})),
        ("Conversations, page 2 (cursor)", lambda: admin.get("/api/v1/sms/conversations/", {"device": device, "cursor": cursor})),
        ("Conversations, unread", lambda: admin.get("/api/v1/sms/conversations/", {"folder": "unread"})),
        ("Conversations, awaiting reply", lambda: admin.get("/api/v1/sms/conversations/", {"folder": "awaiting"})),
        ("Conversations, starred", lambda: admin.get("/api/v1/sms/conversations/", {"folder": "starred"})),
        ("Conversations, search by name", lambda: admin.get("/api/v1/sms/conversations/", {"q": "Customer 42"})),
        ("Conversations, search by number", lambda: admin.get("/api/v1/sms/conversations/", {"q": "0754"})),
        ("Conversations, date range + has MMS", lambda: admin.get("/api/v1/sms/conversations/", {"after": "2026-01-01", "has_mms": "true"})),
        (f"Open biggest thread ({big.message_count:,} msgs)", lambda: admin.get(f"/api/v1/sms/conversations/{big.pk}/", {"peek": "1"})),
        ("Messages, newest page of biggest thread", lambda: admin.get(f"/api/v1/sms/conversations/{big.pk}/messages/")),
        ("Messages, older page (cursor)", lambda: admin.get(f"/api/v1/sms/conversations/{big.pk}/messages/", {"cursor": older})),
        (f"Search inside a thread ({mid.message_count} msgs)", lambda: admin.get(f"/api/v1/sms/conversations/{mid.pk}/messages/", {"q": "oda"})),
        ("Search inside the biggest thread", lambda: admin.get(f"/api/v1/sms/conversations/{big.pk}/messages/", {"q": "oda"})),
        ("Dashboard, 30 days", lambda: admin.get("/api/v1/sms/stats/", {"days": 30})),
        ("Dashboard, 365 days", lambda: admin.get("/api/v1/sms/stats/", {"days": 365})),
        ("Outbox", lambda: admin.get("/api/v1/sms/outbox/")),
        ("Contacts", lambda: admin.get("/api/v1/sms/contacts/", {"device": device})),
        ("Devices list", lambda: admin.get("/api/v1/sms/devices/")),
        ("Session (badges)", lambda: admin.get("/api/v1/auth/me/")),
        ("Reveal a sensitive message", lambda: admin.post(f"/api/v1/sms/messages/{message.pk}/reveal/")),
        ("Phone: sync 200 new messages", sync_batch),
        ("Phone: claim outbox", lambda: phone.post("outbox/claim/", {"limit": 10})),
    ]
    results = [measure(label, call) for label, call in cases]

    print(f"| Endpoint | p50 ms | p95 ms | Max ms | SQL queries | HTTP |  ({args.runs} runs each)")
    print("|---|---:|---:|---:|---:|---:|")
    for r in results:
        flag = " ⚠" if r["p95"] > args.slow_ms else ""
        print(f"| {r['label']}{flag} | {r['median']:.0f} | {r['p95']:.0f} | {r['max']:.0f} | {r['queries']} | {r['status']} |")
    for r in results:
        if r["p95"] > args.slow_ms and r["slowest"]:
            print(f"\n### {r['label']}: slowest query ({float(r['slowest']['time']) * 1000:.0f} ms)\n{r['slowest']['sql'][:1500]}")
            with connection.cursor() as cur:
                cur.execute("EXPLAIN ANALYZE " + r["slowest"]["sql"])
                print("\n".join(row[0] for row in cur.fetchall()[:25]))


if __name__ == "__main__":
    main()
