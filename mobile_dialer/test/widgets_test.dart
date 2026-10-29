import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:ocm_phone/app.dart';
import 'package:ocm_phone/features/phone/phone_screen.dart';
import 'package:ocm_phone/platform/telephony_api.g.dart';
import 'package:ocm_phone/state/events.dart';

void main() {
  test('first screen: the keypad stays reachable whenever OCM Phone is the Phone app', () {
    expect(initialLocation(removed: true, isDefaultDialer: true, enrolled: false), '/removed');
    expect(initialLocation(removed: false, isDefaultDialer: false, enrolled: false), '/enroll');
    // Not enrolled (or removed earlier) but still the Phone app: the keypad, with a banner to connect.
    expect(initialLocation(removed: false, isDefaultDialer: true, enrolled: false), '/phone');
    expect(initialLocation(removed: false, isDefaultDialer: false, enrolled: true), '/onboarding');
    expect(initialLocation(removed: false, isDefaultDialer: true, enrolled: true), '/phone');
  });

  test('call events refresh recents and call-backs once per burst; other events go to the app shell', () async {
    final source = StreamController<TelephonyEvent>();
    var recents = 0;
    var callbacks = 0;
    final container = ProviderContainer(overrides: [
      recentsProvider.overrideWith((ref) async { recents++; return const []; }),
      callbackTasksProvider.overrideWith((ref) async { callbacks++; return const []; }),
      eventRouterProvider.overrideWith((ref) {
        final router = EventRouter(ref, source: source.stream, window: const Duration(milliseconds: 10));
        ref.onDispose(router.dispose);
        return router;
      }),
    ]);
    addTearDown(container.dispose);
    final shell = <String>[];
    container.read(eventRouterProvider).other.listen((e) => shell.add(e.type));
    final keep = [container.listen(recentsProvider, (_, _) {}), container.listen(callbackTasksProvider, (_, _) {})];
    await container.read(recentsProvider.future);
    await container.read(callbackTasksProvider.future);
    for (var i = 0; i < 3; i++) {
      source.add(TelephonyEvent(type: 'calls_changed'));
    }
    source.add(TelephonyEvent(type: 'launch'));
    await Future<void>.delayed(const Duration(milliseconds: 40));
    await container.read(recentsProvider.future);
    await container.read(callbackTasksProvider.future);
    expect((recents, callbacks), (2, 2));
    expect(shell, ['launch']);
    for (final sub in keep) {
      sub.close();
    }
    await source.close();
  });

  test('no SMS screens: every route belongs to the dialer', () {
    final router = buildRouter('/phone');
    final paths = router.configuration.routes.whereType<GoRoute>().map((r) => r.path).toList();
    expect(paths, contains('/phone/keypad'));
    expect(paths.where((p) => p.contains('chat') || p.contains('compose') || p.contains('conversations')), isEmpty);
  });
}
