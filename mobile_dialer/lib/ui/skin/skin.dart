import 'package:flutter/material.dart';

import 'skins/color_os.dart';
import 'skins/company.dart';
import 'skins/hios.dart';
import 'skins/hyper_os.dart';
import 'skins/one_ui.dart';
import 'skins/pixel.dart';
import 'tokens.dart';

/// A look, named by style (no vendor logos, icons or assets: Material icons only).
class SkinSpec {
  const SkinSpec({required this.id, required this.seed, required this.tokens, this.dynamicColor = false, this.cardRadius = 16});
  final String id;
  /// ColorScheme seed when the phone's wallpaper colour is not used.
  final Color seed;
  /// Material You: take the wallpaper colour (Android 12+) instead of [seed].
  final bool dynamicColor;
  final double cardRadius;
  final SkinTokens Function(Brightness brightness, ColorScheme scheme) tokens;
}

const skins = <SkinSpec>[oneUiSkin, pixelSkin, hiosSkin, hyperOsSkin, colorOsSkin, companySkin];

SkinSpec skinById(String id) => skins.firstWhere((s) => s.id == id, orElse: () => pixelSkin);

/// "Match my phone": the look of the Messages app this phone came with.
String skinForPhone(String manufacturer, String brand) {
  final names = '$manufacturer $brand'.toLowerCase();
  bool any(List<String> words) => words.any(names.contains);
  if (any(['samsung'])) return oneUiSkin.id;
  if (any(['google'])) return pixelSkin.id;
  if (any(['tecno', 'infinix', 'itel', 'transsion'])) return hiosSkin.id;
  if (any(['xiaomi', 'redmi', 'poco'])) return hyperOsSkin.id;
  if (any(['oppo', 'realme', 'oneplus', 'oplus'])) return colorOsSkin.id;
  return pixelSkin.id;
}

/// User overrides from Settings → Appearance, applied on top of the skin's tokens.
class AppearanceOverrides {
  const AppearanceOverrides({this.bubbleColour, this.swipeLeft, this.swipeRight});
  final Color? bubbleColour;
  final SwipeAction? swipeLeft, swipeRight;
}

ThemeData buildSkinTheme(SkinSpec spec, Brightness brightness, {ColorScheme? dynamicScheme, AppearanceOverrides overrides = const AppearanceOverrides(), bool compact = false}) {
  final scheme = (spec.dynamicColor ? dynamicScheme : null) ?? ColorScheme.fromSeed(seedColor: spec.seed, brightness: brightness);
  var tokens = spec.tokens(brightness, scheme);
  final bubble = overrides.bubbleColour;
  if (bubble != null) {
    tokens = tokens.copyWith(outgoing: bubble, onOutgoing: ThemeData.estimateBrightnessForColor(bubble) == Brightness.dark ? Colors.white : Colors.black);
  }
  tokens = tokens.copyWith(swipeLeft: overrides.swipeLeft, swipeRight: overrides.swipeRight);
  return ThemeData(
    colorScheme: scheme,
    useMaterial3: true,
    brightness: brightness,
    visualDensity: compact ? VisualDensity.compact : VisualDensity.standard,
    scaffoldBackgroundColor: tokens.pageBackground,
    appBarTheme: AppBarTheme(backgroundColor: tokens.pageBackground, surfaceTintColor: Colors.transparent, scrolledUnderElevation: spec.id == 'company' ? 1 : 0),
    listTileTheme: const ListTileThemeData(contentPadding: EdgeInsets.symmetric(horizontal: 16)),
    cardTheme: CardThemeData(shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(spec.cardRadius))),
    // Predictive back (Android 14+) on every route.
    pageTransitionsTheme: const PageTransitionsTheme(builders: {TargetPlatform.android: PredictiveBackPageTransitionsBuilder()}),
    extensions: [tokens],
  );
}
