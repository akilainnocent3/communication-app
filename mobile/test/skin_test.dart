import 'package:cm_sms/features/chat/message_bubble.dart';
import 'package:cm_sms/l10n/app_localizations.dart';
import 'package:cm_sms/providers.dart';
import 'package:cm_sms/ui/skin/skin.dart';
import 'package:cm_sms/ui/skin/tokens.dart';
import 'package:cm_sms/ui/widgets/skin_preview.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

void main() {
  test('"Match my phone" picks the look of the phone\'s own Messages app', () {
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

  test('every skin defines every token in light and dark', () {
    for (final spec in skins) {
      for (final brightness in Brightness.values) {
        final tokens = buildSkinTheme(spec, brightness).extension<SkinTokens>()!;
        expect(tokens.id, spec.id);
        expect(tokens.outgoing, isNot(tokens.incoming), reason: spec.id);
        // Text on bubbles stays readable (WCAG AA for normal text is 4.5).
        double contrast(Color a, Color b) {
          final (l1, l2) = (a.computeLuminance(), b.computeLuminance());
          return (l1 > l2 ? l1 + 0.05 : l2 + 0.05) / (l1 > l2 ? l2 + 0.05 : l1 + 0.05);
        }
        expect(contrast(tokens.onOutgoing, tokens.outgoing), greaterThan(3.0), reason: '${spec.id} $brightness sent');
        expect(contrast(tokens.onIncoming, tokens.incoming), greaterThan(4.5), reason: '${spec.id} $brightness received');
      }
    }
  });

  test('appearance overrides recolour sent bubbles and choose swipe actions', () {
    final theme = buildSkinTheme(skinById('pixel'), Brightness.light,
        overrides: const AppearanceOverrides(bubbleColour: Color(0xFF8E44AD), swipeLeft: SwipeAction.none, swipeRight: SwipeAction.delete));
    final tokens = theme.extension<SkinTokens>()!;
    expect(tokens.outgoing, const Color(0xFF8E44AD));
    expect(tokens.onOutgoing, Colors.white);
    expect(tokens.swipeLeft, SwipeAction.none);
    expect(tokens.swipeRight, SwipeAction.delete);
  });

  group('goldens: list row, bubbles and compose bar', () {
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
          expect(find.byType(MessageBubble), findsNWidgets(2));
          await expectLater(find.byType(SkinPreview), matchesGoldenFile('goldens/${spec.id}_${brightness.name}.png'));
        });
      }
    }
  });
}
