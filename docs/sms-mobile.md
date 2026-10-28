# SMS platform: company phones

The SMS platform copies the text messages of **company-owned Android phones** to Communication Manager and lets
authorised administrators read them and reply. Replies are sent **by the phone, as ordinary carrier SMS** (billed by
the carrier, from the phone's own number). It is not an internet chat app.

| Piece | Where |
|---|---|
| Android app (default SMS app) | `mobile/` (Flutter UI + Kotlin telephony layer) |
| Phone identity, enrollment, tokens, heartbeat, push | `backend/modules/devices/` (shared, Calls will reuse it) |
| Conversations, messages, outbound queue, admin API | `backend/modules/sms/` |
| Admin UI | `frontend/src/platforms/sms/`, routes under `frontend/src/app/(app)/sms/` |

## Facts that shape the design

- **Android only.** iOS lets no third-party app read or send SMS.
- **Default SMS app.** Only the app holding `RoleManager.ROLE_SMS` receives `SMS_DELIVER`/`WAP_PUSH_DELIVER`, may write
  the Telephony provider and gets the SMS permissions without fuss. To be offered as default the app declares the four
  components the role needs (SMS and MMS receivers, the `SEND`/`SENDTO` activity and the respond-via-message service);
  each is guarded by its system permission (`BROADCAST_SMS`, `BROADCAST_WAP_PUSH`, `SEND_RESPOND_VIA_MESSAGE`).
  Every other component is non-exported.
- **We own the message store.** The receiver inserts each incoming SMS into `Telephony.Sms.Inbox`; the sender writes
  the outbox row, then updates it to sent/failed and its delivery status. MMS is downloaded
  (`downloadMultimediaMessage`) and sent (`sendMultimediaMessage`) by the app, with a minimal PDU codec
  (`mms/Pdu.kt`) and a FileProvider path limited to the MMS scratch folder.
- **The customer sees a normal SMS from the phone's number.** "Sent by admin" is shown in the admin and in the app,
  not to the customer — unless the phone's optional admin signature is on (it is appended and counted).
- **Phones kill background apps.** Every event is written to a durable local outbox in the same code path that
  writes the provider, before anything else; uploads resume from there.
- **RCS is out of scope** (Google's RCS is not available to third-party apps).

## Enrollment and identity

```mermaid
sequenceDiagram
  actor Admin
  actor Holder as Phone holder
  participant App as SMS app
  participant KS as Android Keystore
  participant API as /api/v1/device/
  Admin->>API: (admin API) create enrollment: name, office, options
  API-->>Admin: single-use code (32 random bytes, SHA-256 stored, 24 h) + QR cmsms://enroll?server=…&token=…<br/>+ short code XXXX-XXXX (15 min, single use)
  Holder->>App: scan the QR (or a photo of it), tap the link, or type the short code
  opt short code
    App->>API: POST enroll/resolve {code} (5/min and 20/h per IP, global breaker)
    API-->>App: a fresh token for that invite (usable 15 min)
  end
  App->>App: server must be HTTPS and in ALLOWED_SERVER_HOSTS (build time)
  App->>API: GET enroll/info?token → company, phone name, monitoring notice
  Holder->>App: accept the notice
  App->>KS: EC P-256 key (StrongBox if present), attestation challenge = SHA-256(token)
  App->>API: POST enroll {token, public key, attestation chain, facts, SIMs, signature over ENROLL/sha256(token)/fingerprint/time/nonce}
  API->>API: lock invite · verify signature, clock ±5 min, nonce · verify attestation (and Play Integrity if required) · create Device · consume invite
  API-->>App: device id, code DEV-XXXX-XXXX, first access token (15 min)
  loop every 15 min
    App->>KS: sign AUTH/POST/path/device id/time/nonce
    App->>API: POST auth/token → new opaque token (SHA-256 stored)
  end
```

- Three ways in, one path: the **QR** (camera, or *Scan from photo* for a QR received as a WhatsApp image), the
  **link** `cmsms://enroll?…` (tapped on the phone; it only pre-fills) and the **short code** (`XXXX-XXXX`, Crockford
  base32, 40 bits, typed on the phone; it names no server, so it is resolved only on an allow-listed one). Every path
  then checks HTTPS and the allow-list and shows the monitoring notice; nothing enrolls until the holder accepts it.
- The **device code** (`DEV-7F3K-9Q2M`, Crockford base32) identifies a phone in the admin; it is never a credential.
- No long-lived bearer secret exists on the phone. Tokens live 15 minutes (`SMS_DEVICE_TOKEN_TTL`) and are minted with
  a fresh Keystore signature, a ±5-minute clock window and a never-seen nonce (cache, 10 minutes).
- `SMS_REQUIRE_KEY_ATTESTATION` refuses phones without a hardware-backed, attested key (needs Google's roots in
  `SMS_ATTESTATION_ROOTS_FILE`). `SMS_REQUIRE_PLAY_INTEGRITY` refuses phones that fail Play Integrity; privately
  distributed builds pass only when signed with a certificate listed in `PLAY_INTEGRITY_CERT_DIGESTS`.
- Five failed attempts against one enrollment code revoke it. Every outcome is audited.
- **Suspend** → `403 device_suspended`: the phone keeps everything and retries every 15 minutes. **Revoke** (the admin
  types the device code to confirm) → `401 device_revoked`: the app deletes its key, sync database and settings and
  shows "This phone was removed by your administrator". The phone's own SMS are untouched. Server data stays.
- `SMS_MIN_APP_VERSION`: older apps get `426 upgrade_required` on every request.

## Sync protocol (phone → server)

```mermaid
flowchart LR
  R["SmsReceiver / MmsDownloaded /<br/>sent & delivered receivers /<br/>mark read, delete, block"] -->|"1. write Telephony provider"| P[(Telephony provider)]
  R -->|"2. append event (seq)"| O[(SQLCipher outbox<br/>sync_events)]
  R -->|"3. wake"| T{SyncTrigger}
  R -->|"3. upload directly (≤ 8 s)<br/>when the service is down"| API
  T --> S["SyncService (foreground,<br/>remoteMessaging)<br/>NativeSyncEngine loop"]
  T --> W["WorkManager (expedited + 15 min)<br/>runs NativeSyncEngine"]
  N[NetworkCallback] --> S
  F[FCM data message] --> S
  S -->|"batches ≤ 200 events, < 1 MB"| API["POST /device/sync/events/"]
  API -->|"acked_seq"| S
  S -->|"delete ≤ acked_seq"| O
  S -->|"MMS chunks ≤ 512 KB, resumable, SHA-256"| M["POST /device/sync/media/"]
```

- Event types: `message.upsert`, `message.read`, `message.delete`, `thread.read`, `thread.delete`, `contact.upsert`,
  `block.add`, `block.remove`, `backfill.progress`.
- **Idempotent:** the server skips sequences it already processed and identifies messages by
  (device, kind, provider `_id`, provider date) or by `client_uuid` for admin messages. Retrying is always safe.
- **Untrusted input:** strict serializers, body ≤ 5 000 characters, ≤ 20 recipients, dates between 2000 and now + 1
  day, batch limits, per-device throttle, and an event can only ever touch its own phone's data (a foreign
  `client_uuid` is rejected). Bad events are rejected *and* acknowledged so they can't block the queue.
- **Backfill:** after enrollment the app copies the last `SMS_INITIAL_SYNC_DAYS` (default 90) newest first; progress
  shows on the phone and on the phone's admin page. "Request resync" in the admin repeats it.
- **Heartbeat** every 5 minutes and on network changes: battery, network, signal, default-app check, permissions,
  battery optimisation, upload backlog, app/Android version, SIMs, root/emulator signals (reported, not blocking).
  The admin shows Online (seen within two heartbeats) or Offline with "last seen", and alerts: offline, not the
  default SMS app, permission revoked, battery optimisation on, upload backlog, app outdated.
- **Contacts are minimised:** names are looked up only for numbers that appear in conversations; the server ignores
  names for any other number.

The engine is native Kotlin (`sync/NativeSyncEngine.kt`); no Flutter engine runs in the background. The same
engine runs in the foreground service's loop, in WorkManager jobs, in an FCM wake-up (`PushService`) and, for the upload
of a just-received message, in the SMS/MMS receivers. The UI asks it to "sync now" and reads what it caches (quick
replies, last sync time).

## Keeping messages flowing in the background

Goal: an incoming SMS reaches the server within seconds, and an admin reply goes out promptly, whether the app is open,
in the background, swiped away or the phone has just rebooted.

| Situation | What happens |
|---|---|
| App open, in the background, or another app in front | The foreground service (`remoteMessaging`, silent ongoing notification "Messages sync active") uploads at once |
| Swiped from recents | The service keeps running (`onTaskRemoved` also queues a sync for OEMs that kill the process); START_STICKY restarts it after a kill |
| Process killed, service not back yet | The receiver uploads the new message itself inside its broadcast window (≤ 8 s), then queues expedited work |
| Doze / app standby | High-priority FCM wakes the phone for admin replies; the battery-optimisation exemption keeps the service's network |
| Reboot, app update | BOOT_COMPLETED / MY_PACKAGE_REPLACED start the service (allowed exemptions) and schedule the 15-minute backstop |
| Android 12+ refuses a background service start | The refusal is remembered for 15 min and never retried in a loop; WorkManager runs the engine meanwhile |

**Production needs FCM.** Without it the phone polls every 20 s while the service runs and every 15 minutes otherwise;
with it, admin replies wake the phone in about a second and the service polls only every 5 minutes. Configure
`FCM_PROJECT_ID` / `FCM_SERVICE_ACCOUNT_FILE` on the server and ship `google-services.json` in the app.

**Manufacturer battery killers.** Onboarding and *Settings → Keep messages flowing* detect the manufacturer and open the
right screen (with fallbacks when a screen does not exist on that build):

| Phone | Setting |
|---|---|
| All | Battery optimisation → *Don't optimise* (asked by the app) · App info → Battery → *Unrestricted* |
| Samsung | Settings → Battery → Background usage limits → *Never sleeping apps* → add Messages |
| Xiaomi / Redmi / POCO | Security → *Autostart* on · Battery saver → *No restrictions* · lock the app in Recents |
| Tecno / Infinix / itel | Phone Master → *Auto-start* → allow · lock the app in Recents |
| Oppo / Realme | App info → Battery → *Allow background activity* and *Auto launch* |
| OnePlus | App info → Battery → *Unrestricted* · Battery → Advanced → *Auto-launch* |
| Huawei / Honor | Battery → App launch → Messages → *Manage manually*, all three on |

What Android lets an app check, it checks and reports in every heartbeat: battery-optimisation exemption,
`ActivityManager.isBackgroundRestricted` and the standby bucket (`UsageStatsManager`). The admin's phone page shows
*Background use is restricted* / *Android is holding the app back* with the steps for that manufacturer. The OEM
auto-start switches cannot be read by apps; the app says so and asks the holder to check them once.

**What Android cannot be talked out of.** *Force stop* (App info → Force stop, or some OEM "clean" buttons) puts the app
in the stopped state: Android delivers **no** broadcasts to it, not even incoming SMS, until someone opens it again.
No app can override this. On company phones use MDM policy instead of trusting people: with **Android Enterprise**
(fully managed) or **Samsung Knox**, allow-list the app from battery optimisation, block "Force stop" and uninstall for
it, and keep it as the default SMS app. For everything else the admin's *Offline* alert (no heartbeat for two
intervals) is the safety net.

