import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app.dart';
import '../../l10n/app_localizations.dart';
import '../../providers.dart';

export '../../ui/widgets/avatar.dart';

/// Shown above the Phone screens while calls are not copied to the company (not enrolled) or this app is not the
/// default Phone app (the role can be changed in system settings at any time). The keypad works either way. It sits
/// at the very top, so it takes the status bar inset when shown ([shown]: the page under it then leaves that out).
class DialerBanner extends ConsumerWidget {
  const DialerBanner({super.key});

  static bool shown(WidgetRef ref) {
    final enrolled = ref.watch(servicesProvider.select((s) => s.session != null));
    return !enrolled || ref.watch(callsStatusProvider).value?.isDefaultDialer == false;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final enrolled = ref.watch(servicesProvider.select((s) => s.session != null));
    final status = ref.watch(callsStatusProvider).value;
    final (text, action, route) = switch ((enrolled, status?.isDefaultDialer)) {
      (false, _) => (l10n.enrollBanner, l10n.enrollNow, '/enroll'),
      (true, false) => (l10n.notDefaultDialerBanner, l10n.fixNow, '/onboarding'),
      _ => (null, null, null),
    };
    if (text == null) return const SizedBox.shrink();
    return SafeArea(
      bottom: false,
      child: MaterialBanner(
        leading: const Icon(Icons.warning_amber_rounded),
        content: Text(text),
        actions: [TextButton(onPressed: () => context.push(route!), child: Text(action!))],
      ),
    );
  }
}
