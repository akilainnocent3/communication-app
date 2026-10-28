import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../app.dart';
import '../../l10n/app_localizations.dart';

export '../../ui/widgets/avatar.dart';

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

/// Same calendar day (year, month and day: comparing only the day of the month put no separator between 3 Sept
/// and 3 Oct).
bool sameDay(int a, int b) {
  final x = DateTime.fromMillisecondsSinceEpoch(a);
  final y = DateTime.fromMillisecondsSinceEpoch(b);
  return x.year == y.year && x.month == y.month && x.day == y.day;
}

/// The chat's day separator: "Today", "Yesterday", the weekday within a week, then the date.
String dayLabel(BuildContext context, int millis) {
  final l10n = AppLocalizations.of(context);
  final locale = Localizations.localeOf(context).toString();
  final date = DateTime.fromMillisecondsSinceEpoch(millis);
  final now = DateTime.now();
  final days = DateTime(now.year, now.month, now.day).difference(DateTime(date.year, date.month, date.day)).inDays;
  if (days == 0) return l10n.today;
  if (days == 1) return l10n.yesterday;
  if (days > 1 && days < 7) return DateFormat.EEEE(locale).format(date);
  if (date.year == now.year) return DateFormat.MMMMEEEEd(locale).format(date);
  return DateFormat.yMMMMEEEEd(locale).format(date);
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
