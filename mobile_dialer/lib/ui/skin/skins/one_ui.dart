import 'package:flutter/material.dart';

import '../skin.dart';
import '../tokens.dart';

/// One UI style (Samsung's Phone app): a large centred "Phone" title that fills the top of the screen and collapses on
/// scroll (content stays in reach on tall phones), text-only Keypad / Recents / Contacts tabs with an underline, lists
/// in very round white cards on a soft grey page with no shadows, recents led by the call-type icon, flat light keypad
/// digits and one green call button per SIM.
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
    rowHeight: 78, avatarSize: 40, dividers: true, groupedList: true, listRadius: 26, listInset: 4,
    pageBackground: dark ? Colors.black : const Color(0xFFF6F6F6), listSurface: dark ? const Color(0xFF171717) : const Color(0xFFFCFCFC),
    secondaryText: dark ? const Color(0xFF9A9A9A) : const Color(0xFF8A8A8A), divider: dark ? const Color(0xFF2A2A2A) : const Color(0xFFE6E6E6),
    unread: UnreadStyle.countBadge, badge: const Color(0xFFF56E00), onBadge: Colors.white,
    header: HeaderStyle.largeCollapsing, expandedHeaderFraction: 0.36, centeredLargeTitle: true, tabs: true, phoneTabs: PhoneTabStyle.text,
    compose: ComposeButtonStyle.roundFab, composeColor: dark ? const Color(0xFF2D63D4) : blue, onComposeColor: Colors.white,
    composePlusButton: true, composeFieldRadius: 22, composeField: dark ? const Color(0xFF232325) : Colors.white, sendFilled: false,
    swipeLeft: SwipeAction.delete, swipeRight: SwipeAction.read,
    titleSize: 20, largeTitleSize: 34, rowTitleSize: 17, snippetSize: 13, rowTitleWeight: FontWeight.w400,
    keypadKey: KeypadKeyStyle.flat, keypadKeySize: 76, keypadDigitWeight: FontWeight.w300, callButton: const Color(0xFF13A865),
    missedCall: const Color(0xFFE5372E), recentsRowHeight: 60, recentsAvatar: false, dualSimCallButtons: true,
    avatarColors: const [Color(0xFFF9B233), Color(0xFFB48CE8), Color(0xFF5BB6E8), Color(0xFF7CC576), Color(0xFFF07A7A)],
  );
}
