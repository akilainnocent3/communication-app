import 'package:flutter/material.dart';

/// Material 3 with the phone's dynamic colour when available, company green otherwise.
const seed = Color(0xFF0F766E);

/// Admin-origin bubbles use a distinct colour in both themes.
const adminBubbleLight = Color(0xFF0F766E);
const adminBubbleDark = Color(0xFF115E59);

ThemeData buildTheme(ColorScheme? dynamicScheme, Brightness brightness, double textScale) {
  final scheme = dynamicScheme ?? ColorScheme.fromSeed(seedColor: seed, brightness: brightness);
  return ThemeData(
    colorScheme: scheme,
    useMaterial3: true,
    brightness: brightness,
    visualDensity: VisualDensity.standard,
    appBarTheme: AppBarTheme(backgroundColor: scheme.surface, scrolledUnderElevation: 1),
    listTileTheme: const ListTileThemeData(contentPadding: EdgeInsets.symmetric(horizontal: 16)),
  );
}
