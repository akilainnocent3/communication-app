import 'dart:async';
import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/errors.dart';
import '../../core/enroll/enroll_uri.dart';
import '../../core/enroll/short_code.dart';
import '../../l10n/app_localizations.dart';
import '../../platform/telephony_api.g.dart';
import '../../providers.dart';
import '../onboarding/step_scaffold.dart';

Map<String, dynamic> simPayload(SimInfo sim) =>
    {'subscription_id': sim.subscriptionId, 'slot': sim.slot, 'carrier': sim.carrier, 'country_iso': sim.countryIso, 'number': sim.number ?? '', 'is_default': sim.isDefault};

/// "Connect to company": scan the admin's QR code (or a photo of it), tap the admin's link, or type the 8-character
/// short code. Whatever the source, the server must be HTTPS and in the build's allow-list, and nothing enrolls until
/// the holder has read and accepted the monitoring notice. Then: Keystore key bound to this enrollment (attestation
/// challenge = SHA-256 of the token) → enroll → success screen.
class EnrollScreen extends ConsumerStatefulWidget {
  const EnrollScreen({super.key, this.link});
  /// An ocmphone://enroll link that opened the app.
  final String? link;
  @override
  ConsumerState<EnrollScreen> createState() => _EnrollScreenState();
}

class _EnrollScreenState extends ConsumerState<EnrollScreen> {
  final _code = TextEditingController();
  bool _busy = false;
  String? _error;
  String? _server;

  @override
  void initState() {
    super.initState();
    final hosts = ref.read(servicesProvider).config.allowedServerHosts;
    if (hosts.isNotEmpty) _server = hosts.first;
    // The link only pre-fills: the same checks and the notice follow.
    if (widget.link != null) WidgetsBinding.instance.addPostFrameCallback((_) => _start(widget.link!));
  }

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _scan() async {
    final raw = await context.push<String>('/enroll/scan');
    if (raw != null && mounted) await _start(raw);
  }

