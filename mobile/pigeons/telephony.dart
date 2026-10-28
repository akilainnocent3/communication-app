// Typed platform channels between Dart and the native telephony layer (Kotlin).
// Regenerate with: dart run pigeon --input pigeons/telephony.dart
import 'package:pigeon/pigeon.dart';

@ConfigurePigeon(PigeonOptions(
  dartOut: 'lib/platform/telephony_api.g.dart',
  kotlinOut: 'android/app/src/main/kotlin/com/kilimanjaro/communicationmanager/sms/bridge/TelephonyApi.g.kt',
  kotlinOptions: KotlinOptions(package: 'com.kilimanjaro.communicationmanager.sms.bridge', errorClassName: 'TelephonyError'),
  dartPackageName: 'cm_sms',
))
class RoleStatus {
  RoleStatus({required this.isDefaultSmsApp, required this.roleAvailable});
  bool isDefaultSmsApp;
  bool roleAvailable;
}

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

class ThreadSummary {
  ThreadSummary({required this.threadId, required this.addresses, required this.snippet, required this.date, required this.unreadCount, required this.messageCount, required this.hasMms});
  int threadId;
  List<String> addresses;
  String snippet;
  int date;
  int unreadCount;
  int messageCount;
  bool hasMms;
}

class MmsPartData {
  MmsPartData({required this.seq, required this.contentType, this.filename, required this.size, this.uri});
  int seq;
  String contentType;
  String? filename;
  int size;
  String? uri;
}

/// One message from the Telephony provider (SMS or MMS).
class ProviderMessage {
  ProviderMessage({
    required this.providerId, required this.kind, required this.threadId, required this.addresses, required this.body, required this.date,
    required this.outbound, required this.read, required this.status, this.subscriptionId, this.errorCode, required this.parts, this.subject,
  });
  int providerId;
  String kind; // sms | mms
  int threadId;
  List<String> addresses;
  String body;
  int date;
  bool outbound;
  bool read;
  String status; // received | queued | sending | sent | delivered | failed
  int? subscriptionId;
  int? errorCode;
  List<MmsPartData> parts;
  String? subject;
}

class ContactInfo {
  ContactInfo({required this.address, this.displayName, this.photoUri});
  String address;
  String? displayName;
  String? photoUri;
}

class SendRequest {
  SendRequest({required this.clientUuid, required this.addresses, required this.body, this.subscriptionId, required this.deliveryReport, required this.attachmentUris, required this.origin, this.sentBy});
  String clientUuid;
  List<String> addresses;
  String body;
  int? subscriptionId;
  bool deliveryReport;
  List<String> attachmentUris;
  String origin; // phone | admin
  String? sentBy;
}

class SendResult {
  SendResult({required this.clientUuid, required this.state, this.providerId, this.errorCode, this.parts});
  String clientUuid;
  String state; // sending | failed | duplicate
  int? providerId;
  int? errorCode;
  int? parts;
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
  StartupState({required this.databasePath, required this.databaseKey, required this.isDefaultSmsApp, required this.manufacturer, required this.brand, required this.sdkInt, required this.removed});
  String databasePath;
  /// 64 hex characters: the raw 256-bit SQLCipher key (no PBKDF2 on open).
  String databaseKey;
  bool isDefaultSmsApp;
  String manufacturer;
  String brand;
  int sdkInt;
  /// The administrator revoked this phone while the app was closed (the native sync engine already wiped it).
  bool removed;
}

/// Where an intent asked the app to go: compose (sms:/smsto:), chat (notification, shortcut), enroll (cmsms://enroll
/// link) or route (the sync notification).
class LaunchTarget {
  LaunchTarget({required this.kind, required this.value});
  String kind;
  String value;
}

/// Something that happened natively: a message arrived, a send changed state, the network came back.
/// Outbound state kept natively in the sync database (at-most-once sending).
class OutboundState {
  OutboundState({required this.clientUuid, required this.state, this.providerId, this.errorCode, this.parts, required this.updatedAt});
  String clientUuid;
  String state; // sending | sent | delivered | failed | unknown
  int? providerId;
  int? errorCode;
  int? parts;
  int updatedAt;
}

class TelephonyEvent {
  TelephonyEvent({required this.type, this.threadId, this.providerId, this.clientUuid, this.state});
  /// message_received | message_changed | send_state | contacts_changed | sync_state | launch
  String type;
  int? threadId;
  int? providerId;
  String? clientUuid;
  String? state;
}

// Threading: methods marked @async run their work on Dispatchers.IO (HostApiImpl.io), so no Content Provider query,
// Keystore operation or HTTP call ever runs on the Android main thread. Small binder getters run on a background task
// queue. Only calls that need an Activity (role and permission requests, settings screens, FLAG_SECURE) stay on main.
@HostApi()
abstract class TelephonyHostApi {
  // --- Main thread: need the Activity ----------------------------------------------------------------------------
  @async
  bool requestDefaultSmsRole();
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

  // --- Background task queue: quick binder calls -----------------------------------------------------------------
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  StartupState startup();
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  RoleStatus roleStatus();
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
  bool hasDeviceKey();
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  void deleteDeviceKey();
  /// The native sync engine runs a cycle now (in the foreground service, or as expedited work).
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  void syncNow();
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  void startSyncService();
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  void stopSyncService();
  /// Revoked by the administrator: delete the key, the sync database and stored settings.
  @TaskQueue(type: TaskQueueType.serialBackgroundThread)
  void wipe();

  // --- Dispatchers.IO: provider, contacts, Keystore, network ----------------------------------------------------
  @async
  List<SimInfo> sims();
  /// Newest first. Pages of [limit] (the list asks for 50 at a time).
  @async
  List<ThreadSummary> threads(int limit, int offset);
  /// One conversation row, after an event about it (null when the thread is gone).
  @async
  ThreadSummary? thread(int threadId);
  @async
  List<ProviderMessage> messages(int threadId, int limit, int? beforeDate);
  /// Message bodies containing [query] (SMS and MMS text), newest first.
  @async
  List<ProviderMessage> searchMessages(String query, int limit, int offset);
  /// A small JPEG (longest side ≤ [maxPx]) of an MMS image/video part or a contact photo; null if not an image.
  @async
  Uint8List? thumbnail(String uri, int maxPx);
  @async
  List<ContactInfo> lookupContacts(List<String> addresses);
  @async
  List<ContactInfo> searchContacts(String query, int limit);

  @async
  SendResult sendMessage(SendRequest request);
  @async
  void markThreadRead(int threadId);
  @async
  void deleteMessage(String kind, int providerId);
  @async
  void deleteThread(int threadId);
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

  /// HTTPS through OkHttp with certificate pinning (SPKI pins from the build) and TLS 1.2+ only. Enrollment only:
  /// everything after it is the native sync engine's.
  @async
  HttpResponseData http(HttpRequestData request);
}

@EventChannelApi()
abstract class TelephonyEvents {
  TelephonyEvent events();
}
