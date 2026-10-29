# Deployment (single VPS)

The whole system runs on one small Linux VPS with Docker Compose behind Nginx. A 2 vCPU / 4 GB RAM server is
enough for dozens of mailboxes. Add disk if you keep a long sync window, because the local index grows with
mail volume.

```
Internet ─HTTPS─▶ Nginx :443 ─▶ frontend :3000 (127.0.0.1 only) ─▶ backend :8000 (Docker network)
                                                                    ├─ postgres
                                                                    ├─ redis        (broker + security store: noeviction, AOF)
                                                                    ├─ redis-cache  (plain cache: allkeys-lru, not persisted)
                                                                    └─ worker, beat
```

### Two Redis roles

One Redis used to be both the Celery broker and the cache, with `allkeys-lru`. Under memory pressure LRU may evict
*any* key: a queued task (an outbound SMS dispatch, a sync) would silently vanish, and an evicted replay nonce would let
a captured signed phone request be accepted a second time. The stack therefore runs two instances (decision 59):

| Service | Holds | Policy | Persistence |
|---|---|---|---|
| `redis` (`REDIS_URL`) | Celery queue; the **security store**: device-auth nonces, login lockouts, the short-code breaker, rate-limit counters, throttle history, sync locks | `noeviction`, `REDIS_MAXMEMORY` (256 MB) | AOF (`appendfsync everysec`) in the `redisdata` volume |
| `redis-cache` (`REDIS_CACHE_URL`) | evictable cache: Gmail token buckets and access-token cache, push coalescing | `allkeys-lru`, `REDIS_CACHE_MAXMEMORY` (128 MB) | none |

With `noeviction`, a full `redis` refuses writes: the request that needed it fails (503 `try_later`) instead of being
let through. Security checks **fail closed** (`backend/common/stores.py`; tests in `tests/test_stores.py`). Watch its
memory (`docker compose exec redis redis-cli info memory`); 256 MB is far more than a queue of a few thousand tasks and
the nonces of a few hundred phones need. `python manage.py check --deploy` verifies the policy and AOF of the live
server (`cm.E003`, `cm.W001`) and that `REDIS_CACHE_URL` is set (`cm.W002`). Production refuses to start without
`REDIS_URL`.

## 1. Prepare the server

```bash
# Ubuntu 24.04 example
sudo apt update && sudo apt install -y docker.io docker-compose-v2 nginx certbot python3-certbot-nginx git
sudo usermod -aG docker $USER   # log out and back in
sudo timedatectl set-timezone Africa/Dar_es_Salaam
```

Point a DNS `A` record for your admin domain (called `CM_DOMAIN` below, for example `admin.example.co.tz`) at the
server, and open ports 80 and 443 only.

## 2. Configure

```bash
git clone <your repo> /opt/communication-manager && cd /opt/communication-manager
cp .env.example .env
chmod 600 .env
```

Edit `.env`. The minimum production values are:

```ini
DJANGO_SETTINGS_MODULE=config.settings.prod
DJANGO_SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(50))">
DJANGO_ALLOWED_HOSTS=admin.example.co.tz,localhost,backend
DJANGO_CSRF_TRUSTED_ORIGINS=https://admin.example.co.tz
POSTGRES_PASSWORD=<strong random password>
PUBLIC_APP_URL=https://admin.example.co.tz
COMPANY_NAME=Kilimanjaro Trading Ltd
FRONTEND_PORT=127.0.0.1:3000
SEED_DEMO=0
MAIL_ENABLE_FAKE_PROVIDER=false
MAIL_TOKEN_KEYS=<python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
SMS_DATA_KEYS=<a second, different Fernet key>
SMS_ENABLE_SIMULATOR=false
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
```

Keep `localhost` and `backend` in `DJANGO_ALLOWED_HOSTS`, because the container health check and the
frontend proxy use those host names. Production settings refuse to start without a real `DJANGO_SECRET_KEY`
and `MAIL_TOKEN_KEYS`, or with the dev-only key.

