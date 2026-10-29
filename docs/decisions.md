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
41. **The sync engine is native Kotlin; Dart only enrolls.** The foreground service used to boot a second Flutter
    engine and Dart isolate (tens of MB, seconds to start, a second database opener, and a loop that died for good on
    one uncaught platform exception). `sync/NativeSyncEngine.kt` is a port of the Dart engine with the same protocol,
    idempotency, at-most-once guard and backoff; the Dart tests were ported to Robolectric + MockWebServer. WorkManager,
    FCM, boot and the service all run the same engine; one process-wide lock serialises cycles and a request during a
    cycle runs it once more. Dart keeps the enrollment client (it shows the notice) and reads what the engine caches.
42. **Data methods are `@async` on `Dispatchers.IO`, not one serial Pigeon task queue.** A serial background queue
    takes the work off the main thread but lets one slow call (a body search, a 2 000-message page) hold up the list's
    refresh. Concurrent IO calls don't. Quick binder getters (`roleStatus`, `permissions`, `startup`) use the task
    queue; only Activity calls (role and permission requests, settings screens, FLAG_SECURE) run on main.
43. **SQLCipher raw key, migrated natively before anyone opens the file.** The key is 32 random bytes, so PBKDF2
    (256 000 iterations per open, per opener) bought nothing. `DatabaseKey.ensureRawKey` runs under the key's lock
    before `startup()` hands the key to Dart and before any receiver opens the store; rekey happens in rollback-journal
    mode (it rewrites every page) and the result is verified before the flag is set. New databases start raw.
44. **Read caches live in the same encrypted database and the provider stays the truth.** `thread_cache` (one row per
    conversation) and `message_cache` (each conversation's newest 50) give the first frame something to draw; the
    provider's newest page then replaces the window it covers, so a thread deleted elsewhere disappears and the cache is
    pruned. Nothing else is cached, nothing is logged, and the wipe on revoke deletes them with the file.
45. **Events are precise and coalesced on both sides.** Native events carry the thread id; the UI coalesces them for
    250 ms and refreshes that row and, if open, that chat. The `content://mms-sms/` observer runs only while the UI
    listens, is debounced 500 ms and ignores changes for 1.5 s after the app's own writes (which already raised precise
    events). The app's own actions (archive, pin, mark read) update state directly and raise no event at all.
46. **With FCM, the service polls every 5 minutes; without it, every 20 s.** A registered push token means admin replies
    wake the phone; polling every 20 s on top only costs radio time. Without FCM the server's `poll_seconds` stays the
    fallback. FCM is now required in the production checklist (docs/deployment.md, docs/sms-mobile.md).
47. **The QR scanner uses Google Play services' barcode model (unbundled).** Bundling ML Kit's model cost about 5 MB per
    ABI for a screen used once per phone. The model is fetched at install time (`com.google.mlkit.vision.DEPENDENCIES`).
    Phones without Play services (some Huawei) can't scan: they enroll with the link or the 8-character short code.
