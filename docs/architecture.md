# Architecture

Communication Manager is a Django API (`backend/`) behind a Next.js app (`frontend/`). Each communication
channel is a **platform**: Gmail and SMS are built. Inside the Gmail platform, every mail server is reached through
one **provider** interface. The SMS platform talks to enrolled company phones running the Android app in `mobile/`
(design: [sms-mobile.md](sms-mobile.md)).

## Request path

```mermaid
flowchart LR
  B[Browser] -->|HTTPS| N[Nginx]
  N --> F["Next.js :3000<br/>pages + /api/v1/* rewrite"]
  F -->|/api/v1/*| D["Django + DRF :8000<br/>(gunicorn)"]
  D --> P[(PostgreSQL 16)]
  D --> R[(Redis)]
  R --> W[Celery worker]
  BT[Celery beat] --> R
  W --> P
  W -->|Gmail API / IMAP / SMTP| G[(Mail servers)]
  D -->|on-demand bodies, actions| G
  PH[Company phones<br/>SMS app] -->|HTTPS, pinned<br/>/api/v1/device/*| N
  N -->|/api/v1/device/*| D
  W -->|FCM data-only wake-ups| PH
```

- Phones use a second path: `Phone → Nginx → Django /api/v1/device/…` (no Next.js hop). That surface accepts only
  short-lived device tokens (`Authorization: Bearer`), never cookies; the admin surface accepts only sessions.
- The browser talks only to Next.js. Next.js rewrites `/api/v1/*` to Django, so the session cookie
  (`cm_session`) and CSRF cookie (`cm_csrftoken`) are same-origin and there is no CORS.
- Django holds all state and business logic. Views are thin. Logic lives in `modules/<module>/services/`.
- Celery runs anything slow or delayed: syncs, undo send, scheduled send, snooze wake-ups and body-cache
  eviction. Without `REDIS_URL`, tasks run inline (tests, quick dev).

## Backend modules

| Module | Responsibility |
|---|---|
| `common/` | Error shape (`{code, detail, errors}`), CSRF session auth, cursor pagination, permission helpers, MultiFernet crypto, client IP and throttling |
| `modules/identity` | Email-login `User`, `Role` (on top of Django `Group`), `Office`, login/logout/me, optional TOTP |
| `modules/platforms` | `PlatformRegistry` + `Platform` model (enable, disable and order platforms) |
| `modules/audit` | Append-only `AuditEvent`, list API and CSV export |
| `modules/mail` | The Gmail platform: models, providers, services, API, Celery tasks |
| `modules/devices` | Company phones, shared by phone platforms: enrollment invites, Keystore identity + key attestation, proof-of-possession device tokens, `DeviceTokenAuthentication`, heartbeat and health alerts, commands, FCM push, suspend/revoke |
| `modules/sms` | The SMS platform: encrypted conversations/messages/MMS parts, sync events, outbound queue (leases, at-most-once), access (`DeviceAccess`), analytics, retention, simulated phones |

## Platform registry

```mermaid
flowchart TB
  subgraph Backend
    AC["AppConfig.ready()"] -->|register PlatformSpec| REG[PlatformRegistry]
    REG --> PM[(Platform rows:<br/>is_enabled, order)]
    PM --> API["GET /api/v1/platforms/<br/>enabled ∩ user has permission"]
  end
  subgraph Frontend
    DEF["platforms/gmail/definition.tsx<br/>nav, badges, ContextSwitcher, commands"] --> PL["registry.ts PLATFORMS"]
    CS["coming-soon.tsx<br/>SMS · Calls · Media"] --> PL
    PL --> VIS["visiblePlatforms(server list)"]
    API --> VIS
    VIS --> SW[Header platform switcher]
    URL["first URL segment /gmail/…"] -->|platformForPath| SB["Sidebar: that platform's nav<br/>+ shared Settings"]
  end
```

- **Backend:** a platform is a Django app that registers a `PlatformSpec(key, name, permission,
  default_enabled)` in `AppConfig.ready()`. A `Platform` row stores whether a super admin enabled it and its
  order (**Settings → Platforms**). `GET /api/v1/platforms/` returns the enabled platforms whose permission the
  user has.
