# Security

Communication Manager lets admins read other people's mailboxes, so its security model is about two things:
only the right staff reach a mailbox, and every access leaves a trace. This page lists the controls and
where they live in the code.

## Authentication and sessions

- Email + password login with Django's password hashers and validators. Login is rate-limited to 10 per
  minute per client IP (`ClientIpScopedThrottle`, scope `login`). Failed logins are audited
  (`auth.login_failed`).
- Optional **TOTP 2-step verification** per user (Settings → Preferences). The secret is stored encrypted.
- Browser auth uses a session cookie and a CSRF token (`common/auth.py: CsrfSessionAuthentication`). Every
  unsafe method needs the CSRF header, including for logged-in users.
- Cookies are `HttpOnly` (session), `SameSite=Lax`, and `Secure` in production. Sessions last 12 hours.
- The browser talks only to the Next.js origin, which proxies `/api/v1/*` to Django. There is no CORS
  configuration to get wrong.
- Production settings refuse to start without a real `DJANGO_SECRET_KEY`, `MAIL_TOKEN_KEYS` and `SMS_DATA_KEYS`,
  with a dev-only key, with the two key rings sharing a key, or with the SMS simulator enabled.

## Authorisation

| Layer | Rule | Code |
|---|---|---|
| Platform | User needs the platform permission (`mail.access`, `sms.access`), and the platform must be enabled (`is_platform_enabled`) | `modules/platforms/services.py` |
| Mailbox | Super admin and Admin roles see every mailbox. Everyone else needs a `MailboxAccess` row with `can_read` / `can_send` / `can_delete` / `can_manage` | `modules/mail/services/access.py` |
| Object | Every mail endpoint resolves threads, messages, labels, drafts and attachments **through** `accessible_mailboxes(user, perm)`. An inaccessible object returns 404, not 403, so its existence is not revealed | `get_mailbox`, `get_threads`, `accessible_threads` |
| Settings | Users, roles, offices, platforms, integrations and the audit log each check a specific permission | `common/permissions.py: HasPerm` |

`tests/test_permissions.py` covers the matrix: a user without access cannot list, open, act on, send from,
or download from another office's mailbox, and the unified inbox (`mailbox=all`) only spans accessible
mailboxes.

## Mailbox credentials

- OAuth refresh tokens, IMAP passwords and Workspace service-account keys are encrypted with
  **MultiFernet** (`common/crypto.py`). The keys come only from `MAIL_TOKEN_KEYS`, newest first.
  `rotate_mail_keys` re-encrypts everything under the newest key.
- Credentials are decrypted only inside a provider. They are never serialised to the API and never logged.
  Log lines carry mailbox IDs and error codes only.
- Disconnecting a Google mailbox revokes the token at Google before deleting it.

## Connecting mailboxes (OAuth)

- **Connect links** use a random 32-byte token. Only its SHA-256 hash is stored. Links are single-use,
  expire after 72 hours (`MAIL_INVITE_TTL_HOURS`) and can be revoked. The public endpoints are rate-limited
  (`public_connect`, 60/min).
- **OAuth** uses the authorisation-code flow with **PKCE**. `state` is signed with Django's signing
  framework, carries a nonce and the invite or mailbox ID, and expires quickly. The callback rejects any
  tampered or expired `state`.
- The callback checks that the **signed-in account equals the mailbox email** and that **every required
  scope was granted**. If not, nothing is stored and the person sees a friendly retry screen.
  `tests/test_connect.py` covers state tampering, the wrong account, missing scopes and `invalid_grant`.
- `invalid_grant` or a revoked token sets the mailbox to `needs_reconnect`. It is never retried in a loop.

## Email content

Email HTML is hostile input. It passes through three layers:

1. **Server: nh3 allowlist** (`modules/mail/services/sanitize.py`). Scripts, iframes, objects, forms,
   event handlers, `javascript:` URLs and unknown tags or attributes are removed. Inline styles are
   restricted to a list of layout properties. `tests/test_sanitize.py` covers script, iframe, SVG,
   event-handler and URL payloads.
2. **Client: DOMPurify** runs again before rendering.
3. **Sandboxed iframe** with its own CSP: `default-src 'none'`, no scripts, `form-action 'none'`,
   `base-uri 'none'` and `referrer: no-referrer`. The sandbox allows popups (links open in a new tab) and
   `allow-same-origin`, so the app can measure the content height. It does **not** allow scripts, which is
   what makes `allow-same-origin` safe here.

Also:

