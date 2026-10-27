import 'package:cm_sms/app.dart';
import 'package:cm_sms/core/db/database.dart';
import 'package:cm_sms/data/conversations_repository.dart';
import 'package:cm_sms/features/chat/chat_screen.dart';
import 'package:cm_sms/features/compose/composer.dart';
import 'package:cm_sms/features/conversations/conversation_list_screen.dart';
import 'package:cm_sms/l10n/app_localizations.dart';
import 'package:cm_sms/platform/telephony_api.g.dart';
import 'package:cm_sms/providers.dart';
import 'package:drift/drift.dart' show Value;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

Widget harness(Widget child, {required FakePhone phone, required AppDatabase db}) => ProviderScope(
      overrides: [
        repositoryProvider.overrideWithValue(ConversationsRepository(phone: phone, db: db)),
        roleCheckProvider.overrideWith((ref) async => RoleStatus(isDefaultSmsApp: phone.defaultApp, roleAvailable: true)),
        simsProvider.overrideWith((ref) async => [
              SimInfo(subscriptionId: 1, slot: 0, carrier: 'Vodacom', countryIso: 'tz', isDefault: true),
              SimInfo(subscriptionId: 2, slot: 1, carrier: 'Airtel', countryIso: 'tz', isDefault: false),
            ]),
        quickRepliesProvider.overrideWith((ref) async => [{'id': 1, 'title': 'Asante', 'body': 'Asante sana!'}]),
      ],
      child: MaterialApp(localizationsDelegates: AppLocalizations.localizationsDelegates, supportedLocales: AppLocalizations.supportedLocales, home: child),
    );

void main() {
  late AppDatabase db;
  late FakePhone phone;
  final today = DateTime.now();

  setUp(() {
    db = AppDatabase.memory();
    phone = FakePhone()
      ..names = {'+255754210331': 'Neema Mushi'}
      ..threadList = [
        ThreadSummary(threadId: 1, addresses: ['+255754210331'], snippet: 'Habari, bei gani?', date: today.millisecondsSinceEpoch, unreadCount: 2, messageCount: 3, hasMms: false),
        ThreadSummary(threadId: 2, addresses: ['0713402118'], snippet: 'Invoice please', date: today.subtract(const Duration(hours: 1)).millisecondsSinceEpoch, unreadCount: 0, messageCount: 1, hasMms: false),
        ThreadSummary(threadId: 3, addresses: ['M-PESA'], snippet: 'Imethibitishwa', date: today.subtract(const Duration(hours: 2)).millisecondsSinceEpoch, unreadCount: 0, messageCount: 1, hasMms: false),
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
    final titles = tester.widgetList<ListTile>(find.byType(ListTile)).map((tile) => ((tile.title as Row).children.first as Expanded).child as Text).map((t) => t.data).toList();
    expect(titles.first, 'M-PESA'); // pinned
    expect(find.text('Start chat'), findsOneWidget);
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

  testWidgets('chat labels admin messages, offers Copy code and sends from the composer', (tester) async {
    phone.history = [
      providerMessage(id: 1, threadId: 1, body: 'Msimbo wako ni 4821', date: today.subtract(const Duration(minutes: 5)).millisecondsSinceEpoch),
      providerMessage(id: 2, threadId: 1, outbound: true, body: 'Karibu', status: 'delivered', date: today.millisecondsSinceEpoch),
    ];
    await db.into(db.outboundStates).insert(OutboundStatesCompanion.insert(clientUuid: 'u', state: 'delivered', providerId: const Value(2), sentBy: const Value('Amina Juma'), updatedAt: 0));
    await tester.pumpWidget(harness(const ChatScreen(threadId: 1), phone: phone, db: db));
    await tester.pumpAndSettle();
    expect(find.text('Sent by admin · Amina Juma'), findsOneWidget);
    expect(find.text('Copy code 4821'), findsOneWidget);
    expect(find.text('Delivered'), findsOneWidget);
    expect(phone.calls, contains('read:1'));
    await tester.enterText(find.byType(TextField), 'Asante');
    await tester.pump();
    expect(find.text('1 SMS · 154 left'), findsOneWidget);
    await tester.tap(find.byTooltip('Send'));
    await tester.pumpAndSettle();
    expect(phone.sent.single.body, 'Asante');
    expect(phone.sent.single.origin, 'phone');
    expect(phone.sent.single.addresses, ['+255754210331']);
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
}
