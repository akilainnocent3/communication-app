import 'dart:typed_data';

import '../platform/telephony_api.g.dart';

/// Everything the app needs from the phone itself. The platform implementation talks to the native Kotlin layer
/// through Pigeon; tests use a fake. Repositories and the sync engine are the only users.
abstract class PhoneGateway {
  Future<RoleStatus> roleStatus();
  Future<List<PermissionState>> permissions();
  Future<List<SimInfo>> sims();
  Future<DeviceFacts> deviceFacts();
  Future<ServiceStatus> serviceStatus();
  Future<List<ThreadSummary>> threads(int limit, int offset);
  Future<List<ProviderMessage>> messages(int threadId, int limit, int? beforeDate);
  Future<List<ProviderMessage>> messagesSince(int sinceDate, int limit, int offset);
  Future<Uint8List> readMmsPart(String uri);
  Future<List<ContactInfo>> lookupContacts(List<String> addresses);
  Future<List<ContactInfo>> searchContacts(String query, int limit);
  Future<SendResult> sendMessage(SendRequest request);
  Future<void> markThreadRead(int threadId);
  Future<void> deleteMessage(String kind, int providerId);
  Future<void> deleteThread(int threadId);
  Future<void> blockNumber(String address);
  Future<void> unblockNumber(String address);
  Future<List<String>> blockedNumbers();
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
  Future<List<ProviderMessage>> messages(int threadId, int limit, int? beforeDate) => api.messages(threadId, limit, beforeDate);
  @override
  Future<List<ProviderMessage>> messagesSince(int sinceDate, int limit, int offset) => api.messagesSince(sinceDate, limit, offset);
  @override
  Future<Uint8List> readMmsPart(String uri) => api.readMmsPart(uri);
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
}

/// The server event payload for a provider message (same shape the native receivers write).
Map<String, dynamic> messagePayload(ProviderMessage m) => {
      'kind': m.kind, 'provider_id': m.providerId, 'date': m.date, 'thread_id': m.threadId, 'addresses': m.addresses, 'direction': m.outbound ? 'out' : 'in',
      'body': m.body, 'subject': m.subject ?? '', 'is_read': m.read, 'status': m.status, 'sub_id': m.subscriptionId, 'error_code': m.errorCode,
      if (m.kind == 'mms') 'parts': [for (final p in m.parts) {'seq': p.seq, 'content_type': p.contentType, 'filename': p.filename ?? '', 'size': p.size}],
    };
