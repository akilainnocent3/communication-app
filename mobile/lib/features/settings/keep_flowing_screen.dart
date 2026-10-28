import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../l10n/app_localizations.dart';
import '../../platform/telephony_api.g.dart';
import '../../providers.dart';

final _flowingProvider = FutureProvider.autoDispose<(ServiceStatus, List<String>)>((ref) async {
  final host = ref.watch(servicesProvider).host;
  return (await host.serviceStatus(), await host.oemSettings());
});

/// Settings → "Keep messages flowing": what this phone does to background apps, checked where Android lets us check
/// (battery optimisation, background restriction, standby bucket), and a button per manufacturer screen that exists
/// here. The same facts go to the admin in every heartbeat.
class KeepFlowingScreen extends ConsumerStatefulWidget {
  const KeepFlowingScreen({super.key, this.embedded = false});
  /// Inside the onboarding flow (no app bar).
  final bool embedded;
  @override
  ConsumerState<KeepFlowingScreen> createState() => _KeepFlowingScreenState();
}

class _KeepFlowingScreenState extends ConsumerState<KeepFlowingScreen> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  /// Back from a settings screen: check again.
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) ref.invalidate(_flowingProvider);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final host = ref.read(servicesProvider).host;
    final data = ref.watch(_flowingProvider).value;
    final status = data?.$1;
    final screens = data?.$2 ?? const <String>[];
    final restrictedBucket = (status?.standbyBucket ?? 10) >= 40;
    String oemLabel(String id) => switch (id) {
          'samsung_never_sleeping' => l10n.oemSamsung,
          'xiaomi_autostart' => l10n.oemXiaomi,
          'transsion_autostart' => l10n.oemTranssion,
          'oppo_autolaunch' => l10n.oemOppo,
          'oneplus_autolaunch' => l10n.oemOneplus,
          'huawei_app_launch' => l10n.oemHuawei,
          _ => id,
        };
    final body = ListView(padding: const EdgeInsets.all(16), children: [
      Text(l10n.keepFlowingBody, style: Theme.of(context).textTheme.bodyLarge),
      const SizedBox(height: 16),
      _Check(ok: status != null && !status.batteryOptimised, title: l10n.checkBattery, action: l10n.allow, onTap: () => host.openBatteryOptimisationSettings()),
      _Check(ok: status != null && !status.backgroundRestricted, title: l10n.checkBackground, action: l10n.open, onTap: () => host.openOemSetting('app_battery')),
      if (status?.standbyBucket != null) _Check(ok: !restrictedBucket, title: l10n.checkStandby, action: l10n.open, onTap: () => host.openOemSetting('app_battery')),
      for (final id in screens.where((s) => s != 'battery_optimisation' && s != 'app_battery'))
        Card(
          child: ListTile(
            leading: const Icon(Icons.rocket_launch_outlined),
            title: Text(oemLabel(id)),
            subtitle: Text(l10n.oemCannotCheck),
            trailing: FilledButton.tonal(onPressed: () => host.openOemSetting(id), child: Text(l10n.open)),
          ),
        ),
      const SizedBox(height: 12),
      Text(l10n.forceStopWarning, style: Theme.of(context).textTheme.bodySmall),
    ]);
    if (widget.embedded) return body;
    return Scaffold(appBar: AppBar(title: Text(l10n.keepFlowingTitle)), body: body);
  }
}

class _Check extends StatelessWidget {
  const _Check({required this.ok, required this.title, required this.action, required this.onTap});
  final bool ok;
  final String title;
  final String action;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Card(
        child: ListTile(
          leading: Icon(ok ? Icons.check_circle : Icons.error_outline, color: ok ? Colors.green : Theme.of(context).colorScheme.error),
          title: Text(title),
          trailing: ok ? null : FilledButton(onPressed: onTap, child: Text(action)),
        ),
      );
}
