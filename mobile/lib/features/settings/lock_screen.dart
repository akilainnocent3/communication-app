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
  bool _enabled = false;
  bool _locked = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  Future<void> _load() async {
    final enabled = await ref.read(servicesProvider).db.getValue('setting.app_lock') == '1';
    if (mounted) setState(() { _enabled = enabled; _locked = enabled; });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused) {
      _load();
    }
  }

  Future<void> _unlock() async {
    final ok = await LocalAuthentication().authenticate(localizedReason: AppLocalizations.of(context).unlock);
    if (ok && mounted) setState(() => _locked = false);
  }

  @override
  Widget build(BuildContext context) {
    if (!_enabled || !_locked) return widget.child;
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
