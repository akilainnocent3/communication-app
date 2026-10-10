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
