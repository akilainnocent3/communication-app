# Communication Manager

A company admin platform for managing every communication channel from one place. **Gmail**: authorised admins
open the mailbox of any office and work in it like in Gmail (read, reply, label, search, delete, schedule, assign,
take internal notes). **SMS**: company Android phones run the Communication Manager SMS app as their default SMS
app; their text messages are copied (encrypted) to the admin, where admins read every conversation, see analytics
and reply — the phone sends the reply as a normal carrier SMS. Calls and Media show as "Coming soon".

- Connect a Google mailbox with *open a link → choose account → Allow*. Office staff do not need App Passwords
  or 2-Step Verification.
- `@company.com` mailboxes work on Google Workspace (OAuth or domain-wide delegation) and on non-Google hosting
  (IMAP/SMTP, server settings auto-detected).
- A demo mode uses a fake mail provider and simulated phones, so the whole UI works without Google credentials or a
  real phone.
- Phones enroll by scanning a QR code; they prove their identity with a hardware-backed key and never store a
  long-lived secret ([docs/sms-mobile.md](docs/sms-mobile.md)). The app is Android only (iOS allows no SMS apps).

Stack: Django 5.2 + DRF, Celery, PostgreSQL 16, Redis, Next.js 16 (React 19, Tailwind v4, TanStack Query), and a
Flutter + Kotlin Android app (`mobile/`). The server runs on one small VPS.

## Run locally (one command)

```bash
docker compose up --build
```

Open <http://localhost:3000> and sign in with a demo account (password `Demo-pass-2026!`):

| Email | Role |
|---|---|
| `admin@kilimanjaro-trading.example` | Super admin |
| `manager@kilimanjaro-trading.example` | Admin |
| `arusha.manager@kilimanjaro-trading.example` | Office manager (only the mailboxes it was given) |
| `viewer@kilimanjaro-trading.example` | Viewer |

The stack starts six services: `postgres`, `redis`, `backend` (migrates and seeds demo data on start),
`worker`, `beat` and `frontend`. No `.env` is needed for the demo. Copy `.env.example` to `.env` to change
anything.

## Manual development setup

Requirements: Python 3.12+, Node 22, PostgreSQL 16 and Redis. Start Postgres and Redis however you like, for
example `docker compose up -d postgres redis` (it publishes no ports by default, so add `ports` or run your
own containers).

```bash
# Backend
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.lock
export DATABASE_URL=postgres://cm:cm@127.0.0.1:5432/cm REDIS_URL=redis://127.0.0.1:6379/0
python manage.py migrate
python manage.py seed_demo            # demo offices, users, 4 fake mailboxes, ~300 threads, 2 simulated phones
python manage.py simulate_sms_device --run   # optional: keep the simulated phones sending/receiving
python manage.py runserver 127.0.0.1:8000
celery -A config worker -l INFO       # second terminal
celery -A config beat -l INFO         # third terminal

# Frontend
cd frontend
npm ci
npm run dev                           # http://localhost:3000, proxies /api/v1/* to 127.0.0.1:8000
```

If `REDIS_URL` is empty, Celery tasks run inline and you do not need a worker. Undo send and scheduled send
still need `beat`.

## Checks

```bash
cd backend && pytest --cov=modules/sms --cov=modules/devices               # backend tests (Gmail + SMS + devices)
python manage.py makemigrations --check --dry-run
python manage.py spectacular --file ../contracts/openapi.yaml --validate
cd frontend && npm run typecheck && npm run lint && npm run gen:api
npx playwright test                                                        # needs both dev servers running
cd mobile && flutter analyze && flutter test                               # Dart unit + widget tests
(cd mobile/android && ./gradlew :app:testDebugUnitTest)                    # Kotlin unit tests
```

## Documentation

| Doc | What it covers |
|---|---|
| [docs/google-setup.md](docs/google-setup.md) | Google Cloud project, OAuth consent screen, publishing, Workspace trust and delegation |
| [docs/deployment.md](docs/deployment.md) | Single-VPS deploy with Docker, Nginx and HTTPS; full environment variable list |
| [docs/architecture.md](docs/architecture.md) | Platform registry, provider layer, sync flow, request path |
| [docs/security.md](docs/security.md) | Auth, permissions, HTML sanitising, token encryption, audit log |
| [docs/adding-a-platform.md](docs/adding-a-platform.md) | How to add Calls or Media (SMS followed it) |
| [docs/sms-mobile.md](docs/sms-mobile.md) | SMS platform: phones, enrollment, sync protocol, outbound queue, security, PDPA, distribution |
| [mobile/README.md](mobile/README.md) | Building, signing and distributing the Android app |
| [docs/decisions.md](docs/decisions.md) | Defaults chosen during the build and why |
| [docs/status.md](docs/status.md) | What was built, how it was verified, known limitations, next steps |
