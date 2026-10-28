import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';

part 'database.g.dart';

/// Durable outbox of events for the server. The native receivers append rows here (same SQLCipher file) in the same
/// code path that writes the Telephony provider, so nothing is lost if the process dies before an upload.
@DataClassName('SyncEventRow')
class SyncEvents extends Table {
  @override
  String get tableName => 'sync_events';
  IntColumn get seq => integer().autoIncrement()();
  TextColumn get type => text()();
  TextColumn get payload => text()();
  IntColumn get createdAt => integer().named('created_at')();
}

/// At-most-once record of every admin message this phone started sending. Written natively before SmsManager is
/// called; `reported_state` is what the server already knows.
@DataClassName('OutboundStateRow')
class OutboundStates extends Table {
  @override
  String get tableName => 'outbound_states';
  TextColumn get clientUuid => text().named('client_uuid')();
  TextColumn get state => text()();
  IntColumn get providerId => integer().named('provider_id').nullable()();
  IntColumn get errorCode => integer().named('error_code').nullable()();
  IntColumn get parts => integer().nullable()();
  IntColumn get updatedAt => integer().named('updated_at')();
  TextColumn get reportedState => text().named('reported_state').nullable()();
  TextColumn get sentBy => text().named('sent_by').nullable()();
  @override
  Set<Column> get primaryKey => {clientUuid};
}

/// App-level conversation state the Telephony provider has no column for.
@DataClassName('ConversationPrefRow')
class ConversationPrefs extends Table {
  @override
  String get tableName => 'conversation_prefs';
  IntColumn get threadId => integer().named('thread_id')();
  BoolColumn get pinned => boolean().withDefault(const Constant(false))();
  BoolColumn get archived => boolean().withDefault(const Constant(false))();
  BoolColumn get muted => boolean().withDefault(const Constant(false))();
  BoolColumn get spam => boolean().withDefault(const Constant(false))();
  @override
  Set<Column> get primaryKey => {threadId};
}

@DataClassName('StarredRow')
class StarredMessages extends Table {
  @override
  String get tableName => 'starred_messages';
  TextColumn get kind => text()();
  IntColumn get providerId => integer().named('provider_id')();
  @override
  Set<Column> get primaryKey => {kind, providerId};
}

@DataClassName('DraftRow')
class Drafts extends Table {
  @override
  String get tableName => 'drafts';
  TextColumn get key => text()();
  TextColumn get body => text()();
  IntColumn get updatedAt => integer().named('updated_at')();
  @override
  Set<Column> get primaryKey => {key};
}

/// Messages scheduled on the phone (sent by the sync loop when due).
@DataClassName('ScheduledRow')
class ScheduledSends extends Table {
  @override
  String get tableName => 'scheduled_sends';
  TextColumn get clientUuid => text().named('client_uuid')();
  TextColumn get addresses => text()();
  TextColumn get body => text()();
  IntColumn get subscriptionId => integer().named('subscription_id').nullable()();
  IntColumn get sendAt => integer().named('send_at')();
  @override
  Set<Column> get primaryKey => {clientUuid};
}

/// MMS parts still to upload (declared in a message.upsert event first). Written natively when an MMS arrives.
@DataClassName('PendingMediaRow')
class PendingMedia extends Table {
  @override
  String get tableName => 'pending_media';
  IntColumn get providerId => integer().named('provider_id')();
  IntColumn get date => integer()();
  IntColumn get seq => integer()();
  TextColumn get uri => text()();
  IntColumn get size => integer()();
  IntColumn get offset => integer().withDefault(const Constant(0))();
  @override
  Set<Column> get primaryKey => {providerId, date, seq};
}

@DataClassName('KvRow')
class KeyValues extends Table {
  @override
  String get tableName => 'kv';
  TextColumn get key => text()();
  TextColumn get value => text()();
  @override
  Set<Column> get primaryKey => {key};
}

@DriftDatabase(tables: [SyncEvents, OutboundStates, ConversationPrefs, StarredMessages, Drafts, ScheduledSends, PendingMedia, KeyValues])
class AppDatabase extends _$AppDatabase {
  AppDatabase(super.e);

