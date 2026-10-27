import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'config.dart';
import 'core/services.dart';
import 'core/sync/background.dart';
import 'providers.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final services = await AppServices.open(AppConfig.fromEnvironment());
  runApp(ProviderScope(overrides: [servicesProvider.overrideWithValue(services)], child: const SmsApp()));
}

/// Entry point of the headless engine started by the native foreground service (SyncService). Runs only the sync
/// loop; no UI. Kept alive by the service even when the app's activity is gone.
@pragma('vm:entry-point')
Future<void> backgroundMain() async {
  WidgetsFlutterBinding.ensureInitialized();
  final services = await AppServices.open(AppConfig.fromEnvironment());
  if (services.session == null) return;
  BackgroundSync(services).start();
}
