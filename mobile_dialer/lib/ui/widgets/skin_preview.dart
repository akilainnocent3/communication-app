import 'package:flutter/material.dart';

import '../skin/tokens.dart';
import 'avatar.dart';

/// A recents row and a keypad row with the call button, drawn with the surrounding theme's skin tokens. Settings →
/// Appearance shows one per skin.
class SkinPreview extends StatelessWidget {
  const SkinPreview({super.key});

  @override
  Widget build(BuildContext context) {
    final tokens = SkinTokens.of(context);
    final scheme = Theme.of(context).colorScheme;
    final key = tokens.keypadKeySize * 0.7;
    Widget digit(String d) => Container(
          width: key * (tokens.keypadKey == KeypadKeyStyle.flat ? 1.4 : 1), height: key, alignment: Alignment.center,
          decoration: ShapeDecoration(
            color: tokens.keypadKey == KeypadKeyStyle.flat ? Colors.transparent : scheme.surfaceContainerHigh,
            shape: switch (tokens.keypadKey) {
              KeypadKeyStyle.circle => const CircleBorder(),
              KeypadKeyStyle.rounded => RoundedRectangleBorder(borderRadius: BorderRadius.circular(key * 0.28)),
              KeypadKeyStyle.flat => const StadiumBorder(),
            },
          ),
          child: Text(d, style: TextStyle(fontSize: key * 0.42, fontWeight: tokens.keypadDigitWeight, color: scheme.onSurface)),
        );
    return Container(
      color: tokens.pageBackground,
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        SizedBox(
          height: tokens.recentsRowHeight,
          child: Row(children: [
            if (tokens.recentsAvatar)
              const ContactAvatar(title: 'Neema Mushi', address: '+255754210331', saved: true, size: 42)
            else
              Icon(Icons.call_missed, color: tokens.missedCall),
            const SizedBox(width: 14),
            Expanded(
              child: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Neema Mushi (2)', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: tokens.missedCall)),
                Row(children: [
                  Icon(Icons.call_missed, size: 15, color: tokens.missedCall),
                  const SizedBox(width: 4),
                  Text('09:41', style: TextStyle(color: scheme.onSurfaceVariant)),
                ]),
              ]),
            ),
            Icon(Icons.call_outlined, color: tokens.callButton),
          ]),
        ),
        const SizedBox(height: 8),
        Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [digit('1'), digit('2'), digit('3')]),
        const SizedBox(height: 8),
        CircleAvatar(radius: key / 2, backgroundColor: tokens.callButton, child: const Icon(Icons.call, color: Colors.white)),
      ]),
    );
  }
}
