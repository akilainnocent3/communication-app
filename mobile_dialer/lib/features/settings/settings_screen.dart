import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../l10n/app_localizations.dart';
import '../../providers.dart';

/// Phone-side settings, stored in the encrypted sync database. No app lock: nothing may stand between the keypad and an
/// emergency number (the phone's own screen lock protects it).
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final services = ref.watch(servicesProvider);
    final values = ref.watch(settingsProvider);
    final settings = ref.read(settingsProvider.notifier);
    bool on(String key, {bool fallback = false}) => values[key] == null || values[key]!.isEmpty ? fallback : values[key] == '1';
    return Scaffold(
      appBar: AppBar(title: Text(l10n.settings)),
      body: ListView(children: [
        ListTile(leading: const Icon(Icons.palette_outlined), title: Text(l10n.appearance), subtitle: Text(l10n.appearanceHint), onTap: () => context.push('/settings/appearance')),
        ListTile(leading: const Icon(Icons.battery_charging_full), title: Text(l10n.keepFlowingTitle), subtitle: Text(l10n.keepFlowingHint), onTap: () => context.push('/settings/flowing')),
        const Divider(),
        SwitchListTile(title: Text(l10n.secureScreen), value: on('secure_screen'), onChanged: (v) => settings.set('secure_screen', v ? '1' : '0')),
        const Divider(),
        ListTile(leading: const Icon(Icons.sync), title: Text(l10n.syncStatus), onTap: () => context.push('/settings/sync')),
        AboutListTile(icon: const Icon(Icons.info_outline), applicationName: l10n.companyApp, applicationVersion: services.config.appVersion, aboutBoxChildren: [Text(l10n.aboutBody)]),
      ]),
    );
  }
}
