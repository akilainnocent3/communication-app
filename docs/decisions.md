# Decisions

Defaults chosen without asking, with the reason. Newest at the bottom.

1. **Repo root is this folder**, not a nested `communication-manager/` folder. The reference admin lives in
   `reference/shop-admin/` and is git-ignored (it belongs to another project).
2. **Python 3.14** is used in the dev container because the image's Python 3.12 lacks `venv`; the code
   targets 3.12+ and the Docker image uses `python:3.12-slim`.
3. **Users log in with email + password.** Usernames are not used anywhere.
4. **Roles are Django `Group`s** with a `Role` model on top (slug, name, description, rank). Permissions are
   Django permissions plus a few custom ones (`mail.access`, `mail.manage_mailboxes`, `audit.view`,
   `identity.manage_users`, `platforms.manage`). Super admin = `is_superuser`.
5. **Admins (Super admin and Admin roles) implicitly have full access to every mailbox.** Office managers and
   viewers need `MailboxAccess` rows.
6. **Thread is the unit of action.** Bulk actions take thread ids, like Gmail's conversation view.
7. **Undo send** is a `ScheduledEmail` with `kind=undo` and `send_at = now + delay`; Celery beat picks up
   due rows every 5 s in dev (Celery `eta` is also set when a worker is running). Cancelling deletes the row
   if it has not been claimed. One mechanism serves both undo send and schedule send.
8. **Without Redis/Celery** (unit tests, quick local dev) tasks run eagerly (`CELERY_TASK_ALWAYS_EAGER`).
9. **QR codes are generated server-side** as SVG with `qrcode` (no client dependency, works offline).
10. **Local search** uses Postgres full-text search (`search_vector` on subject, snippet, participants) and
    falls back to `icontains` on SQLite.
11. **The fake provider is a real provider**: it stores its mailbox state in its own table
    (`FakeMessage`) so actions, sends and syncs round-trip exactly like Gmail (incremental history ids
    included). This keeps the sync engine honest in tests and demos.
12. **Message bodies** are cached sanitised on `Message.body_html`/`body_text` with `body_cached_at`; a
    beat task evicts bodies older than `MAIL_BODY_CACHE_DAYS` (default 14).
13. **The theme defaults to the device setting** (`system`), not light. Office staff often open connect links on
    phones in dark mode; the header toggle still lets anyone pin light or dark.
14. **Attachments are CSP-sandboxed by default.** Chrome will not render a PDF inside a sandboxed response, so
    the in-app PDF preview asks for `?preview=1`, which drops only `sandbox` (scripts stay blocked by
    `default-src 'none'`). Downloads and images keep the sandbox.
15. **Thread rows use container queries** (`@container`), not viewport breakpoints, because the list pane is
    narrow in the 3-pane layout even on wide screens.
16. **Native checkboxes are drawn with CSS** (`appearance: none`, theme tokens, 3:1 border contrast). Chromium on
    phones paints unchecked boxes solid white even with `color-scheme: dark`.
17. **Client IP = first `X-Forwarded-For` entry, and Nginx overwrites that header.** The audit log and the login
    throttle (`ClientIpScopedThrottle`) both use it. DRF's default throttle key is the whole header, which a
    client could vary to get past the limit. The frontend port binds to `127.0.0.1` in production, so Nginx
    is the only way in.
18. **Toasts follow the app theme** through a small client `ThemedToaster`. Sonner otherwise stays light.
19. **The SMS build started from `main`, not `claude/busy-knuth-u7r940`.** That branch was not in this repository. The
    SMS work is on `feature/sms-platform`. `is_platform_enabled()` did not exist yet, so it was added to
    `modules/platforms/services.py`, and `can_use_mail` now uses it as docs/security.md already promised: a disabled
    platform refuses its whole API (SMS and Gmail, including the phone-facing SMS endpoints).
20. **`modules/devices` is generic; SMS data lives in `modules/sms`.** Enrollment, Keystore identity, tokens, heartbeat,
    commands and push know nothing about SMS, so the Calls platform can reuse them on the same phone.
21. **Two API surfaces that cannot be mixed.** `/api/v1/device/` (own URL module, `DeviceAPIView`, Bearer tokens only, no
    cookies so no CSRF) and the admin API (session + CSRF). A device token sent to the admin API is ignored (401); a
    browser session sent to the device API is ignored (401). Nginx sends `/api/v1/device/` straight to Django.
22. **Suspended ≠ revoked on the phone.** The brief asked for `401 device_revoked` for both, but a suspended phone
    that wiped its key could never be resumed. Suspended answers `403 device_suspended` (the app keeps its data and
    retries every 15 min); revoked answers `401 device_revoked` (the app deletes key, sync database and settings).
    Both stop every outstanding token at once because each request re-checks the device status.
23. **Key attestation is verified, but "required" needs the Google roots file.** The server parses the KeyDescription
    extension (security level, challenge = SHA-256 of the enrollment token) and checks the chain and the leaf key.
    Trusted roots come from `SMS_ATTESTATION_ROOTS_FILE`; production refuses `SMS_REQUIRE_KEY_ATTESTATION=true` without
    it. Google's revocation list is not checked yet (follow-up).
