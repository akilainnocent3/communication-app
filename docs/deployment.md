# Deployment (single VPS)

The whole system runs on one small Linux VPS with Docker Compose behind Nginx. A 2 vCPU / 4 GB RAM server is
enough for dozens of mailboxes. Add disk if you keep a long sync window, because the local index grows with
mail volume.

```
Internet ─HTTPS─▶ Nginx :443 ─▶ frontend :3000 (127.0.0.1 only) ─▶ backend :8000 (Docker network)
                                                                    ├─ postgres, redis
                                                                    └─ worker, beat
```

## 1. Prepare the server

```bash
# Ubuntu 24.04 example
sudo apt update && sudo apt install -y docker.io docker-compose-v2 nginx certbot python3-certbot-nginx git
sudo usermod -aG docker $USER   # log out and back in
sudo timedatectl set-timezone Africa/Dar_es_Salaam
```

Point a DNS `A` record (for example `mail.company.co.tz`) at the server, and open ports 80 and 443 only.

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
DJANGO_ALLOWED_HOSTS=mail.company.co.tz,localhost,backend
DJANGO_CSRF_TRUSTED_ORIGINS=https://mail.company.co.tz
POSTGRES_PASSWORD=<strong random password>
PUBLIC_APP_URL=https://mail.company.co.tz
COMPANY_NAME=Kilimanjaro Trading Ltd
FRONTEND_PORT=127.0.0.1:3000
SEED_DEMO=0
MAIL_ENABLE_FAKE_PROVIDER=false
MAIL_TOKEN_KEYS=<python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
```

Keep `localhost` and `backend` in `DJANGO_ALLOWED_HOSTS`, because the container health check and the
frontend proxy use those host names. Production settings refuse to start without a real `DJANGO_SECRET_KEY`
and `MAIL_TOKEN_KEYS`, or with the dev-only key.

**Back up `MAIL_TOKEN_KEYS` somewhere safe outside the server** (a password manager). Without it, every
stored mailbox connection is unreadable and every mailbox must be reconnected.

Set up Google first ([google-setup.md](google-setup.md)) and register
`https://mail.company.co.tz/api/v1/mail/oauth/callback/` as an authorised redirect URI.

## 3. Start

```bash
docker compose up -d --build
docker compose ps                     # all services "healthy" / "running"
docker compose exec backend python manage.py createsuperuser
```

The backend container runs migrations on every start. Sign in, then add offices, users and mailboxes.

## 4. Nginx and HTTPS

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/communication-manager
sudo sed -i 's/mail.company.co.tz/YOUR.DOMAIN/g' /etc/nginx/sites-available/communication-manager
sudo ln -s /etc/nginx/sites-available/communication-manager /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
# First certificate: temporarily comment out the 443 server block, reload, then:
sudo certbot --nginx -d YOUR.DOMAIN
sudo nginx -t && sudo systemctl reload nginx
```

Certbot renews certificates automatically (`systemctl list-timers | grep certbot`).

The config **overwrites** `X-Forwarded-For` with the real client address. The audit log and the login rate
limit trust that header, so keep it that way. Also keep `FRONTEND_PORT=127.0.0.1:3000`, so that nobody can
reach the app without going through Nginx.

## 5. Backups

```bash
# Nightly database dump (crontab -e)
15 2 * * * cd /opt/communication-manager && docker compose exec -T postgres pg_dump -U cm -Fc cm > /var/backups/cm-$(date +\%F).dump && find /var/backups -name 'cm-*.dump' -mtime +14 -delete
```

Copy the dumps off the server. Restore with
`docker compose exec -T postgres pg_restore -U cm -d cm --clean < cm-YYYY-MM-DD.dump`. The database holds the
encrypted tokens, so a dump is only useful together with `MAIL_TOKEN_KEYS`. For the same reason, a dump
alone does not expose the tokens. Treat dumps as confidential anyway: they contain mail metadata and
cached bodies.

Redis holds only queues and caches, so it does not need a backup.

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

## 8. Monitoring

- `docker compose logs -f backend worker beat` shows request logs and sync errors. Email bodies and tokens are
  never logged.
- The Gmail **Dashboard** shows mailboxes that need reconnecting or have sync errors.
- Point an uptime monitor at `https://YOUR.DOMAIN/api/v1/auth/csrf/` (it returns 200 when Django is up).

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
| `REDIS_URL` | built by compose | Empty = tasks run inline (dev) |
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
