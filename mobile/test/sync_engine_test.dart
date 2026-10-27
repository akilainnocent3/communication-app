import 'dart:convert';

import 'package:cm_sms/core/api/device_api.dart';
import 'package:cm_sms/core/db/database.dart';
import 'package:cm_sms/core/sync/backoff.dart';
import 'package:cm_sms/core/sync/sync_engine.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

/// A tiny in-memory server for the device API.
class FakeServer {
  int ackedSeq = 0;
  final List<Map<String, dynamic>> events = [];
  List<Map<String, dynamic>> claimable = [];
  List<Map<String, dynamic>> commands = [];
  final List<Map<String, dynamic>> reports = [];
  final List<Map<String, dynamic>> acks = [];
  int heartbeats = 0;
  bool offline = false;
  bool revoked = false;

  (int, Object?) handle(String method, Uri url, Map<String, String> headers, Object? body) {
    if (offline) return (0, null);
    if (url.path == tokenPath) return revoked ? (401, {'code': 'device_revoked'}) : (200, {'access_token': 't', 'expires_in': 900});
    final path = url.path.replaceFirst('/api/v1/device/', '');
    final data = (body as Map?)?.cast<String, dynamic>() ?? const {};
    switch (path) {
      case 'heartbeat/':
        heartbeats++;
        return (200, {'status': 'active', 'attention': [], 'server_time': 0, 'poll_seconds': 20});
      case 'sync/events/':
        final batch = (data['events'] as List).cast<Map<String, dynamic>>();
        for (final event in batch) {
          if ((event['seq'] as int) > ackedSeq) events.add(event);
        }
        ackedSeq = batch.map((e) => e['seq'] as int).fold(ackedSeq, (a, b) => a > b ? a : b);
        return (200, {'acked_seq': ackedSeq, 'processed': batch.length, 'skipped': 0, 'rejected': []});
      case 'outbox/claim/':
        final result = {'messages': claimable, 'commands': commands, 'lease_seconds': 120};
        commands = [];
        return (200, result);
      case 'outbox/status/':
        reports.addAll((data['reports'] as List).cast<Map<String, dynamic>>());
        acks.addAll((data['command_acks'] as List).cast<Map<String, dynamic>>());
        return (200, {'results': [for (final r in (data['reports'] as List)) {'client_uuid': r['client_uuid'], 'result': 'ok'}]});
    }
    return (404, {'code': 'not_found'});
  }
}