24. **Message text is encrypted at rest with its own key ring (`SMS_DATA_KEYS`).** Bodies, list snippets, MMS files and
    the simulator's keys use MultiFernet; numbers, contact names and timestamps stay plaintext. Consequences: the
    database cannot search message text. Conversation search matches contact names and numbers; search inside one
    open conversation decrypts that conversation's messages for that request only (and never matches masked
    sensitive messages). The dashboard uses metadata only.
25. **Sync idempotency by sequence and by message identity.** The server stores each phone's highest processed event
    sequence; anything at or below it is skipped. Messages are unique by (device, kind, provider id, provider date) or
    by `client_uuid`. Malformed events are rejected *and* acknowledged, so one bad event can never block a phone's
    queue; the reason codes are logged (counts only).
26. **At-most-once outbound.** A claim leases messages for 120 s. Until the phone reports `sending`, an expired lease
    re-offers the message; after that the server never offers it again. The phone writes its durable `sending` mark
    before calling SmsManager and refuses any `client_uuid` it has started, so re-offers are harmless. A send without a
    result becomes `unknown` (phone: after 10 min; server: after `SMS_OUTBOUND_TTL_HOURS`) and the admin is told to
    check with the customer before resending. Cancelling is only possible while `queued` (never offered).
27. **Undo and schedule share `send_at`**, like `ScheduledEmail`: undo = now + the user's `undo_send_seconds`. Messages
    whose `send_at` is older than `SMS_OUTBOUND_TTL_HOURS` expire instead of going out days late.
28. **Freshness by polling, not SSE/WebSockets.** Conversation list 10 s, open chat 5 s, phones 30 s, paused while the
    tab is hidden. The backend runs on WSGI (gunicorn) and Gmail already polls; long-lived connections would need an
    ASGI server and a channel layer. Worth doing later, together with Gmail push.
29. **Conversation actions undo by their inverse** (archive ↔ unarchive …) instead of server-side undo tokens: every
    SMS action is reversible by another action, and nothing is deleted from the server by the admin.
30. **Contacts are minimised.** The phone looks up names only for numbers in its conversations, and the server accepts
    `contact.upsert` only for addresses that already appear in that phone's conversations.
31. **Deletions on the phone keep the server copy** (`SMS_MIRROR_DEVICE_DELETES=false`): the company copy is the
    accountability record, the admin shows "Deleted on phone". Retention (`SMS_RETENTION_DAYS`, default 365) bounds
    how long it is kept (PDPA storage limitation). Both are documented settings, not code changes.
32. **Sensitive messages** (one-time codes, banks, mobile money) are detected on arrival with built-in English/Swahili
    patterns plus admin rules, masked by replacing every token that contains a digit, and revealed only with the
    `can_reveal_sensitive` flag; each reveal is audited.
33. **Default admin signature uses a plain hyphen** ("- Head Office"). An em dash is not in GSM-7 and silently turns
    every signed message into UCS-2 (70 characters per SMS); the enroll dialog says so.
34. **The phone app keeps all HTTPS in native code.** Dart's `HttpClient` cannot pin an SPKI before sending data, so the
    Dart API client goes through a Pigeon call to OkHttp with `CertificatePinner` (TLS 1.2+, no redirects, allow-listed
    hosts only). Tests replace the transport with a fake.
35. **One encrypted database, two writers.** Native receivers append outbox events to the SQLCipher file that drift
    owns (`net.zetetic:sqlcipher-android` on the Kotlin side, package:sqlite3's SQLCipher build on the Dart side — the
    old `sqlcipher_flutter_libs` package is end-of-life). The passphrase is random, wrapped by a Keystore AES key. The
    schema is created by drift at enrollment; native code writes nothing before that (the backfill covers it).
36. **The Dart sync loop runs in a headless engine inside the foreground service** (type `remoteMessaging`), started
    by the app, boot, WorkManager (periodic 15 min + expedited "sync now") or an FCM data message. Receivers never need
    the engine: they write the provider and the outbox natively.
37. **Simulated phones are real clients.** `simulate_sms_device` and `seed_demo` enroll through the real enroll and token
    endpoints with a real EC key, and the admin's demo controls (offline, online, process outbox, receive a text) exist
    only when `SMS_ENABLE_SIMULATOR` is on; production refuses to start with it.
38. **Admin-facing SMS serializers carry an `Sms` prefix** and the Gmail enum names are pinned in
    `ENUM_NAME_OVERRIDES`, so adding SMS changed none of Gmail's generated TypeScript types.
39. **The phone falls back to a non-attested key instead of failing enrollment.** Key generation tries StrongBox, then
    the TEE with attestation, then the TEE without attestation: some OEM builds advertise StrongBox or attestation and
    then fail with errors the API does not document, which crashed enrollment. The server already records whether the
    key is hardware-attested, and `SMS_REQUIRE_KEY_ATTESTATION=true` still refuses such phones, so the security decision
    stays on the server.
40. **A sync database whose key is permanently lost is reset, not retried.** If the Keystore key that wraps the SQLCipher
    passphrase is gone or invalidated (or the stored passphrase is missing), the database can never be opened again;
    the app deletes it and asks to enroll again instead of failing on every start and every incoming SMS. Transient
    Keystore errors are not treated as loss. The phone's own SMS are never touched, and the server keeps its copy.
