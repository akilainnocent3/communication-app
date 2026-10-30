import 'package:ocm_phone/config.dart';
import 'package:ocm_phone/core/api/transport.dart';
import 'package:ocm_phone/core/db/database.dart';
import 'package:ocm_phone/core/services.dart';
import 'package:ocm_phone/core/text/phone_format.dart';
import 'package:ocm_phone/data/phone_gateway.dart';
import 'package:ocm_phone/features/phone/dialer_gateway.dart';
import 'package:ocm_phone/features/phone/phone_screen.dart';
import 'package:ocm_phone/features/phone/t9.dart';
import 'package:ocm_phone/l10n/app_localizations.dart';
import 'package:ocm_phone/platform/telephony_api.g.dart';
import 'package:ocm_phone/providers.dart';
import 'package:ocm_phone/ui/skin/skin.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

class FakeDialer implements DialerGateway {
  final placed = <(String, int?, String, String?)>[];
  final reported = <(String, String)>[];
  List<SimInfo> simList = [SimInfo(subscriptionId: 1, slot: 0, carrier: 'Vodacom', countryIso: 'tz', isDefault: true)];
  @override
  Future<CallsStatus> status() async => CallsStatus(enabled: true, isDefaultDialer: true, dialerRoleAvailable: true, canUseFullScreenIntent: true, missingPermissions: []);
  @override
  Future<String> placeCall(String number, {int? subscriptionId, String origin = 'manual', String? callbackTask}) async {
    placed.add((number, subscriptionId, origin, callbackTask));
    return 'placed';
  }
  @override
  Future<List<RecentCall>> recent(int limit, int offset) async => recents;
  @override
  Future<List<PhoneContact>> contacts(int limit) async => contactList;
  @override
  Future<List<CallbackTaskData>> callbacks() async => tasks;
  @override
  Future<void> reportCallback(String id, String state) async => reported.add((id, state));
  @override
  Future<void> deleteRecent(int id) async {}
  @override
  Future<List<SimInfo>> sims() async => simList;
  @override
  Future<void> addContact(String number) async {}
  final messaged = <String>[];
  @override
  Future<void> message(String number) async => messaged.add(number);
  final tones = <String>[];
  @override
  Future<void> dialTone(String key) async => tones.add(key);
}

final at = DateTime(2026, 10, 28, 9, 30).millisecondsSinceEpoch;
final contactList = [
  PhoneContact(name: 'Neema Mushi', number: '+255754210331', starred: true),
  PhoneContact(name: 'Baraka Mwakyusa', number: '0713402118', starred: false, directoryName: 'Baraka (Mwanza Cement)'),
  PhoneContact(name: 'Juma Hassan', number: '+255765330912', starred: false),
];
final recents = [
  RecentCall(id: 1, number: '+255754210331', name: 'Neema Mushi', nameSource: 'contact', direction: 'in', result: 'missed', date: at, durationSeconds: 0),
  RecentCall(id: 2, number: '+255754210331', name: 'Neema Mushi', nameSource: 'contact', direction: 'in', result: 'missed', date: at - 60000, durationSeconds: 0),
  RecentCall(id: 3, number: '+255688120554', name: 'Rehema (Arusha Hardware)', nameSource: 'directory', direction: 'out', result: 'answered', date: at - 3600000, durationSeconds: 95),
  RecentCall(id: 4, number: '+255765330912', name: 'Juma Hassan', nameSource: 'contact', direction: 'in', result: 'answered', date: at - 7200000, durationSeconds: 30),
];
final tasks = [
  CallbackTaskData(id: 't1', number: '+255713402118', name: 'Baraka Mwakyusa', reason: 'Quote for 40 bags', requestedBy: 'Halima', priority: 'high', dueAt: at, state: 'notified'),
];

Widget harness(Widget child, FakeDialer dialer, {String skin = 'pixel', Brightness brightness = Brightness.light, AppServices? services}) => ProviderScope(
      overrides: [
        settingsProvider.overrideWith(MemorySettings.new),
        dialerProvider.overrideWithValue(dialer),
        clockProvider.overrideWithValue(() => DateTime(2026, 10, 28, 12)),
        if (services != null) servicesProvider.overrideWithValue(services),
      ],
      child: MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: buildSkinTheme(skinById(skin), brightness),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(body: child),
      ),
    );

