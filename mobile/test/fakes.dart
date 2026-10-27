import 'dart:convert';
import 'dart:typed_data';

import 'package:cm_sms/core/api/device_api.dart';
import 'package:cm_sms/core/api/transport.dart';
import 'package:cm_sms/data/phone_gateway.dart';
import 'package:cm_sms/platform/telephony_api.g.dart';

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

ProviderMessage providerMessage({int id = 1, bool outbound = false, String body = 'Habari', int? date, int threadId = 7, String address = '+255754210331', String status = 'received'}) =>
    ProviderMessage(providerId: id, kind: 'sms', threadId: threadId, addresses: [address], body: body, date: date ?? DateTime(2026, 10, 1).millisecondsSinceEpoch,
        outbound: outbound, read: true, status: status, subscriptionId: 1, parts: const []);

class FakePhone implements PhoneGateway {
  List<ProviderMessage> history = [];
  List<ThreadSummary> threadList = [];
  Map<String, String> names = {};
  final List<SendRequest> sent = [];
  final Set<String> started = {};
  final List<String> calls = [];
  bool defaultApp = true;

  @override
  Future<RoleStatus> roleStatus() async => RoleStatus(isDefaultSmsApp: defaultApp, roleAvailable: true);
  @override
  Future<List<PermissionState>> permissions() async => [PermissionState(name: 'READ_SMS', granted: true), PermissionState(name: 'SEND_SMS', granted: true)];
  @override
  Future<List<SimInfo>> sims() async => [SimInfo(subscriptionId: 1, slot: 0, carrier: 'Vodacom', countryIso: 'tz', isDefault: true)];
  @override
  Future<DeviceFacts> deviceFacts() async => DeviceFacts(manufacturer: 'samsung', model: 'A15', androidVersion: '14', sdkInt: 34, appVersion: '1.0.0', isEmulator: false, isRooted: false, debuggerAttached: false);
  @override
  Future<ServiceStatus> serviceStatus() async => ServiceStatus(running: true, batteryOptimised: false, networkAvailable: true, networkType: 'wifi', battery: 80, charging: false, signal: 3);
  @override
  Future<List<ThreadSummary>> threads(int limit, int offset) async => threadList;
  @override
  Future<List<ProviderMessage>> messages(int threadId, int limit, int? beforeDate) async => history.where((m) => m.threadId == threadId).toList();
  @override
  Future<List<ProviderMessage>> messagesSince(int sinceDate, int limit, int offset) async => history.where((m) => m.date >= sinceDate).skip(offset).take(limit).toList();
  @override
  Future<Uint8List> readMmsPart(String uri) async => Uint8List(0);
  @override
  Future<List<ContactInfo>> lookupContacts(List<String> addresses) async => [for (final a in addresses) ContactInfo(address: a, displayName: names[a])];
  @override
  Future<List<ContactInfo>> searchContacts(String query, int limit) async => const [];
  @override
  Future<SendResult> sendMessage(SendRequest request) async {
    // Mirrors the native at-most-once guard.
    if (!started.add(request.clientUuid)) return SendResult(clientUuid: request.clientUuid, state: 'duplicate');
    sent.add(request);
    return SendResult(clientUuid: request.clientUuid, state: 'sending', providerId: 900 + sent.length);
  }
  @override
  Future<void> markThreadRead(int threadId) async => calls.add('read:$threadId');
  @override
  Future<void> deleteMessage(String kind, int providerId) async => calls.add('delete:$providerId');
  @override
  Future<void> deleteThread(int threadId) async => calls.add('delete-thread:$threadId');
  @override
  Future<void> blockNumber(String address) async => calls.add('block:$address');
  @override
  Future<void> unblockNumber(String address) async => calls.add('unblock:$address');
  @override
  Future<List<String>> blockedNumbers() async => const [];
}
