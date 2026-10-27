import 'dart:convert';
import 'dart:developer' as developer;
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:drift/drift.dart';

import '../../data/phone_gateway.dart';
import '../../platform/telephony_api.g.dart';
import '../api/device_api.dart';
import '../api/errors.dart';
import '../db/database.dart';

const maxBatchEvents = 200;
const maxBatchBytes = 900 * 1024; // under the server's 1 MB limit
const chunkSize = 256 * 1024;
const heartbeatEvery = Duration(minutes: 5);
const staleSendAfter = Duration(minutes: 10);
const requiredPermissions = ['RECEIVE_SMS', 'READ_SMS', 'SEND_SMS', 'RECEIVE_MMS', 'READ_CONTACTS', 'READ_PHONE_STATE', 'POST_NOTIFICATIONS'];

enum SyncResult { ok, offline, suspended, revoked, upgradeRequired, notEnrolled }

void _log(String message) => developer.log(message, name: 'cm.sync'); // ids and counts only, never content

/// One sync cycle: heartbeat (when due) → backfill (once) → upload events → upload media → outbox → status reports.
/// Safe to run from the UI, the foreground service, WorkManager or an FCM wake-up; every step is idempotent.
class SyncEngine {
  SyncEngine({required this.db, required this.api, required this.phone, required this.appVersion, DateTime Function()? clock}) : _clock = clock ?? DateTime.now;

  final AppDatabase db;
  final DeviceApi api;
  final PhoneGateway phone;
  final String appVersion;
  final DateTime Function() _clock;
  bool _running = false;

  Future<SyncResult> runOnce({bool forceHeartbeat = false}) async {
    if (_running) return SyncResult.ok;
    _running = true;
    try {
      await _heartbeatIfDue(force: forceHeartbeat);
      await backfillIfNeeded();
      await uploadEvents();
      await uploadMedia();
      await sendScheduled();
      await processOutbox();
      await reportStatuses();
      await db.setValue('last_sync_at', '${_clock().millisecondsSinceEpoch}');
      return SyncResult.ok;
    } on DeviceRevoked {
      return SyncResult.revoked;
    } on DeviceSuspended {
      return SyncResult.suspended;
    } on UpgradeRequired {
      return SyncResult.upgradeRequired;
    } on ApiException catch (error) {
      if (error.code == 'not_enrolled') return SyncResult.notEnrolled;
      _log('sync failed: ${error.status} ${error.code}');
      return SyncResult.offline;
    } finally {
      _running = false;
    }
  }

  // --- Heartbeat ---------------------------------------------------------------------------------------------

  Future<void> _heartbeatIfDue({bool force = false}) async {
    final last = int.tryParse(await db.getValue('last_heartbeat_at') ?? '') ?? 0;
    if (!force && _clock().millisecondsSinceEpoch - last < heartbeatEvery.inMilliseconds) return;
    await heartbeat();
  }

  Future<Map<String, dynamic>> heartbeat() async {
    final role = await phone.roleStatus();
    final permissions = await phone.permissions();
    final status = await phone.serviceStatus();
    final sims = await phone.sims();
    final facts = await phone.deviceFacts();
    final lastSync = int.tryParse(await db.getValue('last_sync_at') ?? '');
    final response = await api.heartbeat({
      'battery': status.battery, 'charging': status.charging, 'network_type': status.networkType, 'signal': status.signal,
      'is_default_sms_app': role.isDefaultSmsApp, 'permissions': {for (final p in permissions) p.name: p.granted},
      'battery_optimised': status.batteryOptimised, 'pending_outbox': await db.pendingCount(), 'app_version': appVersion,
      'android_version': facts.androidVersion, if (lastSync != null) 'last_sync_at': DateTime.fromMillisecondsSinceEpoch(lastSync).toUtc().toIso8601String(),
      'risk_signals': {'rooted': facts.isRooted, 'emulator': facts.isEmulator, 'debugger': facts.debuggerAttached},
      'sims': [for (final sim in sims) simPayload(sim)],
    });
    await db.setValue('last_heartbeat_at', '${_clock().millisecondsSinceEpoch}');
    return response;
  }

  static Map<String, dynamic> simPayload(SimInfo sim) =>
      {'subscription_id': sim.subscriptionId, 'slot': sim.slot, 'carrier': sim.carrier, 'country_iso': sim.countryIso, 'number': sim.number ?? '', 'is_default': sim.isDefault};

  // --- Backfill ----------------------------------------------------------------------------------------------

