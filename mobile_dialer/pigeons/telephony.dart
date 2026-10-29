// Typed platform channels between Dart and the native dialer layer (Kotlin) of OCM Phone.
// Regenerate with: dart run pigeon --input pigeons/telephony.dart
import 'package:pigeon/pigeon.dart';

@ConfigurePigeon(PigeonOptions(
  dartOut: 'lib/platform/telephony_api.g.dart',
  kotlinOut: 'android/app/src/main/kotlin/com/kilimanjaro/communicationmanager/phone/bridge/TelephonyApi.g.kt',
  kotlinOptions: KotlinOptions(package: 'com.kilimanjaro.communicationmanager.phone.bridge', errorClassName: 'TelephonyError'),
  dartPackageName: 'ocm_phone',
))

class PermissionState {
  PermissionState({required this.name, required this.granted});
  String name;
  bool granted;
}

class SimInfo {
  SimInfo({required this.subscriptionId, required this.slot, required this.carrier, required this.countryIso, this.number, required this.isDefault});
  int subscriptionId;
  int slot;
  String carrier;
  String countryIso;
  String? number;
  bool isDefault;
}

class DeviceFacts {
  DeviceFacts({required this.manufacturer, required this.model, required this.androidVersion, required this.sdkInt, required this.appVersion, required this.isEmulator, required this.isRooted, required this.debuggerAttached});
  String manufacturer;
  String model;
  String androidVersion;
  int sdkInt;
  String appVersion;
  bool isEmulator;
  bool isRooted;
  bool debuggerAttached;
}

class KeyInfo {
  KeyInfo({required this.publicKeySpki, required this.attestationChain, required this.strongBox});
  String publicKeySpki; // base64 DER SubjectPublicKeyInfo
  List<String> attestationChain; // base64 DER, leaf first
  bool strongBox;
}

class HttpRequestData {
  HttpRequestData({required this.method, required this.url, required this.headers, this.body});
  String method;
  String url;
  Map<String, String> headers;
  Uint8List? body;
}

class HttpResponseData {
  HttpResponseData({required this.status, required this.body});
  int status;
  Uint8List body;
}

class ServiceStatus {
  ServiceStatus({
    required this.running, required this.batteryOptimised, required this.networkAvailable, required this.networkType, this.battery, required this.charging,
    this.signal, required this.backgroundRestricted, this.standbyBucket,
  });
  bool running;
  bool batteryOptimised;
  bool networkAvailable;
  String networkType;
  int? battery;
  bool charging;
  int? signal;
  /// ActivityManager.isBackgroundRestricted: the holder (or the OEM) restricted background work in system settings.
  bool backgroundRestricted;
  /// UsageStatsManager.getAppStandbyBucket (10 active … 45 restricted); null when unknown.
  int? standbyBucket;
}

/// Everything the first frame needs, in one round trip (cold start).
class StartupState {
  StartupState({required this.databasePath, required this.databaseKey, required this.isDefaultDialer, required this.manufacturer, required this.brand, required this.sdkInt, required this.removed});
  String databasePath;
  /// 64 hex characters: the raw 256-bit SQLCipher key (no PBKDF2 on open).
  String databaseKey;
  bool isDefaultDialer;
  String manufacturer;
  String brand;
  int sdkInt;
  /// The administrator revoked this phone while the app was closed (the native sync engine already wiped it).
  bool removed;
}

/// Where an intent asked the app to go: dial (tel:, DIAL), enroll (ocmphone://enroll link) or route (a notification).
class LaunchTarget {
  LaunchTarget({required this.kind, required this.value});
  String kind;
  String value;
}

/// Something that happened natively: calls_changed (a call ended, the call log or call-backs changed), sync_state, launch.
class TelephonyEvent {
  TelephonyEvent({required this.type, this.state});
  String type;
  String? state;
}

/// The dialer's place on this phone. [enabled]: the server has Calls on for this phone (it uploads calls).
class CallsStatus {
  CallsStatus({required this.enabled, required this.isDefaultDialer, required this.dialerRoleAvailable, required this.canUseFullScreenIntent, required this.missingPermissions});
  bool enabled;
  bool isDefaultDialer;
  bool dialerRoleAvailable;
  /// Android 14+: NotificationManager.canUseFullScreenIntent (the incoming-call screen over the lock screen).
  bool canUseFullScreenIntent;
  List<String> missingPermissions;
}

/// One row of the system call log (newest first). USSD/MMI rows are never returned.
class RecentCall {
  RecentCall({required this.id, required this.number, this.name, required this.nameSource, required this.direction, required this.result, required this.date, required this.durationSeconds, this.subscriptionId});
  int id;
  String number;
  String? name;
  /// contact | directory | none
  String nameSource;
  String direction; // in | out
  String result; // answered | missed | rejected | blocked | voicemail | no_answer | answered_elsewhere
  int date;
  int durationSeconds;
  int? subscriptionId;
}

