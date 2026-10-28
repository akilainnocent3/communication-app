import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../l10n/app_localizations.dart';
import '../../providers.dart';

/// Phone-side settings, stored in the encrypted sync database.
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final services = ref.watch(servicesProvider);
    final values = ref.watch(settingsProvider);
    final settings = ref.read(settingsProvider.notifier);
    final sims = ref.watch(simsProvider).value ?? const [];
    bool on(String key, {bool fallback = false}) => values[key] == null || values[key]!.isEmpty ? fallback : values[key] == '1';
    return Scaffold(
      appBar: AppBar(title: Text(l10n.settings)),
      body: ListView(children: [
        ListTile(leading: const Icon(Icons.palette_outlined), title: Text(l10n.appearance), subtitle: Text(l10n.appearanceHint), onTap: () => context.push('/settings/appearance')),
        ListTile(leading: const Icon(Icons.battery_charging_full), title: Text(l10n.keepFlowingTitle), subtitle: Text(l10n.keepFlowingHint), onTap: () => context.push('/settings/flowing')),
        const Divider(),
        if (sims.length > 1)
          ListTile(
            title: Text(l10n.defaultSim),
            trailing: DropdownButton<String>(
              value: values['default_sim']?.isNotEmpty == true ? values['default_sim'] : '${sims.first.subscriptionId}',
              items: [for (final sim in sims) DropdownMenuItem(value: '${sim.subscriptionId}', child: Text('SIM ${sim.slot + 1} · ${sim.carrier}'))],
              onChanged: (value) => settings.set('default_sim', value ?? ''),
            ),
          ),
        SwitchListTile(title: Text(l10n.deliveryReports), value: on('delivery_reports', fallback: true), onChanged: (v) => settings.set('delivery_reports', v ? '1' : '0')),
        ListTile(
          title: Text(l10n.mmsAutoDownload),
          trailing: DropdownButton<String>(
            value: values['mms_download']?.isNotEmpty == true ? values['mms_download'] : 'wifi',
            items: [
              DropdownMenuItem(value: 'wifi', child: Text(l10n.mmsWifiOnly)),
              DropdownMenuItem(value: 'always', child: Text(l10n.mmsAlways)),
              DropdownMenuItem(value: 'never', child: Text(l10n.mmsNever)),
            ],
            onChanged: (value) => settings.set('mms_download', value ?? 'wifi'),
          ),
        ),
        SwitchListTile(title: Text(l10n.hideOnLockScreen), value: on('hide_on_lock_screen', fallback: true), onChanged: (v) => settings.set('hide_on_lock_screen', v ? '1' : '0')),
        SwitchListTile(title: Text(l10n.appLock), value: on('app_lock'), onChanged: (v) => settings.set('app_lock', v ? '1' : '0')),
        SwitchListTile(title: Text(l10n.secureScreen), value: on('secure_screen'), onChanged: (v) => settings.set('secure_screen', v ? '1' : '0')),
        const Divider(),
        ListTile(leading: const Icon(Icons.sync), title: Text(l10n.syncStatus), onTap: () => context.push('/settings/sync')),
        AboutListTile(icon: const Icon(Icons.info_outline), applicationName: l10n.companyApp, applicationVersion: services.config.appVersion, aboutBoxChildren: [Text(l10n.aboutBody)]),
      ]),
    );
  }
}