void main() {
  test('T9 matches name words through the keypad letters, and numbers (local or international)', () {
    String name(PhoneContact c) => c.name;
    String number(PhoneContact c) => c.number;
    expect(t9Search(contactList, '6336', name: name, number: number).map((c) => c.name), ['Neema Mushi']); // NEEM(a)
    expect(t9Search(contactList, '687', name: name, number: number).map((c) => c.name), ['Neema Mushi']); // MUS(hi)
    expect(t9Search(contactList, '0754', name: name, number: number).map((c) => c.name), ['Neema Mushi']); // local form of +255 754
    expect(t9Search(contactList, '402', name: name, number: number).map((c) => c.name), ['Baraka Mwakyusa']); // contains
    expect(t9Search(contactList, '', name: name, number: number), isEmpty);
    expect(t9Digits('Juma'), '5862');
  });

  test('recents group consecutive calls with the same number and kind on the same day', () {
    final groups = groupRecents(recents);
    expect(groups.map((g) => g.length), [2, 1, 1]);
  });

  testWidgets('keypad dials what was typed; T9 suggests contacts; long-press 0 is +', (tester) async {
    final dialer = FakeDialer();
    await tester.pumpWidget(harness(const KeypadTab(), dialer));
    await tester.pumpAndSettle();
    for (final key in ['6', '3', '3', '6']) {
      await tester.tap(find.byKey(Key('key-$key')));
    }
    await tester.pumpAndSettle();
    expect(find.text('Neema Mushi'), findsOneWidget);
    await tester.tap(find.text('Neema Mushi'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('call-button')));
    await tester.pumpAndSettle();
    expect(dialer.placed.single.$1, '+255754210331');
    expect(dialer.placed.single.$3, 'manual');
  });

  testWidgets('keypad keys play the dial tone; Call on an empty keypad brings back the last number dialled', (tester) async {
    final dialer = FakeDialer();
    await tester.pumpWidget(harness(const KeypadTab(), dialer));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('key-5')));
    await tester.tap(find.byKey(const Key('key-#')));
    expect(dialer.tones, ['5', '#']);
    await tester.pump();
    for (var i = 0; i < 2; i++) {
      await tester.tap(find.byIcon(Icons.backspace_outlined));
      await tester.pump();
    }
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('call-button')));
    await tester.pumpAndSettle();
    expect(dialer.placed, isEmpty); // the first tap only fills the number
    expect(find.text(formatNumber('+255688120554')), findsOneWidget);
    await tester.tap(find.byKey(const Key('call-button')));
    await tester.pumpAndSettle();
    expect(dialer.placed.single.$1, '+255688120554');
  });

  testWidgets('switching tabs keeps the typed number', (tester) async {
    final host = TelephonyHostApi();
    final db = AppDatabase.memory();
    addTearDown(db.close);
    final services = AppServices(
      config: const AppConfig(allowedServerHosts: [], pinnedSpki: [], fcmEnabled: false, appVersion: 'test'),
      host: host, db: db, phone: PlatformPhoneGateway(host), transport: NativeHttpTransport(host),
      startup: StartupState(databasePath: '', databaseKey: '', isDefaultDialer: true, manufacturer: 'Google', brand: 'google', sdkInt: 35, removed: false),
    )..session = Session(server: Uri.parse('https://ocm.test'), deviceId: 'd', deviceCode: 'P-1', deviceName: 'Phone');
    await tester.pumpWidget(harness(const PhoneScreen(), FakeDialer(), services: services));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('key-7')));
    await tester.tap(find.text('Recents'));
    await tester.pumpAndSettle();
    expect(find.text('Neema Mushi (2)'), findsOneWidget);
    await tester.tap(find.text('Keypad'));
    await tester.pumpAndSettle();
    expect(tester.widget<Text>(find.byKey(const Key('keypad-number'))).data, '7');
  });

  testWidgets('recents have day headers; contacts have letter headers and a tap opens Call / Message', (tester) async {
    final dialer = FakeDialer();
    await tester.pumpWidget(harness(const RecentsTab(), dialer));
    await tester.pumpAndSettle();
    expect(find.text('Today'), findsOneWidget);
    await tester.pumpWidget(harness(const ContactsTab(), dialer));
    await tester.pumpAndSettle();
    expect(find.text('B'), findsOneWidget);
    expect(find.text('J'), findsOneWidget);
    await tester.tap(find.text('Juma Hassan'));
    await tester.pumpAndSettle();
    expect(dialer.placed, isEmpty); // a stray tap never calls
    await tester.tap(find.text('Message'));
    await tester.pumpAndSettle();
    expect(dialer.messaged.single, '+255765330912');
  });

  testWidgets('long-press 0 types +; long-press 1 on an empty keypad calls voicemail', (tester) async {
    final dialer = FakeDialer();
    await tester.pumpWidget(harness(const KeypadTab(), dialer));
    await tester.pumpAndSettle();
    await tester.longPress(find.byKey(const Key('key-1')));
    await tester.pumpAndSettle();
    expect(dialer.placed.single.$1, 'voicemail');
    await tester.longPress(find.byKey(const Key('key-0')));
    await tester.pumpAndSettle();
    expect(find.textContaining('+'), findsWidgets);
  });

  testWidgets('dual-SIM: the person chooses the SIM', (tester) async {
    final dialer = FakeDialer()..simList = [
      SimInfo(subscriptionId: 1, slot: 0, carrier: 'Vodacom', countryIso: 'tz', isDefault: true),
      SimInfo(subscriptionId: 2, slot: 1, carrier: 'Airtel', countryIso: 'tz', isDefault: false),
    ];
    await tester.pumpWidget(harness(const KeypadTab(initial: '0754210331'), dialer));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('call-button')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Airtel'));
    await tester.pumpAndSettle();
    expect(dialer.placed.single.$2, 2);
  });

  testWidgets('recents: grouped rows, directory names marked, call back is a redial', (tester) async {
    final dialer = FakeDialer();
    await tester.pumpWidget(harness(const RecentsTab(), dialer));
    await tester.pumpAndSettle();
    expect(find.text('Neema Mushi (2)'), findsOneWidget);
    expect(find.text('Company directory'), findsOneWidget);
    await tester.tap(find.byTooltip('Call').first);
    await tester.pumpAndSettle();
    expect(dialer.placed.single, ('+255754210331', 1, 'redial', null));
  });

  testWidgets('call-backs: Call places the call for the task; Done is reported', (tester) async {
    final dialer = FakeDialer();
    await tester.pumpWidget(harness(const CallbacksTab(), dialer));
    await tester.pumpAndSettle();
    expect(find.text('Quote for 40 bags'), findsOneWidget);
    await tester.tap(find.widgetWithText(FilledButton, 'Call'));
    await tester.pumpAndSettle();
    expect(dialer.placed.single, ('+255713402118', 1, 'callback_task', 't1'));
    await tester.tap(find.text('Done'));
    await tester.pumpAndSettle();
    expect(dialer.reported.single, ('t1', 'done'));
  });

  group('goldens: keypad and recents', () {
    for (final spec in skins) {
      for (final brightness in Brightness.values) {
        testWidgets('${spec.id} ${brightness.name}', (tester) async {
          tester.view.physicalSize = const Size(2160, 2100); // two 400 dp phone screens side by side
          tester.view.devicePixelRatio = 2.7;
          addTearDown(tester.view.reset);
          await tester.pumpWidget(harness(
            RepaintBoundary(child: Row(children: const [Expanded(child: KeypadTab(initial: '0754 210')), Expanded(child: RecentsTab())])),
            FakeDialer(), skin: spec.id, brightness: brightness,
          ));
          await tester.pumpAndSettle();
          await expectLater(find.byType(RepaintBoundary).first, matchesGoldenFile('goldens/phone_${spec.id}_${brightness.name}.png'));
        });
      }
    }
  });
}