48. **Short codes: HMAC, a second token per invite, and a global breaker instead of per-invite counting.** The code is
    40 bits (8 Crockford characters); a bare SHA-256 of it could be brute-forced from a database copy, so it is stored
    as an HMAC with `SECRET_KEY`. Resolving it issues a fresh token for the invite (only its hash kept, usable for the
    code's 15 minutes) rather than storing the QR token reversibly; the QR keeps working. A wrong code does not say
    which invite it was aimed at, so misses cannot be counted "per invite" without giving up entropy to an invite
    selector. Instead: 5/min and 20/h per IP, and `SMS_SHORT_CODE_MAX_FAILURES` (50) misses from everyone within 15
    minutes lock every live short code (QR and links unaffected), audited. Once a code resolves, the invite's existing
    five-failure burn applies to enrollment attempts with its token.
49. **Receivers upload the new message themselves when the service is down.** After the provider row and the outbox
    event, the SMS/MMS receiver uploads inside its goAsync window (8 s budget, calls bounded by an OkHttp call timeout,
    sharing the engine's process lock) and then queues expedited work for the rest. With the service up, it just
    nudges the service.
50. **A refused foreground start is remembered, never looped on.** Android 12+ refuses background starts outside its
    exemptions; the refusal is kept for 15 minutes and WorkManager runs the engine itself meanwhile. Exemptions that do
    start it: high-priority FCM, BOOT_COMPLETED, MY_PACKAGE_REPLACED, the battery-optimisation exemption.
51. **Skins are tokens plus two layout variants.** `SkinTokens` (a ThemeExtension) carries every visual decision;
    screens read tokens and never test which skin is active, except for the header and the compose button, which are
    variants chosen by token. "Match my phone" is resolved from manufacturer/brand at each start (nothing to migrate if
    the mapping improves). The Pixel skin seeds Material 3 from the wallpaper accent colour, read before the first frame:
    `dynamic_color`'s full schemes now use `material_ui`'s `ColorScheme`, a different type from Flutter's.
52. **No deferred Dart libraries.** Deferred components shrink the download only with Play Feature Delivery; this app is
    an MDM/private APK, where a deferred import still lands in the same `libapp.so`. Rarely used screens are lazy in the
    sense that matters: built on navigation, and the camera and scanner start only on the scanner screen.
53. **Measurement code exists only in debug and profile builds.** `cm.perf` timings print only in profile/debug (names
    and milliseconds); the seeding receiver lives in `src/devtools` (debug/profile source sets) and is guarded by
    `android.permission.DUMP`, so only `adb shell` can trigger it. Release builds contain neither.
54. **Conversation channels on Android 11+, one channel per thread before.** With a long-lived shortcut and
    MessagingStyle, Android 11+ files the notifications under Conversations and offers per-conversation settings on a
    `messages` parent channel; Android 10 has no conversation API, so it keeps the per-thread channels.
55. **The camera permission is asked for in-app and not reported to the server.** Only the scanner needs it; listing it
    in the heartbeat would raise "permission revoked" alerts for something the phone's job does not need.
56. **WorkManager initialises on demand.** Its androidx.startup initializer opened its database on the main thread at
    every process start, including every incoming-SMS receiver start; `CmApplication` provides the configuration
    instead. EmojiCompat's initializer is removed (Flutter renders its own emoji).
57. **Phone sync batches may take seconds; admin endpoints may not.** With 100 000 messages on one phone every admin
    endpoint is under 300 ms p95 (docs/sms-mobile-performance.md). Searching inside a 6 400-message thread was 659 ms:
    it built 5 000 full model rows to decrypt their bodies; it now scans only `(id, ciphertext)` and loads the matches
    (28 ms). A 200-event batch from 200 new numbers takes about 3.5 s, about 14 round trips per event (savepoint,
    look-ups, insert, row refresh); `refresh_conversation` went from 7 queries to 4 and the SIM look-up is memoised per
    batch. That worst case only happens during backfill, inside the phone's 60 s read timeout; a live message is one
    event (about 20 ms). Bulk ingestion would cost per-event rejection and savepoint isolation, so it was not done.
58. **Native libraries are compressed in the APK.** Phones get the APK file itself (link, MDM), and with stored
    libraries the arm64 split was about 28 MB (budget 25 MB). Deflated it is about 16 MB; Android extracts the
    libraries once at install (about 20 MB more on disk). Dex files stay stored so ART can map them.
59. **Two Redis roles; security state fails closed.** The broker Redis also holds the *security store* (Django cache
    alias `security`: device-auth nonces, login lockouts, the short-code breaker, SMS rate-limit counters, DRF throttle
    history, the Gmail sync lock) and runs `noeviction` + AOF; plain cache data (token buckets, push coalescing, cached
    Gmail access tokens) lives in a second, `allkeys-lru` instance (`REDIS_CACHE_URL`). With LRU on one shared instance
    an evicted nonce would have let a replayed signed request through and an evicted task would have lost an outbound
    SMS. `common/stores.py` wraps the store: any error raises `SecurityStoreUnavailable`, which every view turns into
    `503 try_later` (a store outage never burns an enrollment code). Throttles that cannot read their history refuse too.
    Production refuses to start without `REDIS_URL`; `check --deploy` reads the live policy.
60. **Nginx compresses static assets only.** gzip is on for `/_next/static/` (JS, CSS, SVG) and off for HTML and the
    API: compressed responses that mix a secret (CSRF token, mail text) with attacker-influenced input are the BREACH
    pattern. Static bundles are the bulk of the bytes anyway. The config is a template (`${CM_DOMAIN}`) rendered by
    `deploy/render-nginx.sh`, so no placeholder domain can be left in a live config.
61. **Polled lists hold their order under the pointer.** The flaky SMS journey (mobile-dark) was a re-sort between
    pointerdown and pointerup: the row moved, the click landed on the list itself and nothing opened. `useHeldOrder`
    (frontend/src/hooks) freezes the on-screen order while the pointer moves over the list, is pressed, or was released
    within 600 ms; row data still updates in place, new rows wait, the next page is appended. A resting mouse releases
    the hold after 1.5 s, so a hovering admin still sees new conversations rise. No retries were added to the test.
62. **OCM branding; no system-app names.** The launcher label "Messages" imitated the system app (Play impersonation
    policy). The application label is "OCM"; launcher entries are activity-aliases ("OCM Messages", and "OCM Phone" on
    Calls phones) with OCM's own ring mark, not a vendor icon. The admin brand is "OCM" (Office Communication
    Management); `COMPANY_NAME` stays configurable. Screen titles inside the app ("Messages") are generic words and stay.
63. **The monitoring flag sits directly under `<manifest>`.** Google's *Stalkerware and monitoring applications* help page
    (checked 2026-10-28) shows `<meta-data android:name="isMonitoringTool" …/>` as a child of `<manifest>`, not of
    `<application>`; aapt2 keeps it there. Every flavor carries `enterprise_management`.
64. **The monitoring notice is always visible.** The service channel was `IMPORTANCE_MIN` (no status-bar icon); a channel's
    importance cannot be raised, so a new `monitoring` channel (`IMPORTANCE_LOW`, silent) replaces `sync_service`, the
    notification is shown at once (`FOREGROUND_SERVICE_IMMEDIATE`) and, because Android 14+ lets people swipe
    foreground notifications away, its delete intent posts it again.
65. **Two flavors, `play` and `private`.** Play restricts `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`; only `private` (MDM)
    declares it, through a flavor manifest, and `BuildConfig.DIRECT_BATTERY_REQUEST` decides whether the direct dialog is
    offered or the battery-optimisation list is opened.
66. **One sync pipeline for every phone platform.** `sync/events` moved from SMS to `modules/devices`: a registry of event
    types per platform (SMS registers its nine, Calls its five), one ordered, idempotent, savepointed batch. An event of
    a platform switched off on the server stops the batch *before* it (kept on the phone, 403 if nothing could be done);
    an event of a platform the phone is not enrolled for is rejected and acknowledged (`platform_not_enabled`), so a
    phone that is not a Calls phone can never get call data stored. The SMS response shape is unchanged.
67. **"Returned" means the customer was reached.** A missed incoming call (missed, declined, voicemail) is returned by the
    next *answered* call with that number, in either direction, from **any** company phone: customers call the office,
    not a person, and a call-back from a colleague's phone counts. An unanswered call-back attempt does not. The link is
    made both ways because the call-log backfill arrives newest first. "Unreturned" (the management metric) = not
    reached within `CallSettings.unreturned_hours` (default 4); still inside the window = "open".
68. **Rollups are UTC hours; the dashboard buckets them in the viewer's zone.** `CallStatHourly` (hour × phone × SIM ×
    office × direction × result × after-hours) and `CallerDaily` are maintained in the call's transaction under the
    phone's row lock (subtract the old contribution, add the new one when a late call-log row refines a call), and the
    nightly task rebuilds the last 3 days. Converting UTC hours to a zone with a non-whole-hour offset would shift by
    the remainder; Tanzania (+3) and every zone the company uses are whole hours. Only the unreturned metrics and the
    medians read call rows, through indexes and for missed/answered calls only.
