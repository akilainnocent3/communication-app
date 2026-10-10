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
- Production settings refuse to start without a real `DJANGO_SECRET_KEY` and `MAIL_TOKEN_KEYS`, or with the
  dev-only token key.

## Authorisation

| Layer | Rule | Code |
|---|---|---|
| Platform | User needs the platform permission (`mail.access`), and the platform must be enabled | `modules/platforms/services.py` |
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

## Reporting

Report suspected vulnerabilities privately to the system owner. Do not open a public issue.
