import 'dart:io';

import 'package:ocm_phone/core/db/database.dart';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqlite3/sqlite3.dart';

const hex = '00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff';

void main() {
  late Directory dir;
  setUp(() => dir = Directory.systemTemp.createTempSync('cm_db'));
  tearDown(() => dir.deleteSync(recursive: true));

  test('SQLCipher raw key: a 1.0.x passphrase database is rekeyed once and then opens only with the raw key', () {
    // Exactly what DatabaseKey.ensureRawKey does natively, run against the same SQLCipher on the host.
    final path = '${dir.path}/old.db';
    final old = sqlite3.open(path)
      ..execute("PRAGMA key = '$hex'") // 1.0.x: the hex string was the passphrase (PBKDF2)
      ..execute('PRAGMA journal_mode = WAL')
      ..execute('CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT)')
      ..execute("INSERT INTO kv VALUES ('device_id', 'dev')");
    old.close();

    final migrate = sqlite3.open(path)..execute("PRAGMA key = '$hex'");
    migrate.select('PRAGMA journal_mode = DELETE');
    migrate.execute('PRAGMA rekey = "x\'$hex\'"');
    migrate.select('PRAGMA journal_mode = WAL');
    migrate.close();

    final raw = sqlite3.open(path)..execute('PRAGMA key = "x\'$hex\'"');
    expect(raw.select("SELECT value FROM kv WHERE key = 'device_id'").single['value'], 'dev');
    raw.close();
    final passphrase = sqlite3.open(path)..execute("PRAGMA key = '$hex'");
    expect(() => passphrase.select('SELECT count(*) FROM sqlite_master'), throwsA(isA<SqliteException>()));
    passphrase.close();
  });

  test('AppDatabase opens with the raw key and refuses anything that is not one', () async {
    final path = '${dir.path}/app.db';
    final db = AppDatabase.open(path: path, hexKey: hex);
    await db.setValue('device_id', 'dev');
    await db.close();
    final again = AppDatabase.open(path: path, hexKey: hex);
    expect(await again.getValue('device_id'), 'dev');
    await again.close();
    expect(() => AppDatabase.open(path: path, hexKey: "x'; DROP TABLE kv; --"), throwsArgumentError);
    // The file is really encrypted: plain SQLite cannot read it.
    final plain = sqlite3.open(path);
    expect(() => plain.select('SELECT count(*) FROM sqlite_master'), throwsA(isA<SqliteException>()));
    plain.close();
  });

  test('schema 1 → 2 adds the read caches and keeps the outbox', () async {
    final path = '${dir.path}/v1.db';
    final v1 = sqlite3.open(path)..execute('PRAGMA key = "x\'$hex\'"');
    // The schema 1.0.x created (drift, version 1): the outbox and kv are enough to prove nothing is lost.
    v1.execute('CREATE TABLE "sync_events" ("seq" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "type" TEXT NOT NULL, "payload" TEXT NOT NULL, "created_at" INTEGER NOT NULL)');
    v1.execute('CREATE TABLE "kv" ("key" TEXT NOT NULL, "value" TEXT NOT NULL, PRIMARY KEY ("key"))');
    v1.execute("INSERT INTO sync_events (type, payload, created_at) VALUES ('message.upsert', '{}', 1)");
    v1.execute('PRAGMA user_version = 1');
    v1.close();
    final db = AppDatabase(NativeDatabase(File(path), setup: (raw) => raw.execute('PRAGMA key = "x\'$hex\'"')));
    expect(await db.pendingCount(), 1);
    expect(await db.cachedThreads(), isEmpty); // the new table exists
    await db.close();
  });

  test('the Kotlin store tests use drift\'s real schema (android/app/src/test/resources/sync_schema.sql)', () async {
    final db = AppDatabase.memory();
    final rows = await db.customSelect("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type DESC, name").get();
    final ddl = '${rows.map((r) => r.read<String>('sql')).join(';\n')};\n';
    await db.close();
    final fixture = File('android/app/src/test/resources/sync_schema.sql');
    if (Platform.environment['UPDATE_SCHEMA'] == '1') fixture.writeAsStringSync(ddl);
    expect(fixture.readAsStringSync(), ddl, reason: 'run UPDATE_SCHEMA=1 flutter test test/db_test.dart after changing tables');
  });
}
