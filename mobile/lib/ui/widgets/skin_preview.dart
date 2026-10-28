import 'package:flutter/material.dart';

import '../../platform/telephony_api.g.dart';
import '../../features/chat/message_bubble.dart';
import '../skin/tokens.dart';
import 'avatar.dart';
import 'badges.dart';

/// A list row, a received and a sent bubble and the compose bar, drawn with the surrounding theme's skin tokens.
/// Settings → Appearance shows one per skin; the golden tests render it for every skin in light and dark.
class SkinPreview extends StatelessWidget {
  const SkinPreview({super.key, this.compose = true});
  final bool compose;

  static final _in = ProviderMessage(providerId: 1, kind: 'sms', threadId: 1, addresses: ['+255754210331'], body: 'Habari, bei gani?', date: DateTime(2026, 10, 1, 9, 41).millisecondsSinceEpoch,
      outbound: false, read: true, status: 'received', parts: const []);
  static final _out = ProviderMessage(providerId: 2, kind: 'sms', threadId: 1, addresses: ['+255754210331'], body: 'TSh 25,000. Karibu!', date: DateTime(2026, 10, 1, 9, 42).millisecondsSinceEpoch,
      outbound: true, read: true, status: 'delivered', parts: const []);

  @override
  Widget build(BuildContext context) {
    final tokens = SkinTokens.of(context);
    final scheme = Theme.of(context).colorScheme;
    return Container(
      color: tokens.pageBackground,
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Container(
          height: tokens.rowHeight,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: BoxDecoration(color: tokens.listSurface, borderRadius: BorderRadius.circular(tokens.groupedList ? tokens.listRadius : 12)),
          child: Row(children: [
            const ContactAvatar(title: 'Neema Mushi', address: '+255754210331', saved: true),
            const SizedBox(width: 14),
            Expanded(
              child: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: Text('Neema Mushi', style: TextStyle(fontSize: tokens.rowTitleSize, fontWeight: FontWeight.w700, color: scheme.onSurface))),
                  Text('09:41', style: TextStyle(fontSize: 12, color: tokens.badge, fontWeight: FontWeight.w700)),
                ]),
                const SizedBox(height: 3),
                Row(children: [
                  Expanded(child: Text('Habari, bei gani?', maxLines: 1, style: TextStyle(fontSize: tokens.snippetSize, color: scheme.onSurface))),
                  const UnreadBadge(count: 2),
                ]),
              ]),
            ),
          ]),
        ),
        const SizedBox(height: 10),
        Align(alignment: Alignment.centerLeft, child: MessageBubble(message: _in, onLongPress: () {})),
        const SizedBox(height: 6),
        Align(alignment: Alignment.centerRight, child: MessageBubble(message: _out, onLongPress: () {})),
        if (compose) ...[
          const SizedBox(height: 10),
          Row(children: [
            Icon(tokens.composePlusButton ? Icons.add : Icons.add_circle_outline, color: scheme.onSurfaceVariant),
            const SizedBox(width: 8),
            Expanded(
              child: Container(
                height: 44,
                alignment: Alignment.centerLeft,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                decoration: BoxDecoration(color: tokens.composeField, borderRadius: BorderRadius.circular(tokens.composeFieldRadius)),
                child: Text('Text message', style: TextStyle(color: scheme.onSurfaceVariant)),
              ),
            ),
            const SizedBox(width: 8),
            tokens.sendFilled
                ? CircleAvatar(radius: 20, backgroundColor: tokens.outgoing, child: Icon(Icons.send, size: 18, color: tokens.onOutgoing))
                : Icon(Icons.send, color: tokens.outgoing),
          ]),
        ],
      ]),
    );
  }
}
