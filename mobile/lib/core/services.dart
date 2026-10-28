import 'dart:typed_data';
import 'dart:ui' show Color;

import 'package:dynamic_color/dynamic_color.dart';

import '../config.dart';
import '../data/phone_gateway.dart';
import '../platform/telephony_api.g.dart';
import 'api/device_api.dart';
import 'api/transport.dart';
import 'db/database.dart';

class PlatformSigner implements DeviceSigner {
  PlatformSigner(this.api);
  final TelephonyHostApi api;
  @override
  Future<Uint8List> sign(Uint8List message) => api.sign(message);
}

/// Where this phone is enrolled. Stored in the encrypted sync database; none of it is a credential.
class Session {
  const Session({required this.server, required this.deviceId, required this.deviceCode, required this.deviceName});
  final Uri server;
  final String deviceId;
  final String deviceCode;
  final String deviceName;
}

/// The UI's composition root. Syncing with the server is the native engine's job (NativeSyncEngine.kt); Dart only
/// talks to the server to enroll.
class AppServices {
  AppServices({required this.config, required this.host, required this.db, required this.phone, required this.transport, required this.startup, this.settings = const {}, this.accent});

  final AppConfig config;
  final TelephonyHostApi host;
  final AppDatabase db;
  final PhoneGateway phone;
  final HttpTransport transport;
  final StartupState startup;
  /// `setting.*` values read before the first frame (look, text size), so the first frame is already right.
  final Map<String, String> settings;
  /// Android 12+ wallpaper colour (Material You); null on older phones.
  final Color? accent;
  Session? session;

  /// One platform round trip (path, raw key, role, manufacturer), then one database read. Nothing else is awaited
  /// before the first frame.
  static Future<AppServices> open(AppConfig config) async {
    final host = TelephonyHostApi();
    final accentFuture = DynamicColorPlugin.getAccentColor().then<Color?>((c) => c, onError: (Object _) => null);
    final startup = await host.startup();
    final db = AppDatabase.open(path: startup.databasePath, hexKey: startup.databaseKey);
    final values = await db.allValues();
    final services = AppServices(
      config: config, host: host, db: db, phone: PlatformPhoneGateway(host), transport: NativeHttpTransport(host), startup: startup,
      settings: {for (final e in values.entries) if (e.key.startsWith('setting.')) e.key.substring(8): e.value}, accent: await accentFuture,
    );
    services.session = sessionFrom(values);
    return services;
  }

  static Session? sessionFrom(Map<String, String> values) {
    final server = values['server'];
    final deviceId = values['device_id'];
    if (server == null || deviceId == null) return null;
    return Session(server: Uri.parse(server), deviceId: deviceId, deviceCode: values['device_code'] ?? '', deviceName: values['device_name'] ?? '');
  }

  DeviceApi apiFor(Uri server) => DeviceApi(transport: transport, server: server, signer: PlatformSigner(host), appVersion: config.appVersion);

  Future<void> saveEnrollment(Uri server, Map<String, dynamic> response) async {
    final options = (response['options'] as Map?)?.cast<String, dynamic>() ?? const {};
    // device_id last: the native layer treats the phone as enrolled once it exists.
    await db.setValue('server', server.toString());
    await db.setValue('device_code', response['device_code'] as String);
    await db.setValue('device_name', response['name'] as String);
    await db.setValue('backfill_days', '${options['backfill_days'] ?? 90}');
    await db.setValue('signature_enabled', options['signature_enabled'] == true ? '1' : '0');
    await db.setValue('signature', (options['signature'] as String?) ?? '');
    await db.setValue('device_id', response['device_id'] as String);
    session = sessionFrom(await db.allValues());
  }
}
