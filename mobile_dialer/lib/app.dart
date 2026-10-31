import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'features/enroll/enroll_screen.dart';
import 'features/enroll/scanner_screen.dart';
import 'features/onboarding/calls_onboarding_screen.dart';
import 'features/phone/phone_screen.dart';
import 'features/settings/appearance_screen.dart';
import 'features/settings/keep_flowing_screen.dart';
import 'features/settings/settings_screen.dart';
import 'features/settings/sync_status_screen.dart';
import 'l10n/app_localizations.dart';
import 'platform/telephony_api.g.dart';
import 'providers.dart';
import 'state/events.dart';
import 'ui/skin/skin.dart';

/// The first screen, decided from what main() already has (no platform call, no await). The Phone screens work before
/// enrollment too: once OCM Phone is the phone's Phone app, the keypad must always be there (decision 80).
String initialLocation({required bool removed, required bool isDefaultDialer, required bool enrolled}) {
  if (removed) return '/removed';
  if (!enrolled) return isDefaultDialer ? '/phone' : '/enroll';
  if (!isDefaultDialer) return '/onboarding';
  return '/phone';
}

GoRouter buildRouter(String initial) => GoRouter(
  initialLocation: initial,
  routes: [
    GoRoute(path: '/onboarding', builder: (_, _) => const CallsOnboardingScreen()),
    GoRoute(path: '/phone', builder: (_, state) => PhoneScreen(number: state.uri.queryParameters['number'])),
    GoRoute(path: '/phone/keypad', builder: (_, state) => PhoneScreen(number: state.uri.queryParameters['number'])),
    GoRoute(path: '/phone/recents', builder: (_, _) => const PhoneScreen(tab: PhoneTab.recents)),
    GoRoute(path: '/phone/contacts', builder: (_, _) => const PhoneScreen(tab: PhoneTab.contacts)),
    GoRoute(path: '/enroll', builder: (_, state) => EnrollScreen(link: state.uri.queryParameters['link'])),
    GoRoute(path: '/enroll/scan', builder: (_, _) => const ScannerScreen()),
    GoRoute(path: '/enroll/done', builder: (_, state) => EnrolledScreen(deviceCode: state.uri.queryParameters['code'] ?? '')),
    GoRoute(path: '/removed', builder: (_, _) => const RemovedScreen()),
    GoRoute(path: '/settings', builder: (_, _) => const SettingsScreen()),
    GoRoute(path: '/settings/appearance', builder: (_, _) => const AppearanceScreen()),
    GoRoute(path: '/settings/flowing', builder: (_, _) => const KeepFlowingScreen()),
    GoRoute(path: '/settings/sync', builder: (_, _) => const SyncStatusScreen()),
  ],
);

final routerProvider = Provider<GoRouter>((ref) => throw UnimplementedError('routerProvider must be overridden'));

/// Re-checked on every resume (the Phone app role and permissions can be changed in system settings).
final callsStatusProvider = FutureProvider<CallsStatus>((ref) => ref.watch(dialerProvider).status());

/// The active look: "Match my phone" (default) picks the skin of the Phone app this phone came with (asked from the
/// system at startup), so the app looks at home on each phone it is installed on.
final skinProvider = Provider<SkinSpec>((ref) {
  final chosen = ref.watch(settingsProvider.select((s) => s['skin'] ?? 'auto'));
  if (chosen != 'auto') return skinById(chosen);
  final startup = ref.watch(servicesProvider).startup;
  return skinById(skinForPhone(startup.manufacturer, startup.brand, dialer: startup.systemDialer));
});

class PhoneApp extends ConsumerStatefulWidget {
  const PhoneApp({super.key});
  @override
  ConsumerState<PhoneApp> createState() => _PhoneAppState();
}

class _PhoneAppState extends ConsumerState<PhoneApp> with WidgetsBindingObserver {
  StreamSubscription<TelephonyEvent>? _events;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _events = ref.read(eventRouterProvider).other.listen((event) {
      if (event.type == 'sync_state' && event.state == 'revoked') ref.read(routerProvider).go('/removed');
      if (event.type == 'launch') _consumeLaunch();
    });
    WidgetsBinding.instance.addPostFrameCallback((_) => _consumeLaunch());
  }

  /// A tel: / DIAL intent, a notification or an enroll link opened the app. Dialing works without enrollment.
  Future<void> _consumeLaunch() async {
    final target = await ref.read(servicesProvider).host.consumeLaunch();
    if (target == null || !mounted) return;
    final router = ref.read(routerProvider);
    final enrolled = ref.read(servicesProvider).session != null;
    switch (target.kind) {
      case 'dial':
        router.go('/phone/keypad?number=${Uri.encodeComponent(target.value)}');
      case 'route' when target.value.startsWith('/phone'):
        router.go(target.value);
      case 'route' when enrolled:
        router.push(target.value);
      case 'enroll' when !enrolled:
        router.go('/enroll?link=${Uri.encodeComponent(target.value)}');
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _events?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      ref.invalidate(callsStatusProvider);
      ref.invalidate(recentsProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(routerProvider);
    final skin = ref.watch(skinProvider);
    final textScale = ref.watch(textScaleProvider);
    final settings = ref.watch(settingsProvider);
    final mode = switch (settings['theme_mode']) {
      'light' => ThemeMode.light,
      'dark' => ThemeMode.dark,
      _ => ThemeMode.system,
    };
    // Material You: the wallpaper colour (Android 12+), read before the first frame.
    final accent = ref.watch(servicesProvider).accent;
    ColorScheme? wallpaper(Brightness b) => accent == null ? null : ColorScheme.fromSeed(seedColor: accent, brightness: b);
    return MaterialApp.router(
      onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
      theme: buildSkinTheme(skin, Brightness.light, dynamicScheme: wallpaper(Brightness.light)),
      darkTheme: buildSkinTheme(skin, Brightness.dark, dynamicScheme: wallpaper(Brightness.dark)),
      themeMode: mode,
      routerConfig: router,
      localizationsDelegates: const [AppLocalizations.delegate, GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate, GlobalCupertinoLocalizations.delegate],
      supportedLocales: AppLocalizations.supportedLocales,
      builder: (context, child) {
        final dark = Theme.of(context).brightness == Brightness.dark;
        // Edge-to-edge: transparent system bars, icons that contrast with the skin's page colour.
        return AnnotatedRegion<SystemUiOverlayStyle>(
          value: (dark ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark).copyWith(
            statusBarColor: Colors.transparent,
            systemNavigationBarColor: Colors.transparent,
            systemNavigationBarContrastEnforced: false,
          ),
          child: MediaQuery(data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(textScale)), child: child ?? const SizedBox.shrink()),
        );
      },
    );
  }
}
