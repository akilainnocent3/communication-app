import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'config.dart';
import 'core/services.dart';
import 'core/sync/background.dart';
import 'l10n/app_localizations.dart';
import 'providers.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final AppServices services;
  try {
    services = await AppServices.open(AppConfig.fromEnvironment());
  } on Object catch (error) {
    // Without this the phone stays on the splash screen forever (e.g. the Keystore is briefly unavailable after an
    // update). Only the type is logged: errors can carry paths or SQL.
    debugPrint('startup failed: ${error.runtimeType}');
    runApp(StartupErrorApp(onRetry: main));
    return;
  }
  runApp(ProviderScope(overrides: [servicesProvider.overrideWithValue(services)], child: const SmsApp()));
}

/// Shown instead of the app when the local services could not be opened.
class StartupErrorApp extends StatelessWidget {
  const StartupErrorApp({super.key, required this.onRetry});
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Builder(builder: (context) {
        final l10n = AppLocalizations.of(context);
        return Scaffold(
          body: SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                const Icon(Icons.error_outline, size: 56),
                const SizedBox(height: 16),
                Text(l10n.startupErrorTitle, textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                Text(l10n.startupErrorBody, textAlign: TextAlign.center),
                const SizedBox(height: 24),
                FilledButton(onPressed: onRetry, child: Text(l10n.tryAgain)),
              ]),
            ),
          ),
        );
      }),
    );
  }
}

/// Entry point of the headless engine started by the native foreground service (SyncService). Runs only the sync
/// loop; no UI. Kept alive by the service even when the app's activity is gone.
@pragma('vm:entry-point')
Future<void> backgroundMain() async {
  WidgetsFlutterBinding.ensureInitialized();
  // The service outlives the UI, so a failed open (e.g. the database still locked by another engine) is retried
  // rather than leaving the service running without a sync loop.
  AppServices? services;
  for (var attempt = 1; services == null; attempt++) {
    try {
      services = await AppServices.open(AppConfig.fromEnvironment());
    } on Object catch (error) {
      debugPrint('background startup failed (attempt $attempt): ${error.runtimeType}');
      if (attempt == 5) return;
      await Future<void>.delayed(Duration(seconds: 2 * attempt));
    }
  }
  if (services.session == null) return;
  BackgroundSync(services).start();
}
