import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'config.dart';
import 'core/perf.dart';
import 'core/services.dart';
import 'l10n/app_localizations.dart';
import 'providers.dart';
import 'state/threads.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  Perf.mark('dart_main');
  Perf.watchFrames();
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
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
  Perf.mark('services_open');
  final initial = initialLocation(removed: services.startup.removed, isDefaultSmsApp: services.startup.isDefaultSmsApp, enrolled: services.session != null);
  final container = ProviderContainer(overrides: [
    servicesProvider.overrideWithValue(services),
    routerProvider.overrideWithValue(buildRouter(initial)),
  ]);
  // Start reading the conversation cache now, in parallel with the first frame.
  if (initial == '/conversations') container.read(threadsProvider);
  runApp(UncontrolledProviderScope(container: container, child: const SmsApp()));
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
