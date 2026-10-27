import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app.dart';
import '../../l10n/app_localizations.dart';
import '../../platform/telephony_api.g.dart';
import '../../providers.dart';

/// Default SMS app first (most SMS permissions come with the role), then the remaining permissions with their
/// reasons, notifications, and battery-optimisation guidance per manufacturer.
class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});
  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

const _groups = {
  'sms': ['RECEIVE_SMS', 'READ_SMS', 'SEND_SMS', 'RECEIVE_MMS', 'RECEIVE_WAP_PUSH'],
  'contacts': ['READ_CONTACTS'],
  'phone': ['READ_PHONE_STATE', 'READ_PHONE_NUMBERS'],
  'notifications': ['POST_NOTIFICATIONS'],
};

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  RoleStatus? _role;
  Map<String, bool> _granted = const {};
  ServiceStatus? _status;
  String _manufacturer = '';

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final phone = ref.read(servicesProvider).phone;
    final role = await phone.roleStatus();
    final permissions = await phone.permissions();
    final status = await phone.serviceStatus();
    final facts = await phone.deviceFacts();
    if (!mounted) return;
    setState(() {
      _role = role;
      _granted = {for (final p in permissions) p.name: p.granted};
      _status = status;
      _manufacturer = facts.manufacturer.toLowerCase();
    });
  }

  bool _group(String key) => _groups[key]!.every((name) => _granted[name] ?? true);

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final host = ref.read(servicesProvider).host;
    final role = _role;
    final allGranted = _groups.keys.every(_group);
    return Scaffold(
      appBar: AppBar(title: Text(l10n.companyApp)),
      body: role == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(padding: const EdgeInsets.all(16), children: [
              _Step(
                done: role.isDefaultSmsApp, icon: Icons.sms_outlined, title: l10n.onboardingTitle, body: l10n.onboardingBody,
                action: FilledButton(onPressed: () async { await host.requestDefaultSmsRole(); await _refresh(); }, child: Text(l10n.setDefault)),
              ),
              _Step(
                done: allGranted, icon: Icons.verified_user_outlined, title: l10n.permissionsTitle, body: l10n.permissionsBody,
                details: [
                  for (final entry in {'sms': l10n.permissionSms, 'contacts': l10n.permissionContacts, 'phone': l10n.permissionPhone, 'notifications': l10n.permissionNotifications}.entries)
                    ListTile(dense: true, leading: Icon(_group(entry.key) ? Icons.check_circle : Icons.radio_button_unchecked, color: _group(entry.key) ? Colors.green : null), title: Text(entry.value)),
                ],
                action: FilledButton.tonal(
                  onPressed: role.isDefaultSmsApp ? () async { await host.requestPermissions(_groups.values.expand((v) => v).toList()); await _refresh(); } : null,
                  child: Text(l10n.grant),
                ),
              ),
              _Step(
                done: !(_status?.batteryOptimised ?? false), icon: Icons.battery_saver_outlined, title: l10n.batteryTitle,
                body: _manufacturer.contains('samsung') ? '${l10n.batteryBody}\n\n${l10n.batterySamsung}' : l10n.batteryBody,
                action: OutlinedButton(onPressed: () async { await host.openBatteryOptimisationSettings(); }, child: Text(l10n.batteryOpen)),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: role.isDefaultSmsApp ? () { ref.invalidate(roleCheckProvider); context.go(ref.read(servicesProvider).session == null ? '/enroll' : '/conversations'); } : null,
                child: Text(l10n.continueLabel),
              ),
            ]),
    );
  }
}

class _Step extends StatelessWidget {
  const _Step({required this.done, required this.icon, required this.title, required this.body, required this.action, this.details = const []});
  final bool done;
  final IconData icon;
  final String title;
  final String body;
  final Widget action;
  final List<Widget> details;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(done ? Icons.check_circle : icon, color: done ? Colors.green : scheme.primary),
            const SizedBox(width: 12),
            Expanded(child: Text(title, style: Theme.of(context).textTheme.titleMedium)),
          ]),
          const SizedBox(height: 8),
          Text(body, style: Theme.of(context).textTheme.bodyMedium),
          ...details,
          if (!done) Padding(padding: const EdgeInsets.only(top: 12), child: action),
        ]),
      ),
    );
  }
}
