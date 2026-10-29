import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'data/conversations_repository.dart';
import 'features/chat/chat_screen.dart';
import 'features/compose/compose_screen.dart';
import 'features/conversations/conversation_list_screen.dart';
import 'features/enroll/enroll_screen.dart';
import 'features/enroll/scanner_screen.dart';
import 'features/onboarding/calls_onboarding_screen.dart';
import 'features/onboarding/onboarding_screen.dart';
import 'features/phone/phone_screen.dart';
import 'features/settings/appearance_screen.dart';
import 'features/settings/keep_flowing_screen.dart';
import 'features/settings/lock_screen.dart';
import 'features/settings/settings_screen.dart';
import 'features/settings/sync_status_screen.dart';
import 'l10n/app_localizations.dart';
import 'platform/telephony_api.g.dart';
import 'providers.dart';
import 'state/events.dart';
import 'ui/skin/skin.dart';
import 'ui/skin/tokens.dart';

/// The first screen, decided from what main() already has (no platform call, no await): a removed phone, a phone
/// where this is not the default SMS app, an unenrolled phone, or the conversation list.
String initialLocation({required bool removed, required bool isDefaultSmsApp, required bool enrolled}) {
  if (removed) return '/removed';
  if (!isDefaultSmsApp) return '/onboarding';
  if (!enrolled) return '/enroll';
  return '/conversations';
}

GoRouter buildRouter(String initial) => GoRouter(
  initialLocation: initial,
  routes: [
    GoRoute(path: '/onboarding', builder: (_, _) => const OnboardingScreen()),
    GoRoute(path: '/onboarding/calls', builder: (_, _) => const CallsOnboardingScreen()),
    GoRoute(path: '/phone', builder: (_, state) => PhoneScreen(number: state.uri.queryParameters['number'])),
    GoRoute(path: '/phone/keypad', builder: (_, state) => PhoneScreen(number: state.uri.queryParameters['number'])),
    GoRoute(path: '/phone/recents', builder: (_, _) => const PhoneScreen(tab: PhoneTab.recents)),
    GoRoute(path: '/phone/contacts', builder: (_, _) => const PhoneScreen(tab: PhoneTab.contacts)),
    GoRoute(path: '/phone/callbacks', builder: (_, _) => const PhoneScreen(tab: PhoneTab.callbacks)),
    GoRoute(
      path: '/enroll',
      builder: (_, state) => EnrollScreen(link: state.uri.queryParameters['link']),
    ),
    GoRoute(path: '/enroll/scan', builder: (_, _) => const ScannerScreen()),
    GoRoute(
      path: '/enroll/done',
      builder: (_, state) => EnrolledScreen(deviceCode: state.uri.queryParameters['code'] ?? ''),
    ),
    GoRoute(path: '/removed', builder: (_, _) => const RemovedScreen()),
    GoRoute(
      path: '/conversations',
      builder: (_, _) => const ConversationListScreen(folder: Folder.inbox),
    ),
    GoRoute(
      path: '/archived',
      builder: (_, _) => const ConversationListScreen(folder: Folder.archived),
    ),
    GoRoute(
      path: '/spam',
      builder: (_, _) => const ConversationListScreen(folder: Folder.spam),
    ),
    GoRoute(
      path: '/chat/:id',
      builder: (_, state) => ChatScreen(threadId: int.parse(state.pathParameters['id']!)),
    ),
    GoRoute(
      path: '/compose',
      builder: (_, state) => ComposeScreen(initialTo: state.uri.queryParameters['to'], initialBody: state.extra as String?),
    ),
    GoRoute(path: '/settings', builder: (_, _) => const SettingsScreen()),
    GoRoute(path: '/settings/appearance', builder: (_, _) => const AppearanceScreen()),
    GoRoute(path: '/settings/flowing', builder: (_, _) => const KeepFlowingScreen()),
    GoRoute(path: '/settings/sync', builder: (_, _) => const SyncStatusScreen()),
  ],
);

final routerProvider = Provider<GoRouter>((ref) => throw UnimplementedError('routerProvider must be overridden'));

