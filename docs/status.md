# Status — final report

Gmail, SMS and **Calls** are working platforms; Media shows as "Coming soon". With no Google credentials, the whole
product runs on the fake provider and simulated phones. The latest report is first.

## Deployment hardening (Part A) and Calls (Part B) — status (2026-10-29)

### Part A — deployment readiness

| Item | Result |
|---|---|
| A1 Redis eviction | Two Redis roles: broker + security store on `noeviction` + AOF, cache on `allkeys-lru`; security state fails closed (503) with tests (decision 59) |
| A2 Branding and Play | OCM label and icons, *OCM Messages* / *OCM Phone* aliases, `isMonitoringTool`, always-visible monitoring notice, `play` / `private` flavors, [play-store.md](play-store.md) (decisions 62–65) |
| A3 Frontend image | Next.js standalone, non-root runtime image; verified with `docker compose up --build` |
| A4 Ops | Health check on `/api/v1/health/`, log limits on every service, Nginx template (`${CM_DOMAIN}`, login rate limit, security headers, gzip for static assets only), `deploy/backup.sh` + `restore.sh` and the offline-keys rule in deployment.md |
| A5 CI | `.github/workflows/ci.yml`: backend (Postgres, coverage gate, migrations, OpenAPI diff), frontend, mobile (analyze, test, Kotlin, both flavors, APK size); Playwright nightly |
| A6 Flaky E2E | Cause fixed: polled lists hold their order under the pointer (decision 61), no retries |
| A7 Phone checks | Flutter/Kotlin checks and both flavor builds green (below); arm64 **16.0 MB**. Phone budgets and background matrix: see open items |
| A8 Security pass | Review of the SMS + devices surface recorded 2026-10-28 in [security.md](security.md); no finding reached the bar |

### Part B — Calls

Backend `modules/calls` + `modules/directory`, admin under `/calls`, and **OCM Phone**, a separate Flutter app
(`mobile_dialer/`) that becomes the phone's default Phone app; OCM Messages (`mobile/`) is SMS only again
([calls-mobile.md](calls-mobile.md), decisions 66–82). No call audio is recorded ([calls-recording.md](calls-recording.md)).

