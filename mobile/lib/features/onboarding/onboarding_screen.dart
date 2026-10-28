import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app.dart';
import '../../l10n/app_localizations.dart';
import '../../platform/telephony_api.g.dart';
import '../../providers.dart';
import '../settings/keep_flowing_screen.dart';
import 'step_scaffold.dart';

const _smsPermissions = ['RECEIVE_SMS', 'READ_SMS', 'SEND_SMS', 'RECEIVE_MMS', 'RECEIVE_WAP_PUSH'];
const _contactPermissions = ['READ_CONTACTS'];
const _phonePermissions = ['READ_PHONE_STATE', 'READ_PHONE_NUMBERS'];
const _notificationPermissions = ['POST_NOTIFICATIONS'];

enum _Step { welcome, role, permissions, notifications, flowing }

/// Welcome → default Messages app → permissions → notifications → keep messages flowing, then enrollment (Connect →
/// Done). One goal per screen; a step the phone already satisfies is skipped, and a step advances by itself when the
/// system grants it (the app re-checks on every return from a system dialog or settings screen).
class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});
  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> with WidgetsBindingObserver {
  _Step _step = _Step.welcome;
  RoleStatus? _role;
  Map<String, bool> _granted = const {};
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

  bool _all(List<String> names) => names.every((n) => _granted[n] ?? true);

  bool _satisfied(_Step step) => switch (step) {
        _Step.welcome => false,
        _Step.role => _role?.isDefaultSmsApp ?? false,
        _Step.permissions => _all(_smsPermissions) && _all(_contactPermissions) && _all(_phonePermissions),
        _Step.notifications => _all(_notificationPermissions),
        _Step.flowing => false,
      };

  Future<void> _refresh() async {
    final phone = ref.read(repositoryProvider).phone;
    final role = await phone.roleStatus();
    final permissions = await phone.permissions();
    if (!mounted) return;
    final wasSatisfied = _satisfied(_step);
    setState(() {
      _role = role;
      _granted = {for (final p in permissions) p.name: p.granted};
    });
    // Granted while we were in a system screen: show "done" for a moment, then move on.
    if (!wasSatisfied && _satisfied(_step)) _advanceSoon();
  }

  void _advanceSoon() {
    setState(() => _justDone = true);
    Timer(const Duration(milliseconds: 700), () {
      if (mounted) _next();
    });
  }

  void _next() {
    var index = _step.index + 1;
    while (index < _Step.values.length && _satisfied(_Step.values[index])) {
      index++;
    }
    if (index >= _Step.values.length) return _finish();
    setState(() {
      _step = _Step.values[index];
      _justDone = false;
    });
  }

  void _finish() {
    ref.invalidate(roleCheckProvider);
    context.go(ref.read(servicesProvider).session == null ? '/enroll' : '/conversations');
  }

  Future<void> _requestRole() async {
    final host = ref.read(servicesProvider).host;
    final ok = await host.requestDefaultSmsRole();
    await _refresh();
    if (!ok && !(_role?.isDefaultSmsApp ?? false)) setState(() => _roleRefused = true);
  }

  Future<void> _request(List<String> names) async {
    await ref.read(servicesProvider).host.requestPermissions(names);
    await _refresh();
    // Denied for good: Android shows no dialog any more, so offer the app's settings page.
    if (!_all(names) && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(AppLocalizations.of(context).permissionDeniedForGood),
        action: SnackBarAction(label: AppLocalizations.of(context).openSettings, onPressed: () => ref.read(servicesProvider).host.openAppSettings()),
      ));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final total = _Step.values.length + 2; // + Connect, Done (the enrollment screens)
    if (_role == null) return const Scaffold(body: SizedBox.shrink());
    final done = _justDone || _satisfied(_step);
    return switch (_step) {
      _Step.welcome => StepScaffold(
          index: 0, total: total, illustration: const StepIllustration(icon: Icons.forum_rounded), title: l10n.welcomeTitle, body: l10n.welcomeBody,
          primary: StepAction(l10n.getStarted, _next),
        ),
      _Step.role => StepScaffold(
          index: 1, total: total, illustration: const StepIllustration(icon: Icons.sms_rounded), title: l10n.onboardingTitle, body: l10n.onboardingBody,
          why: l10n.whyDefault, done: done,
          primary: StepAction(l10n.setDefault, _requestRole),
          extra: _roleRefused
              ? Column(children: [
                  Text(l10n.roleFallback, textAlign: TextAlign.center),
                  TextButton(onPressed: () => ref.read(servicesProvider).host.openDefaultAppsSettings(), child: Text(l10n.openDefaultApps)),
                ])
              : null,
        ),
      _Step.permissions => StepScaffold(
          index: 2, total: total, illustration: const StepIllustration(icon: Icons.verified_user_rounded), title: l10n.permissionsTitle, body: l10n.permissionsBody,
          why: l10n.whyPermissions, done: done,
          primary: StepAction(l10n.grant, () => _request([..._smsPermissions, ..._contactPermissions, ..._phonePermissions])),
          extra: Column(children: [
            for (final (names, label) in [(_smsPermissions, l10n.permissionSms), (_contactPermissions, l10n.permissionContacts), (_phonePermissions, l10n.permissionPhone)])
              ListTile(dense: true, leading: Icon(_all(names) ? Icons.check_circle : Icons.radio_button_unchecked, color: _all(names) ? Colors.green : null), title: Text(label)),
          ]),
        ),
      _Step.notifications => StepScaffold(
          index: 3, total: total, illustration: const StepIllustration(icon: Icons.notifications_active_rounded), title: l10n.notificationsTitle,
          body: l10n.permissionNotifications, why: l10n.whyNotifications, done: done,
          primary: StepAction(l10n.allow, () => _request(_notificationPermissions)), secondary: StepAction(l10n.notNow, _next),
        ),
      _Step.flowing => StepScaffold(
          index: 4, total: total, illustration: const StepIllustration(icon: Icons.battery_charging_full_rounded), title: l10n.keepFlowingTitle, body: '',
          why: l10n.whyFlowing, primary: StepAction(l10n.continueLabel, _finish),
          extra: const SizedBox(height: 360, child: KeepFlowingScreen(embedded: true)),
        ),
    };
  }
}
