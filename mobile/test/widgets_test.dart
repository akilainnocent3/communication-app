import 'dart:async';

import 'package:cm_sms/app.dart';
import 'package:cm_sms/core/db/database.dart';
import 'package:cm_sms/data/conversations_repository.dart';
import 'package:cm_sms/features/chat/chat_screen.dart';
import 'package:cm_sms/features/compose/composer.dart';
import 'package:cm_sms/features/conversations/conversation_list_screen.dart';
import 'package:cm_sms/l10n/app_localizations.dart';
import 'package:cm_sms/platform/telephony_api.g.dart';
import 'package:cm_sms/providers.dart';
import 'package:cm_sms/state/events.dart';
import 'package:cm_sms/state/threads.dart';
import 'package:cm_sms/ui/skin/skin.dart';
import 'package:cm_sms/ui/skin/skins/company.dart';
import 'package:drift/drift.dart' show Value;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

List<Override> overrides(FakePhone phone, AppDatabase db) => [
      repositoryProvider.overrideWithValue(ConversationsRepository(phone: phone, db: db)),
      settingsProvider.overrideWith(MemorySettings.new),
      roleCheckProvider.overrideWith((ref) async => RoleStatus(isDefaultSmsApp: phone.defaultApp, roleAvailable: true)),
      simsProvider.overrideWith((ref) async => [
            SimInfo(subscriptionId: 1, slot: 0, carrier: 'Vodacom', countryIso: 'tz', isDefault: true),
            SimInfo(subscriptionId: 2, slot: 1, carrier: 'Airtel', countryIso: 'tz', isDefault: false),
          ]),
      quickRepliesProvider.overrideWith((ref) async => [{'id': 1, 'title': 'Asante', 'body': 'Asante sana!'}]),
    ];

Widget harness(Widget child, {required FakePhone phone, required AppDatabase db, ProviderContainer? container}) {
  final app = MaterialApp(
    theme: buildSkinTheme(companySkin, Brightness.light),
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: child,
  );
  return container == null ? ProviderScope(overrides: overrides(phone, db), child: app) : UncontrolledProviderScope(container: container, child: app);
}