  /// Copies the message history inside the backfill window once (newest first), as ordinary upsert events.
  Future<void> backfillIfNeeded() async {
    if (await db.getValue('backfill_done') == '1') return;
    final days = int.tryParse(await db.getValue('backfill_days') ?? '') ?? 90;
    final since = _clock().subtract(Duration(days: days)).millisecondsSinceEpoch;
    var offset = int.tryParse(await db.getValue('backfill_offset') ?? '') ?? 0;
    final addresses = <String>{};
    while (true) {
      final page = await phone.messagesSince(since, 200, offset);
      if (page.isEmpty) break;
      for (final message in page) {
        addresses.addAll(message.addresses);
        await db.appendEvent('message.upsert', jsonEncode(messagePayload(message)));
        await _queueParts(message);
      }
      offset += page.length;
      await db.setValue('backfill_offset', '$offset');
      await db.appendEvent('backfill.progress', jsonEncode({'phase': 'running', 'done': offset, 'total': offset + (page.length == 200 ? 200 : 0)}));
      if (page.length < 200) break;
    }
    // Names only for numbers that appear in conversations (data minimisation), never the whole address book.
    final contacts = await phone.lookupContacts(addresses.toList());
    for (final contact in contacts.where((c) => (c.displayName ?? '').isNotEmpty)) {
      await db.appendEvent('contact.upsert', jsonEncode({'address': contact.address, 'display_name': contact.displayName, 'photo_hash': ''}));
    }
    for (final number in await phone.blockedNumbers()) {
      await db.appendEvent('block.add', jsonEncode({'address': number}));
    }
    await db.appendEvent('backfill.progress', jsonEncode({'phase': 'done', 'done': offset, 'total': offset}));
    await db.setValue('backfill_done', '1');
    await db.setValue('backfill_offset', null);
    _log('backfill queued $offset messages');
  }

  Future<void> _queueParts(ProviderMessage message) async {
    if (message.kind != 'mms') return;
    for (final part in message.parts.where((p) => p.uri != null)) {
      await db.into(db.pendingMedia).insertOnConflictUpdate(PendingMediaCompanion.insert(
        providerId: message.providerId, date: message.date, seq: part.seq, uri: part.uri!, size: part.size,
      ));
    }
  }

  // --- Upload ------------------------------------------------------------------------------------------------

  /// Uploads the durable outbox in batches (≤ 200 events, < 1 MB) and deletes what the server acknowledged.
  Future<int> uploadEvents() async {
    var uploaded = 0;
    while (true) {
      final rows = await db.pendingEvents(limit: maxBatchEvents);
      if (rows.isEmpty) return uploaded;
      final batch = <Map<String, dynamic>>[];
      var bytes = 0;
      for (final row in rows) {
        bytes += row.payload.length + 64;
        if (batch.isNotEmpty && bytes > maxBatchBytes) break;
        batch.add({'seq': row.seq, 'type': row.type, 'payload': jsonDecode(row.payload)});
      }
      final result = await api.syncEvents(batch);
      final acked = (result['acked_seq'] as num).toInt();
      final rejected = (result['rejected'] as List?) ?? const [];
      if (rejected.isNotEmpty) _log('server rejected ${rejected.length} events');
      await db.acknowledge(acked);
      uploaded += batch.length;
      if (acked < batch.last['seq']) return uploaded; // the server is behind; try again next cycle
    }
  }

  Future<void> uploadMedia() async {
    final parts = await db.select(db.pendingMedia).get();
    for (final part in parts) {
      final data = await phone.readMmsPart(part.uri);
      var offset = part.offset;
      while (offset < data.length) {
        final end = min(offset + chunkSize, data.length);
        try {
          final result = await api.uploadChunk(providerId: part.providerId, date: part.date, seq: part.seq, offset: offset, chunk: Uint8List.sublistView(data, offset, end));
          offset = (result['received_bytes'] as num).toInt();
          if (result['complete'] == true) break;
        } on ApiException catch (error) {
          if (error.code == 'offset_mismatch' || error.code == 'checksum_mismatch') {
            offset = 0; // the server tells us where to resume; restart cleanly
            if (error.code == 'checksum_mismatch') break;
            continue;
          }
          if (error.status == 404) break; // not declared yet: the event upload will come first next time
          rethrow;
        }
        await (db.update(db.pendingMedia)..where((t) => t.providerId.equals(part.providerId) & t.date.equals(part.date) & t.seq.equals(part.seq)))
            .write(PendingMediaCompanion(offset: Value(offset)));
      }
      if (offset >= data.length) {
        await (db.delete(db.pendingMedia)..where((t) => t.providerId.equals(part.providerId) & t.date.equals(part.date) & t.seq.equals(part.seq))).go();
      }
    }
  }

