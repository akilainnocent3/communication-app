import 'dart:typed_data';

import '../platform/telephony_api.g.dart';

/// Everything the UI needs from the phone itself. The platform implementation talks to the native Kotlin layer through
/// Pigeon (all provider work runs on Dispatchers.IO there); tests use a fake. Syncing with the server is native too.
abstract class PhoneGateway {
  Future<RoleStatus> roleStatus();
  Future<List<PermissionState>> permissions();
  Future<List<SimInfo>> sims();
  Future<DeviceFacts> deviceFacts();
  Future<ServiceStatus> serviceStatus();
  Future<List<ThreadSummary>> threads(int limit, int offset);
  Future<ThreadSummary?> thread(int threadId);
  Future<List<ProviderMessage>> messages(int threadId, int limit, int? beforeDate);
  Future<List<ProviderMessage>> searchMessages(String query, int limit, int offset);
  Future<Uint8List?> thumbnail(String uri, int maxPx);
  Future<List<ContactInfo>> lookupContacts(List<String> addresses);
  Future<List<ContactInfo>> searchContacts(String query, int limit);
  Future<SendResult> sendMessage(SendRequest request);
  Future<void> markThreadRead(int threadId);
  Future<void> deleteMessage(String kind, int providerId);
  Future<void> deleteThread(int threadId);
  Future<void> blockNumber(String address);
  Future<void> unblockNumber(String address);
  Future<List<String>> blockedNumbers();
  Future<void> syncNow();
}

class PlatformPhoneGateway implements PhoneGateway {
  PlatformPhoneGateway(this.api);
  final TelephonyHostApi api;

  @override
  Future<RoleStatus> roleStatus() => api.roleStatus();
  @override
  Future<List<PermissionState>> permissions() => api.permissions();
  @override
  Future<List<SimInfo>> sims() => api.sims();
  @override
  Future<DeviceFacts> deviceFacts() => api.deviceFacts();
  @override
  Future<ServiceStatus> serviceStatus() => api.serviceStatus();
  @override
  Future<List<ThreadSummary>> threads(int limit, int offset) => api.threads(limit, offset);
  @override
  Future<ThreadSummary?> thread(int threadId) => api.thread(threadId);
  @override
  Future<List<ProviderMessage>> messages(int threadId, int limit, int? beforeDate) => api.messages(threadId, limit, beforeDate);
  @override
  Future<List<ProviderMessage>> searchMessages(String query, int limit, int offset) => api.searchMessages(query, limit, offset);
  @override
  Future<Uint8List?> thumbnail(String uri, int maxPx) => api.thumbnail(uri, maxPx);
  @override
  Future<List<ContactInfo>> lookupContacts(List<String> addresses) => api.lookupContacts(addresses);
  @override
  Future<List<ContactInfo>> searchContacts(String query, int limit) => api.searchContacts(query, limit);
  @override
  Future<SendResult> sendMessage(SendRequest request) => api.sendMessage(request);
  @override
  Future<void> markThreadRead(int threadId) => api.markThreadRead(threadId);
  @override
  Future<void> deleteMessage(String kind, int providerId) => api.deleteMessage(kind, providerId);
  @override
  Future<void> deleteThread(int threadId) => api.deleteThread(threadId);
  @override
  Future<void> blockNumber(String address) => api.blockNumber(address);
  @override
  Future<void> unblockNumber(String address) => api.unblockNumber(address);
  @override
  Future<List<String>> blockedNumbers() => api.blockedNumbers();
  @override
  Future<void> syncNow() => api.syncNow();
}

/// ProviderMessage ⇄ JSON for the encrypted message cache.
Map<String, Object?> messageToJson(ProviderMessage m) => {
      'id': m.providerId, 'kind': m.kind, 'thread': m.threadId, 'addresses': m.addresses, 'body': m.body, 'date': m.date, 'out': m.outbound,
      'read': m.read, 'status': m.status, 'sub': m.subscriptionId, 'error': m.errorCode, 'subject': m.subject,
      'parts': [for (final p in m.parts) {'seq': p.seq, 'type': p.contentType, 'name': p.filename, 'size': p.size, 'uri': p.uri}],
    };

ProviderMessage messageFromJson(Map<String, dynamic> j) => ProviderMessage(
      providerId: j['id'] as int, kind: j['kind'] as String, threadId: j['thread'] as int, addresses: (j['addresses'] as List).cast<String>(),
      body: j['body'] as String, date: j['date'] as int, outbound: j['out'] as bool, read: j['read'] as bool, status: j['status'] as String,
      subscriptionId: j['sub'] as int?, errorCode: j['error'] as int?, subject: j['subject'] as String?,
      parts: [
        for (final p in (j['parts'] as List).cast<Map<String, dynamic>>())
          MmsPartData(seq: p['seq'] as int, contentType: p['type'] as String, filename: p['name'] as String?, size: p['size'] as int, uri: p['uri'] as String?),
      ],
    );
