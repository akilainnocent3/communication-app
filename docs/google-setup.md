# Google setup

This guide lets Communication Manager connect Gmail and Google Workspace mailboxes with **"Connect with
Google"**. You do it **once** for the whole company, in about 20 minutes. Office staff never need 2-Step
Verification, App Passwords or any technical steps.

You need:

- a Google account that will own the project. A normal `@gmail.com` address works, for example the
  company's main Gmail address. Use an account the company controls, not a staff member's private one,
  so the project stays with the company when people leave. Add a second owner as a backup
  (**IAM & Admin → IAM → Grant access**, role **Owner**);
- the public address of your server, e.g. `https://mail.company.co.tz` (this is `PUBLIC_APP_URL`).


> **Google changes its console and policies often.** Menu names below were correct when this was written.
> If something looks different, search the console for the item's name, and check the current rules on
> Google's "OAuth app verification" and "Unverified apps" help pages.

---

## 1. Create a project

1. Open <https://console.cloud.google.com/> and sign in.
2. Click the project picker at the top → **New project**.
3. Name it `Communication Manager` → **Create**. Make sure the new project is selected.
   With a `@gmail.com` owner, **Location** shows **No organization**. That is fine.

## 2. Turn on the Gmail API

1. Menu → **APIs & Services → Library**.
2. Search **Gmail API** → open it → **Enable**.

## 3. Set up the consent screen

This is the screen office staff see when they tap "Connect with Google". In newer consoles it is called
**Google Auth Platform**. In older ones it is **APIs & Services → OAuth consent screen**.