The scenarios to verify on emulators and phones (API 29–36) and their results are in the background matrix in
[sms-mobile-performance.md](sms-mobile-performance.md#background-matrix).

## How the app looks: skins

The app replaces the phone's own Messages app, so it looks like it. One widget tree, driven by design tokens
(`lib/ui/skin/tokens.dart`); each look's values are in one file under `lib/ui/skin/skins/`, so they can be tuned without
touching widgets. Looks are named by style; there are no vendor logos, icons or assets (Material icons only).

| Skin | For | Character |
|---|---|---|
| One UI style | Samsung | Large "Messages" title over the top third that collapses on scroll, Conversations / Contacts tabs, list in a rounded container, blue sent bubbles, round compose button |
| Pixel / Material You | Google and everyone else | Wallpaper colours (Android 12+), search-bar header, extended "Start chat" button, tonal bubbles, "+" and a round "Text message" field |
| HiOS / XOS style | Tecno, Infinix, itel | Compact title bar, brand-blue bubbles, larger avatars and spacing, round compose button |
| HyperOS / MIUI style | Xiaomi, Redmi, POCO | Large left-aligned title with a search field under it, flat surfaces, red unread dots, round "+" |
| ColorOS style | Oppo, Realme, OnePlus | Collapsing large title, green bubbles, round "+" |
| Company | — | The app's own teal theme |

*Match my phone* (default) picks the skin from the manufacturer/brand. *Settings → Appearance* chooses another, with a
live preview, plus theme (system/light/dark), bubble colour, text size, density, swipe actions and contact photos;
changes apply at once. Every skin has predictive back, edge-to-edge, haptics on long-press, English and Swahili. Golden
tests (`test/goldens/`) pin each skin's list row, bubbles and compose bar in light and dark.

**Team:** put real screenshots of each original Messages app (Samsung, Google, Tecno/Infinix, Xiaomi, Oppo/Realme;
light and dark; the conversation list, a chat, the compose bar) in `docs/design/references/`, then tune the token files
against them. The current values were set from public material, not side by side with a device.

## Admin reply → phone sends it

```mermaid
stateDiagram-v2
  [*] --> queued: admin sends (undo window / schedule = send_at)
  queued --> cancelled: Undo / Cancel (never offered to the phone)
  queued --> dispatched: phone claims (lease 120 s)
  dispatched --> dispatched: lease expired before "sending" → offered again
  dispatched --> sending: phone wrote its durable mark (never offered again)
  sending --> sent: SmsManager: all parts sent
  sent --> delivered: delivery report
  sending --> failed: SmsManager error (reason shown, Retry = new message)
  sending --> unknown: no result (app died mid-send) — check with the customer
  queued --> expired: older than SMS_OUTBOUND_TTL_HOURS
  dispatched --> expired
```

1. The admin writes in a conversation (needs `can_send`). The server validates the recipient (no sender IDs; short codes
   and premium-rate numbers refused unless `SMS_ALLOW_SHORT_CODES`), applies the per-user and per-phone rate limits and
   the daily cap (`SMS_DEVICE_DAILY_CAP`, protects the SIM from carrier spam blocks), appends the phone's signature if
   enabled, stores the message encrypted, audits `sms.send` (masked numbers only), and wakes the phone (FCM).
2. **Undo send and scheduled send** both set `send_at` (now + the user's undo seconds, or the chosen time); the phone
   can only claim messages whose `send_at` has passed.
3. The phone claims due messages, checks its own durable table (never send a `client_uuid` twice), records `sending`,
   writes the outbox row, sends on the chosen SIM (default: the SIM the conversation last used, else the phone's
   default) with `divideMessage`/`sendMultipartTextMessage`, and reports each state change.
4. **Offline phone:** the message waits ("Waiting for Arusha front desk to come online — it will be sent
   automatically") in the chat and the Outbox, and expires after `SMS_OUTBOUND_TTL_HOURS` instead of going out days
   late.
5. On the phone, admin messages have their own bubble colour and "Sent by admin · Name"
   (`SMS_SHOW_ADMIN_NAME_ON_PHONE`). They can't be edited (SMS can't be); deleting them locally is reported.

Commands (mark read on open, resync, block/unblock) ride on the same claim and are acknowledged.

## Security summary

- Message bodies, snippets and MMS files are encrypted at rest with `SMS_DATA_KEYS` (MultiFernet, separate from
  `MAIL_TOKEN_KEYS`; production refuses to start without it). `rotate_sms_keys` re-encrypts everything.
- MMS media is served only through `GET /sms/messages/{id}/media/{part}/` after the phone-access check, audited, with
  `nosniff` and a sandboxing CSP. The real type comes from the file's magic bytes, not the phone's claim.
- Object-level access (`DeviceAccess`: read, send, manage, reveal sensitive); anything a user can't read answers 404.
- One-time codes and bank/mobile-money messages are masked ("Verification code ••••••"); revealing needs
  `can_reveal_sensitive` and is audited. The phone's notification offers "Copy code".
- Opening a conversation is audited (`sms.conversation_open`) and marks it read (and, if the phone's option is on,
  on the phone too). `?peek=1` does neither.
- Logs carry ids, counts and masked numbers (`+2557•••••331`), never text, contact names, tokens or full numbers.
- Phone: no backups (`allowBackup=false`, extraction rules exclude everything), no cleartext, SPKI pinning, R8 and Dart
  obfuscation, Keystore keys, SQLCipher database (raw 256-bit key, Keystore-wrapped), optional app lock and
  FLAG_SECURE, lock-screen text hidden by default. The read caches (conversation rows and each conversation's newest 50
  messages) live in the same encrypted database, are never logged and are deleted with it on revoke.

## Retention and PDPA (Tanzania)

- Lawful basis and transparency: the phone holder must accept the company's monitoring notice before enrollment
  (stored with the phone; editable in Settings → Integrations). The app is meant for company-owned phones.
- Purpose and storage limitation: `SMS_RETENTION_DAYS` (default 365) deletes older messages and media from the server.
  Deletions on the phone do not delete the server copy by default (`SMS_MIRROR_DEVICE_DELETES=false`): the copy is
  the company's accountability record and shows "Deleted on phone". Set it to `true` if your policy says otherwise.
- Minimisation: only numbers in conversations are named; the address book is never uploaded; analytics use metadata.
- Accountability: every read, reveal, send, cancel, retry, block, enrollment, suspension, revocation and option
  change is in the append-only audit log.

## Distribution

Google Play restricts SMS permissions to default SMS handlers and requires a Permissions Declaration. Distribute the
app privately: as a **managed Google Play private app** through your EMM, or as a **signed APK pushed by MDM**.
Battery-optimisation exemption (`REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`) is only acceptable for private distribution.
Build, signing, pins and Firebase: [mobile/README.md](../mobile/README.md).

## Without FCM

Development and demos work without Firebase. Without `FCM_*` on the server and `google-services.json` in the app, the
foreground service polls every `SMS_DEVICE_POLL_SECONDS` (20 s) while online and WorkManager syncs every 15 minutes.
With FCM, admin replies reach the phone in about a second (data-only, high-priority messages: `{"type": "outbox",
"device": id}`, no content), the engine runs straight from the push, and the service polls every 5 minutes.
**Production should always configure FCM**: it is the exemption Android 12+ honours for starting background work.

## Demo without a phone

`seed_demo` (with `SMS_ENABLE_SIMULATOR=true`, the dev default) creates two simulated phones (one dual-SIM) that enroll
through the real endpoints with a real EC key and upload Swahili/English conversations, M-PESA-style sender IDs,
one-time codes and an MMS photo. On a simulated phone's page the admin can switch it offline/online, process the
outbox and make it receive a text. `python manage.py simulate_sms_device --run` keeps them working (heartbeats,
sending → sent → delivered with realistic delays, occasional new messages; numbers ending in 000 fail).
