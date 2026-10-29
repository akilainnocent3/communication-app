import 'package:flutter/material.dart';

import '../skin.dart';
import '../tokens.dart';

/// Company: the app's own teal theme (the look before skins existed).
const companySkin = SkinSpec(id: 'company', seed: Color(0xFF0F766E), cardRadius: 12, tokens: _tokens);

SkinTokens _tokens(Brightness brightness, ColorScheme s) {
  final dark = brightness == Brightness.dark;
  return SkinTokens(
    id: 'company',
    incoming: s.surfaceContainerHighest, onIncoming: s.onSurface, outgoing: s.primary, onOutgoing: s.onPrimary,
    admin: dark ? const Color(0xFF115E59) : const Color(0xFF0F766E), onAdmin: Colors.white,
    bubbleRadius: 18, tailRadius: 4, time: TimePlacement.below,
    rowHeight: 72, avatarSize: 44, dividers: false,
    pageBackground: s.surface, listSurface: s.surface,
    unread: UnreadStyle.countBadge, badge: s.primary, onBadge: s.onPrimary,
    header: HeaderStyle.compact,
    compose: ComposeButtonStyle.extendedFab, composeColor: s.primaryContainer, onComposeColor: s.onPrimaryContainer,
    composePlusButton: false, composeFieldRadius: 24, composeField: s.surfaceContainerHighest, sendFilled: true,
    titleSize: 22, largeTitleSize: 32, rowTitleSize: 16, snippetSize: 14, rowTitleWeight: FontWeight.w500,
    keypadKey: KeypadKeyStyle.rounded, keypadKeySize: 70, callButton: const Color(0xFF0F766E), recentsRowHeight: 68,
  );
}
