# OCM — Office Communication (Android)

The company's default SMS app. It sends and receives real carrier SMS and MMS (billed by the carrier, like any
phone), copies them to the company's Communication Manager, and sends the replies administrators write in the admin.
It is **Android only**: iOS does not let any third-party app read or send SMS or become the SMS app.

Design, security model and the sync protocol are in [docs/sms-mobile.md](../docs/sms-mobile.md).

## Layout

```
lib/
  main.dart                  UI entry point: one native round trip and one database read, then the first frame
  app.dart                   router (first route from cached values), skin theming, launch targets
  config.dart                --dart-define values (allowed servers, SPKI pins, FCM)
  platform/                  Pigeon-generated bindings (do not edit; regenerate)
  core/api/                  enrollment client (the native engine does the rest), transport (native, pinned)
  core/db/                   drift + SQLCipher (raw key): outbox, outbound states, app state, read caches
  core/enroll, core/text     QR/link parsing (allow-list), short codes, segment counter, numbers, one-time codes
  core/perf.dart             profile-only timings (cm.perf in logcat)
  data/                      phone gateway (native) and the cache-first conversations repository
  state/                     list and chat controllers, event coalescing
  ui/skin/                   design tokens and one file per skin (One UI, Pixel, HiOS, HyperOS, ColorOS, Company)
  features/                  onboarding, enroll + scanner, conversations, chat, compose, settings
  l10n/app_en.arb, app_sw.arb  every user-facing string, English and Swahili
pigeons/telephony.dart       the Dart ↔ Kotlin contract
android/app/src/main/kotlin/com/kilimanjaro/communicationmanager/sms/
  telephony/                 SMS receiver, sender + sent/delivered receivers, provider access, notifications,
                             blocking, contacts, reply-with-message service
  mms/                       WAP push receiver, download/send, minimal PDU codec
  security/                  Keystore device key (attestation), DB key wrapping, pinned OkHttp
  data/                      native writer for the shared SQLCipher sync database
  sync/                      native sync engine, device API client, foreground service (remoteMessaging),
                             WorkManager, boot, FCM, revocation
  bridge/                    Pigeon host API implementation, device state, event bus
  Oem.kt                     manufacturer battery / auto-start screens
src/devtools/                debug and profile builds only: the seeding receiver for performance runs
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
flutter analyze && flutter test                                 # Dart unit, widget and golden tests
flutter test --update-goldens test/skin_test.dart              # after changing a skin on purpose
UPDATE_SCHEMA=1 flutter test test/db_test.dart                 # after changing tables (Kotlin tests use the schema)
(cd android && ./gradlew :app:testPlayDebugUnitTest)           # Kotlin unit tests (Robolectric + MockWebServer)
flutter run --flavor private --dart-define=ALLOWED_SERVER_HOSTS=sms.company.co.tz
```

## Flavors: `play` and `private`

Every build is one of two product flavors (`android/app/build.gradle.kts`). Both carry the Google Play
`isMonitoringTool=enterprise_management` flag and the always-visible "OCM: company monitoring active" notification.

| Flavor | For | Battery optimisation |
|---|---|---|
| `play` | Google Play (public listing or managed Google Play) | Does **not** declare `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` (Play restricts it to a few app categories). *Keep messages flowing* opens Android's battery-optimisation list and tells the holder to pick OCM → *Don't optimise* |
| `private` | MDM push / signed APK | Declares it (`src/private/AndroidManifest.xml`) and shows Android's direct "Let OCM always run in the background?" dialog |

```bash
flutter build apk --release --flavor private --split-per-abi --dart-define=…     # MDM / APK
flutter build appbundle --release --flavor play --dart-define=…                    # Google Play
flutter test; (cd android && ./gradlew :app:testPlayDebugUnitTest)                 # tests (either flavor)
```

Store listing, permission declarations and Data safety answers: [docs/play-store.md](../docs/play-store.md).

## Build a release

Every value below is build-time configuration, not a secret:

| Define | Meaning |
|---|---|
| `ALLOWED_SERVER_HOSTS` | **Required.** Comma-separated hosts the app may enroll with (exact match, HTTPS only). A QR code pointing anywhere else is refused. |
| `PINNED_SPKI` | Base64 SHA-256 SPKI pins of the server certificate chain, comma separated. Give **at least two** (current key and a backup key). Empty = system trust only. |
| `FCM_ENABLED` | `true` when `android/app/google-services.json` is present (near-instant delivery). Without it the app polls every 20 s while online and WorkManager syncs every 15 min. |
| `APP_VERSION` | Sent with every request; the server refuses versions below `SMS_MIN_APP_VERSION` (426). Keep it equal to `version:` in pubspec.yaml. |

```bash
# One APK per ABI (company phones are arm64-v8a; armeabi-v7a for old ones):
flutter build apk --release --flavor private --split-per-abi --obfuscate --split-debug-info=build/symbols \
  --dart-define=ALLOWED_SERVER_HOSTS=sms.company.co.tz \
  --dart-define=PINNED_SPKI=<current-pin>,<backup-pin> \
  --dart-define=FCM_ENABLED=true --dart-define=APP_VERSION=1.1.0
# Managed Google Play private app: an AAB (Play serves each phone only its ABI)
flutter build appbundle --release --flavor play --obfuscate --split-debug-info=build/symbols --dart-define=…
```

The QR scanner uses Google Play services' barcode model (`dev.steenbakker.mobile_scanner.useUnbundled=true` in
`android/gradle.properties`, fetched at install time) instead of bundling ML Kit's (~5 MB per ABI). Phones without Play
services enroll with the link or the short code. R8 and resource shrinking stay on for release.

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

`build/symbols/` (from `--split-debug-info`) and `build/app/outputs/mapping/release/mapping.txt` are needed to read
crash stack traces of that exact build. Archive them privately with each release; they are git-ignored and must not
be committed.

### Building on a small machine (≤ 8 GB RAM)

R8 and Dart's AOT compiler together need most of 8 GB. If the Gradle daemon is killed during
`minifyReleaseWithR8`, override the project settings for your user only (`~/.gradle/gradle.properties`, which wins
over `android/gradle.properties`), close other heavy processes, and build one ABI:

```properties
org.gradle.jvmargs=-Xmx1536m -XX:MaxMetaspaceSize=512m -XX:ReservedCodeCacheSize=192m
org.gradle.workers.max=1
org.gradle.daemon=false
```

```bash
flutter build apk --release --target-platform android-arm64 --dart-define=…
```

On a 2-core, 7.7 GB Codespace this built `app-release.apk` (arm64, 54.5 MB) in about 13 minutes, with memory peaking
at about 6.9 GB in use.

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

## Measuring performance

Profile builds print `cm.perf …` lines (startup marks, chat-open spans, frame summaries) to logcat; release builds
print nothing. To fill a test phone or emulator (debug/profile builds only; the receiver needs adb shell's DUMP
permission and the app must be the default SMS app):

```bash
adb shell am broadcast -n com.kilimanjaro.communicationmanager.sms/.devtools.SeedReceiver \
  --ei threads 300 --ei messages 20000 --ei big 2000
```

Method and results: [docs/sms-mobile-performance.md](../docs/sms-mobile-performance.md).

## Emulator test

```bash
flutter run --dart-define=ALLOWED_SERVER_HOSTS=10.0.2.2   # the server needs HTTPS even here
adb emu sms send +255754210331 "Habari, test"              # inbound: appears in the app and then in the admin
```

Outbound from the admin is sent by the emulator's modem; with two emulators (`emulator-5554`, `emulator-5556`) the
second receives what the first sends (address `5556`).

## Release checks on Android 10 and 16

A release build must pass this on an Android 10 (API 29) and an Android 16 (API 36) emulator before it is shipped;
Android 10 and 11 lack several newer APIs, and R8 only runs in release builds:

1. Fresh install → default SMS app → permissions → battery → enroll (the server needs HTTPS: give the emulator a
   certificate it trusts, e.g. a throwaway build whose network security config also trusts a local test CA).
2. Send from the chat, receive (`adb emu sms send`), queue an admin reply with the app in the background.
3. `adb install -r` over the running app (the update starts the sync service while the UI starts), reboot, and kill
   the process (`adb root; adb shell kill -9 <pid>`) then receive an SMS.
4. `adb logcat | grep -E "FATAL|AndroidRuntime|CmSms|startup failed"` stays empty apart from `CmSms` warnings.

`./gradlew :app:lintDebug` also flags calls that are too new for `minSdk` 29 (`NewApi`).