**Back up `MAIL_TOKEN_KEYS` and `SMS_DATA_KEYS` somewhere safe outside the server** (a password manager). Without them, every
stored mailbox connection is unreadable (every mailbox must be reconnected) and every stored text message and MMS file
is lost for good.

Set up Google first ([google-setup.md](google-setup.md)) and register
`https://admin.example.co.tz/api/v1/mail/oauth/callback/` as an authorised redirect URI.

## 3. Start

```bash
docker compose up -d --build
docker compose ps                     # all services "healthy" / "running"
docker compose exec backend python manage.py createsuperuser
```

The backend container runs migrations on every start. Sign in, then add offices, users and mailboxes.

## 4. Nginx and HTTPS

`deploy/nginx.conf.template` is rendered for your domain by `deploy/render-nginx.sh` (`envsubst` of `${CM_DOMAIN}`
only, so Nginx's own `$variables` stay intact):

```bash
sudo apt install -y gettext-base                       # envsubst
sudo CM_DOMAIN=admin.example.co.tz deploy/render-nginx.sh
sudo ln -s /etc/nginx/sites-available/communication-manager /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
# First certificate: temporarily comment out the 443 server block, reload, then:
sudo certbot --nginx -d admin.example.co.tz
sudo nginx -t && sudo systemctl reload nginx
```

What the config adds on top of proxying:

- **Rate limits:** `/api/v1/device/` 20 r/s per address (burst 40); `/api/v1/auth/login/` 10 r/min per address
  (burst 5), under Django's own login throttle and per-email lockout.
- **Security headers** Django sends in production (`nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options:
  DENY`, HSTS), added only when the upstream did not send them, so Next.js pages, error pages and static files carry
  them too and nothing is duplicated.
- **gzip for static text assets only** (`/_next/static/`: JS, CSS, SVG). HTML and API responses are not compressed:
  compression of responses that carry a secret (CSRF token, mail content) next to attacker-influenced text enables
  BREACH-style attacks (decision 60).
- `server_tokens off`.

A separate phone domain (see *Separate domains* below) uses `deploy/nginx-api.conf.template`:
`sudo CM_API_DOMAIN=api.example.co.tz deploy/render-nginx.sh api`. It serves only `/api/v1/device/` and answers 404 to
everything else; it relies on the zones and header maps of the admin template, so install both.

Certbot renews certificates automatically (`systemctl list-timers | grep certbot`).

Phones call `/api/v1/device/` directly on Django (the config proxies that prefix to `127.0.0.1:8000`, with its own
rate limit and a 2 MB body limit). Everything else goes through Next.js. Phones refuse plain HTTP and any host not
compiled into the app, so the certificate must be valid; if the app was built with SPKI pins, renew the certificate
**with the same key** or follow the pin rotation steps in `mobile/README.md`.

The config **overwrites** `X-Forwarded-For` with the real client address. The audit log and the login rate
limit trust that header, so keep it that way. Also keep `FRONTEND_PORT=127.0.0.1:3000`, so that nobody can
reach the app without going through Nginx.

## 5. Backups

`deploy/backup.sh` makes a consistent nightly backup and keeps `BACKUP_RETENTION_DAYS` (default 14) of them in
`BACKUP_DIR` (default `/var/backups/communication-manager`, mode 700):

- `db-<time>.dump`: `pg_dump -Fc` of the whole database, checked with `pg_restore --list` before it is kept;
- `sms-media-<time>.tgz`: the `smsmedia` volume (encrypted MMS files);
- `checksums-<time>.sha256`.

```bash
# crontab -e (as a user in the docker group)
15 2 * * * /opt/communication-manager/deploy/backup.sh >> /var/log/cm-backup.log 2>&1
# and copy the directory off the server, for example:
45 2 * * * rsync -a --delete /var/backups/communication-manager/ backup@offsite:/srv/cm/
```

**Keys are not in the backup, and must never be stored with it.** The database holds mailbox tokens encrypted with
`MAIL_TOKEN_KEYS` and SMS/call text encrypted with `SMS_DATA_KEYS`; the media archive is encrypted with
`SMS_DATA_KEYS`. Keep those keys (and `DJANGO_SECRET_KEY`) **offline and separately**, for example in the company
password manager and on paper in a safe. A backup without its keys is useless — nobody, including you, can read the
messages — and a backup stored *with* its keys is a full copy of every conversation for whoever finds it. Treat dumps as
confidential anyway: numbers, names and timestamps are plaintext.

Redis holds only queues, nonces and counters; it is not backed up. Its AOF only protects queued tasks across restarts.

### Restore (tested procedure)

1. On the target server, check out the same version of the code and create `.env` with the **same**
   `MAIL_TOKEN_KEYS`, `SMS_DATA_KEYS` and `DJANGO_SECRET_KEY` from the offline copy.
2. `docker compose up -d postgres redis redis-cache`
3. `deploy/restore.sh /path/db-<time>.dump /path/sms-media-<time>.tgz` — verifies the checksums, asks you to type
   `restore`, stops the app containers, recreates the database, restores the dump and the media volume, and starts
   everything (migrations run on start).
4. Sign in; open an SMS conversation with an MMS photo (decrypts text and media) and a mailbox (decrypts its token).
5. Phones need nothing: they keep their identity and resume uploading; events the server had not yet stored when the
   backup was taken are uploaded again from each phone's outbox only if the phone still holds them, so take backups
   often enough for your tolerance.

Test a restore on a spare machine at least every quarter. The procedure above was run end to end on the Docker stack
during the deployment-hardening work (docs/status.md).

## 6. Updating

```bash
cd /opt/communication-manager
git pull
docker compose up -d --build          # migrations run on backend start
docker image prune -f
```

## 7. Rotating the token key

```bash
# 1. Prepend a new key: MAIL_TOKEN_KEYS=<new>,<old>
docker compose up -d
docker compose exec backend python manage.py rotate_mail_keys
# 2. Remove the old key from MAIL_TOKEN_KEYS, then:
docker compose up -d
```

## 7b. Rotating the SMS data key

```bash
# Prepend a new key: SMS_DATA_KEYS=<new>,<old>
docker compose up -d
docker compose exec backend python manage.py rotate_sms_keys   # SMS bodies, snippets, MMS files, call notes, call-back reasons, directory notes
# Remove the old key from SMS_DATA_KEYS, then:
docker compose up -d
```

## 7c. Phones (SMS)

1. Build and distribute the app privately (`mobile/README.md`).
2. Optional, for near-instant delivery: create a Firebase project, put `google-services.json` in the app build,
   set `FCM_PROJECT_ID` and mount the service account (`FCM_SERVICE_ACCOUNT_FILE`, never baked into the image).
3. In the admin: **SMS → Enroll phone**, scan the QR code with the app.

## 7d. Phones (Calls)

1. Install OCM Phone (`mobile_dialer/README.md`), a separate app from OCM Messages.
2. In the admin: **Calls → Phones → Enroll OCM Phone**. Pick the SMS phone on the same handset if it runs OCM Messages
   (the missed-call SMS is sent through it), then scan the QR with OCM Phone.
3. On the phone: accept the notice, *Set as default Phone app*, the call permissions and, on Android 14+, the
   incoming-call screen.
4. Set office hours, outcomes, tariffs and (optionally) the missed-call SMS under **Calls → Tools**.

Calls need no extra service or secret: they use the same device API, Redis, Celery and `SMS_DATA_KEYS`.

### Separate domains for the admin and the phone API

Phones may use their own domain, for example admin at `https://communicationadmin.schoolsoft.online` and phones at
`https://communicationapi.schoolsoft.online`:

```bash
PUBLIC_APP_URL=https://communicationadmin.schoolsoft.online     # connect links, OAuth redirect
SMS_DEVICE_API_URL=https://communicationapi.schoolsoft.online   # what the enrollment QR tells phones
DJANGO_ALLOWED_HOSTS=communicationadmin.schoolsoft.online,communicationapi.schoolsoft.online,127.0.0.1,localhost
```

Build the app with `--dart-define=ALLOWED_SERVER_HOSTS=communicationapi.schoolsoft.online` (the QR host must be on
that list, or the phone refuses it). Production refuses to start unless `SMS_DEVICE_API_URL` is `https://`.

On the API domain, expose **only** `/api/v1/device/` (the `location /api/v1/device/` block of `deploy/nginx.conf`,
with `return 404` for everything else). The admin API stays behind Next.js: keep `CM_API_ORIGIN` pointing at Django
over the private network (`http://127.0.0.1:8000` or `http://backend:8000`), not at the public API domain. That keeps
the admin API off the internet and keeps a single proxy hop, which `X-Forwarded-For` handling relies on.

## 8. Monitoring

- `docker compose logs -f backend worker beat` shows request logs and sync errors. Email bodies and tokens are
  never logged.
- The Gmail **Dashboard** shows mailboxes that need reconnecting or have sync errors.
- The SMS **Dashboard** and **Phones** page show phones that are offline, no longer the default SMS app, missing a
  permission, battery-optimised, behind on uploads or running an old app.
- Point an uptime monitor at `https://YOUR.DOMAIN/api/v1/health/` (it returns `{"ok": true}` when Django is up; the
  backend container's health check uses the same URL).
- Container logs rotate (json-file driver, `LOG_MAX_SIZE` × `LOG_MAX_FILES` per container, default 10 MB × 5).
- Watch the broker/security Redis memory: `docker compose exec redis redis-cli info memory | grep used_memory_human`.

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` | `config.settings.prod` on a server |
| `DJANGO_SECRET_KEY` | dev-only value | **Required in prod** |
| `DJANGO_DEBUG` | `false` | Never `true` in prod (prod forces it off) |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,backend` | Add your domain |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `http://localhost:3000` | `https://your.domain` |
| `COOKIE_SECURE` | `false` | Prod forces secure cookies |
| `SESSION_COOKIE_AGE` | `43200` (12 h) | Seconds |
| `TIME_ZONE` | `Africa/Dar_es_Salaam` | Server and Celery time zone |
| `LOG_LEVEL` | `INFO` | |
| `GUNICORN_WORKERS` | `3` | About 2 × CPU + 1 |
| `CELERY_CONCURRENCY` | `2` | Worker processes |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `cm` / `cm` / `cm` | **Strong password in prod** |
| `DATABASE_URL` | built by compose | Manual setups only |
| `REDIS_URL` | built by compose | Celery broker + security store (noeviction, AOF). Empty = tasks run inline (dev only; prod refuses) |
| `REDIS_CACHE_URL` | built by compose | Evictable cache (allkeys-lru). Empty = DB 1 on `REDIS_URL`'s server (dev only) |
| `REDIS_MAXMEMORY` / `REDIS_CACHE_MAXMEMORY` | `256mb` / `128mb` | Compose: memory of the two Redis instances |
| `LOG_MAX_SIZE` / `LOG_MAX_FILES` | `10m` / `5` | Compose: log rotation per container |
| `BACKUP_DIR` / `BACKUP_RETENTION_DAYS` | `/var/backups/communication-manager` / `14` | `deploy/backup.sh` |
| `COMPANY_NAME` | `Your Company` | Shown on the public connect page |
| `PUBLIC_APP_URL` | `http://localhost:3000` | Used for connect links and the OAuth redirect |
| `SEED_DEMO` | `1` (compose) | `0` in prod |
| `FRONTEND_PORT` | `3000` | `127.0.0.1:3000` in prod |
| `MAIL_TOKEN_KEYS` | — | **Required in prod.** Fernet keys, newest first |
| `MAIL_ENABLE_FAKE_PROVIDER` | `true` (dev) / `false` (prod) | Demo mailboxes |
| `MAIL_INITIAL_SYNC_DAYS` | `90` | Initial sync window |
| `MAIL_INITIAL_SYNC_MAX_THREADS` | `3000` | Initial sync cap |
| `MAIL_INVITE_TTL_HOURS` | `72` | Connect-link lifetime |
| `MAIL_BODY_CACHE_DAYS` | `14` | Cached body eviction |
| `MAIL_MAX_ATTACHMENT_BYTES` | `26214400` | 25 MB, Gmail's limit |
| `MAIL_RATE_PER_SECOND` | `15` | Per-mailbox Gmail API budget |
| `GOOGLE_OAUTH_CLIENT_ID` / `_SECRET` | — | From Google Cloud |
| `GOOGLE_OAUTH_REDIRECT_URI` | `${PUBLIC_APP_URL}/api/v1/mail/oauth/callback/` | Must match Google Cloud exactly |
| `GOOGLE_OAUTH_SCOPES` | openid, email, mail.google.com, gmail.settings.basic | Comma separated |
| `SECURE_HSTS_SECONDS` | `2592000` | Prod only |
| `SMS_DATA_KEYS` | dev-only value | **Required in prod.** Fernet keys for all device-derived data (SMS bodies and MMS files, call notes, call-back reasons, directory notes), newest first, not shared with `MAIL_TOKEN_KEYS` |
| `SMS_DEVICE_API_URL` | `PUBLIC_APP_URL` | https URL phones use, encoded in the enrollment QR; must be in the app's `ALLOWED_SERVER_HOSTS` |
| `SMS_MEDIA_ROOT` | `backend/private/sms-media` (`/data/sms-media` in compose) | Encrypted MMS files, private |
| `SMS_MAX_MMS_BYTES` | `2097152` | Per MMS part |
| `SMS_INITIAL_SYNC_DAYS` | `90` | History copied at enrollment |
| `SMS_ENROLL_TTL_HOURS` | `24` | Enrollment code lifetime |
| `SMS_DEVICE_TOKEN_TTL` | `15` | Device token lifetime, minutes |
| `SMS_MIN_APP_VERSION` | `1.0.0` | Older apps get 426 |
| `SMS_REQUIRE_KEY_ATTESTATION` | `false` | Needs `SMS_ATTESTATION_ROOTS_FILE` (Google roots, PEM) |
| `SMS_REQUIRE_PLAY_INTEGRITY` | `false` | Needs `PLAY_INTEGRITY_PACKAGE_NAME`, `PLAY_INTEGRITY_SERVICE_ACCOUNT_FILE`, optionally `PLAY_INTEGRITY_CERT_DIGESTS` |
| `SMS_OUTBOUND_TTL_HOURS` | `24` | Unsent admin messages expire |
| `SMS_DEVICE_DAILY_CAP` | `300` | Admin messages per phone per day |
| `SMS_DEVICE_RATE_PER_MINUTE` / `SMS_USER_RATE_PER_MINUTE` | `20` / `30` | Send rate limits |
| `SMS_ALLOW_SHORT_CODES` | `false` | Short codes can be premium-rate |
| `SMS_RETENTION_DAYS` | `365` | `0` keeps messages forever |
| `SMS_MIRROR_DEVICE_DELETES` | `false` | Phone deletions also delete the server copy |
| `SMS_DEFAULT_REGION` | `TZ` | For numbers without a country code |
| `SMS_SHOW_ADMIN_NAME_ON_PHONE` | `true` | "Sent by admin · Name" on the phone |
| `SMS_DEVICE_POLL_SECONDS` | `20` | Phone poll interval without FCM |
| `SMS_ENABLE_SIMULATOR` | `true` (dev) / `false` (prod) | Simulated demo phones; prod refuses `true` |
| `CALLS_RETENTION_DAYS` | `365` | Server copy of calls, events and notes; `0` keeps them forever. Calls → Settings may set a shorter period |
| `FCM_PROJECT_ID` / `FCM_SERVICE_ACCOUNT_FILE` | — | Optional push wake-ups; the file is a mounted secret |
