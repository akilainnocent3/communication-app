# Google Play: listing, declarations and review

How to publish the two OCM Android apps (flavor `play`) on Google Play, as managed private apps for your organisation
or as public listings. They are **separate apps with separate listings** (decision 80): each holds one default-handler
role and declares only that role's permissions. Private MDM distribution (flavor `private`) needs none of this, but the
same disclosures apply on the phone. Google's policies change; re-read the linked policy pages before each submission.

| Item | OCM Messages (`mobile/`) | OCM Phone (`mobile_dialer/`) |
|---|---|---|
| Play title | **OCM Messages – Office Communication** | **OCM Phone – Office Communication** |
| Package | `com.kilimanjaro.communicationmanager.sms` | `com.kilimanjaro.communicationmanager.phone` |
| Launcher entry | *OCM Messages* | *Phone* (Swahili: *Simu*) |
| Default handler role | SMS (`ROLE_SMS`) | Phone (`ROLE_DIALER`) |
| Category | Business | Business |
| Monitoring flag | `isMonitoringTool=enterprise_management`, a direct child of `<manifest>`, every build and flavor | the same |
| Disclosure on the phone | Ongoing notification "OCM: company monitoring active" whenever the sync service runs; re-posted if swiped away | Onboarding notice, Settings → About, and "Recorded in company call records" on every ongoing-call notification (no persistent service, decision 81) |
| Target audience | Adults; employees of the publishing company only | the same |

Neither app may look like a system app: the names *Messages* or *Phone* alone, the system icons, or a vendor's logo
would be impersonation. All labels start with OCM and the icons are OCM's own ring mark.

## Permissions Declaration Form

Google restricts SMS and Call Log permissions to the app holding the matching **default handler** role. Each OCM app
declares only its own group and requests nothing until the holder has made it the default app.

### OCM Messages: SMS (default SMS handler)

- **Core functionality:** *Default SMS handler.* OCM Messages is the phone's SMS/MMS app: it receives, stores, shows and sends
  every text message (`SMS_DELIVER`, `WAP_PUSH_DELIVER`, the Telephony provider) and is set as default in onboarding.
- **Permissions:** `READ_SMS`, `RECEIVE_SMS`, `SEND_SMS`, `RECEIVE_MMS`, `RECEIVE_WAP_PUSH`.
- **Declaration text (paste):**
  > OCM Messages is the default SMS app on company-owned phones. It receives, stores, displays and sends SMS and MMS like any
  > messaging app. In addition, as disclosed to the employee before enrollment and in a persistent notification, it
  > copies the phone's messages to the employer's OCM server, where authorised administrators can read them and ask the
  > phone to send replies. The app requests the SMS permissions only after the user has chosen it as the default SMS
  > app, and it cannot work without them.

### OCM Phone: Phone and call log (default phone handler)

- **Core functionality:** *Default Phone handler.* OCM Phone is the dialer: keypad, recents (call log), contacts,
  in-call screen (`InCallService` with `IN_CALL_SERVICE_UI`), incoming-call screen and ringing, call screening.
- **Permissions:** `READ_CALL_LOG`, `WRITE_CALL_LOG`, `CALL_PHONE`, `ANSWER_PHONE_CALLS`, `READ_PHONE_STATE`,
  `READ_PHONE_NUMBERS`, `READ_CONTACTS`, `WRITE_CONTACTS`. No SMS permission.
- **Declaration text (paste):**
  > OCM Phone is the default phone app on company-owned phones: it places and answers calls, shows the call history
  > and the in-call screen, and screens calls against the company's blocked list. As disclosed to the employee before
  > enrollment and on every ongoing-call notification, it copies call metadata (number, time, duration,
  > result, SIM) to the employer's OCM server so authorised administrators can see call logs and assign call-backs.
  > Call audio is never recorded. Digits typed during calls and USSD codes and their responses are never stored or
  > sent. Emergency calls are never blocked or screened.

## Foreground services

| App | Service | `foregroundServiceType` | Permission | Why (Play Console → App content → Foreground services) |
|---|---|---|---|---|
| OCM Messages | `SyncService` | `remoteMessaging` | `FOREGROUND_SERVICE_REMOTE_MESSAGING` | Relays the phone's SMS to the company server and the admins' replies back to the phone, within seconds, while the app is not in the foreground. User-visible: the monitoring notification |
| OCM Phone | `OcmInCallService` (Telecom-bound) | `phoneCall` | `FOREGROUND_SERVICE_PHONE_CALL` | The ongoing-call notification and screen of the default dialer during a call. OCM Phone has no other foreground service |

Video for the foreground-service declaration: show the notification while the app is closed, an SMS arriving, and it
appearing in the admin within seconds; then an admin reply being sent by the phone.

`REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` is **not** in the `play` flavor (Play allows it only for a few app types); the
app guides the holder to Settings → Battery optimisation instead.

## Data safety form

Answers for the `play` flavor; fill one form per app (OCM Messages: the SMS rows; OCM Phone: the call-log rows; both:
contacts, phone number, IDs, diagnostics). "Collected" = sent off the device to the employer's server (the developer here is the
employer: the app talks only to the server compiled into it). No data goes to the app's developer otherwise, and none
is shared with third parties. FCM receives only a device token and a content-free wake-up.