class PhoneContact {
  PhoneContact({required this.name, required this.number, required this.starred, this.photoUri, this.directoryName});
  String name;
  String number;
  bool starred;
  String? photoUri;
  /// The company directory's name for this number, when it has one.
  String? directoryName;
}

class CallbackTaskData {
  CallbackTaskData({required this.id, required this.number, required this.name, required this.reason, required this.requestedBy, required this.priority, required this.dueAt, required this.state});
  String id;
  String number;
  String name;
  String reason;
  String requestedBy;
  String priority;
  int dueAt;
  String state;
}

// Threading: methods marked @async run their work on Dispatchers.IO (HostApiImpl.io), so no Content Provider query,
// Keystore operation or HTTP call ever runs on the Android main thread. Small binder getters run on a background task
// queue. Only calls that need an Activity (role and permission requests, settings screens, FLAG_SECURE) stay on main.
@HostApi()
abstract class TelephonyHostApi {
  // --- Main thread: need the Activity ----------------------------------------------------------------------------
  /// Fallback when the role dialog is dismissed or no longer shown: Settings → Default apps.
  bool openDefaultAppsSettings();
  @async
  List<PermissionState> requestPermissions(List<String> names);
  void openBatteryOptimisationSettings();
  /// Manufacturer screens that stop background work (see Oem.kt); false when the intent does not exist here.
  bool openOemSetting(String id);
  void openAppSettings();
  void setSecureScreen(bool secure);
  /// System photo picker; the chosen image is copied to the app cache and its path returned (QR from a photo).
  @async
  String? pickImage();
  /// Calls: RoleManager.ROLE_DIALER ("Set as default Phone app").
  @async
  bool requestDefaultDialerRole();
  /// Android 14+: the "full screen notifications" settings page for this app.
  void openFullScreenIntentSettings();
  /// The system "new contact" screen, pre-filled with [number] (the person saves it).
  void addContact(String number);
  /// The phone's SMS app (ACTION_SENDTO smsto:), OCM Messages on company phones.
  void messageNumber(String number);

  // --- Background task queue: quick binder calls -----------------------------------------------------------------
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  StartupState startup();
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  List<PermissionState> permissions();
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  DeviceFacts deviceFacts();
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  ServiceStatus serviceStatus();
  /// Ids of the manufacturer settings screens that exist on this phone.
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  List<String> oemSettings();
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  LaunchTarget? consumeLaunch();
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  CallsStatus callsStatus();
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  bool hasDeviceKey();
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  void deleteDeviceKey();
  /// The native sync engine runs a cycle now (expedited work).
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  void syncNow();
  /// Revoked by the administrator: delete the key, the sync database and stored settings.
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  void wipe();

  // --- Dispatchers.IO: provider, contacts, Keystore, network ----------------------------------------------------
  @async
  List<SimInfo> sims();
  /// A small JPEG (longest side ≤ [maxPx]) of a contact photo; null if not an image.
  @async
  Uint8List? thumbnail(String uri, int maxPx);
  @async
  bool canBlockNumbers();
  @async
  void blockNumber(String address);
  @async
  void unblockNumber(String address);
  @async
  List<String> blockedNumbers();

  @async
  KeyInfo createDeviceKey(Uint8List attestationChallenge);
  @async
  Uint8List sign(Uint8List message);

  // --- Calls ------------------------------------------------------------------------------------------------------
  /// Places a call through TelecomManager (emergency numbers always; USSD/MMI handled by Telecom). Returns "placed",
  /// "permission" or "empty". [origin]: manual | redial | from_sms | callback_task.
  @async
  String placeCall(String number, int? subscriptionId, String origin, String? callbackTask);
  @async
  List<RecentCall> recentCalls(int limit, int offset);
  /// The phone's address book (names and numbers), for the keypad's T9 search and the Contacts tab.
  @async
  List<PhoneContact> phoneContacts(int limit);
  @async
  List<CallbackTaskData> callbackTasks();
  /// done | snoozed | dialed (reported to the server as callback.state).
  @async
  void reportCallback(String id, String state);
  @async
  void deleteRecentCall(int id);

  /// HTTPS through OkHttp with certificate pinning (SPKI pins from the build) and TLS 1.2+ only. Enrollment only:
  /// everything after it is the native sync engine's.
  @async
  HttpResponseData http(HttpRequestData request);
}

@EventChannelApi()
abstract class TelephonyEvents {
  TelephonyEvent events();
}
