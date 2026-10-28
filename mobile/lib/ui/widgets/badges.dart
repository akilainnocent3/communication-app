import 'package:flutter/material.dart';

import '../skin/tokens.dart';

/// Unread indicator in the skin's style: a small filled count, or a dot.
class UnreadBadge extends StatelessWidget {
  const UnreadBadge({super.key, required this.count});
  final int count;

  @override
  Widget build(BuildContext context) {
    final tokens = SkinTokens.of(context);
    if (tokens.unread == UnreadStyle.dot) {
      return Container(width: 9, height: 9, decoration: BoxDecoration(color: tokens.badge, shape: BoxShape.circle));
    }
    return Container(
      constraints: const BoxConstraints(minWidth: 20),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(color: tokens.badge, borderRadius: BorderRadius.circular(10)),
      child: Text(count > 99 ? '99+' : '$count', textAlign: TextAlign.center, style: TextStyle(color: tokens.onBadge, fontSize: 11.5, fontWeight: FontWeight.w700)),
    );
  }
}

/// The "new conversation" button in the skin's style: extended FAB, round FAB, or nothing (a header icon instead).
class ComposeButton extends StatelessWidget {
  const ComposeButton({super.key, required this.label, required this.onPressed});
  final String label;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final tokens = SkinTokens.of(context);
    return switch (tokens.compose) {
      ComposeButtonStyle.extendedFab => FloatingActionButton.extended(
          onPressed: onPressed, backgroundColor: tokens.composeColor, foregroundColor: tokens.onComposeColor,
          icon: const Icon(Icons.chat_outlined), label: Text(label),
        ),
      ComposeButtonStyle.roundFab => FloatingActionButton(
          onPressed: onPressed, tooltip: label, backgroundColor: tokens.composeColor, foregroundColor: tokens.onComposeColor, shape: const CircleBorder(),
          child: Icon(tokens.composePlusButton ? Icons.add : Icons.chat_outlined),
        ),
      ComposeButtonStyle.headerIcon => const SizedBox.shrink(),
    };
  }
}