1. **Branding / App information:**
   - App name: `Communication Manager` (or your company's name for it).
   - User support email: an address staff can write to.
   - App logo: optional. Uploading one can trigger a brand review, so skip it at first.
   - Developer contact email: your address.
2. **Audience / User type:** choose **External**. This allows normal `@gmail.com` office accounts.
   **Internal** would only allow your own Workspace domain.
3. **Data access / Scopes:** click **Add or remove scopes** and add:

   | Scope | Why |
   |---|---|
   | `openid` | Confirms which account signed in |
   | `https://www.googleapis.com/auth/userinfo.email` | Reads that account's email address, so a wrong account can be rejected |
   | `https://mail.google.com/` | Full mailbox access: read, send, label, delete, and permanent delete |
   | `https://www.googleapis.com/auth/gmail.settings.basic` | Filters, vacation responder and signatures |

   If a scope is not listed, paste it into **Manually add scopes**. These are the defaults in
   `GOOGLE_OAUTH_SCOPES`. If you change that variable, change this list to match.

## 4. Create the OAuth client

1. **Clients** (or **APIs & Services → Credentials**) → **Create client** / **Create credentials → OAuth client ID**.
2. Application type: **Web application**. Name: `Communication Manager web`.
3. **Authorised redirect URIs:** add one for each place the app runs. Each must match **exactly**, including
   the trailing slash:

   | Where | Redirect URI |
   |---|---|
   | Local development | `http://localhost:3000/api/v1/mail/oauth/callback/` |
   | Production | `https://mail.company.co.tz/api/v1/mail/oauth/callback/` |

   The app uses `PUBLIC_APP_URL` + `/api/v1/mail/oauth/callback/` unless you set `GOOGLE_OAUTH_REDIRECT_URI`.
   **Settings → Integrations** in the app shows the exact value it uses.
4. **Create.** Copy the **Client ID** and **Client secret** into the server's `.env`:

   ```
   GOOGLE_OAUTH_CLIENT_ID=1234567890-abc.apps.googleusercontent.com
   GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-...
   ```

   Restart the backend (`docker compose up -d`). **Settings → Integrations** should now say Google sign-in is
   configured.

## 5. Publish the app (important)

A new app starts in **Testing**. In Testing, only listed test users can connect, and **Google expires their
refresh tokens after 7 days**: every mailbox would disconnect weekly.

1. **Audience** (or **OAuth consent screen**) → **Publishing status** → **Publish app** → confirm
   **In production**.
2. **Do not submit for verification** (unless you later decide to; see below). The app works unverified.

What "in production but unverified" means:

| | |
|---|---|
| ✅ | Refresh tokens no longer expire after 7 days; mailboxes stay connected |
| ⚠️ | Staff see **"Google hasn't verified this app"**. They tap **Advanced → Go to Communication Manager (unsafe)**. The connect page explains this with an illustrated helper |
| ⚠️ | **100-user cap:** an unverified app using restricted scopes (like `https://mail.google.com/`) can be authorised by at most 100 Google accounts over the app's lifetime. That is about 100 connected mailboxes. Workspace accounts that mark the app as Trusted (step 6) don't count against it |

Full verification removes the warning and the cap. For restricted Gmail scopes it requires a security
assessment by a Google-approved assessor (yearly, with a fee), so for a company connecting its own offices
the unverified route is usually the right choice. Revisit it if you approach 100 mailboxes.

## 6. (Workspace only) Mark the app as Trusted

If `@company.com` runs on Google Workspace, a Workspace admin can remove the warning for company accounts:

1. <https://admin.google.com/> → **Security → Access and data control → API controls**.
2. **Manage third-party app access** → **Configure new app** → search by the **Client ID** from step 4.
3. Choose your organisation (or an organisational unit) → access: **Trusted** → **Finish**.

Company accounts then go straight from "Choose an account" to "Allow".

## 7. (Optional) Workspace domain-wide delegation: zero clicks per mailbox

With delegation, a super admin adds `anyone@company.com` and it connects instantly, with no consent screen.
Use it only for a Workspace domain you control. It gives the app access to **every** mailbox in that domain.

### 7a. Create a service account and key (Google Cloud)

1. In the same project: **IAM & Admin → Service accounts → Create service account**. Name:
   `cm-delegation`. Skip the optional role steps.
2. Open the service account → **Keys → Add key → Create new key → JSON**. A `.json` file downloads.
   Keep it safe: anyone with it can act as the service account.
   - If key creation is blocked, your organisation enforces the policy
     `iam.disableServiceAccountKeyCreation` (on by default for many new organisations). An organisation
     policy admin can make an exception for this project under **IAM & Admin → Organization policies**.

### 7b. Upload it in Communication Manager

1. **Settings → Integrations → Google Workspace** → enter the domain (e.g. `company.com`) → upload the JSON.
   The key is stored encrypted (`MAIL_TOKEN_KEYS`), and is never shown again or sent to the browser.
2. The page shows the **Client ID** and the **exact scope string** to paste in the next step.

### 7c. Authorise it (Google Admin)

1. <https://admin.google.com/> → **Security → Access and data control → API controls → Manage domain-wide
   delegation** → **Add new**.
2. Paste the **Client ID** and the **scope string** from the Integrations page (comma separated, copy it
   exactly) → **Authorise**.
3. Back in Communication Manager, click **Test**. It tries to open a mailbox in the domain as that user.
   Changes can take a few minutes to apply at Google. If the test fails at first, wait and try again.

From then on, mailboxes in that domain are detected as **Workspace** and connect without any consent.

---

## How connecting works for staff

1. An admin opens **Gmail → Add mailbox**, enters the office and email address, and the app detects the
   provider (MX lookup).
2. **Connect now** (the admin is with the office person), or **Send connect link** (copy, WhatsApp or QR). The
   link is single-use and expires in 72 hours (`MAIL_INVITE_TTL_HOURS`).
3. The office person opens the link → **Connect with Google** → picks the account (it is pre-selected with
   `login_hint`) → (unverified warning → Advanced → Go to…) → **Allow** → "Mailbox connected".

The app rejects the connection if the person signs in with a different account, or unticks a permission, and
explains how to retry.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `redirect_uri_mismatch` | The redirect URI in step 4 doesn't exactly match the one in Settings → Integrations (http vs https, trailing slash, port) |
| "Access blocked: app is in testing" / `access_denied` | Publish the app (step 5), or add the account as a test user |
| Mailbox shows **Needs reconnect** | The owner revoked access, changed their password with "sign out everywhere", or the refresh token expired (Testing mode). Use **Send reconnect link** |
| "This app is blocked" for a Workspace account | The Workspace admin restricts third-party apps. Mark the app as Trusted (step 6) |
| Delegation test fails with `unauthorized_client` | The Client ID or scopes in Google Admin don't match the Integrations page, or it hasn't applied yet (wait up to an hour) |
| "You've reached the user limit" | You've hit the 100-user cap for unverified apps (step 5) |