void main() {
  late AppDatabase db;
  late FakePhone phone;
  final today = DateTime.now();

  setUp(() {
    db = AppDatabase.memory();
    phone = FakePhone()
      ..names = {'+255754210331': 'Neema Mushi'}
      ..threadList = [
        thread(1, '+255754210331', snippet: 'Habari, bei gani?', date: today, unread: 2),
        thread(2, '0713402118', snippet: 'Invoice please', date: today.subtract(const Duration(hours: 1))),
        thread(3, 'M-PESA', snippet: 'Imethibitishwa', date: today.subtract(const Duration(hours: 2))),
      ];
  });
  tearDown(() => db.close());

  testWidgets('list shows names for saved contacts, formatted numbers otherwise, unread counts and pinned first', (tester) async {
    await db.updatePref(3, const ConversationPrefsCompanion(pinned: Value(true)));
    await tester.pumpWidget(harness(const ConversationListScreen(folder: Folder.inbox), phone: phone, db: db));
    await tester.pumpAndSettle();
    expect(find.text('Neema Mushi'), findsOneWidget);
    expect(find.text('+255 713 402 118'), findsOneWidget);
    expect(find.text('2'), findsOneWidget); // unread badge
    final first = tester.getTopLeft(find.text('M-PESA')).dy;
    expect(first, lessThan(tester.getTopLeft(find.text('Neema Mushi')).dy)); // pinned first
    expect(find.text('Start chat'), findsOneWidget);
  });

  testWidgets('the list draws the encrypted cache before the phone answers, then reconciles', (tester) async {
    final repo = ConversationsRepository(phone: phone, db: db);
    await repo.saveToCache(await repo.withNames(await repo.page(0)));
    phone.calls.clear();
    final gate = Completer<void>();
    phone.gate = gate.future;
    phone.threadList = [...phone.threadList.where((t) => t.threadId != 2)]; // deleted on the phone meanwhile
    await tester.pumpWidget(harness(const ConversationListScreen(folder: Folder.inbox), phone: phone, db: db));
    await tester.pump();
    await tester.pump();
    expect(find.text('Neema Mushi'), findsOneWidget); // from the cache, provider still pending
    expect(find.text('+255 713 402 118'), findsOneWidget);
    gate.complete();
    await tester.pumpAndSettle();
    expect(find.text('+255 713 402 118'), findsNothing); // the provider is the truth
    expect((await db.cachedThreads()).map((r) => r.threadId), isNot(contains(2)));
  });

  testWidgets('long-press selects and archive moves conversations out of the inbox', (tester) async {
    await tester.pumpWidget(harness(const ConversationListScreen(folder: Folder.inbox), phone: phone, db: db));
    await tester.pumpAndSettle();
    await tester.longPress(find.text('Neema Mushi'));
    await tester.pumpAndSettle();
    expect(find.text('1 selected'), findsOneWidget);
    await tester.tap(find.byTooltip('Archive'));
    await tester.pumpAndSettle();
    expect(find.text('Neema Mushi'), findsNothing);
    expect((await db.prefsFor([1]))[1]!.archived, isTrue);
  });

  testWidgets('banner when the app is no longer the default SMS app', (tester) async {
    phone.defaultApp = false;
    await tester.pumpWidget(harness(const ConversationListScreen(folder: Folder.inbox), phone: phone, db: db));
    await tester.pumpAndSettle();
    expect(find.textContaining('not the default SMS app'), findsOneWidget);
  });

  testWidgets('search filters the cache at once and searches bodies once, after typing stops', (tester) async {
    phone.searchHits = [providerMessage(id: 9, threadId: 2, address: '0713402118', body: 'The invoice for October')];
    await tester.pumpWidget(harness(const ConversationListScreen(folder: Folder.inbox), phone: phone, db: db));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Search conversations'));
    await tester.pumpAndSettle();
    for (final partial in ['n', 'ne', 'nee', 'neem', 'neema']) {
      await tester.enterText(find.byType(TextField), partial);
      await tester.pump(const Duration(milliseconds: 60));
    }
    expect(find.text('Neema Mushi'), findsOneWidget); // local match, no wait
    expect(find.text('M-PESA'), findsNothing);
    expect(phone.count('search:'), 0);
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pumpAndSettle();
    expect(phone.calls.where((c) => c.startsWith('search:')).toList(), ['search:neema']); // debounced: one query
  });

  testWidgets('an event refreshes only its thread (no full reload) and bursts are coalesced', (tester) async {
    final events = StreamController<TelephonyEvent>();
    final container = ProviderContainer(overrides: [...overrides(phone, db), eventRouterProvider.overrideWith((ref) => EventRouter(ref, source: events.stream))]);
    addTearDown(container.dispose);
    container.read(eventRouterProvider);
    await tester.pumpWidget(harness(const ConversationListScreen(folder: Folder.inbox), phone: phone, db: db, container: container));
    await tester.pumpAndSettle();
    phone.calls.clear();
    phone.threadList[1] = thread(2, '0713402118', snippet: 'New text', date: today.add(const Duration(minutes: 1)), unread: 1);
    for (var i = 0; i < 5; i++) {
      events.add(TelephonyEvent(type: 'send_state', threadId: 2));
    }
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pumpAndSettle();
    expect(phone.count('thread:2'), 1); // five events, one refresh
    expect(phone.count('threads:'), 0); // the list was not reloaded
    expect(find.text('New text'), findsOneWidget);
    await events.close();
  });

  testWidgets('chat: contact name as title, admin label, Copy code, read once, paging, send', (tester) async {
    phone.history = [
      for (var i = 0; i < 60; i++) providerMessage(id: 100 + i, threadId: 1, body: 'Old $i', date: today.subtract(Duration(days: 40, minutes: i)).millisecondsSinceEpoch),
      providerMessage(id: 1, threadId: 1, body: 'Msimbo wako ni 4821', date: today.subtract(const Duration(minutes: 5)).millisecondsSinceEpoch),
      providerMessage(id: 2, threadId: 1, outbound: true, body: 'Karibu', status: 'delivered', date: today.millisecondsSinceEpoch),
    ];
    await db.into(db.outboundStates).insert(OutboundStatesCompanion.insert(clientUuid: 'u', state: 'delivered', providerId: const Value(2), sentBy: const Value('Amina Juma'), updatedAt: 0));
    final container = ProviderContainer(overrides: overrides(phone, db));
    addTearDown(container.dispose);
    await container.read(threadsProvider.notifier).refresh();
    await tester.pumpWidget(harness(const ChatScreen(threadId: 1), phone: phone, db: db, container: container));
    await tester.pumpAndSettle();
    expect(find.text('Neema Mushi'), findsOneWidget); // the saved name, not the number
    expect(find.text('+255 754 210 331'), findsOneWidget); // number as subtitle
    expect(find.text('Sent by admin · Amina Juma'), findsOneWidget);
    expect(find.text('Copy code 4821'), findsOneWidget);
    expect(find.text('Delivered'), findsOneWidget);
    expect(phone.count('read:1'), 1);
    expect(phone.calls.where((c) => c.startsWith('messages:1')).toList(), ['messages:1:-']); // the newest page only
    await tester.fling(find.byType(ListView), const Offset(0, 3000), 3000);
    await tester.pumpAndSettle();
    expect(phone.calls.where((c) => c.startsWith('messages:1:') && !c.endsWith('-')), isNotEmpty); // older page on scroll
    await tester.enterText(find.byType(TextField), 'Asante');
    await tester.pump();
    expect(find.text('1 SMS · 154 left'), findsOneWidget);
    await tester.tap(find.byTooltip('Send'));
    await tester.pumpAndSettle();
    expect(phone.sent.single.body, 'Asante');
    expect(phone.sent.single.origin, 'phone');
    expect(phone.sent.single.addresses, ['+255754210331']);
  });

  testWidgets('opening a read conversation writes nothing', (tester) async {
    phone.history = [providerMessage(id: 5, threadId: 2, address: '0713402118', body: 'Invoice please')];
    final container = ProviderContainer(overrides: overrides(phone, db));
    addTearDown(container.dispose);
    await container.read(threadsProvider.notifier).refresh();
    await tester.pumpWidget(harness(const ChatScreen(threadId: 2), phone: phone, db: db, container: container));
    await tester.pumpAndSettle();
    expect(phone.count('read:'), 0);
  });

  testWidgets('a cached chat shows its messages before the phone answers', (tester) async {
    phone.history = [providerMessage(id: 7, threadId: 3, address: 'M-PESA', body: 'Imethibitishwa')];
    final repo = ConversationsRepository(phone: phone, db: db);
    await repo.messages(3); // fills the cache
    final gate = Completer<void>();
    phone.gate = gate.future;
    await tester.pumpWidget(harness(const ChatScreen(threadId: 3), phone: phone, db: db));
    await tester.pump();
    await tester.pump();
    expect(find.text('Imethibitishwa'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNothing);
    gate.complete();
    await tester.pumpAndSettle();
  });

  testWidgets('day separators compare the whole date', (tester) async {
    final sept = DateTime(today.year - 1, 9, 3, 10).millisecondsSinceEpoch;
    final oct = DateTime(today.year - 1, 10, 3, 10).millisecondsSinceEpoch;
    phone.history = [providerMessage(id: 1, threadId: 1, body: 'September', date: sept), providerMessage(id: 2, threadId: 1, body: 'October', date: oct)];
    await tester.pumpWidget(harness(const ChatScreen(threadId: 1), phone: phone, db: db));
    await tester.pumpAndSettle();
    expect(find.textContaining('September 3'), findsOneWidget);
    expect(find.textContaining('October 3'), findsOneWidget); // same day of the month, different month: two separators
  });

  testWidgets('composer counts Unicode segments and saves drafts', (tester) async {
    await tester.pumpWidget(harness(Scaffold(body: Composer(draftKey: 'thread:9', onSend: (body, sim, at) async {})), phone: phone, db: db));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Habari 😊');
    await tester.pump();
    expect(find.text('1 SMS · 61 left'), findsOneWidget);
    expect(find.text('SIM 1'), findsOneWidget); // dual SIM picker
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    expect(await ConversationsRepository(phone: phone, db: db).draft('thread:9'), 'Habari 😊');
  });

  testWidgets('composer keeps the text and explains when the phone refuses to send', (tester) async {
    await tester.pumpWidget(harness(Scaffold(body: Composer(draftKey: 'thread:9', onSend: (body, sim, at) async => throw const SendRefused(1001))), phone: phone, db: db));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Habari');
    await tester.pump();
    await tester.tap(find.byIcon(Icons.send));
    await tester.pumpAndSettle();
    expect(find.textContaining('Message not sent'), findsOneWidget);
    expect(find.text('Habari'), findsOneWidget);
  });
}