| Data type | Collected | Shared | Optional | Purpose | Notes |
|---|---|---|---|---|---|
| SMS / MMS messages (Messages → SMS or MMS) | Yes | No | No | App functionality, Account management (company) | Encrypted at rest on the server |
| Call logs (Calls, B) | Yes | No | No | App functionality | Number, time, duration, result, SIM; never audio |
| Contacts (Personal info → Contacts) | Yes, minimised | No | No | App functionality | Only names of numbers that appear in messages or calls; the address book is never uploaded |
| Phone number (Personal info) | Yes | No | No | App functionality | The SIM's own number, when the SIM exposes it |
| Device or other IDs | Yes | No | No | App functionality, Fraud prevention & security | Keystore public key, app-generated device id, FCM token |
| App info and performance (diagnostics) | Yes | No | No | App functionality | Battery, network type, permissions state, app version |
| Photos (Photos and videos) | Yes (MMS attachments; OCM Messages only) | No | No | App functionality | Only attachments of MMS messages |
| Location, audio, health, financial info | No | — | — | — | Mobile-money SMS are stored like other SMS and masked in the admin |

- **Encrypted in transit:** yes (HTTPS only, TLS 1.2+, optional certificate pinning).
- **Deletion:** data on the server is deleted after the company's retention period (`SMS_RETENTION_DAYS`,
  `CALLS_RETENTION_DAYS`); an employee can ask the company (the controller) for deletion. Revoking the phone wipes the
  app's local data.
- **Independent security review:** not claimed.

## Store listing disclosure

Put this at the **top** of each full description (Play requires prominent disclosure for monitoring apps):

> **OCM Messages is a company monitoring app for employer-owned phones.** When enrolled by your employer, it copies the
> text messages of this phone to your employer's OCM server, where authorised administrators can read them and reply.
> You are told before enrollment and a notification is shown at all times while monitoring is active. Do not install
> it on a personal phone.

> **OCM Phone is a company monitoring app for employer-owned phones.** When enrolled by your employer, it records the
> calls of this phone (number, time, duration, result; never the conversation) on your employer's OCM server, where
> authorised administrators can see them and ask you to call customers back. You are told before enrollment and on
> every call. Do not install it on a personal phone.

Short descriptions (80 characters): *Company SMS app for employer-owned phones (monitored).* and *Company Phone app for
employer-owned phones (call records kept, no audio).*

Screenshots: OCM Messages: the notice, the monitoring notification, the conversation list. OCM Phone: the notice, the
keypad, recents and the in-call screen. No screenshot may show a vendor's or Google's app name or icon.

## Privacy policy (outline)

Host it on the company website and link it in Play Console and in the app (Settings → About).

1. Who we are: the company (controller), contact and data-protection contact.
2. Scope: employer-owned phones enrolled by the company; not for personal devices.
3. What is collected: SMS/MMS content and metadata; call metadata (no audio); minimal contact names; device and SIM
   facts; diagnostics. What is *not*: call audio, USSD codes and responses, DTMF digits, location, the address book.
4. Purpose and lawful basis (Tanzania PDPA 2022 and company policy): business communication records, customer service
   follow-up, accountability; the employee notice and acceptance at enrollment.
5. Who can see it: authorised administrators by role and per-phone grants; every access is audit-logged.
6. Storage and security: the company's own server; encryption at rest of message text and notes; HTTPS; hardware-backed
   device keys.
7. Retention: the configured periods; deletion on the phone keeps the company copy (accountability record).
8. Rights: access, correction, deletion requests to the company; complaints to the PDPC.
9. Changes to the policy.

## Reviewer access

Google reviews each app on its own devices, so give them a working, isolated demo (one code per app: SMS → Enroll
phone for OCM Messages, Calls → Phones → Enroll OCM Phone for OCM Phone):

1. Run a demo server (`SEED_DEMO=1`, simulator **off**, real HTTPS) at a host compiled into a dedicated reviewer build
   (`ALLOWED_SERVER_HOSTS=demo.example.co.tz`), or accept that reviewers use the onboarding screens only.
2. Create a long-lived enrollment: an invite whose expiry you extend for the review period
   (`SMS_ENROLL_TTL_HOURS=720` on the demo server only) and a short code issued just before submitting; paste the code,
   the server address and the steps into *App access → Instructions*.
3. Give an admin login to the demo admin (read-only Viewer role is enough to see that messages arrive).
4. Wipe the demo server after the review.

## Video checklist (Permissions Declaration and foreground services)

OCM Messages:

- [ ] Fresh install → onboarding shows the monitoring notice **before** any permission or role request.
- [ ] Set as default SMS app (system dialog), then the SMS permissions.
- [ ] Enroll; the notification "OCM: company monitoring active" appears and stays.
- [ ] Receive an SMS; it shows in the app and, seconds later, in the admin.

OCM Phone:

- [ ] Fresh install → enrollment shows the calls monitoring notice **before** any permission or role request.
- [ ] Set as default Phone app (system dialog), then call permissions and the incoming-call screen (full-screen intent).
- [ ] Make and receive a call with the OCM in-call screen ("Recorded in company call records" on the notification); the
      call shows in the admin call log.
- [ ] Dial an emergency number on a test SIM-less emulator (show it is never blocked); dial a USSD code (show the
      response dialog and that nothing about it appears in the admin).
- [ ] Settings → About shows the notice and the privacy-policy link.