- **Remote images are blocked by default.** Their URLs move to `data-cm-src`, and the CSP blocks
  `http(s):` images until the user chooses "Show images" or "Always show from this sender". This stops
  tracking pixels.
- Links open in a new tab with `rel="noopener noreferrer"`. When a link's visible text is a URL to a
  different host than its target, the link is flagged and the user is warned.
- Compose HTML is sanitised server-side before sending (`sanitize_compose_html`).

## Attachments

- No public URLs. Attachments stream through `GET /mail/messages/{id}/attachments/{aid}/` after the same
  mailbox permission check, and each download is audited.
- Responses carry `Content-Security-Policy: default-src 'none'; …; sandbox` and `nosniff`, so an HTML or SVG
  attachment opened directly cannot run script. The in-app PDF preview (`?preview=1`) drops only `sandbox`,
  because Chrome will not render a sandboxed PDF. Scripts stay blocked.
- Uploads are limited to `MAIL_MAX_ATTACHMENT_BYTES` (25 MB).

## Audit log

`modules/audit` is append-only: there is no update or delete API, and it is not exposed in the Django admin. Each event
records the actor, action, mailbox, target, IP, user agent and metadata. Audited actions include:

- **Auth:** login, failed login, logout, TOTP on/off
- **Mailboxes:** create, update, delete, connect, wrong-account attempt, disconnect, needs-reconnect,
  invite create and revoke, access changes
