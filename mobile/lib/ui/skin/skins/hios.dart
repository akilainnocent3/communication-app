import 'package:flutter/material.dart';

import '../skin.dart';
import '../tokens.dart';

/// HiOS / XOS style (Tecno, Infinix, itel): a compact title bar, brand-blue sent bubbles, larger avatars and more
/// spacing, and a round floating compose button.
const hiosSkin = SkinSpec(id: 'hios', seed: Color(0xFF2F6BFF), cardRadius: 14, tokens: _tokens);

SkinTokens _tokens(Brightness brightness, ColorScheme scheme) {
  final dark = brightness == Brightness.dark;
  const blue = Color(0xFF2F6BFF);
  return SkinTokens(
    id: 'hios',
    incoming: dark ? const Color(0xFF26282C) : const Color(0xFFF0F2F5), onIncoming: dark ? const Color(0xFFEDEDED) : const Color(0xFF1B1B1B),
    outgoing: blue, onOutgoing: Colors.white, admin: dark ? const Color(0xFF115E59) : const Color(0xFF0F766E), onAdmin: Colors.white,
    bubbleRadius: 16, tailRadius: 4, time: TimePlacement.below,
    rowHeight: 84, avatarSize: 54, dividers: true,
    pageBackground: dark ? const Color(0xFF111214) : Colors.white, listSurface: dark ? const Color(0xFF111214) : Colors.white,
    unread: UnreadStyle.countBadge, badge: const Color(0xFFFF3B30), onBadge: Colors.white,
    header: HeaderStyle.compact,
    compose: ComposeButtonStyle.roundFab, composeColor: blue, onComposeColor: Colors.white,
    composePlusButton: true, composeFieldRadius: 20, composeField: dark ? const Color(0xFF1E2024) : const Color(0xFFF3F4F6), sendFilled: true,
    swipeLeft: SwipeAction.delete, swipeRight: SwipeAction.archive,
    titleSize: 20, largeTitleSize: 30, rowTitleSize: 17, snippetSize: 14.5, rowTitleWeight: FontWeight.w600,
  );
}
