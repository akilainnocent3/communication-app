# OCM Phone (Android)

The company's default **Phone** app. It places and answers ordinary carrier calls, and copies each call's record
(number, times, duration, result, SIM; never the audio) to the company's OCM, where admins see the call log, unreturned
missed calls and analytics, and send call-back tasks the staff member places with one tap.

OCM Phone is a **separate app** from OCM Messages (`../mobile/`, the default SMS app): its own package
(`com.kilimanjaro.communicationmanager.phone`), enrollment code (`ocmphone://enroll`), Keystore key and device in the
admin (decision 80). A company phone usually runs both; the admin links them as the same handset. Android only.

Design, emergency and USSD guarantees, and the call merge are in [docs/calls-mobile.md](../docs/calls-mobile.md).

## Layout

```
lib/
  main.dart, app.dart        entry point, router (first route from cached values), skin theming, launch targets
  config.dart                --dart-define values (allowed servers, SPKI pins, FCM)
  platform/                  Pigeon-generated bindings (do not edit; regenerate)
  core/api, core/enroll      enrollment client (app "calls"), ocmphone:// links and short codes (allow-list)
  core/db/                   drift + SQLCipher (raw key): the outbox and settings, shared with the native engine
  data/, state/              phone gateway (native), event coalescing (calls_changed, contacts_changed)
  ui/skin/                   design tokens and one file per skin (One UI, Pixel, HiOS, HyperOS, ColorOS, Company)
  features/phone             Keypad (T9), Recents, Contacts, Call-backs, SIM picker
  features/onboarding        default Phone app → call permissions → incoming-call screen → background
  features/enroll, settings  enroll + scanner, appearance, background, sync status
pigeons/telephony.dart       the Dart ↔ Kotlin contract
android/app/src/main/kotlin/com/kilimanjaro/communicationmanager/phone/
  dialer/                    InCallService, native call screen, ringer, screening, call-log copy, call tracker,
                             notifications, call-back tasks, caller ID, placing calls (emergency always)
  security/, data/           Keystore device key (attestation), DB key wrapping, pinned OkHttp, SQLCipher writer
  sync/                      native sync engine (no SMS), device API client, WorkManager, boot, FCM, revocation
  telephony/                 block list, contacts, sync trigger (call-log content trigger, periodic, expedited)
  bridge/                    Pigeon host API implementation, device state, event bus
```

## Requirements and checks

Flutter stable (3.47+), JDK 17, Android SDK 36; phones with Android 10+ (minSdk 29: `RoleManager.ROLE_DIALER`).

```bash
flutter pub get
dart run pigeon --input pigeons/telephony.dart                 # after changing the contract
flutter gen-l10n                                               # after changing app_en.arb / app_sw.arb
flutter analyze && flutter test                                 # Dart unit, widget and golden tests
(cd android && ./gradlew :app:testPlayDebugUnitTest)           # Kotlin (Robolectric + MockWebServer)
flutter run --flavor private --dart-define=ALLOWED_SERVER_HOSTS=sms.company.co.tz
```

## Flavors and release builds

Same two flavors as OCM Messages: `play` (Google Play; no `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`) and `private` (MDM /
signed APK). Both declare `isMonitoringTool=enterprise_management`. The same `--dart-define` values apply
(`ALLOWED_SERVER_HOSTS` required, `PINNED_SPKI`, `FCM_ENABLED`, `APP_VERSION` = pubspec `version`):

```bash
flutter build apk --release --flavor private --split-per-abi --obfuscate --split-debug-info=build/symbols \
  --dart-define=ALLOWED_SERVER_HOSTS=sms.company.co.tz --dart-define=PINNED_SPKI=<current>,<backup> \
  --dart-define=FCM_ENABLED=true --dart-define=APP_VERSION=1.0.0
flutter build appbundle --release --flavor play --obfuscate --split-debug-info=build/symbols --dart-define=…
```

Signing: use a release key kept outside git (`android/key.properties`, as for OCM Messages; the two apps may share the
company key or use separate ones). Without it, release builds are debug-signed (CI).

## Background

OCM Phone runs no persistent foreground service (decision 81). During a call Telecom keeps it in the foreground
(`phoneCall`), and the call is uploaded as soon as it ends. Call-log rows written while the app is not running trigger a
WorkManager content-URI job. A 15-minute periodic job and FCM wake-ups (`{"type": "callbacks"}`) cover call-back tasks.
The monitoring disclosure appears in onboarding, in Settings → About, and on the ongoing-call notification.

## Distribute and enroll

1. Build and install (MDM, signed APK or managed Google Play).
2. Admin: **Calls → Phones → Enroll OCM Phone**. Optionally pick the SMS phone on the same handset.
3. Phone: open OCM Phone, scan the QR (or tap the link / type the short code), accept the notice, then *Set as default
   Phone app*, the call permissions and, on Android 14+, the incoming-call screen.

An OCM Messages code (`cmsms://`) is refused by OCM Phone, and the server refuses it too (`wrong_app`) without using it up.

## Emulator test

```bash
adb shell cmd role add-role-holder android.app.role.DIALER com.kilimanjaro.communicationmanager.phone 0
adb emu gsm call 0713402118                                     # incoming: the native call screen
adb shell am start -a android.intent.action.CALL -d tel:112 \
  -n com.kilimanjaro.communicationmanager.phone/.CallIntentHandler   # emergency: placed, system in-call UI
```
