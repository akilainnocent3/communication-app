import 'dart:typed_data';

import '../platform/telephony_api.g.dart';

/// What the UI needs from the phone itself (besides the dialer, see features/phone/dialer_gateway.dart). The platform
/// implementation talks to the native Kotlin layer through Pigeon; tests use a fake. Syncing with the server is native.
abstract class PhoneGateway {
  Future<List<PermissionState>> permissions();
  Future<List<SimInfo>> sims();
  Future<DeviceFacts> deviceFacts();
  Future<ServiceStatus> serviceStatus();
  Future<Uint8List?> thumbnail(String uri, int maxPx);
  Future<void> blockNumber(String address);
  Future<void> unblockNumber(String address);
  Future<List<String>> blockedNumbers();
  Future<void> syncNow();
}

class PlatformPhoneGateway implements PhoneGateway {
  PlatformPhoneGateway(this.api);
  final TelephonyHostApi api;

  @override
  Future<List<PermissionState>> permissions() => api.permissions();
  @override
  Future<List<SimInfo>> sims() => api.sims();
  @override
  Future<DeviceFacts> deviceFacts() => api.deviceFacts();
  @override
  Future<ServiceStatus> serviceStatus() => api.serviceStatus();
  @override
  Future<Uint8List?> thumbnail(String uri, int maxPx) => api.thumbnail(uri, maxPx);
  @override
  Future<void> blockNumber(String address) => api.blockNumber(address);
  @override
  Future<void> unblockNumber(String address) => api.unblockNumber(address);
  @override
  Future<List<String>> blockedNumbers() => api.blockedNumbers();
  @override
  Future<void> syncNow() => api.syncNow();
}