  /// Opens the SQLCipher database. The passphrase comes from the native layer (random, wrapped by the Keystore).
  factory AppDatabase.open({required String path, required String passphrase}) {
    final escaped = passphrase.replaceAll("'", "''");
    return AppDatabase(NativeDatabase.createInBackground(File(path), setup: (db) {
      db.execute("PRAGMA key = '$escaped'");
      // busy_timeout before journal_mode: the UI engine, the sync service's engine and the native receivers open this
      // file at the same moment after an install, update or boot, and switching to WAL needs a lock. Set the other
      // way round, the switch failed at once with "database is locked" and the app could not start.
      db.execute('PRAGMA busy_timeout = 5000');
      db.execute('PRAGMA journal_mode = WAL');
      // Fail fast on a wrong key instead of later, mid-sync.
      db.select('SELECT count(*) FROM sqlite_master');
    }));
  }

  factory AppDatabase.memory() => AppDatabase(NativeDatabase.memory());

  @override
  int get schemaVersion => 1;

  // --- Outbox ------------------------------------------------------------------------------------------------

  Future<int> appendEvent(String type, String payload) =>
      into(syncEvents).insert(SyncEventsCompanion.insert(type: type, payload: payload, createdAt: DateTime.now().millisecondsSinceEpoch));

  Future<List<SyncEventRow>> pendingEvents({int limit = 200}) => (select(syncEvents)..orderBy([(t) => OrderingTerm.asc(t.seq)])..limit(limit)).get();

  Future<int> pendingCount() async => (await customSelect('SELECT count(*) AS c FROM sync_events').getSingle()).read<int>('c');

  Future<void> acknowledge(int upTo) => (delete(syncEvents)..where((t) => t.seq.isSmallerOrEqualValue(upTo))).go();

  // --- Outbound ----------------------------------------------------------------------------------------------

  Future<OutboundStateRow?> outbound(String clientUuid) => (select(outboundStates)..where((t) => t.clientUuid.equals(clientUuid))).getSingleOrNull();

  Future<List<OutboundStateRow>> unreportedOutbound() =>
      (select(outboundStates)..where((t) => t.reportedState.isNull() | t.reportedState.equalsExp(t.state).not())).get();

  Future<void> markReported(String clientUuid, String state) =>
      (update(outboundStates)..where((t) => t.clientUuid.equals(clientUuid))).write(OutboundStatesCompanion(reportedState: Value(state)));

  /// A send the phone started but never got a result for (the process died mid-send): mark it unknown.
  Future<int> markStaleSendsUnknown(DateTime olderThan) => (update(outboundStates)
        ..where((t) => t.state.equals('sending') & t.updatedAt.isSmallerThanValue(olderThan.millisecondsSinceEpoch)))
      .write(OutboundStatesCompanion(state: const Value('unknown'), updatedAt: Value(DateTime.now().millisecondsSinceEpoch)));

  // --- Key/value ---------------------------------------------------------------------------------------------

  Future<String?> getValue(String key) async => (await (select(keyValues)..where((t) => t.key.equals(key))).getSingleOrNull())?.value;

  Future<void> setValue(String key, String? value) async {
    if (value == null) {
      await (delete(keyValues)..where((t) => t.key.equals(key))).go();
    } else {
      await into(keyValues).insertOnConflictUpdate(KeyValuesCompanion.insert(key: key, value: value));
    }
  }

  // --- Conversation preferences ------------------------------------------------------------------------------

  Future<Map<int, ConversationPrefRow>> prefsFor(Iterable<int> threadIds) async {
    final rows = await (select(conversationPrefs)..where((t) => t.threadId.isIn(threadIds.toList()))).get();
    return {for (final row in rows) row.threadId: row};
  }

  Future<void> updatePref(int threadId, ConversationPrefsCompanion change) =>
      into(conversationPrefs).insert(change.copyWith(threadId: Value(threadId)), onConflict: DoUpdate((_) => change));
}
