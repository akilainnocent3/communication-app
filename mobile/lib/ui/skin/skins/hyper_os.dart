import 'package:flutter/material.dart';

import '../skin.dart';
import '../tokens.dart';

/// HyperOS / MIUI style (Xiaomi, Redmi, POCO): a large left-aligned title with a search field under it, flat white
/// (or black) surfaces without dividers, red unread dots and a round "+" button.
const hyperOsSkin = SkinSpec(id: 'hyper_os', seed: Color(0xFF3482FF), cardRadius: 18, tokens: _tokens);

SkinTokens _tokens(Brightness brightness, ColorScheme scheme) {
  final dark = brightness == Brightness.dark;
  const blue = Color(0xFF3482FF);
  return SkinTokens(
    id: 'hyper_os',
    incoming: dark ? const Color(0xFF242424) : const Color(0xFFF2F2F2), onIncoming: dark ? const Color(0xFFE6E6E6) : const Color(0xFF000000),
    outgoing: blue, onOutgoing: Colors.white, admin: dark ? const Color(0xFF115E59) : const Color(0xFF0F766E), onAdmin: Colors.white,
    bubbleRadius: 18, tailRadius: 18, time: TimePlacement.below,
    rowHeight: 78, avatarSize: 48, dividers: false,
    pageBackground: dark ? Colors.black : Colors.white, listSurface: dark ? Colors.black : Colors.white,
    unread: UnreadStyle.dot, badge: const Color(0xFFFF4A3D), onBadge: Colors.white,
    header: HeaderStyle.largeWithSearch,
    compose: ComposeButtonStyle.roundFab, composeColor: blue, onComposeColor: Colors.white,
    composePlusButton: true, composeFieldRadius: 18, composeField: dark ? const Color(0xFF1C1C1C) : const Color(0xFFF2F2F2), sendFilled: false,
    swipeLeft: SwipeAction.delete, swipeRight: SwipeAction.read,
    titleSize: 20, largeTitleSize: 34, rowTitleSize: 16.5, snippetSize: 14, rowTitleWeight: FontWeight.w600,
  );
}
