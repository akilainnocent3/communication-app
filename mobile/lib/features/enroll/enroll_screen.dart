import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../core/api/errors.dart';
import '../../core/enroll/enroll_uri.dart';
import '../../core/sync/sync_engine.dart';
import '../../l10n/app_localizations.dart';
import '../../providers.dart';

/// Scan the admin's QR code (or paste the code) → read the monitoring notice → accept → create a Keystore key bound
/// to this enrollment (attestation challenge = SHA-256 of the code) → enroll.
class EnrollScreen extends ConsumerStatefulWidget {
  const EnrollScreen({super.key});
  @override
  ConsumerState<EnrollScreen> createState() => _EnrollScreenState();
}

class _EnrollScreenState extends ConsumerState<EnrollScreen> {
  final _code = TextEditingController();
  bool _scanning = false;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _start(String raw) async {
    final l10n = AppLocalizations.of(context);
    final services = ref.read(servicesProvider);
    final hosts = services.config.allowedServerHosts;
    EnrollTarget target;
    try {
      target = parseEnrollTarget(raw, allowedHosts: hosts, defaultServer: hosts.length == 1 ? 'https://${hosts.first}' : null);
    } on EnrollUriException catch (error) {
      setState(() => _error = error.code == 'invalid' ? l10n.enrollBody : l10n.untrustedServer);
      return;
    }
    setState(() { _busy = true; _error = null; _scanning = false; });
    try {
      final api = services.apiFor(target.server);
      final info = await api.enrollInfo(target.token);
      if (!mounted) return;
      final accepted = await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (context) => AlertDialog(
          title: Text(l10n.noticeTitle),
          content: SingleChildScrollView(child: Text('${info['company_name']} · ${info['device_name']}\n\n${info['notice']}')),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: Text(l10n.noticeDecline)),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(l10n.noticeAccept)),
          ],
        ),
      );
      if (accepted != true) return;
      final host = services.host;
      final key = await host.createDeviceKey(Uint8List.fromList(sha256.convert(utf8.encode(target.token)).bytes));
      final facts = await services.phone.deviceFacts();
      final sims = await services.phone.sims();
      final response = await api.enroll(
        token: target.token, publicKeySpki: key.publicKeySpki, attestationChain: key.attestationChain, noticeText: info['notice'] as String,
        device: {'manufacturer': facts.manufacturer, 'model': facts.model, 'android_version': facts.androidVersion, 'sdk_int': facts.sdkInt},
        sims: [for (final sim in sims) SyncEngine.simPayload(sim)],
      );
      await services.saveEnrollment(target.server, response);
      await host.startSyncService();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(l10n.enrolled(response['device_code'] as String))));
      context.go('/conversations');
    } on ApiException catch (error) {
      await ref.read(servicesProvider).host.deleteDeviceKey();
      setState(() => _error = error.detail.isEmpty ? error.code : error.detail);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(l10n.enrollTitle)),
      body: _busy
          ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [const CircularProgressIndicator(), const SizedBox(height: 16), Text(l10n.enrolling)]))
          : _scanning
              ? MobileScanner(onDetect: (capture) {
                  final value = capture.barcodes.firstOrNull?.rawValue;
                  if (value != null && !_busy) _start(value);
                })
              : ListView(padding: const EdgeInsets.all(16), children: [
                  Text(l10n.enrollBody, style: Theme.of(context).textTheme.bodyLarge),
                  const SizedBox(height: 24),
                  FilledButton.icon(onPressed: () => setState(() => _scanning = true), icon: const Icon(Icons.qr_code_scanner), label: Text(l10n.scanQr)),
                  const SizedBox(height: 24),
                  TextField(controller: _code, decoration: InputDecoration(labelText: l10n.codeLabel, border: const OutlineInputBorder()), autocorrect: false, enableSuggestions: false),
                  const SizedBox(height: 12),
                  OutlinedButton(onPressed: () => _start(_code.text), child: Text(l10n.enterCode)),
                  if (_error != null) Padding(padding: const EdgeInsets.only(top: 16), child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
                ]),
    );
  }
}

/// Shown after the administrator revoked the phone (the app has already wiped its key and sync data).
class RemovedScreen extends StatelessWidget {
  const RemovedScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            const Icon(Icons.phonelink_erase, size: 56),
            const SizedBox(height: 16),
            Text(l10n.removedTitle, textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(l10n.removedBody, textAlign: TextAlign.center),
            const SizedBox(height: 24),
            FilledButton(onPressed: () => SystemNavigator.pop(), child: Text(l10n.continueLabel)),
          ]),
        ),
      ),
    );
  }
}