69. **XLSX without a spreadsheet library.** The export writes a minimal Office Open XML workbook (one sheet, inline strings)
    with `zipfile`; adding openpyxl for one sheet was not worth a dependency. CSV cells that start with = + - @ are
    prefixed with ' (formula injection). The query parameter is `file_format`: DRF reserves `format`.
70. **The directory creates customers only for real phone numbers.** Short codes and sender IDs (M-PESA, 15300) are
    services; an admin can add one, after which traffic links to it. A directory name is the company's own and is never
    taken from a phone's address book. Phones receive names only for customers they have been in contact with
    (`CustomerDevice`) or that an admin flagged for every phone.
71. **USSD and emergency calls are refused server-side too.** The dialer never sends them; the server rejects any
    `call.upsert` whose number contains `*`/`#` or is an emergency number for the SIM's region (libphonenumber short-number
    data plus 112/911), acknowledging it so it is never retried, storing nothing and logging only the reason code.
72. **The automatic missed-call SMS uses the SMS queue.** It is a `Message` with origin `auto`, claimed and sent by the phone
    like an admin message, sharing the phone's rate limit and daily cap, refusing short codes, premium numbers and
    blocked numbers. On top: only for calls that ended in the last 30 minutes (never history), one per number per day
    and a cool-down by default, never to an opted-out customer, never once the call was returned.
