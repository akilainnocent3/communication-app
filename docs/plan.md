# Communication Manager — build plan

A company admin platform for managing every communication channel from one place. Gmail is the first
platform; SMS, Calls and Media appear as "Coming soon" until they are built.

## Architecture in one paragraph

A Django 5.2 + DRF API (`backend/`) and a Next.js 16 App Router frontend (`frontend/`). The browser only
talks to Next.js; `/api/v1/*` is rewritten to Django, so the session cookie and CSRF cookie stay
same-origin. Each communication channel is a **platform**. On the backend a platform is a Django app that
registers itself in `PlatformRegistry` from `AppConfig.ready()`. On the frontend it is a
`PlatformDefinition` in `src/platforms/registry.ts` that owns its sidebar, badges, context switcher and ⌘K
commands. The Gmail platform talks to mail servers only through the `MailProvider` interface
(`gmail_oauth`, `workspace_delegation`, `imap_smtp`, `fake`). Celery runs syncs, delayed sends (undo send),
scheduled sends and snooze wake-ups. Postgres holds a local index of threads (with a full-text
`search_vector`) so lists and search are instant and work across mailboxes.

## Milestones

| # | Milestone | Verification |
|---|---|---|
| 1 | Foundation: repo, docker-compose, settings, auth (session + CSRF), roles, offices, audit, platform registry; Next.js shell rebranded from the reference, platform switcher, login, theme toggle | Login works; switcher shows Gmail active and SMS/Calls/Media "Soon" (Playwright screenshot) |
| 2 | Mail core on `FakeMailProvider`: models, provider interface, `seed_demo`, list/thread/action endpoints, full 3-pane mail UI with optimistic actions + shortcuts | Whole Gmail UX works offline (Playwright) |
| 3 | Google connection: OAuth (PKCE, state, login_hint, scope + account checks), invites + public connect page, MX detection, MultiFernet, sync engine, Gmail provider, health/reconnect | Unit tests with mocked Google; manual check needs real credentials |
| 4 | Compose & send: compose windows, drafts autosave, threading, attachments, templates, signatures, undo send, schedule send, snooze | API tests + Playwright reply flow |
| 5 | Tools, dashboard, settings: filters, vacation, labels CRUD, stats, access management, audit UI + CSV, Workspace delegation, IMAP/SMTP | API tests + screenshots |
| 6 | Hardening: security review, performance, accessibility, docs, status report | pytest ≥ 85 % on mail services/api, `tsc`, ESLint, Playwright in both themes and sizes |

## Order of work inside each milestone

Backend model → service → API → tests, then frontend API hooks → components → pages → Playwright. The
OpenAPI schema is exported to `contracts/openapi.yaml` and TypeScript types are generated from it into
`frontend/src/services/api/schema.d.ts` (`npm run gen:api`).

## Key risks

- **No Google credentials in the build environment.** All Google calls are behind `GmailApiProvider`
  and tested with mocks; the fake provider drives the UI and E2E tests.
- **Scope.** The UI has many surfaces; shared primitives (`components/ui`) keep each page small.
