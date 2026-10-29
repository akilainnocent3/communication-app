import 'dart:ui' show lerpDouble;

import 'package:flutter/material.dart';

/// How the conversation list's header looks (the one layout choice a skin makes besides the compose button).
enum HeaderStyle {
  /// Big title that collapses into a compact bar on scroll (One UI, ColorOS).
  largeCollapsing,
  /// A plain compact app bar (HiOS/XOS, Company).
  compact,
  /// A rounded search field as the header, menu at the side (Pixel / Material You).
  searchPill,
  /// A large left-aligned title with a search field under it (HyperOS / MIUI).
  largeWithSearch,
}

enum ComposeButtonStyle { extendedFab, roundFab, headerIcon }

enum UnreadStyle { countBadge, dot }

enum AvatarShape { circle, rounded }

enum TimePlacement { below, inside }

enum SwipeAction { archive, delete, read, none }

/// Dialer keypad keys: filled circles (Pixel, HiOS), rounded squares (Company) or flat digits on the page (One UI,
/// HyperOS, ColorOS).
enum KeypadKeyStyle { circle, rounded, flat }

/// Everything a skin decides, resolved for one brightness. Widgets read these and nothing else: no screen asks which
/// skin is active. Values live in `lib/ui/skin/skins/<skin>.dart`, one file per skin, so they can be tuned without
/// touching widgets.
@immutable
class SkinTokens extends ThemeExtension<SkinTokens> {
  const SkinTokens({
    required this.id,
    required this.incoming, required this.onIncoming, required this.outgoing, required this.onOutgoing, required this.admin, required this.onAdmin,
    this.bubbleRadius = 20, this.tailRadius = 6, this.bubbleMaxWidth = 0.78, this.time = TimePlacement.below,
    this.rowHeight = 76, this.avatarSize = 48, this.avatarShape = AvatarShape.circle, this.dividers = false, this.groupedList = false,
    required this.pageBackground, required this.listSurface, this.listRadius = 0,
    this.unread = UnreadStyle.countBadge, required this.badge, required this.onBadge,
    this.header = HeaderStyle.compact, this.expandedHeaderFraction = 0.0, this.tabs = false,
    this.compose = ComposeButtonStyle.extendedFab, required this.composeColor, required this.onComposeColor,
    this.composePlusButton = false, this.composeFieldRadius = 24, required this.composeField, this.sendFilled = true,
    this.swipeLeft = SwipeAction.archive, this.swipeRight = SwipeAction.archive,
    this.titleSize = 22, this.largeTitleSize = 34, this.rowTitleSize = 16, this.snippetSize = 14, this.rowTitleWeight = FontWeight.w500,
    this.keypadKey = KeypadKeyStyle.circle, this.keypadLetters = true, this.keypadKeySize = 72, this.callButton = const Color(0xFF16A34A),
    this.missedCall = const Color(0xFFDC2626), this.recentsRowHeight = 68,
  });

  final String id;

  // Bubbles.
  final Color incoming, onIncoming, outgoing, onOutgoing, admin, onAdmin;
  final double bubbleRadius;
  /// Corner on the sender's side at the bottom (a small radius reads as the "tail").
  final double tailRadius;
  final double bubbleMaxWidth;
  final TimePlacement time;

  // Conversation list.
  /// Comfortable row height (logical px at text scale 1); compact density takes 12 off.
  final double rowHeight;
  final double avatarSize;
  final AvatarShape avatarShape;
  final bool dividers;
  /// One UI: the rows sit in one rounded container on a tinted page.
  final bool groupedList;
  final Color pageBackground;
  final Color listSurface;
  final double listRadius;
  final UnreadStyle unread;
  final Color badge, onBadge;

  // Header and compose.
  final HeaderStyle header;
  /// Large headers: how much of the screen height the expanded title takes (reachability on tall phones).
  final double expandedHeaderFraction;
  final bool tabs;
  final ComposeButtonStyle compose;
  final Color composeColor, onComposeColor;
  final bool composePlusButton;
  final double composeFieldRadius;
  final Color composeField;
  final bool sendFilled;
  final SwipeAction swipeLeft, swipeRight;

  // Typography.
  final double titleSize, largeTitleSize, rowTitleSize, snippetSize;
  final FontWeight rowTitleWeight;

