import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';

part 'database.g.dart';

/// Durable outbox of events for the server. The native call code appends rows here (same SQLCipher file) in the same
/// code path that records the call, so nothing is lost if the process dies before an upload.
@DataClassName('SyncEventRow')
class SyncEvents extends Table {
  @override
  String get tableName => 'sync_events';
  IntColumn get seq => integer().autoIncrement()();
  TextColumn get type => text()();
  TextColumn get payload => text()();
  IntColumn get createdAt => integer().named('created_at')();
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

@DriftDatabase(tables: [SyncEvents, KeyValues])
class AppDatabase extends _$AppDatabase {
  AppDatabase(super.e);

  /// Opens the SQLCipher database with the raw 256-bit key from the native layer (random, wrapped by the Keystore):
  /// `PRAGMA key = "x'…'"` skips PBKDF2, which cost hundreds of milliseconds on every open. The native side migrated
  /// 1.0.x databases (passphrase format) before handing the key out (DatabaseKey.ensureRawKey).
  factory AppDatabase.open({required String path, required String hexKey}) {
    if (!RegExp(r'^[0-9a-f]{64}$').hasMatch(hexKey)) throw ArgumentError('not a raw key');
    return AppDatabase(NativeDatabase.createInBackground(File(path), setup: (db) {
      db.execute('PRAGMA key = "x\'$hexKey\'"');
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
  int get schemaVersion => 3;

  /// Tables schema 1 and 2 carried over from OCM Messages. OCM Phone never sends or stores SMS.
  static const _smsTables = ['outbound_states', 'conversation_prefs', 'starred_messages', 'drafts', 'scheduled_sends', 'pending_media', 'thread_cache', 'message_cache'];

  @override
  MigrationStrategy get migration => MigrationStrategy(
        onUpgrade: (m, from, to) async {
          if (from < 3) {
            for (final table in _smsTables) {
              await customStatement('DROP TABLE IF EXISTS "$table"');
            }
          }
        },
      );

  // --- Outbox ------------------------------------------------------------------------------------------------

  Future<int> appendEvent(String type, String payload) =>
      into(syncEvents).insert(SyncEventsCompanion.insert(type: type, payload: payload, createdAt: DateTime.now().millisecondsSinceEpoch));

  Future<List<SyncEventRow>> pendingEvents({int limit = 200}) => (select(syncEvents)..orderBy([(t) => OrderingTerm.asc(t.seq)])..limit(limit)).get();

  Future<int> pendingCount() async => (await customSelect('SELECT count(*) AS c FROM sync_events').getSingle()).read<int>('c');

  Future<void> acknowledge(int upTo) => (delete(syncEvents)..where((t) => t.seq.isSmallerOrEqualValue(upTo))).go();

  // --- Key/value ---------------------------------------------------------------------------------------------

  Future<Map<String, String>> allValues() async => {for (final row in await select(keyValues).get()) row.key: row.value};

  Future<String?> getValue(String key) async => (await (select(keyValues)..where((t) => t.key.equals(key))).getSingleOrNull())?.value;

  Future<void> setValue(String key, String? value) async {
    if (value == null) {
      await (delete(keyValues)..where((t) => t.key.equals(key))).go();
    } else {
      await into(keyValues).insertOnConflictUpdate(KeyValuesCompanion.insert(key: key, value: value));
    }
  }
}
