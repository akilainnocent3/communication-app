# Status — final report

**All six milestones are built and verified** (2026-10-10). Gmail is a working platform. SMS, Calls and
Media show as "Coming soon". With no Google credentials, the whole product runs on the fake provider.

## What was built

| Milestone | Delivered |
|---|---|
| 1 Foundation | Django 5.2 + DRF API, session + CSRF auth, optional TOTP, roles (Super admin, Admin, Office manager, Viewer), offices, append-only audit log, platform registry (backend + frontend), Next.js 16 shell rebuilt from the reference design system (collapsible sidebar, blurred header, centred platform switcher, ⌘K palette, light/dark), login |
| 2 Mail core | Provider interface, `FakeMailProvider`, `seed_demo` (3 offices, 4 mailboxes, ~300 threads), thread list/detail, 20+ bulk actions with undo tokens, unified inbox, 3-pane resizable workspace, virtualised list, optimistic updates, keyboard shortcuts + `?` cheat sheet, mobile list → thread with swipe actions and FAB |
| 3 Google connection | OAuth with PKCE, signed `state`, `login_hint`, account and scope checks; single-use connect links (copy, WhatsApp, server-side QR, live status); public `/connect/[token]` page with a PDPA notice and an "unverified app" helper; MX detection (Gmail, Workspace, IMAP, Microsoft 365 refused); MultiFernet token storage + `rotate_mail_keys`; sync engine (metadata-only initial sync with progress, `history.list` incremental, expired-cursor full resync, batch requests, token bucket + backoff); health → `needs_reconnect` + reconnect link |
| 4 Compose & send | Floating, stacking compose windows (full screen on mobile), From/alias, chip autocomplete, TipTap editor, signatures, templates, attachments (drag, paste, 25 MB), draft autosave, missing-attachment warning, reply/reply-all/forward threading, undo send (5–30 s), schedule send, snooze |
| 5 Tools, dashboard, settings | Labels CRUD, filters & rules (incl. block sender), signatures, vacation responder, dashboard (KPIs, received vs sent chart, per-office table, top senders, unanswered > 24 h), mailbox list / 3-step add wizard / detail / access manager, users & roles, offices, platforms, integrations (Workspace delegation with Test, connect notice), audit log + CSV, IMAP/SMTP provider with capabilities |
| 6 Hardening | Sanitising (nh3 → DOMPurify → sandboxed iframe with CSP), remote-image blocking, link-mismatch warnings, sandboxed attachment responses, object-level permission checks, IP-safe throttling, deploy checks, Docker Compose, Nginx config, docs |

The platform design was tested by adding a stub SMS platform behind a flag, verifying it end to end, and
then removing it (`docs/screenshots/*-sms-stub-proof.png`).

## How it was verified (final run)

| Check | Result |
|---|---|
| `pytest` (backend) | **137 passed** |
| Coverage, `mail/services` + `mail/api` | **86 %** (target ≥ 85 %) |
| `makemigrations --check` | No changes |
| OpenAPI | `spectacular --validate` passes; `contracts/openapi.yaml` regenerated; TS types regenerated (`npm run gen:api`) |
| `tsc --noEmit`, ESLint | 0 errors |
| Playwright, 4 projects (desktop 1440×900 / mobile 390×844 × light / dark) | **18 passed, 2 skipped** (the keyboard-shortcut test is skipped on mobile by design). The suite covers login → switch mailbox → open → reply → archive + undo → search → label → delete forever with confirmation, the connect link (dialog, public page, wrong account, success, invalid link), and every page rendering without console errors |
| `manage.py check --deploy` (prod settings) | No issues (3 deliberately silenced, see `config/settings/prod.py`) |
| `docker compose up --build` | All 6 services healthy; demo login works through the frontend proxy (session 8) |
| Screenshots | 110 in `docs/screenshots/`, reviewed for visual quality in both themes and sizes |

Fixes made in the final session:

- The login throttle now keys on a single client IP, and the Nginx config overwrites `X-Forwarded-For`, so
  the IP cannot be spoofed.
- Native checkboxes are themed (they rendered white in mobile dark mode).
- Toasts now follow the dark theme.
- The connect E2E test now deletes the mailbox it creates.
- The Next.js dev indicator is hidden.
- The OpenAPI contract was stale (it lacked the attachment `preview` parameter) and has been regenerated.

## Known limitations

- **Real Google credentials were not available in the build environment.** The OAuth flow, Gmail provider
  and sync engine are tested with mocks and the fake provider. Connecting a real mailbox (milestone 3's
  "≤ 4 clicks" check) needs a manual run once the Google Cloud project exists (`docs/google-setup.md`).
- **Unverified Google app:** office staff see the "Google hasn't verified this app" screen, and Google caps
  unverified apps that use restricted scopes at **100 users**. A Workspace admin can mark the app as Trusted
  for company accounts. Removing the cap needs Google verification and a security assessment for the
  restricted `mail.google.com` scope.
- **Microsoft 365 mailboxes are not supported.** They are detected and refused with a clear message.
- **IMAP mailboxes** have no Gmail categories, filters or server-side vacation; the UI hides these. Search
  across bodies uses the server's IMAP `SEARCH`, which is slower than Gmail.
- Gmail push notifications (Pub/Sub `users.watch`) are not wired up. Sync polls every 60 s and also runs
  after every action.
- English only. All strings are in `frontend/src/i18n/en.ts`, ready for Swahili.
- Workspace delegation and IMAP were tested against mocks, not live servers.

## Recommended next steps

1. Create the Google Cloud project, publish the app, and connect one real `@gmail.com` and one Workspace
   mailbox. Watch the first sync and quota behaviour.
2. Deploy to the VPS (`docs/deployment.md`), set up nightly `pg_dump` backups, and store `MAIL_TOKEN_KEYS`
   offline.
3. Ask the Workspace admin to mark the app as Trusted and, for company domains, consider domain-wide
   delegation (zero clicks per mailbox).
4. Add Gmail push notifications for near-instant inbox updates.
5. Add the Swahili translation.
6. Start the SMS platform using `docs/adding-a-platform.md`.
7. Run Playwright in CI on every change.

## Build log

Sessions 1–8 built milestones 1–5, the E2E suite, the SMS stub proof and Docker Compose. Session 9 (final)
wrote the README and the architecture, deployment and security docs plus `deploy/nginx.conf`, made the
hardening fixes above, and re-ran every check. Design choices are recorded in `docs/decisions.md`.
