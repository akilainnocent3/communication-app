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
  ServiceStatus({required this.running, required this.batteryOptimised, required this.networkAvailable, required this.networkType, this.battery, required this.charging, this.signal});
  bool running;
  bool batteryOptimised;
  bool networkAvailable;
  String networkType;
  int? battery;
  bool charging;
  int? signal;
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
  String type; // message_received | message_changed | send_state | network | outbox_changed
  int? threadId;
  int? providerId;
  String? clientUuid;
  String? state;
}

@HostApi()
abstract class TelephonyHostApi {
  RoleStatus roleStatus();
  @async
  bool requestDefaultSmsRole();
  List<PermissionState> permissions();
  @async
  List<PermissionState> requestPermissions(List<String> names);
  List<SimInfo> sims();
  DeviceFacts deviceFacts();

  List<ThreadSummary> threads(int limit, int offset);
  List<ProviderMessage> messages(int threadId, int limit, int? beforeDate);
  /// Newest first, for the initial backfill and rescans after changes made by other apps.
  List<ProviderMessage> messagesSince(int sinceDate, int limit, int offset);
  /// Bytes of one MMS part (content://mms/part/…) for upload.
  Uint8List readMmsPart(String uri);
  List<ContactInfo> lookupContacts(List<String> addresses);
  List<ContactInfo> searchContacts(String query, int limit);

  @async
  SendResult sendMessage(SendRequest request);
  void markThreadRead(int threadId);
  void deleteMessage(String kind, int providerId);
  void deleteThread(int threadId);
  bool canBlockNumbers();
  void blockNumber(String address);
  void unblockNumber(String address);
  List<String> blockedNumbers();

  /// SQLCipher key for the local sync database (random, wrapped by a Keystore key, never leaves the phone).
  String databaseKey();
  String databasePath();
  bool hasDeviceKey();
  KeyInfo createDeviceKey(Uint8List attestationChallenge);
  Uint8List sign(Uint8List message);
  void deleteDeviceKey();

  /// HTTPS through OkHttp with certificate pinning (SPKI pins from the build) and TLS 1.2+ only.
  @async
  HttpResponseData http(HttpRequestData request);

  void startSyncService();
  void stopSyncService();
  ServiceStatus serviceStatus();
  void openBatteryOptimisationSettings();
  String? launchAddress();
  void setSecureScreen(bool secure);
  /// Revoked by the administrator: delete the key, the sync database and stored settings.
  void wipe();
}

@EventChannelApi()
abstract class TelephonyEvents {
  TelephonyEvent events();
}
