# Communication Manager SMS (Android)

The company's default SMS app. It sends and receives real carrier SMS and MMS (billed by the carrier, like any
phone), copies them to the company's Communication Manager, and sends the replies administrators write in the admin.
It is **Android only**: iOS does not let any third-party app read or send SMS or become the SMS app.

Design, security model and the sync protocol are in [docs/sms-mobile.md](../docs/sms-mobile.md).

## Layout

```
lib/
  main.dart                  UI entry point and `backgroundMain` (headless sync engine in the foreground service)
  app.dart, theme.dart       router (go_router), Material 3, dynamic colour, l10n
  config.dart                --dart-define values (allowed servers, SPKI pins, FCM)
  platform/                  Pigeon-generated bindings (do not edit; regenerate)
  core/api/                  device API client (proof-of-possession tokens), transport (native, pinned)
  core/db/                   drift + SQLCipher: durable outbox, outbound states, app state
  core/sync/                 sync engine, background loop, backoff
  core/enroll, core/text     QR parsing (allow-list), segment counter, numbers, one-time codes
  data/                      phone gateway (native) and conversations repository
  features/                  onboarding, enroll, conversations, chat, compose, settings
  l10n/app_en.arb            every user-facing string (add app_sw.arb for Swahili)
pigeons/telephony.dart       the Dart ↔ Kotlin contract
android/app/src/main/kotlin/com/kilimanjaro/communicationmanager/sms/
  telephony/                 SMS receiver, sender + sent/delivered receivers, provider access, notifications,
                             blocking, contacts, reply-with-message service
  mms/                       WAP push receiver, download/send, minimal PDU codec
  security/                  Keystore device key (attestation), DB key wrapping, pinned OkHttp
  data/                      native writer for the shared SQLCipher sync database
  sync/                      foreground service (remoteMessaging), WorkManager, boot, FCM
  bridge/                    Pigeon host API implementation and event bus
```

## Requirements

- Flutter stable (3.47+, Dart 3.13+), JDK 17, Android SDK 36, NDK (installed by Gradle).
- A phone with Android 10+ (minSdk 29: `RoleManager.ROLE_SMS`).

## Develop

```bash
flutter pub get
dart run pigeon --input pigeons/telephony.dart                 # after changing the contract
dart run build_runner build --delete-conflicting-outputs       # after changing drift tables
flutter gen-l10n                                               # after changing app_en.arb
flutter analyze && flutter test                                 # Dart unit and widget tests
(cd android && ./gradlew :app:testDebugUnitTest)               # Kotlin unit tests (Robolectric)
flutter run --dart-define=ALLOWED_SERVER_HOSTS=sms.company.co.tz
```

## Build a release

Every value below is build-time configuration, not a secret:

| Define | Meaning |
|---|---|
| `ALLOWED_SERVER_HOSTS` | **Required.** Comma-separated hosts the app may enroll with (exact match, HTTPS only). A QR code pointing anywhere else is refused. |
| `PINNED_SPKI` | Base64 SHA-256 SPKI pins of the server certificate chain, comma separated. Give **at least two** (current key and a backup key). Empty = system trust only. |
| `FCM_ENABLED` | `true` when `android/app/google-services.json` is present (near-instant delivery). Without it the app polls every 20 s while online and WorkManager syncs every 15 min. |
| `APP_VERSION` | Sent with every request; the server refuses versions below `SMS_MIN_APP_VERSION` (426). Keep it equal to `version:` in pubspec.yaml. |

```bash
flutter build apk --release --obfuscate --split-debug-info=build/symbols \
  --dart-define=ALLOWED_SERVER_HOSTS=sms.company.co.tz \
  --dart-define=PINNED_SPKI=<current-pin>,<backup-pin> \
  --dart-define=APP_VERSION=1.0.0
```

Get a pin from the live server (repeat for the backup key's CSR/certificate):

```bash
openssl s_client -connect sms.company.co.tz:443 -servername sms.company.co.tz </dev/null 2>/dev/null \
  | openssl x509 -pubkey -noout | openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | base64
```

**Pin rotation:** ship a build that contains the new pin *and* the old one, wait until every phone has updated
(the admin shows each phone's app version), then rotate the certificate key, then drop the old pin in the next build.
Raise `SMS_MIN_APP_VERSION` on the server to force stragglers to update.

### Signing

Create a release key once and keep it outside git (a password manager or the company's HSM):

```bash
keytool -genkeypair -v -keystore ~/cm-sms-release.jks -keyalg EC -groupname secp256r1 -validity 10000 -alias cm-sms
```

Then create `android/key.properties` (git-ignored):

```properties
storeFile=/home/you/cm-sms-release.jks
storePassword=…
keyAlias=cm-sms
keyPassword=…
```

Release builds use R8 (minify + resource shrinking) and Dart obfuscation. Without `key.properties` the release APK is
signed with the debug key, which is only acceptable for testing.

### Firebase (optional)

Create a Firebase project, add an Android app with the package `com.kilimanjaro.communicationmanager.sms`, download
`google-services.json` into `android/app/` (git-ignored) and build with `--dart-define=FCM_ENABLED=true`. On the server set
`FCM_PROJECT_ID` and mount the service-account file at `FCM_SERVICE_ACCOUNT_FILE`.

## Distribute (private)

Google Play only allows SMS permissions for apps that are the default SMS handler and requires a Permissions
Declaration. This is an internal company app, so distribute it privately:

1. **Managed Google Play private app** (recommended with an EMM such as Google Workspace endpoint management or
   Intune): upload the signed AAB/APK as a private app for your organisation; Play Protect and updates still work.
   Fill in the SMS Permissions Declaration ("default SMS handler").
2. **MDM / signed APK**: push the signed APK with the MDM, or install it with `adb install` on company phones. Keep
   "Install unknown apps" disabled afterwards. Updates are new APKs signed with the same key.

On each phone: install → open → make it the default SMS app → allow permissions → turn off battery optimisation
(Samsung: Settings → Battery → Background usage limits → Never sleeping apps) → scan the QR code from
**Admin → SMS → Enroll phone** → accept the monitoring notice.

## Emulator test

```bash
flutter run --dart-define=ALLOWED_SERVER_HOSTS=10.0.2.2   # the server needs HTTPS even here
adb emu sms send +255754210331 "Habari, test"              # inbound: appears in the app and then in the admin
```

Outbound from the admin is sent by the emulator's modem; with two emulators (`emulator-5554`, `emulator-5556`) the
second receives what the first sends (address `5556`).