| Check | Result (2026-10-29) |
|---|---|
| `pytest` (Gmail + SMS + devices + Calls + directory) | **286 passed** (incl. the two-app enrollment tests) |
| Coverage, `modules/calls` + `modules/directory` | **93 %** (gate 85 %) |
| `makemigrations --check`, `spectacular --validate` | clean; `contracts/openapi.yaml` current |
| `tsc --noEmit`, ESLint | 0 errors |
| OCM Messages (`mobile/`): `flutter analyze`, `flutter test` | no issues; **50 passed** (unchanged from before the dialer) |
| OCM Phone (`mobile_dialer/`): `flutter analyze`, `flutter test` | no issues; **55 passed** (incl. keypad/recents goldens per skin, light and dark) |
| OCM Phone Kotlin Robolectric (`testPlayDebugUnitTest`, `testPrivateDebugUnitTest`) | **20 passed** per flavor (12 dialer, 8 sync engine) |
| OCM Phone `flutter build apk --release --split-per-abi` | arm64 **14.9 MB**, armeabi-v7a 14.1 MB, x86_64 15.3 MB (budget 25 MB); no SMS permission or component in the manifest (`aapt2`) |
| Playwright, 4 projects, full suite (Gmail + SMS + Calls) | 4 full runs: run 1 had 1 failure (SMS journey, desktop-light, right after a fresh `seed_demo`; trace lost, not reproduced in 6 isolated runs or a reseeded full-project run); **runs 2, 3 and 4 green in a row: 42 passed, 2 skipped** (keyboard tests on mobile, by design). No retries added |
| Security review of the Calls diff | one finding (score 9), **fixed**: any app could make OCM place calls / run MMI codes through an explicit `ACTION_CALL` to `MainActivity`; reproduced and re-checked on an emulator. CSV formula guard tightened. Details in [security.md](security.md) |
| Emulator (API 29, API 34) | OCM as default dialer: cold incoming-call screen 1.15–1.33 s on API 34 (Google's dialer 1.8–2.05 s on the same emulator; the rest is emulator EGL start-up); 112 placed by an unenrolled OCM and handed to the system in-call UI; USSD never logged. [sms-mobile-performance.md](sms-mobile-performance.md) |

Both apps side by side on an API 34 emulator: OCM Messages holds the SMS role and OCM Phone the Phone role; neither
declares the other's permissions; a cold incoming call opens OCM Phone's call screen (846 ms on the emulator); an
unenrolled OCM Phone places 112; an explicit `ACTION_CALL` to `MainActivity` places nothing. Screenshots:
`docs/screenshots/calls-mobile-keypad.png`, `-incoming.png`, `-in-call.png`. Cosmetic follow-ups: icons on the round
call buttons, a person icon instead of the first digit for unknown callers.

Changed at the owner's request (2026-10-29): the dialer moved out of OCM Messages into OCM Phone, with its own
enrollment code, key and device, linked to the SMS phone of the same handset (decisions 80–82). The CI workflow file
was invalid YAML since it was added (an unquoted `:` in a step name), so GitHub could not run it; fixed, and the mobile
job now builds and tests both apps.

Fixed earlier in this session: the Phone UI tests (T9 typo, single-SIM calls now carry their SIM, keypad and recents fit
narrow windows); the ringer now honours DND priority callers on Android 10–12 (decision 76); the `ACTION_CALL` hole
above.

Open items, in order:
1. **Real phones** (Samsung, Tecno/Itel low-end): incoming-call screen ≤ 300 ms from a cold process, ringer under
   DND, Bluetooth routing, dual-SIM picker, OEM battery killers. The emulator cannot measure the 300 ms budget (software
   GPU).
2. **Enrolled-phone measurements**: SMS phone budgets, the background matrix (API 29–36), Recents ≤ 150 ms, SMS →
   admin ≤ 5 s, and the emulator walkthrough screenshots (`docs/screenshots/sms-mobile-*`, `calls-mobile-*`). These need
   the app enrolled against a server it accepts: the release build only accepts `communicationapi.schoolsoft.online`, so
   either enroll a test phone there or build with a staging host that has a valid HTTPS certificate.
3. Sign OCM Phone for release (`mobile_dialer/android/key.properties`): decide whether it shares OCM Messages' key.
4. Skin reference screenshots in `docs/design/references/` (SMS open item 3).

## SMS platform — status (2026-10-28)

Backend (`modules/devices`, `modules/sms`), the admin under `/sms`, and the Flutter + Kotlin default-SMS app in
`mobile/` are built. The 1.1.0 performance, background, skins and onboarding work is described in
[sms-mobile.md](sms-mobile.md) and decisions 41–58; measurements are in
[sms-mobile-performance.md](sms-mobile-performance.md).

| Check | Result (2026-10-28) |
|---|---|
| `pytest` (backend, Gmail + SMS + devices) | **242 passed** |
| `makemigrations --check`, `spectacular --validate` | clean; `contracts/openapi.yaml` and TS types current |
| `tsc --noEmit`, ESLint | 0 errors |
| Playwright, 4 projects, full suite (Gmail + SMS) in one run | 29 passed, 1 failed, 2 skipped. The failure was the SMS journey on mobile-dark: the list re-sorted while a row was being tapped. It passed 3 of 3 times when re-run alone |
| Admin API with 100 000 messages on one phone | every admin endpoint ≤ 300 ms p95 (in-thread search fixed: 659 → 28 ms) |
| Security review of the 1.1.0 diff | no findings at high confidence. One hardening applied: a copied one-time code is marked sensitive on Android 13+ |
| `flutter analyze`, `flutter test` (incl. skin goldens), Kotlin Robolectric tests, `flutter build apk --release --split-per-abi` | **not re-run after the codespace restart**: the Flutter SDK and Android SDK lived in `/tmp` and are gone. Last green in the session that wrote the code |
| Phone budgets (cold start, chat open, frames, memory, SMS → admin ≤ 5 s) and the background matrix | **not measured**: they need the Android SDK and an emulator; method in sms-mobile-performance.md |

Open items, in order:
1. Reinstall Flutter (stable ≥ 3.47) and the Android SDK, then run `flutter analyze`, `flutter test`,
   `./gradlew :app:testDebugUnitTest` and `flutter build apk --release --split-per-abi`. Confirm the arm64 APK is
   ≤ 25 MB (estimate ~15.5 MB) and that `libbarhopper_v3.so` is gone.
2. Fill in the phone budgets and the background matrix (API 29, 31, 33, 34, 35/36) in sms-mobile-performance.md.
3. Put screenshots of each original Messages app in `docs/design/references/` and tune the skin tokens.
4. Emulator walkthrough screenshots (`docs/screenshots/sms-mobile-*`).

## Gmail platform — what was built

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