  // --- Outbox: admin replies ---------------------------------------------------------------------------------

  /// Claims due admin messages and sends each exactly once. The native sender records `sending` durably before it
  /// calls SmsManager and refuses a client_uuid it has already started, so a crash can never cause a duplicate.
  Future<int> processOutbox() async {
    await db.markStaleSendsUnknown(_clock().subtract(staleSendAfter));
    final claim = await api.claimOutbox();
    final acks = <Map<String, dynamic>>[];
    for (final command in (claim['commands'] as List).cast<Map<String, dynamic>>()) {
      acks.add({'id': command['id'], 'ok': await _runCommand(command['kind'] as String, (command['payload'] as Map).cast<String, dynamic>())});
    }
    var sent = 0;
    for (final item in (claim['messages'] as List).cast<Map<String, dynamic>>()) {
      final clientUuid = item['client_uuid'] as String;
      if (await db.outbound(clientUuid) != null) continue; // already started: its state is reported below
      final expires = DateTime.tryParse(item['expires_at'] as String? ?? '');
      if (expires != null && _clock().isAfter(expires)) {
        await db.into(db.outboundStates).insertOnConflictUpdate(OutboundStatesCompanion.insert(
          clientUuid: clientUuid, state: 'failed', errorCode: const Value(1003), updatedAt: _clock().millisecondsSinceEpoch,
        ));
        continue;
      }
      final result = await phone.sendMessage(SendRequest(
        clientUuid: clientUuid, addresses: (item['addresses'] as List).cast<String>(), body: item['body'] as String,
        subscriptionId: item['subscription_id'] as int?, deliveryReport: true, attachmentUris: const [], origin: 'admin', sentBy: item['sent_by'] as String?,
      ));
      if (result.state == 'sending') sent++;
    }
    if (acks.isNotEmpty) await api.reportStatus(commandAcks: acks);
    return sent;
  }

  Future<bool> _runCommand(String kind, Map<String, dynamic> payload) async {
    try {
      switch (kind) {
        case 'mark_read':
          await phone.markThreadRead(payload['thread_id'] as int);
        case 'block':
          await phone.blockNumber(payload['address'] as String);
        case 'unblock':
          await phone.unblockNumber(payload['address'] as String);
        case 'resync':
          await db.setValue('backfill_done', null);
          if (payload['days'] != null) await db.setValue('backfill_days', '${payload['days']}');
        default:
          return false;
      }
      return true;
    } on Exception {
      return false;
    }
  }

  /// Sends every state change the server has not seen yet (sending → sent → delivered, failed, unknown).
  Future<void> reportStatuses() async {
    final rows = await db.unreportedOutbound();
    if (rows.isEmpty) return;
    final reports = [
      for (final row in rows)
        {'client_uuid': row.clientUuid, 'status': row.state, 'at': row.updatedAt, if (row.errorCode != null) 'error_code': row.errorCode, if (row.parts != null) 'parts': row.parts},
    ];
    final result = await api.reportStatus(reports: reports);
    final byUuid = {for (final row in rows) row.clientUuid: row};
    for (final item in (result['results'] as List).cast<Map<String, dynamic>>()) {
      // ok, ignored (the server already knows better) or unknown_message: none of them is worth sending again.
      final row = byUuid[item['client_uuid']];
      if (row != null) await db.markReported(row.clientUuid, row.state);
    }
  }

  // --- Phone-side scheduled sends ----------------------------------------------------------------------------

  Future<void> sendScheduled() async {
    final due = await (db.select(db.scheduledSends)..where((t) => t.sendAt.isSmallerOrEqualValue(_clock().millisecondsSinceEpoch))).get();
    for (final item in due) {
      await phone.sendMessage(SendRequest(
        clientUuid: item.clientUuid, addresses: (jsonDecode(item.addresses) as List).cast<String>(), body: item.body, subscriptionId: item.subscriptionId,
        deliveryReport: true, attachmentUris: const [], origin: 'phone',
      ));
      await (db.delete(db.scheduledSends)..where((t) => t.clientUuid.equals(item.clientUuid))).go();
    }
  }
}

/// A stable id for local data (never sent anywhere): sha256 of a value, hex.
String localHash(String value) => sha256.convert(utf8.encode(value)).toString();
