import 'package:flutter/material.dart';

import '../skin.dart';
import '../tokens.dart';

/// ColorOS style (Oppo, Realme, OnePlus): a large title that collapses, green sent bubbles, flat rows with inset
/// dividers and a round "+" button.
const colorOsSkin = SkinSpec(id: 'color_os', seed: Color(0xFF22A35A), cardRadius: 16, tokens: _tokens);

SkinTokens _tokens(Brightness brightness, ColorScheme scheme) {
  final dark = brightness == Brightness.dark;
  const green = Color(0xFF22A35A);
  return SkinTokens(
    id: 'color_os',
    incoming: dark ? const Color(0xFF262626) : const Color(0xFFF1F1F1), onIncoming: dark ? const Color(0xFFEAEAEA) : const Color(0xFF141414),
    outgoing: dark ? const Color(0xFF1C8A4C) : green, onOutgoing: Colors.white, admin: dark ? const Color(0xFF115E59) : const Color(0xFF0F766E), onAdmin: Colors.white,
    bubbleRadius: 18, tailRadius: 6, time: TimePlacement.below,
    rowHeight: 78, avatarSize: 46, dividers: true,
    pageBackground: dark ? const Color(0xFF0E0E0E) : const Color(0xFFFAFAFA), listSurface: dark ? const Color(0xFF0E0E0E) : const Color(0xFFFAFAFA),
    unread: UnreadStyle.countBadge, badge: green, onBadge: Colors.white,
    header: HeaderStyle.largeCollapsing, expandedHeaderFraction: 0.22,
    compose: ComposeButtonStyle.roundFab, composeColor: green, onComposeColor: Colors.white,
    composePlusButton: true, composeFieldRadius: 20, composeField: dark ? const Color(0xFF1D1D1D) : Colors.white, sendFilled: true,
    swipeLeft: SwipeAction.delete, swipeRight: SwipeAction.archive,
    titleSize: 20, largeTitleSize: 32, rowTitleSize: 16, snippetSize: 14, rowTitleWeight: FontWeight.w600,
  );
}
