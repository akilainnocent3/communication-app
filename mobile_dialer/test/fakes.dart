import 'dart:convert';
import 'dart:typed_data';

import 'package:ocm_phone/core/api/device_api.dart';
import 'package:ocm_phone/core/api/transport.dart';
import 'package:ocm_phone/data/phone_gateway.dart';
import 'package:ocm_phone/platform/telephony_api.g.dart';
import 'package:ocm_phone/providers.dart';

/// Settings without services (widget tests): kept in memory.
class MemorySettings extends SettingsController {
  MemorySettings([this.initial = const {}]);
  final Map<String, String> initial;
  @override
  Map<String, String> build() => Map.of(initial);
  @override
  Future<void> set(String key, String value) async => state = {...state, key: value};
}

class FakeSigner implements DeviceSigner {
  final List<String> signed = [];
  @override
  Future<Uint8List> sign(Uint8List message) async {
    signed.add(utf8.decode(message));
    return Uint8List.fromList([1, 2, 3]);
  }
}

typedef Handler = (int, Object?) Function(String method, Uri url, Map<String, String> headers, Object? body);

/// A scripted server: records every request and answers from `handler`.
class FakeTransport implements HttpTransport {
  FakeTransport(this.handler);
  final Handler handler;
  final List<(String, String, Map<String, String>, Object?)> requests = [];

  @override
  Future<TransportResponse> send(String method, Uri url, {Map<String, String> headers = const {}, Uint8List? body}) async {
    Object? decoded;
    if (body != null && (headers['Content-Type'] ?? '').startsWith('application/json')) decoded = jsonDecode(utf8.decode(body));
    requests.add((method, url.path, headers, decoded ?? body));
    final (status, response) = handler(method, url, headers, decoded ?? body);
    return TransportResponse(status, Uint8List.fromList(utf8.encode(response == null ? '' : jsonEncode(response))));
  }
}

class FakePhone implements PhoneGateway {
  final List<String> blocked = [];
  int syncs = 0;

  @override
  Future<List<PermissionState>> permissions() async => [PermissionState(name: 'READ_CALL_LOG', granted: true), PermissionState(name: 'CALL_PHONE', granted: true)];
  @override
  Future<List<SimInfo>> sims() async => [SimInfo(subscriptionId: 1, slot: 0, carrier: 'Vodacom', countryIso: 'tz', isDefault: true)];
  @override
  Future<DeviceFacts> deviceFacts() async => DeviceFacts(manufacturer: 'samsung', model: 'A15', androidVersion: '14', sdkInt: 34, appVersion: '1.0.0', isEmulator: false, isRooted: false, debuggerAttached: false);
  @override
  Future<ServiceStatus> serviceStatus() async =>
      ServiceStatus(running: false, batteryOptimised: false, networkAvailable: true, networkType: 'wifi', battery: 80, charging: false, signal: 3, backgroundRestricted: false, standbyBucket: 10);
  @override
  Future<Uint8List?> thumbnail(String uri, int maxPx) async => null;
  @override
  Future<void> blockNumber(String address) async => blocked.add(address);
  @override
  Future<void> unblockNumber(String address) async => blocked.remove(address);
  @override
  Future<List<String>> blockedNumbers() async => List.of(blocked);
  @override
  Future<void> syncNow() async => syncs++;
}
