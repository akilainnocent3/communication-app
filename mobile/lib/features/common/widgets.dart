import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../app.dart';
import '../../core/text/phone_format.dart';
import '../../l10n/app_localizations.dart';

/// Coloured initials (or "#" for an unsaved number), stable per address.
class ContactAvatar extends StatelessWidget {
  const ContactAvatar({super.key, required this.title, required this.address, this.saved = false, this.size = 44});
  final String title;
  final String address;
  final bool saved;
  final double size;

  @override
  Widget build(BuildContext context) {
    final hue = address.codeUnits.fold<int>(0, (h, c) => (h * 31 + c) & 0x7fffffff) % 360;
    final words = title.trim().split(RegExp(r'\s+')).where((w) => w.isNotEmpty).toList();
    final label = saved && words.isNotEmpty
        ? (words.first[0] + (words.length > 1 ? words.last[0] : '')).toUpperCase()
        : addressKind(address) == AddressKind.alphanumeric ? address.substring(0, 1).toUpperCase() : '#';
    return CircleAvatar(
      radius: size / 2,
      backgroundColor: HSLColor.fromAHSL(1, hue.toDouble(), 0.5, 0.42).toColor(),
      child: Text(label, style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: size * 0.36)),
    );
  }
}

/// "15:42" today, "Tue" this week, "3 Oct" this year, "3 Oct 2024" otherwise.
String listTime(BuildContext context, int millis) {
  final date = DateTime.fromMillisecondsSinceEpoch(millis);
  final now = DateTime.now();
  final locale = Localizations.localeOf(context).toString();
  final today = DateTime(now.year, now.month, now.day);
  final day = DateTime(date.year, date.month, date.day);
  final days = today.difference(day).inDays;
  if (days == 0) return DateFormat.Hm(locale).format(date);
  if (days > 0 && days < 7) return DateFormat.E(locale).format(date);
  if (date.year == now.year) return DateFormat.MMMd(locale).format(date);
  return DateFormat.yMMMd(locale).format(date);
}

/// Shown on every main screen while this app is not the default SMS app (the role can be removed at any time).
class DefaultAppBanner extends ConsumerWidget {
  const DefaultAppBanner({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final role = ref.watch(roleCheckProvider).value;
    if (role == null || role.isDefaultSmsApp) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    return MaterialBanner(
      leading: const Icon(Icons.warning_amber_rounded),
      content: Text(l10n.notDefaultBanner),
      actions: [TextButton(onPressed: () => context.go('/onboarding'), child: Text(l10n.fixNow))],
    );
  }
}
