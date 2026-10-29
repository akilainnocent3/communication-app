import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../l10n/app_localizations.dart';
import '../../platform/telephony_api.g.dart';
import '../../providers.dart';
import '../phone/phone_screen.dart';
import 'step_scaffold.dart';

const callPermissions = [
  'READ_CALL_LOG', 'WRITE_CALL_LOG', 'CALL_PHONE', 'ANSWER_PHONE_CALLS', 'READ_PHONE_STATE', 'READ_PHONE_NUMBERS', 'READ_CONTACTS', 'WRITE_CONTACTS',
  'BLUETOOTH_CONNECT', 'POST_NOTIFICATIONS',
];

enum _Step { role, permissions, fullScreen, flowing }

/// OCM Phone's setup after enrollment: default Phone app → call permissions → incoming-call screen (Android 14+) → keep
/// running in the background (the battery/OEM screen). Steps already done are skipped; each step re-checks on return
/// from the system dialog or settings.
class CallsOnboardingScreen extends ConsumerStatefulWidget {
  const CallsOnboardingScreen({super.key});
  @override
  ConsumerState<CallsOnboardingScreen> createState() => _CallsOnboardingScreenState();
}

class _CallsOnboardingScreenState extends ConsumerState<CallsOnboardingScreen> with WidgetsBindingObserver {
  _Step _step = _Step.role;
  CallsStatus? _status;
  bool _roleRefused = false;
  bool _justDone = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _refresh();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _refresh();
  }

  bool _satisfied(_Step step, CallsStatus s) => switch (step) {
        _Step.role => s.isDefaultDialer,
        _Step.permissions => !s.missingPermissions.any(callPermissions.contains),
        _Step.fullScreen => s.canUseFullScreenIntent,
        _Step.flowing => false,
      };

  Future<void> _refresh() async {
    final status = await ref.read(dialerProvider).status();
    if (!mounted) return;
    final was = _status != null && _satisfied(_step, _status!);
    setState(() => _status = status);
    if (!was && _satisfied(_step, status)) {
      setState(() => _justDone = true);
      Timer(const Duration(milliseconds: 700), () { if (mounted) _next(); });
    }
  }

  void _next() {
    var index = _step.index + 1;
    while (index < _Step.values.length && _satisfied(_Step.values[index], _status!)) {
      index++;
    }
    if (index >= _Step.values.length) {
      ref.invalidate(phoneContactsProvider);
      context.go('/phone');
      return;
    }
    setState(() { _step = _Step.values[index]; _justDone = false; });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final status = _status;
    if (status == null) return const Scaffold(body: SizedBox.shrink());
    final host = ref.read(servicesProvider).host;
    final done = _justDone || _satisfied(_step, status);
    const total = 4;
    return switch (_step) {
      _Step.role => StepScaffold(
          index: 0, total: total, illustration: const StepIllustration(icon: Icons.phone_in_talk_rounded), title: l10n.dialerTitle, body: l10n.dialerBody,
          why: l10n.whyDialer, done: done,
          primary: StepAction(l10n.setDefaultDialer, () async {
            final ok = await host.requestDefaultDialerRole();
            await _refresh();
            if (!ok && !(_status?.isDefaultDialer ?? false)) setState(() => _roleRefused = true);
          }),
          extra: _roleRefused
              ? Column(children: [
                  Text(l10n.dialerFallback, textAlign: TextAlign.center),
                  TextButton(onPressed: () => host.openDefaultAppsSettings(), child: Text(l10n.openDefaultApps)),
                ])
              : null,
        ),
      _Step.permissions => StepScaffold(
          index: 1, total: total, illustration: const StepIllustration(icon: Icons.verified_user_rounded), title: l10n.callPermissionsTitle, body: l10n.callPermissionsBody,
          done: done,
          primary: StepAction(l10n.grant, () async {
            final messenger = ScaffoldMessenger.of(context);
            await host.requestPermissions(callPermissions);
            await _refresh();
            if (mounted && (_status?.missingPermissions.any(callPermissions.contains) ?? false)) {
              messenger.showSnackBar(SnackBar(
                content: Text(l10n.permissionDeniedForGood),
                action: SnackBarAction(label: l10n.openSettings, onPressed: host.openAppSettings),
              ));
            }
          }),
          secondary: StepAction(l10n.continueLabel, _next),
        ),
      _Step.fullScreen => StepScaffold(
          index: 2, total: total, illustration: const StepIllustration(icon: Icons.screen_lock_portrait_rounded), title: l10n.fsiTitle, body: l10n.fsiBody,
          done: done, primary: StepAction(l10n.allowInSettings, host.openFullScreenIntentSettings), secondary: StepAction(l10n.continueLabel, _next),
        ),
      _Step.flowing => StepScaffold(
          index: 3, total: total, illustration: const StepIllustration(icon: Icons.battery_charging_full_rounded), title: l10n.batteryTitle, body: l10n.batteryBody,
          primary: StepAction(l10n.batteryOpen, () => context.push('/settings/flowing')), secondary: StepAction(l10n.continueLabel, _next),
        ),
    };
  }
}
