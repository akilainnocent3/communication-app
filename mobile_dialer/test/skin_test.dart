import 'package:ocm_phone/l10n/app_localizations.dart';
import 'package:ocm_phone/providers.dart';
import 'package:ocm_phone/ui/skin/skin.dart';
import 'package:ocm_phone/ui/skin/tokens.dart';
import 'package:ocm_phone/ui/widgets/skin_preview.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

void main() {
  test('"Match my phone" picks the look of the phone\'s own Phone app', () {
    expect(skinForPhone('samsung', 'samsung'), 'one_ui');
    expect(skinForPhone('Google', 'google'), 'pixel');
    expect(skinForPhone('TECNO MOBILE LIMITED', 'TECNO'), 'hios');
    expect(skinForPhone('INFINIX MOBILITY LIMITED', 'Infinix'), 'hios');
    expect(skinForPhone('itel', 'itel'), 'hios');
    expect(skinForPhone('Xiaomi', 'Redmi'), 'hyper_os');
    expect(skinForPhone('Xiaomi', 'POCO'), 'hyper_os');
    expect(skinForPhone('OPPO', 'OPPO'), 'color_os');
    expect(skinForPhone('realme', 'realme'), 'color_os');
    expect(skinForPhone('OnePlus', 'OnePlus'), 'color_os');
    expect(skinForPhone('HMD Global', 'Nokia'), 'pixel'); // everyone else: Material You
  });

  test('the Phone app the phone came with decides before the manufacturer', () {
    expect(skinForPhone('samsung', 'samsung', dialer: 'com.samsung.android.dialer'), 'one_ui');
    expect(skinForPhone('Xiaomi', 'Redmi', dialer: 'com.google.android.dialer'), 'pixel'); // global Xiaomi with Google's Phone
    expect(skinForPhone('OnePlus', 'OnePlus', dialer: 'com.google.android.dialer'), 'pixel');
    expect(skinForPhone('realme', 'realme', dialer: 'com.oplus.dialer'), 'color_os');
    expect(skinForPhone('INFINIX MOBILITY LIMITED', 'Infinix', dialer: 'com.transsion.dialer'), 'hios');
    // AOSP package names are shared by several manufacturers' dialers: the manufacturer decides.
    expect(skinForPhone('Xiaomi', 'Redmi', dialer: 'com.android.contacts'), 'hyper_os');
    expect(skinForPhone('TECNO MOBILE LIMITED', 'TECNO', dialer: 'com.android.dialer'), 'hios');
    expect(skinForPhone('samsung', 'samsung', dialer: ''), 'one_ui');
  });

  test('every skin defines the dialer tokens in light and dark, readable on its page', () {
    double contrast(Color a, Color b) {
      final (l1, l2) = (a.computeLuminance(), b.computeLuminance());
      return (l1 > l2 ? l1 + 0.05 : l2 + 0.05) / (l1 > l2 ? l2 + 0.05 : l1 + 0.05);
    }
    for (final spec in skins) {
      for (final brightness in Brightness.values) {
        final tokens = buildSkinTheme(spec, brightness).extension<SkinTokens>()!;
        expect(tokens.id, spec.id);
        expect(tokens.keypadKeySize, inInclusiveRange(56, 84), reason: spec.id);
        expect(tokens.recentsRowHeight, greaterThanOrEqualTo(56), reason: spec.id);
        // The white handset on the call button, and missed calls on the page (large text / icons: 3.0).
        expect(contrast(Colors.white, tokens.callButton), greaterThan(2.0), reason: '${spec.id} $brightness call');
        expect(contrast(tokens.missedCall, tokens.pageBackground), greaterThan(3.0), reason: '${spec.id} $brightness missed');
      }
    }
  });

  group('goldens: recents row and keypad', () {
    for (final spec in skins) {
      for (final brightness in Brightness.values) {
        testWidgets('${spec.id} ${brightness.name}', (tester) async {
          tester.view.physicalSize = const Size(1080, 1000);
          tester.view.devicePixelRatio = 2.7;
          addTearDown(tester.view.reset);
          await tester.pumpWidget(ProviderScope(
            overrides: [settingsProvider.overrideWith(MemorySettings.new)],
            child: MaterialApp(
              debugShowCheckedModeBanner: false,
              theme: buildSkinTheme(spec, brightness),
              localizationsDelegates: AppLocalizations.localizationsDelegates,
              supportedLocales: AppLocalizations.supportedLocales,
              home: const Scaffold(body: Align(alignment: Alignment.topCenter, child: RepaintBoundary(child: SkinPreview()))),
            ),
          ));
          await tester.pumpAndSettle();
          await expectLater(find.byType(SkinPreview), matchesGoldenFile('goldens/preview_${spec.id}_${brightness.name}.png'));
        });
      }
    }
  });
}