- **Frontend:** `src/platforms/registry.ts` lists `PlatformDefinition`s. Each definition owns its sidebar
  sections, badge hook, context switcher (Gmail's mailbox switcher), and ⌘K commands. The header switcher
  shows the intersection of the server list and the code registry. Coming-soon platforms show as disabled
  with a "Soon" badge.
- The active platform is the first URL segment. Switching platforms restores the last route visited in that
  platform (`localStorage`, falling back to the platform home).

See [adding-a-platform.md](adding-a-platform.md). The design was tested by adding a stub SMS platform behind
a flag and then removing it (screenshot `docs/screenshots/desktop-light-sms-stub-proof.png`).

## Provider layer

```mermaid
classDiagram
  class MailProvider {
    capabilities()
    list_labels() / create / update / delete_label
    list_threads() / get_thread() / get_threads()
    modify_threads() / trash / untrash / delete_permanently
    mark_spam() / mark_not_spam()
    send(mime) / drafts_*
    get_attachment() / get_raw()
    sync_full() / sync_incremental(cursor)
    list_send_as() / update_signature()
    filters_*() / vacation_get() / vacation_set()
  }
  MailProvider <|-- GmailApiProvider : gmail_oauth
  GmailApiProvider <|-- WorkspaceDelegationProvider : impersonated service account
  MailProvider <|-- ImapSmtpProvider : imap_smtp
  MailProvider <|-- FakeMailProvider : fake (demo, tests)
```

- `providers/base.py` defines the interface, the data classes (`ProviderThread`, `ProviderMessage`,
  `ChangeSet`, `Capabilities`…) and typed errors: `AuthError` sets the mailbox to `needs_reconnect`,
  `CursorExpired` triggers a full resync, and `Unsupported` covers features a provider lacks.
- `capabilities()` tells the UI what to hide. IMAP has no Gmail filters, categories or server-side vacation.
- Credentials are stored in `Mailbox.encrypted_credentials` (MultiFernet) and decrypted only inside the
  provider.
- `FakeMailProvider` stores its own server state (`FakeMessage`) and history IDs, so the sync engine,
  actions and sends round-trip exactly as they do with Gmail. The demo and the E2E tests run on it.

### Choosing a provider

When an admin adds a mailbox (`services/mailboxes.py` → `detect`):

1. `@gmail.com` / `@googlemail.com` → `gmail_oauth`.
2. Otherwise, look up the domain's MX records (dnspython):
   - Google MX → `workspace_delegation` if the domain has a verified delegation config, else `gmail_oauth`.
   - Microsoft 365 MX → refused with "Microsoft 365 mailboxes are not supported yet."
   - Anything else → `imap_smtp`, prefilled with `mail.<domain>`, 993 / 465 (or 587 STARTTLS).

## Connecting a Google mailbox

```mermaid
sequenceDiagram
  actor Admin
  actor Staff as Office staff
  participant CM as Communication Manager
  participant G as Google
  Admin->>CM: Add mailbox → Send connect link
  CM-->>Admin: single-use link (token hash stored, 72 h), Copy · WhatsApp · QR
  Admin->>Staff: shares link
  Staff->>CM: GET /connect/{token}
  CM-->>Staff: notice + "Connect with Google"
  Staff->>CM: /mail/oauth/start
  CM->>G: redirect (PKCE, offline, prompt=consent, login_hint, signed state)
  G-->>CM: /mail/oauth/callback?code&state
  CM->>CM: verify state · exchange code · check email == mailbox · check scopes
  CM->>CM: encrypt refresh token · mark invite used · status=connected
  CM--)CM: queue initial sync (Celery)
  CM-->>Staff: "Mailbox connected"
  loop every 5 s while dialog open
    Admin->>CM: GET invite status
  end
```

A wrong account or a missing scope stores nothing and shows a retry screen. Later, `invalid_grant` or a
revoked token sets `needs_reconnect`, and the UI offers "Send reconnect link".

## Sync flow

```mermaid
flowchart TB
  T1["beat: mail.sync_all_mailboxes (60 s)"] --> Q
  T2[user action / connect / Sync now] --> Q["mail.sync_mailbox(id)"]
  Q --> L{SyncLock<br/>per mailbox}
  L -->|held| X[skip]
  L --> C{history_id stored?}
  C -->|no| FS["full_sync: newest first, metadata only,<br/>≤ MAIL_INITIAL_SYNC_DAYS / _MAX_THREADS,<br/>batches of ≤ 50, progress shown in UI"]
  C -->|yes| IS["incremental_sync: history.list from history_id"]
  IS -->|CursorExpired 404| FS
  IS --> ST["store: upsert Thread / Message / Label,<br/>search_vector, contacts"]
  FS --> ST
  IS -->|AuthError| NR[status = needs_reconnect]
```

- **Bodies** are fetched when a thread opens, sanitised (nh3), cached on `Message.body_html`, and evicted
  after `MAIL_BODY_CACHE_DAYS` by `mail.evict_cached_bodies` (every 6 h).
- **Quota safety:** each mailbox has a token bucket in the shared cache (Redis) (`MAIL_RATE_PER_SECOND`, kept below Gmail's
  per-user limit). Calls back off exponentially with jitter on 429 and `rateLimitExceeded` /
  `userRateLimitExceeded`. API requests never wait on a sync.
- **Actions** (`services/actions.py`) update the local index first, then call the provider. The response
  returns the updated thread summaries, so the client reconciles its optimistic update.
- **Sending:** undo send and schedule send are both `ScheduledEmail` rows. `mail.dispatch_due_sends` (every
  5 s) claims due rows. Cancelling before the claim deletes the row.
- **Push:** Gmail Pub/Sub `users.watch` is not required. A webhook can call `mail.sync_mailbox` later.

## SMS: sync and outbound

```mermaid
sequenceDiagram
  participant P as Phone (receiver, native)
  participant O as SQLCipher outbox
  participant L as Sync loop (headless Dart, foreground service)
  participant D as Django /device/
  participant A as Admin (browser)
  P->>O: new SMS → provider row + event (seq)
  P-->>L: event / network back / FCM
  L->>D: POST sync/events (≤ 200)
  D-->>L: acked_seq
  L->>O: delete ≤ acked_seq
  A->>D: POST /sms/send (queued, send_at = now + undo)
  D-->>P: FCM {"type":"outbox"} (no content)
  L->>D: POST outbox/claim (lease 120 s)
  L->>P: durable "sending" mark → SmsManager
  P-->>L: sent / delivered receivers
  L->>D: POST outbox/status (sending, sent, delivered)
  A->>D: poll chat (5 s): Queued → Sent to phone → Sending → Sent → Delivered
```

Celery beat adds: `sms.dispatch_due` (5 s, wakes phones whose undo/schedule window ended), `sms.expire_outbound`
(1 min), `devices.refresh_health` (1 min, offline/attention), `devices.prune` (hourly: heartbeats, tokens, invites,
commands), `sms.retention_purge` (6 h), `sms.media_cleanup` (hourly), `sms.simulator_tick` (5 s, demo only).

## Frontend

```
src/
  app/(auth)/login                 sign-in
  app/(connect)/connect/[token]    public connect page (no shell)
  app/(app)/layout.tsx             shell: sidebar · header (switcher, ⌘K, theme, profile) · content panel
  app/(app)/gmail/…                mail workspace, dashboard, mailboxes, labels, tools
  app/(app)/settings/…             users & roles, offices, platforms, integrations, audit log, preferences
  platforms/registry.ts            PLATFORMS + helpers
  platforms/gmail/                 definition, nav, API hooks, mail components, compose, shortcuts
  platforms/sms/                   definition, DeviceSwitcher, API hooks, inbox/chat/composer, devices, tools
  app/(app)/sms/…                  inbox folders, outbox, scheduled, dashboard, contacts, phones, tools
  components/tailgrids/core        UI primitives (react-aria-components), from the reference design system
  components/shell, components/ui  app shell and shared page patterns (tables, states, cards)
  services/api/                    fetch client (CSRF, ApiError, session-expired event) + generated schema.d.ts
```

- Server state is in TanStack Query. List and thread queries use a `staleTime`. Every mail action is
  optimistic, rolls back on error, and offers undo where it makes sense.
- Long lists are virtualised (`@tanstack/react-virtual`). The 3-pane layout uses `react-resizable-panels`,
  and pane sizes are remembered.
- API types are generated from `contracts/openapi.yaml` (drf-spectacular → openapi-typescript), not written
  by hand.
- User-facing text for the shell and mail lives in `src/i18n/en.ts`, so Swahili can be added later.
