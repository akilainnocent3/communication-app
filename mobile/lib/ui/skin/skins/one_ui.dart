import 'package:flutter/material.dart';

import '../skin.dart';
import '../tokens.dart';

/// One UI style (Samsung Messages): a large "Messages" title that fills the top third and collapses on scroll (content
/// stays in reach on tall phones), Conversations / Contacts tabs, the list in one rounded container on a tinted page,
/// blue sent bubbles, light grey received bubbles, small filled count badges, round compose button bottom-right.
const oneUiSkin = SkinSpec(id: 'one_ui', seed: Color(0xFF3E7BFA), cardRadius: 26, tokens: _tokens);

SkinTokens _tokens(Brightness brightness, ColorScheme scheme) {
  final dark = brightness == Brightness.dark;
  const blue = Color(0xFF3E7BFA);
  return SkinTokens(
    id: 'one_ui',
    incoming: dark ? const Color(0xFF2A2A2D) : const Color(0xFFEDEDF0), onIncoming: dark ? const Color(0xFFF2F2F2) : const Color(0xFF111111),
    outgoing: dark ? const Color(0xFF2D63D4) : blue, onOutgoing: Colors.white,
    admin: dark ? const Color(0xFF115E59) : const Color(0xFF0F766E), onAdmin: Colors.white,
    bubbleRadius: 22, tailRadius: 22, time: TimePlacement.below,
    rowHeight: 78, avatarSize: 48, dividers: true, groupedList: true, listRadius: 26,
    pageBackground: dark ? Colors.black : const Color(0xFFF4F4F6), listSurface: dark ? const Color(0xFF171719) : Colors.white,
    unread: UnreadStyle.countBadge, badge: const Color(0xFFF56E00), onBadge: Colors.white,
    header: HeaderStyle.largeCollapsing, expandedHeaderFraction: 0.3, tabs: true,
    compose: ComposeButtonStyle.roundFab, composeColor: dark ? const Color(0xFF2D63D4) : blue, onComposeColor: Colors.white,
    composePlusButton: true, composeFieldRadius: 22, composeField: dark ? const Color(0xFF232325) : Colors.white, sendFilled: false,
    swipeLeft: SwipeAction.delete, swipeRight: SwipeAction.read,
    titleSize: 20, largeTitleSize: 36, rowTitleSize: 16.5, snippetSize: 14, rowTitleWeight: FontWeight.w600,
  );
}
