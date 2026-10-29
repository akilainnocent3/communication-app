import 'package:flutter/material.dart';

import '../skin.dart';
import '../tokens.dart';

/// Pixel / Material You style (Google Messages): the wallpaper's colours on Android 12+, a rounded search bar as the
/// header, an extended "Start chat" button, a plain Material 3 list, tonal sent bubbles, surface-container received
/// bubbles, and a compose bar with "+" and a fully rounded "Text message" field.
const pixelSkin = SkinSpec(id: 'pixel', seed: Color(0xFF1A73E8), dynamicColor: true, cardRadius: 20, tokens: _tokens);

SkinTokens _tokens(Brightness brightness, ColorScheme s) => SkinTokens(
      id: 'pixel',
      incoming: s.surfaceContainerHighest, onIncoming: s.onSurface, outgoing: s.primaryContainer, onOutgoing: s.onPrimaryContainer,
      admin: s.tertiaryContainer, onAdmin: s.onTertiaryContainer,
      bubbleRadius: 20, tailRadius: 4, time: TimePlacement.below,
      rowHeight: 76, avatarSize: 44, dividers: false,
      pageBackground: s.surface, listSurface: s.surface,
      unread: UnreadStyle.countBadge, badge: s.primary, onBadge: s.onPrimary,
      header: HeaderStyle.searchPill,
      compose: ComposeButtonStyle.extendedFab, composeColor: s.primaryContainer, onComposeColor: s.onPrimaryContainer,
      composePlusButton: true, composeFieldRadius: 28, composeField: s.surfaceContainerHigh, sendFilled: true,
      swipeLeft: SwipeAction.archive, swipeRight: SwipeAction.archive,
      titleSize: 22, largeTitleSize: 32, rowTitleSize: 16, snippetSize: 14, rowTitleWeight: FontWeight.w500,
      keypadKey: KeypadKeyStyle.circle, keypadKeySize: 72, callButton: const Color(0xFF1E8E3E), missedCall: s.error, recentsRowHeight: 68,
    );