void main() {
  late AppDatabase db;
  late FakeServer server;
  late FakePhone phone;
  late SyncEngine engine;
  final now = DateTime(2026, 10, 27, 12);

  setUp(() {
    db = AppDatabase.memory();
    server = FakeServer();
    phone = FakePhone();
    final api = DeviceApi(transport: FakeTransport(server.handle), server: Uri.parse('https://sms.company.co.tz'), signer: FakeSigner(), appVersion: '1.0.0', deviceId: 'dev', clock: () => now);
    engine = SyncEngine(db: db, api: api, phone: phone, appVersion: '1.0.0', clock: () => now);
  });
  tearDown(() => db.close());

  test('backfill turns history into upsert, contact and progress events, once', () async {
    phone.history = [providerMessage(id: 1, date: now.subtract(const Duration(days: 2)).millisecondsSinceEpoch), providerMessage(id: 2, date: now.subtract(const Duration(days: 400)).millisecondsSinceEpoch)];
    phone.names = {'+255754210331': 'Neema Mushi'};
    expect(await engine.runOnce(), SyncResult.ok);
    final types = server.events.map((e) => e['type']).toList();
    expect(types.where((t) => t == 'message.upsert').length, 1); // outside the 90-day window is skipped
    expect(types, contains('contact.upsert'));
    expect(types.last, 'backfill.progress');
    expect(await db.pendingCount(), 0); // acknowledged events are deleted
    server.events.clear();
    await engine.runOnce();
    expect(server.events, isEmpty);
    expect(server.heartbeats, 1); // heartbeats only every 5 minutes
  });

  test('the durable outbox survives being offline and uploads in order later', () async {
    await db.setValue('backfill_done', '1');
    await db.appendEvent('message.upsert', jsonEncode({'provider_id': 1}));
    await db.appendEvent('message.read', jsonEncode({'provider_id': 1}));
    server.offline = true;
    expect(await engine.runOnce(), SyncResult.offline);
    expect(await db.pendingCount(), 2);
    server.offline = false;
    expect(await engine.runOnce(), SyncResult.ok);
    expect(server.events.map((e) => e['seq']), [1, 2]);
    expect(await db.pendingCount(), 0);
  });

  test('admin messages are sent at most once and their states reported', () async {
    await db.setValue('backfill_done', '1');
    server.claimable = [
      {'client_uuid': 'u-1', 'kind': 'sms', 'addresses': ['+255754210331'], 'body': 'Karibu', 'subscription_id': 1, 'sent_by': 'Amina', 'expires_at': now.add(const Duration(hours: 1)).toIso8601String()},
    ];
    await engine.runOnce();
    expect(phone.sent.single.clientUuid, 'u-1');
    expect(phone.sent.single.origin, 'admin');
    // The lease expired and the server offers it again: the phone never sends a started message twice.
    await db.into(db.outboundStates).insert(OutboundStatesCompanion.insert(clientUuid: 'u-1', state: 'sending', updatedAt: now.millisecondsSinceEpoch));
    await engine.runOnce();
    expect(phone.sent, hasLength(1));
    expect(server.reports.single['status'], 'sending');
    // The native receiver records "sent": reported once.
    await db.customStatement("UPDATE outbound_states SET state = 'sent', parts = 1 WHERE client_uuid = 'u-1'");
    await engine.runOnce();
    await engine.runOnce();
    expect(server.reports.map((r) => r['status']), ['sending', 'sent']);
  });

  test('a send that never got a result becomes unknown; expired messages are not sent', () async {
    await db.setValue('backfill_done', '1');
    await db.into(db.outboundStates).insert(OutboundStatesCompanion.insert(clientUuid: 'old', state: 'sending', updatedAt: now.subtract(const Duration(hours: 1)).millisecondsSinceEpoch));
    server.claimable = [{'client_uuid': 'late', 'kind': 'sms', 'addresses': ['+255754210331'], 'body': 'x', 'expires_at': now.subtract(const Duration(minutes: 1)).toIso8601String()}];
    await engine.runOnce();
    expect(phone.sent, isEmpty);
    final byUuid = {for (final r in server.reports) r['client_uuid']: r};
    expect(byUuid['old']!['status'], 'unknown');
    expect(byUuid['late']!['status'], 'failed');
    expect(byUuid['late']!['error_code'], 1003);
  });

  test('commands from the admin run and are acknowledged', () async {
    await db.setValue('backfill_done', '1');
    server.commands = [{'id': 5, 'kind': 'mark_read', 'payload': {'thread_id': 7}}, {'id': 6, 'kind': 'block', 'payload': {'address': '+255700111222'}}, {'id': 7, 'kind': 'nonsense', 'payload': {}}];
    await engine.runOnce();
    expect(phone.calls, ['read:7', 'block:+255700111222']);
    expect(server.acks.map((a) => a['ok']), [true, true, false]);
  });

  test('a revoked phone stops syncing', () async {
    server.revoked = true;
    expect(await engine.runOnce(forceHeartbeat: true), SyncResult.revoked);
  });

  test('backoff grows with jitter and never spins', () {
    final backoff = Backoff();
    final waits = [for (var i = 0; i < 12; i++) backoff.next()];
    expect(waits.every((w) => w >= const Duration(seconds: 2) && w <= const Duration(minutes: 5)), isTrue);
    backoff.reset();
    expect(backoff.failures, 0);
  });
}