  Future<void> _start(String raw) async {
    final l10n = AppLocalizations.of(context);
    final services = ref.read(servicesProvider);
    final hosts = services.config.allowedServerHosts;
    setState(() { _busy = true; _error = null; });
    try {
      EnrollTarget target;
      final short = normaliseShortCode(raw);
      if (short != null) {
        // A short code names no server: it is resolved on the chosen allowed server only.
        final server = allowedServer(_server ?? '', allowedHosts: hosts);
        final token = await services.apiFor(server).resolveShortCode(short);
        target = parseEnrollTarget('ocmphone://enroll?server=${Uri.encodeComponent(server.toString())}&token=${Uri.encodeComponent(token)}', allowedHosts: hosts);
      } else {
        target = parseEnrollTarget(raw, allowedHosts: hosts, defaultServer: hosts.length == 1 ? 'https://${hosts.first}' : null);
      }
      await _enroll(target);
    } on EnrollUriException catch (error) {
      setState(() => _error = error.code == 'invalid' ? l10n.notAnEnrollCode : l10n.untrustedServer);
    } on ApiException catch (error) {
      setState(() => _error = error.status == 0 ? l10n.noConnection : error.code == 'throttled' ? l10n.tooManyAttempts : (error.detail.isEmpty ? error.code : error.detail));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _enroll(EnrollTarget target) async {
    final l10n = AppLocalizations.of(context);
    final services = ref.read(servicesProvider);
    final api = services.apiFor(target.server);
    final info = await api.enrollInfo(target.token);
    if (!mounted) return;
    // An OCM Messages code: refused before any key is made (the server refuses it too, without burning the code).
    if (info['platform'] != null && info['platform'] != 'calls') throw ApiException(409, 'wrong_app', l10n.wrongAppCode);
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
    try {
      final facts = await services.phone.deviceFacts();
      final sims = await services.phone.sims();
      final response = await api.enroll(
        token: target.token, publicKeySpki: key.publicKeySpki, attestationChain: key.attestationChain, noticeText: info['notice'] as String,
        device: {'manufacturer': facts.manufacturer, 'model': facts.model, 'android_version': facts.androidVersion, 'sdk_int': facts.sdkInt},
        sims: [for (final sim in sims) simPayload(sim)],
      );
      await services.saveEnrollment(target.server, response);
      await host.syncNow();
      if (!mounted) return;
      HapticFeedback.mediumImpact();
      context.go('/enroll/done?code=${Uri.encodeComponent(response['device_code'] as String)}');
    } on ApiException {
      await host.deleteDeviceKey();
      rethrow;
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final hosts = ref.read(servicesProvider).config.allowedServerHosts;
    if (_busy) {
      return Scaffold(body: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [const CircularProgressIndicator(), const SizedBox(height: 16), Text(l10n.enrolling)])));
    }
    return StepScaffold(
      index: 5, total: 7, illustration: const StepIllustration(icon: Icons.domain_rounded), title: l10n.enrollTitle, body: l10n.enrollBody, why: l10n.whyEnroll,
      primary: StepAction(l10n.scanQr, _scan),
      extra: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const SizedBox(height: 8),
        Row(children: [const Expanded(child: Divider()), Padding(padding: const EdgeInsets.symmetric(horizontal: 12), child: Text(l10n.orTypeCode)), const Expanded(child: Divider())]),
        const SizedBox(height: 12),
        if (hosts.length > 1)
          DropdownButtonFormField<String>(
            initialValue: _server,
            decoration: InputDecoration(labelText: l10n.serverLabel, border: const OutlineInputBorder()),
            items: [for (final h in hosts) DropdownMenuItem(value: h, child: Text(h))],
            onChanged: (v) => setState(() => _server = v),
          ),
        if (hosts.length > 1) const SizedBox(height: 12),
        TextField(
          controller: _code,
          textCapitalization: TextCapitalization.characters,
          autocorrect: false,
          enableSuggestions: false,
          style: const TextStyle(fontSize: 20, letterSpacing: 2),
          decoration: InputDecoration(labelText: l10n.shortCodeLabel, hintText: 'XXXX-XXXX', border: const OutlineInputBorder()),
          onSubmitted: _start,
        ),
        const SizedBox(height: 8),
        OutlinedButton(onPressed: () => _start(_code.text), child: Text(l10n.enterCode)),
        if (_error != null) Padding(padding: const EdgeInsets.only(top: 16), child: Text(_error!, textAlign: TextAlign.center, style: TextStyle(color: Theme.of(context).colorScheme.error))),
      ]),
    );
  }
}

/// Done: the device code (what the admin sees) and the history copy's progress, then the conversation list.
class EnrolledScreen extends StatelessWidget {
  const EnrolledScreen({super.key, required this.deviceCode});
  final String deviceCode;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return StepScaffold(
      index: 2, total: 6, illustration: const StepIllustration(icon: Icons.check_rounded, done: true), title: l10n.enrolledTitle,
      body: l10n.enrolledBody,
      primary: StepAction(l10n.continueLabel, () => context.go('/onboarding')),
      extra: Column(children: [
        Text(l10n.deviceCode, style: Theme.of(context).textTheme.labelLarge),
        SelectableText(deviceCode, style: Theme.of(context).textTheme.headlineSmall?.copyWith(letterSpacing: 1.5)),
      ]),
    );
  }
}

/// Shown after the administrator revoked the phone (the native engine has already wiped its key and sync data). OCM
/// Phone may still be the phone's Phone app: the keypad keeps working, and the holder can pick another Phone app.
class RemovedScreen extends ConsumerWidget {
  const RemovedScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return StepScaffold(
      index: 0, total: 1, illustration: const StepIllustration(icon: Icons.phonelink_erase_rounded), title: l10n.removedTitle, body: l10n.removedBody,
      primary: StepAction(l10n.openKeypad, () => context.go('/phone')),
      secondary: StepAction(l10n.choosePhoneApp, () => ref.read(servicesProvider).host.openDefaultAppsSettings()),
    );
  }
}