/// Re-checked on every resume (the role and permissions can be revoked in system settings).
final roleCheckProvider = FutureProvider<RoleStatus>((ref) => ref.watch(repositoryProvider).phone.roleStatus());

/// The active look: "Match my phone" (default) picks the skin of the Messages app this phone came with.
final skinProvider = Provider<SkinSpec>((ref) {
  final chosen = ref.watch(settingsProvider.select((s) => s['skin'] ?? 'auto'));
  if (chosen != 'auto') return skinById(chosen);
  final startup = ref.watch(servicesProvider).startup;
  return skinById(skinForPhone(startup.manufacturer, startup.brand));
});

class SmsApp extends ConsumerStatefulWidget {
  const SmsApp({super.key});
  @override
  ConsumerState<SmsApp> createState() => _SmsAppState();
}

class _SmsAppState extends ConsumerState<SmsApp> with WidgetsBindingObserver {
  StreamSubscription<TelephonyEvent>? _events;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _events = ref.read(eventRouterProvider).other.listen((event) {
      if (event.type == 'sync_state' && event.state == 'revoked') ref.read(routerProvider).go('/removed');
      if (event.type == 'launch') _consumeLaunch();
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _consumeLaunch();
      _checkCalls();
    });
  }

  bool _callsOnboardingShown = false;

  /// When the admin enables Calls, the phone asks (once per run) to become the Phone app. The heartbeat that carries
  /// the capability may arrive while the app is open, so this also runs on every resume.
  Future<void> _checkCalls() async {
    if (_callsOnboardingShown || ref.read(servicesProvider).session == null) return;
    try {
      final status = await ref.read(dialerProvider).status();
      if (!mounted || !status.enabled || status.isDefaultDialer) return;
      _callsOnboardingShown = true;
      ref.read(routerProvider).push('/onboarding/calls');
    } on Object {
      // Widget tests and phones without a dialer role: nothing to ask.
    }
  }

  /// A notification, a conversation shortcut, an sms: intent, an enroll link or the sync notification opened the app.
  Future<void> _consumeLaunch() async {
    final target = await ref.read(servicesProvider).host.consumeLaunch();
    if (target == null || !mounted) return;
    final router = ref.read(routerProvider);
    final enrolled = ref.read(servicesProvider).session != null;
    switch (target.kind) {
      case 'compose' when enrolled:
        router.push('/compose?to=${Uri.encodeComponent(target.value)}');
      case 'chat' when enrolled:
        router.push('/chat/${target.value}');
      case 'route' when enrolled && target.value.startsWith('/phone'):
        router.go(target.value);
      case 'route' when enrolled:
        router.push(target.value);
      case 'dial' when enrolled:
        router.go('/phone/keypad?number=${Uri.encodeComponent(target.value)}');
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
    // Permissions and the SMS role can be revoked while the app is in the background: re-check on every resume.
    if (state == AppLifecycleState.resumed) {
      ref.invalidate(roleCheckProvider);
      _checkCalls();
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
    SwipeAction? swipe(String key) => SwipeAction.values.where((a) => a.name == settings[key]).firstOrNull;
    final bubble = int.tryParse(settings['bubble_colour'] ?? '', radix: 16);
    final overrides = AppearanceOverrides(bubbleColour: bubble == null ? null : Color(bubble), swipeLeft: swipe('swipe_left'), swipeRight: swipe('swipe_right'));
    final compact = settings['density'] == 'compact';
    // Material You: the wallpaper colour (Android 12+), read before the first frame.
    final accent = ref.watch(servicesProvider).accent;
    ColorScheme? wallpaper(Brightness b) => accent == null ? null : ColorScheme.fromSeed(seedColor: accent, brightness: b);
    return MaterialApp.router(
      onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
      theme: buildSkinTheme(skin, Brightness.light, dynamicScheme: wallpaper(Brightness.light), overrides: overrides, compact: compact),
      darkTheme: buildSkinTheme(skin, Brightness.dark, dynamicScheme: wallpaper(Brightness.dark), overrides: overrides, compact: compact),
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
          child: MediaQuery(
            data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(textScale)),
            child: AppLockGate(child: child ?? const SizedBox.shrink()),
          ),
        );
      },
    );
  }
}
