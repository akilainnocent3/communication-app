import 'dart:typed_data';

import '../config.dart';
import '../data/phone_gateway.dart';
import '../platform/telephony_api.g.dart';
import 'api/device_api.dart';
import 'api/transport.dart';
import 'db/database.dart';
import 'sync/sync_engine.dart';

class PlatformSigner implements DeviceSigner {
  PlatformSigner(this.api);
  final TelephonyHostApi api;
  @override
  Future<Uint8List> sign(Uint8List message) => api.sign(message);
}

/// Where this phone is enrolled. Stored in the encrypted sync database; none of it is a credential.
class Session {
  const Session({required this.server, required this.deviceId, required this.deviceCode, required this.deviceName, required this.options});
  final Uri server;
  final String deviceId;
  final String deviceCode;
  final String deviceName;
  final Map<String, dynamic> options;
}

/// The app's composition root, shared by the UI engine and the background sync engine.
class AppServices {
  AppServices({required this.config, required this.host, required this.db, required this.phone, required this.transport});

  final AppConfig config;
  final TelephonyHostApi host;
  final AppDatabase db;
  final PhoneGateway phone;
  final HttpTransport transport;
  Session? session;
  DeviceApi? _api;

  static Future<AppServices> open(AppConfig config) async {
    final host = TelephonyHostApi();
    final db = AppDatabase.open(path: await host.databasePath(), passphrase: await host.databaseKey());
    final services = AppServices(config: config, host: host, db: db, phone: PlatformPhoneGateway(host), transport: NativeHttpTransport(host));
    await services.loadSession();
    return services;
  }

  Future<Session?> loadSession() async {
    final server = await db.getValue('server');
    final deviceId = await db.getValue('device_id');
    if (server == null || deviceId == null) return session = null;
    return session = Session(
      server: Uri.parse(server), deviceId: deviceId, deviceCode: await db.getValue('device_code') ?? '', deviceName: await db.getValue('device_name') ?? '',
      options: {'signature_enabled': await db.getValue('signature_enabled') == '1', 'signature': await db.getValue('signature') ?? ''},
    );
  }

  DeviceApi apiFor(Uri server) => DeviceApi(transport: transport, server: server, signer: PlatformSigner(host), appVersion: config.appVersion);

  DeviceApi? get api {
    final current = session;
    if (current == null) return null;
    return _api ??= apiFor(current.server)..deviceId = current.deviceId;
  }

  SyncEngine? get engine {
    final client = api;
    return client == null ? null : SyncEngine(db: db, api: client, phone: phone, appVersion: config.appVersion);
  }

  Future<void> saveEnrollment(Uri server, Map<String, dynamic> response) async {
    await db.setValue('server', server.toString());
    await db.setValue('device_id', response['device_id'] as String);
    await db.setValue('device_code', response['device_code'] as String);
    await db.setValue('device_name', response['name'] as String);
    final options = (response['options'] as Map?)?.cast<String, dynamic>() ?? const {};
    await db.setValue('backfill_days', '${options['backfill_days'] ?? 90}');
    await db.setValue('signature_enabled', options['signature_enabled'] == true ? '1' : '0');
    await db.setValue('signature', (options['signature'] as String?) ?? '');
    _api = null;
    await loadSession();
  }

  /// Revoked: the key, the sync database and settings are deleted natively. The phone's own SMS stay.
  Future<void> wipe() async {
    await db.close();
    await host.wipe();
    session = null;
    _api = null;
  }
}
