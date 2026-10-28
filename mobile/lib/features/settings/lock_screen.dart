import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_auth/local_auth.dart';

import '../../l10n/app_localizations.dart';
import '../../providers.dart';

/// Optional app lock (fingerprint, face or the phone's PIN). Locks again whenever the app goes to the background.
class AppLockGate extends ConsumerStatefulWidget {
  const AppLockGate({super.key, required this.child});
  final Widget child;
  @override
  ConsumerState<AppLockGate> createState() => _AppLockGateState();
}

class _AppLockGateState extends ConsumerState<AppLockGate> with WidgetsBindingObserver {
  // From the settings read before the first frame: an enabled lock covers the very first frame too.
  late bool _locked = ref.read(settingsProvider)['app_lock'] == '1';

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

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused && ref.read(settingsProvider)['app_lock'] == '1') setState(() => _locked = true);
  }

  Future<void> _unlock() async {
    final ok = await LocalAuthentication().authenticate(localizedReason: AppLocalizations.of(context).unlock);
    if (ok && mounted) setState(() => _locked = false);
  }

  @override
  Widget build(BuildContext context) {
    if (!_locked || ref.watch(settingsProvider)['app_lock'] != '1') return widget.child;
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      body: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.lock_outline, size: 48),
        const SizedBox(height: 12),
        Text(l10n.locked, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 16),
        FilledButton(onPressed: _unlock, child: Text(l10n.unlock)),
      ])),
    );
  }
}
