# Adding a platform

A **platform** is one communication channel (Gmail today; SMS, Calls and Media later). The shell — sidebar,
platform switcher, mobile context bar, ⌘K palette, Settings → Platforms — knows nothing about any specific
platform. It reads two registries:

| Side | Registry | A platform contributes |
|---|---|---|
| Backend | `modules/platforms/registry.py` (`PlatformRegistry`) | a `PlatformSpec` (key, name, permission, default enablement, order) registered from `AppConfig.ready()` |
| Frontend | `src/platforms/registry.ts` (`PLATFORMS`) | a `PlatformDefinition` (name, icon, base path, nav, badges, commands, optional context switcher / provider) |

The switcher shows the **intersection**: platforms in `PLATFORMS` with `status: "active"` that also appear in
`GET /api/v1/platforms/` (enabled by a super admin **and** permitted for the user), in the server's order.
`coming_soon` entries are always shown, disabled, with a "Soon" badge.

This guide uses SMS as the example, and the real SMS platform (`modules/sms`, `src/platforms/sms`) followed it step
by step. A platform whose data lives on company phones should reuse `modules/devices` (enrollment, identity, device
tokens, heartbeat, push) rather than build its own; give admin-facing serializers a platform prefix so drf-spectacular
component names never collide with another platform's. Every step below was first carried out on a stub SMS platform
behind a feature flag (Playwright: switch to SMS from the header, the sidebar changes to SMS's own nav, `/sms`
renders, a user without `sms.access` doesn't see it). The stub was then removed. Screenshots:
`docs/screenshots/desktop-light-sms-stub-proof.png`, `docs/screenshots/mobile-dark-sms-stub-proof.png`.

## Backend

### 1. Create the Django app

```
backend/modules/sms/
  __init__.py
  apps.py
  models.py
  migrations/__init__.py
  services/         # business logic (keep views thin)
  api/              # serializers.py, views.py, urls.py
  tasks.py          # Celery tasks, if any
```

### 2. Register the platform (`apps.py`)

```python
from django.apps import AppConfig


class SmsConfig(AppConfig):
    name = "modules.sms"
    label = "sms"
    verbose_name = "SMS"

    def ready(self):
        from modules.platforms.registry import PlatformSpec, registry

        registry.register(PlatformSpec(key="sms", name="SMS", permission="sms.access", order=20))
```

- `key` must equal the frontend definition's `key` and the first URL segment (`/sms`).
- `order` is the default position. Super admins can reorder in **Settings → Platforms**, which stores it on
  the `platforms.Platform` row. Rows are created automatically the first time platforms are listed.
- `default_enabled=False` ships a platform switched off until a super admin enables it.
- `session_data=callable(user) -> dict` (optional) adds platform data to `GET /auth/me/` under
  `platform_data["sms"]`. Gmail uses it for the mailbox switcher.

### 3. Declare the access permission (`models.py`)

The permission is a normal Django permission. Put it on your main model's `Meta.permissions`. Until real
models exist, a permission-only model works:

```python
from django.db import models


class SmsPlatform(models.Model):
    """Holds the platform's permissions until real SMS models exist."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [("access", "Use the SMS platform")]
```

Then add `"modules.sms"` to `INSTALLED_APPS` in `config/settings/base.py` and run
`python manage.py makemigrations sms && python manage.py migrate`.

The permission automatically appears in **Settings → Users & roles** (the grantable list includes every
registered platform's permission). Super admins have it implicitly. To give it to seeded roles, add
`"sms.access"` to `ROLE_PERMISSIONS` in `modules/identity/services.py`.

### 4. API

Add `modules/sms/api/urls.py` and include it in `config/urls.py` (`path("", include("modules.sms.api.urls"))`),
under `/api/v1/sms/...`. Guard every view with the platform permission plus object-level checks, as
`modules/mail/api/permissions.py` does. Errors must use the shared shape from `common/errors.py`
(`{code, detail, errors}`). Then regenerate the contract:

```bash
cd backend && python manage.py spectacular --file ../contracts/openapi.yaml --validate
cd ../frontend && npm run gen:api
```

### 5. Audit

Call `modules.audit.services.record(actor, action, ...)` for every sensitive action (e.g. `sms.send`).

## Frontend

### 6. Definition (`src/platforms/sms/definition.tsx`)

```tsx
import { DashboardIcon, MessageIcon } from "@/components/ui/icons";
import { m } from "@/i18n";
import type { PlatformDefinition } from "../types";

export const sms: PlatformDefinition = {
  key: "sms",
  name: m.platforms.sms.name,
  description: m.platforms.sms.description,
  icon: <MessageIcon />,
  accent: "text-[#10b981]",
  basePath: "/sms",
  homePath: "/sms",
  permission: "sms.access",
  status: "active",
  nav: [{ label: "OVERVIEW", items: [{ title: "Dashboard", icon: <DashboardIcon />, url: "/sms" }] }],
  useCommands: () => [{ id: "sms-home", group: "SMS", title: "Open SMS dashboard", icon: <MessageIcon />, href: "/sms" }],
};
```

Optional members (see `src/platforms/types.ts` and `src/platforms/gmail/definition.tsx`):

| Member | Use |
|---|---|
| `useBadges()` | counts keyed by `badgeKey` for nav items (e.g. unread) |
| `ContextSwitcher` | rendered at the top of the sidebar and in the mobile context bar (Gmail: mailbox switcher) |
| `SidebarAction` | prominent button under it (Gmail: Compose) |
| `Provider` | wraps the shell while the platform is active (stores, keyboard shortcuts, floating windows) |
| `nav[].items` as a hook | dynamic entries (Gmail: the selected mailbox's labels) |
| `permission` on nav items / commands | hides entries the user can't use |

Keep user-facing text in `src/i18n/en.ts` (`m.platforms.sms` already exists).

### 7. Routes (`src/app/(app)/sms/`)

Put pages under `src/app/(app)/sms/` so they get the shell. Use the shared building blocks: `Page`,
`PageHeader`, `SectionCard`, `RequestState`, `EmptyState` from `src/components/ui/`, and `usePageTitle()` for
the breadcrumb. API calls go through `src/services/api/client.ts` (same-origin, CSRF, friendly errors).

### 8. Register it

In `src/platforms/registry.ts`, replace the coming-soon entry:

```ts
import { sms } from "./sms/definition";

export const PLATFORMS: PlatformDefinition[] = [gmail, sms, callsComingSoon, mediaComingSoon];
```

…and remove `smsComingSoon` from `coming-soon.tsx` when nothing else uses it.

## Check it

1. `pytest` and `python manage.py makemigrations --check`.
2. `npm run typecheck && npm run lint`.
3. Sign in as a super admin. **SMS** appears in the header switcher. Clicking it opens `/sms`, shows a "Switched
   to SMS" toast, and the sidebar shows only SMS's nav plus the shared Settings section.
4. **Settings → Platforms:** disabling SMS removes it from the switcher for everyone.
5. A user whose role lacks `sms.access` doesn't see SMS.
6. Add a Playwright spec under `frontend/e2e/` for the platform's main flow.
