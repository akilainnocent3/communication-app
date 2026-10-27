import 'dart:async';

import 'package:dynamic_color/dynamic_color.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'data/conversations_repository.dart';
import 'features/chat/chat_screen.dart';
import 'features/compose/compose_screen.dart';
import 'features/conversations/conversation_list_screen.dart';
import 'features/enroll/enroll_screen.dart';
import 'features/onboarding/onboarding_screen.dart';
import 'features/settings/lock_screen.dart';
import 'features/settings/settings_screen.dart';
import 'features/settings/sync_status_screen.dart';
import 'l10n/app_localizations.dart';
import 'platform/telephony_api.g.dart';
import 'providers.dart';
import 'theme.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final services = ref.watch(servicesProvider);
  return GoRouter(
    initialLocation: '/',
    redirect: (context, state) async {
      if (state.matchedLocation == '/') {
        final role = await services.phone.roleStatus();
        if (!role.isDefaultSmsApp) return '/onboarding';
        if (services.session == null) return '/enroll';
        final launch = await services.host.launchAddress();
        return launch != null ? '/compose?to=${Uri.encodeComponent(launch)}' : '/conversations';
      }
      return null;
    },
    routes: [
      GoRoute(path: '/', builder: (_, _) => const SizedBox.shrink()),
      GoRoute(path: '/onboarding', builder: (_, _) => const OnboardingScreen()),
      GoRoute(path: '/enroll', builder: (_, _) => const EnrollScreen()),
      GoRoute(path: '/removed', builder: (_, _) => const RemovedScreen()),
      GoRoute(path: '/conversations', builder: (_, _) => const ConversationListScreen(folder: Folder.inbox)),
      GoRoute(path: '/archived', builder: (_, _) => const ConversationListScreen(folder: Folder.archived)),
      GoRoute(path: '/spam', builder: (_, _) => const ConversationListScreen(folder: Folder.spam)),
      GoRoute(path: '/chat/:id', builder: (_, state) => ChatScreen(threadId: int.parse(state.pathParameters['id']!))),
      GoRoute(path: '/compose', builder: (_, state) => ComposeScreen(initialTo: state.uri.queryParameters['to'], initialBody: state.extra as String?)),
      GoRoute(path: '/settings', builder: (_, _) => const SettingsScreen()),
      GoRoute(path: '/settings/sync', builder: (_, _) => const SyncStatusScreen()),
    ],
  );
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
    _events = events().listen((event) {
      if (event.type != 'network') ref.read(refreshTickProvider.notifier).bump();
    });
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
      ref.read(refreshTickProvider.notifier).bump();
      ref.invalidate(roleCheckProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(routerProvider);
    final textScale = ref.watch(textScaleProvider);
    final accent = ref.watch(accentProvider).value;
    final light = accent == null ? null : ColorScheme.fromSeed(seedColor: accent);
    final dark = accent == null ? null : ColorScheme.fromSeed(seedColor: accent, brightness: Brightness.dark);
    return Builder(builder: (context) {
      return MaterialApp.router(
        onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
        theme: buildTheme(light, Brightness.light, textScale),
        darkTheme: buildTheme(dark, Brightness.dark, textScale),
        themeMode: ThemeMode.system,
        routerConfig: router,
        localizationsDelegates: const [AppLocalizations.delegate, GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate, GlobalCupertinoLocalizations.delegate],
        supportedLocales: AppLocalizations.supportedLocales,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(textScale)),
          child: AppLockGate(child: child ?? const SizedBox.shrink()),
        ),
      );
    });
  }
}

/// Re-checked on every resume (the role and permissions can be revoked in system settings).
final roleCheckProvider = FutureProvider<RoleStatus>((ref) => ref.watch(servicesProvider).phone.roleStatus());

class TextScale extends Notifier<double> {
  @override
  double build() => 1.0;
  void set(double value) => state = value;
}

final textScaleProvider = NotifierProvider<TextScale, double>(TextScale.new);

/// Android 12+ wallpaper colour (Material You); null on older phones, which use the company colour.
final accentProvider = FutureProvider<Color?>((ref) async {
  try {
    return await DynamicColorPlugin.getAccentColor();
  } on Exception {
    return null;
  }
});