73. **One app holds both roles; the Phone entry exists only on Calls phones.** `ROLE_SMS` and `ROLE_DIALER` share one
    enrollment, Keystore key, sync engine and SQLCipher store, so a phone is one device in the admin and revocation wipes
    both at once. *OCM Phone* and the `ACTION_CALL` handler are activity-aliases that start disabled and are enabled from
    the heartbeat's `capabilities.calls`; a phone that is not a Calls phone never offers a dialer it cannot use, and
    disabling Calls makes the role unqualified, so Android returns it to the system dialer. `ACTION_CALL` (dials at once)
    is a separate alias behind `CALL_PHONE`, so no app without that permission can dial through OCM.
74. **The call screen is native (plain Views); Flutter draws only Keypad, Recents, Contacts and Call-backs.** An incoming
    call is the case where the process is most often dead, so a pre-warmed Flutter engine cannot be guaranteed, and a
    cold engine (load `libflutter.so` + the AOT snapshot, first frame) does not fit the ≤ 300 ms budget on a low-end
    phone. Compose would cost ~2–3 MB per ABI plus first-composition warm-up. `InCallActivity` builds its views in code
    (no XML inflation), `OcmInCallService` and `Ringer` never touch Flutter, and the state the screen shows is written to
    the outbox by `CallTracker` before any UI work. Measurements: [sms-mobile-performance.md](sms-mobile-performance.md).
75. **The phone sends the live call and the call-log row separately; the server merges.** Telecom writes the call log,
    not the dialer, and some calls are never seen by the dialer (before enrollment, while another app was default).
    Sending both raw (`call_key` from `CallTracker`, `call_log_id` from `CallLogMapper`) keeps the phone simple and
    makes the merge testable in one place: lookup by either key, else number + start window + SIM; unique constraints
    on both keys make every retry idempotent. A log row refines a generic live "missed" but never overwrites live
    timestamps.
76. **The app rings and follows Do Not Disturb conservatively.** With `IN_CALL_SERVICE_RINGING` the dialer owns the
    ringtone. Silent mode → nothing; vibrate → vibration; normal → the contact's ringtone (or default) and vibration if
    the system setting is on. Under DND it rings only when the system would: `matchesCallFilter` on Android 13+, and on
    10–12 the public notification policy (calls category on, and the caller is anyone / a contact / a starred contact as
    the person chose; repeat callers are not detected). When in doubt it stays silent; the call still shows and can be
    answered.
77. **A single SIM is named on every call.** With one SIM the app passes its subscription to Telecom, so the record
    carries its `SimLine` from the first event; dual-SIM phones always ask (label and colour from the admin). Emergency
    calls never get a SIM override: Telecom picks the best network.
78. **Screening uses the block list only; no spam source in v1.** `CallScreeningService` rejects numbers on the phone's
    block list (shared with SMS and the admin's *block*) and still lets the system log them as *blocked*, so the admin
    sees blocked attempts. There is no trustworthy Tanzanian spam database to subscribe to, so nothing is flagged as
    spam. Emergency numbers and outgoing calls are never screened.
79. **No call audio, ever, from the phone.** Android 10+ reserves the voice-call audio source for system apps and Play
    bans Accessibility recording; mic/speaker tricks are unreliable and undisclosed. The only acceptable route is a
    cloud PBX recording server-side with an announcement ([calls-recording.md](calls-recording.md)).