- **Mail:** opening a thread (who read which office's mail), show original, attachment download, send,
  schedule, delete, permanent delete, labels, filters, signature, vacation, notes, unsubscribe
- **Settings:** users, roles, offices, platforms, connect notice, Workspace domains, audit export

The audit UI (Settings → Audit log) is admin-only and exports to CSV. The export itself is audited.

### Client IP

The IP comes from the first `X-Forwarded-For` entry (`common/http.py: client_ip`). This is trustworthy only
because the Nginx config in `deploy/` **overwrites** the header with the real peer address, and because the
frontend port binds to `127.0.0.1` in production. Keep both if you change the proxy setup. The login
throttle uses the same function, so a client cannot dodge it by sending varied headers.

## Transport and headers

- HTTPS at Nginx with HSTS. Django adds `SECURE_PROXY_SSL_HEADER`, HSTS, `nosniff`,
  `Referrer-Policy: same-origin` and `X-Frame-Options: DENY`.
- Next.js adds `nosniff`, `Referrer-Policy`, `X-Frame-Options: SAMEORIGIN` and a restrictive
  `Permissions-Policy`.

## Privacy and compliance (Tanzania PDPA)

- The public connect page shows a plain-language notice before consent ("Authorised company administrators
  will be able to read, send and manage email in this mailbox. All access is logged."). Admins can edit it
  in Settings → Integrations.
- Access is limited by role and per-mailbox grants, and every read is audited. This supports the company's
  accountability obligations. Retention of cached bodies is bounded (`MAIL_BODY_CACHE_DAYS`).
- The company should still record its lawful basis for mailbox monitoring, and tell staff in its policies.
  This software supports those obligations but does not replace them.

## Secrets

- Secrets come only from environment variables (`.env`, which is git-ignored; see `.env.example`). The repo
  contains no credentials. The dev settings carry one clearly labelled dev-only Fernet key, which prod
  refuses.
- Demo users and the fake provider are disabled in production (`SEED_DEMO=0`,
  `MAIL_ENABLE_FAKE_PROVIDER=false`, and `seed_demo` refuses to run when the fake provider is off).

## Company phones and SMS

Full design: [sms-mobile.md](sms-mobile.md). The controls, and where they live:

| Control | Code |
|---|---|
| Enrollment codes: 32 random bytes, SHA-256 stored, single use, 24 h, revocable, burned after 5 failures, audited | `modules/devices/services/enrollment.py` |
| Allow-listed HTTPS server only (a malicious QR or link can't redirect a phone); a typed short code is resolved only on an allow-listed server | `mobile/lib/core/enroll/enroll_uri.dart` |
| Enrollment links (`cmsms://enroll`) only pre-fill: the same allow-list, HTTPS check and monitoring notice follow | `mobile/…/bridge/HostApiImpl.kt` (`LaunchIntent`), `features/enroll/enroll_screen.dart` |
| Short codes: 40 bits (8 Crockford characters), HMAC-SHA256 with `SECRET_KEY` stored, 15 minutes, single use, bound to one invite; resolving issues a second token (hash only, usable 15 min); 5/min and 20/h per IP; 50 misses from all clients in 15 min lock every live short code; issue, resolve, miss and lock audited | `modules/devices/services/enrollment.py`, `api/views.py` (`EnrollResolveView`) |
| Keystore EC P-256 identity (StrongBox when present); attestation chain + challenge = SHA-256(code) verified; optional hard requirement and Play Integrity | `modules/devices/services/identity.py`, `integrity.py`, `mobile/…/security/DeviceKey.kt` |
| No long-lived secret on the phone: 15-minute opaque tokens minted from a signed, timestamped, single-use-nonce request; only SHA-256 stored | `modules/devices/services/auth.py` |
| Separate surfaces: `/api/v1/device/` = device tokens only (no cookies, no CSRF), admin = sessions only | `modules/devices/api/auth.py`, `base.py`, `config/urls.py` |
| Every device query scoped to `request.auth.device`; foreign `client_uuid`s rejected | `modules/sms/services/store.py`, `outbound.py` |
| Untrusted input: strict serializers, size caps, timestamp sanity, per-device throttle, Nginx rate limit | `modules/sms/services/sync.py`, `deploy/nginx.conf` |
| Suspend (403, data kept) / revoke (401, the app wipes key + sync DB); status re-checked on every request | `modules/devices/services/manage.py`, `auth.py` |
| Bodies, snippets and MMS files encrypted with `SMS_DATA_KEYS` (separate ring, prod refuses to start without it, `rotate_sms_keys`) | `modules/sms/services/crypto.py`, `media.py` |
| MMS: type from magic bytes, private storage, permission-checked + audited download, `nosniff` + sandbox CSP | `modules/sms/services/media.py`, `api/conversations.py` |
| Object-level access per phone (read / send / manage / reveal sensitive); 404 for anything not readable; disabled platform refuses all | `modules/sms/services/access.py` |
| Sensitive messages (codes, banks, mobile money) masked; reveal needs a flag and is audited | `modules/sms/services/text.py`, `api/conversations.py` |
| At-most-once sending (durable mark before SmsManager, leases, `unknown` instead of resending) | `modules/sms/services/outbound.py`, `mobile/…/telephony/SmsSender.kt` |
| Outbound abuse limits: per user and per phone rate, daily cap, short codes / premium numbers refused | `modules/sms/services/outbound.py` |
| Logs: ids and masked numbers only (`+2557•••••331`) | `modules/devices/services/phone.py: mask` |
| Phone read caches (conversation rows, each conversation's newest 50 messages): same SQLCipher file, never logged, deleted with it on revoke | `mobile/lib/core/db/database.dart`, `…/sync/Revocation.kt` |
| Phone: no backups, no cleartext, SPKI pinning in OkHttp, R8 + obfuscation, SQLCipher DB with a Keystore-wrapped raw 256-bit key, only the four role components exported (each behind its system permission), narrow FileProvider, optional FLAG_SECURE and app lock, lock-screen text hidden by default, root/emulator signals reported | `mobile/android/…`, `AndroidManifest.xml` |
| Retention and PDPA: notice accepted before enrollment and stored; `SMS_RETENTION_DAYS`; phone deletes keep the server copy unless `SMS_MIRROR_DEVICE_DELETES`; contacts minimised | `modules/sms/services/retention.py`, `docs/sms-mobile.md` |

Audited SMS/device actions: enrollment code create/revoke, short code issue/resolve/miss/lockdown, enroll success and failure (with reason), token failures
(rate-limited), notice acceptance, suspend/resume/revoke, option and SIM changes, access changes, resync requests,
conversation opens, sensitive reveals, sends/schedules/cancels/retries, expiries and unknowns, blocks, notes,
quick-reply and rule changes, media downloads, retention purges, SMS settings.

### Security review of the SMS and phone surface (2026-10-27)

A full review of the branch against `main` (backend `modules/devices` and `modules/sms`, the URL and settings changes,
Nginx, the admin SMS UI, and the Android/Flutter app) was run as two passes: one to identify issues, then an
independent false-positive check for each candidate. Only findings scored **≥ 8/10** count as vulnerabilities.
**None reached that bar.** Two candidates were real bugs below it, and both were fixed anyway with regression tests:

| Candidate | Score | What was wrong | Fix |
|---|---|---|---|
| Attestation chain accepted a forged leaf | 7 | `verify_attestation` checked only that each certificate was signed by the next. A genuine attested Keystore key (which can sign any bytes) could therefore "issue" a forged leaf for a software key carrying a made-up KeyDescription, and the phone was stored as hardware-backed. Only mattered with `SMS_REQUIRE_KEY_ATTESTATION=true` | Every issuer must be a CA (`BasicConstraints ca=True`, `keyCertSign` when KeyUsage is present), the leaf must not be a CA, and only the leaf may carry the KeyDescription (`identity.py`; `test_attestation_rejects_leaf_forged_with_a_genuine_attested_key`, `…_key_description_outside_the_leaf`) |
| A heartbeat could undo a revoke | 5 | `record_heartbeat` and the admin `update` saved the whole `Device` row from the copy loaded at the start of the request, so one that finished after a concurrent suspend/revoke wrote `status=active` back. Exploiting it means winning a race of a few tens of ms | Both save only the columns they own (`save(update_fields=…)`), so nothing but `_set_status` (row-locked) writes `status` (`test_stale_heartbeat_or_edit_cannot_undo_a_revoke`) |

Live device tokens are still kept on suspend/revoke on purpose: every request re-checks the status, which is how the
phone learns `device_suspended` / `device_revoked` instead of a generic `invalid_token`.

Checked and dismissed (no issue):

- **Surface mixing:** the admin API authenticates only by session + CSRF, so a device token is ignored. Device views
  set their own authentication class; `IsDevice` needs a device principal and token; Nginx drops `Cookie` on
  `/api/v1/device/`; a device principal holds no permissions.
- **Cross-device writes and reads:** every lookup in `store.py`, `sync.py`, `outbound.py` (claim, report,
  command acks), the MMS upload and the SIM helpers filters on the authenticated device. A foreign `client_uuid` is
  rejected (`foreign_message`), and phone-originated messages never store one, so it can't be pre-claimed.
- **Admin object access:** every view resolves through `get_device`, `get_conversation(s)`, `get_message` or
  `accessible_devices` (404 for invisible phones). Read-only users can't send, retry, cancel or change
  conversations; blocking needs manage. Managers can't grant `can_manage` / `can_reveal_sensitive` they don't have.
- **Enrollment:** the invite is locked with `select_for_update`, consumed in the same transaction, and burned
  after 5 failures. PoP signing strings are separated by purpose (ENROLL / AUTH), P-256 only, ±300 s window,
  single-use nonces, hashed random tokens.
- **MMS / media XSS:** the type is sniffed server-side (HTML/SVG become `text/plain`), there is an inline allow-list,
  and responses carry `nosniff`, a sandbox CSP and a sanitised filename. Storage names are random hex and checked;
  chunk names are integers; size and SHA-256 are verified.
- **Admin UI XSS:** `linkify` only builds `http(s)` links; message text is rendered as React text; the only
  `dangerouslySetInnerHTML` is the server QR SVG, passed through DOMPurify.
- **Sensitive-message leaks:** snippets, the dashboard's recent list and message bodies are masked unless revealed
  (flag + audit). In-conversation search skips sensitive messages, so it can't be used as an oracle. FCM carries no
  content. Logs carry ids, device codes and masked numbers only.
- **Android:** each exported component is guarded by its system permission. Mutable PendingIntents are explicit. The
  FileProvider is unexported and limited to `cache/mms/`. SENDTO only pre-fills a draft. The enroll URI needs HTTPS,
  an exact allow-listed host and no userinfo; native HTTPS repeats the host check and refuses redirects.
- **Simulator / dev keys:** production refuses to start with either; the simulator endpoints also need
  `is_simulated`, which a phone cannot set.

Follow-ups (hardening, not vulnerabilities): check Google's attestation revocation list, and optionally require
`verifiedBootState=Verified` / a locked bootloader when attestation is required (see decision 23).

### Security review of the deployment hardening (2026-10-28)

The Part A diff (security store and Redis split, Nginx templates, backup scripts, CI, standalone frontend image, OCM
branding, Android flavors, the monitoring notice) and, again, the whole SMS + devices surface were reviewed with the
same two-pass method. **No finding reached the bar.** Verified: every replay nonce, lockout, short-code breaker and
throttle uses the never-evicted security store and every store error is refused (no path turns it into "allowed"); a
full noeviction store refuses the request before a password or code guess is checked, because the throttle write runs
first; every Nginx location still overwrites `X-Forwarded-For`; headers are server-level only; the phone-only domain
serves nothing but `/api/v1/device/`; the backup directory is 700 and keys are never in it; CI runs on `pull_request`
with read-only permissions and no secrets; the new launcher alias targets the already exported activity, whose launch
handling only pre-fills; the notice's delete intent is explicit and immutable and targets a non-exported service.
One config bug found along the way was fixed: a `REDIS_URL` without a database path produced a malformed derived cache
URL.

## Reporting

Report suspected vulnerabilities privately to the system owner. Do not open a public issue.