  // Dialer (Phone: keypad, recents).
  final KeypadKeyStyle keypadKey;
  final bool keypadLetters;
  final double keypadKeySize;
  final Color callButton, missedCall;
  final double recentsRowHeight;

  double rowExtent({required bool compact, required double textScale}) => (rowHeight - (compact ? 12 : 0)) + (textScale - 1) * 30;

  static SkinTokens of(BuildContext context) => Theme.of(context).extension<SkinTokens>()!;

  @override
  SkinTokens copyWith({Color? outgoing, Color? onOutgoing, SwipeAction? swipeLeft, SwipeAction? swipeRight}) => SkinTokens(
        id: id, incoming: incoming, onIncoming: onIncoming, outgoing: outgoing ?? this.outgoing, onOutgoing: onOutgoing ?? this.onOutgoing, admin: admin, onAdmin: onAdmin,
        bubbleRadius: bubbleRadius, tailRadius: tailRadius, bubbleMaxWidth: bubbleMaxWidth, time: time, rowHeight: rowHeight, avatarSize: avatarSize,
        avatarShape: avatarShape, dividers: dividers, groupedList: groupedList, pageBackground: pageBackground, listSurface: listSurface, listRadius: listRadius,
        unread: unread, badge: badge, onBadge: onBadge, header: header, expandedHeaderFraction: expandedHeaderFraction, tabs: tabs, compose: compose,
        composeColor: composeColor, onComposeColor: onComposeColor, composePlusButton: composePlusButton, composeFieldRadius: composeFieldRadius,
        composeField: composeField, sendFilled: sendFilled, swipeLeft: swipeLeft ?? this.swipeLeft, swipeRight: swipeRight ?? this.swipeRight,
        titleSize: titleSize, largeTitleSize: largeTitleSize, rowTitleSize: rowTitleSize, snippetSize: snippetSize, rowTitleWeight: rowTitleWeight,
        keypadKey: keypadKey, keypadLetters: keypadLetters, keypadKeySize: keypadKeySize, callButton: callButton, missedCall: missedCall, recentsRowHeight: recentsRowHeight,
      );

  /// Skins switch instantly; only colours and sizes are blended during the theme animation.
  @override
  SkinTokens lerp(SkinTokens? other, double t) {
    if (other == null || other.id != id) return t < 0.5 ? this : (other ?? this);
    Color c(Color a, Color b) => Color.lerp(a, b, t)!;
    double d(double a, double b) => lerpDouble(a, b, t)!;
    return SkinTokens(
      id: id, incoming: c(incoming, other.incoming), onIncoming: c(onIncoming, other.onIncoming), outgoing: c(outgoing, other.outgoing),
      onOutgoing: c(onOutgoing, other.onOutgoing), admin: c(admin, other.admin), onAdmin: c(onAdmin, other.onAdmin), bubbleRadius: d(bubbleRadius, other.bubbleRadius),
      tailRadius: d(tailRadius, other.tailRadius), bubbleMaxWidth: bubbleMaxWidth, time: time, rowHeight: rowHeight, avatarSize: avatarSize, avatarShape: avatarShape,
      dividers: dividers, groupedList: groupedList, pageBackground: c(pageBackground, other.pageBackground), listSurface: c(listSurface, other.listSurface),
      listRadius: listRadius, unread: unread, badge: c(badge, other.badge), onBadge: c(onBadge, other.onBadge), header: header,
      expandedHeaderFraction: expandedHeaderFraction, tabs: tabs, compose: compose, composeColor: c(composeColor, other.composeColor),
      onComposeColor: c(onComposeColor, other.onComposeColor), composePlusButton: composePlusButton, composeFieldRadius: composeFieldRadius,
      composeField: c(composeField, other.composeField), sendFilled: sendFilled, swipeLeft: swipeLeft, swipeRight: swipeRight, titleSize: titleSize,
      largeTitleSize: largeTitleSize, rowTitleSize: rowTitleSize, snippetSize: snippetSize, rowTitleWeight: rowTitleWeight,
      keypadKey: keypadKey, keypadLetters: keypadLetters, keypadKeySize: keypadKeySize, callButton: c(callButton, other.callButton),
      missedCall: c(missedCall, other.missedCall), recentsRowHeight: recentsRowHeight,
    );
  }
}
