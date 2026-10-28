import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/text/phone_format.dart';
import '../../l10n/app_localizations.dart';
import '../../platform/telephony_api.g.dart';
import '../../providers.dart';
import '../common/widgets.dart';
import 'composer.dart';

/// New conversation: one or more recipients (group MMS), contact search, then the composer.
class ComposeScreen extends ConsumerStatefulWidget {
  const ComposeScreen({super.key, this.initialTo, this.initialBody});
  final String? initialTo;
  final String? initialBody;
  @override
  ConsumerState<ComposeScreen> createState() => _ComposeScreenState();
}

class _ComposeScreenState extends ConsumerState<ComposeScreen> {
  final _to = TextEditingController();
  final List<String> _recipients = [];
  List<ContactInfo> _suggestions = const [];
  Timer? _debounce;
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    if (widget.initialTo != null && widget.initialTo!.isNotEmpty) _recipients.add(widget.initialTo!);
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _to.dispose();
    super.dispose();
  }

  /// Debounced (250 ms) and stale-safe: an answer for an older query is dropped.
  void _search(String query) {
    _debounce?.cancel();
    final generation = ++_generation;
    if (query.trim().length < 2) {
      setState(() => _suggestions = const []);
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 250), () async {
      final results = await ref.read(repositoryProvider).phone.searchContacts(query, 20);
      if (mounted && generation == _generation) setState(() => _suggestions = results);
    });
  }

  void _add(String address) {
    final value = address.trim();
    if (value.isEmpty || _recipients.contains(value)) return;
    setState(() { _recipients.add(value); _to.clear(); _suggestions = const []; });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(l10n.newConversation)),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Wrap(spacing: 6, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
            for (final r in _recipients) InputChip(label: Text(formatNumber(r)), onDeleted: () => setState(() => _recipients.remove(r))),
            SizedBox(
              width: 220,
              child: TextField(
                controller: _to, autofocus: _recipients.isEmpty, keyboardType: TextInputType.phone,
                decoration: InputDecoration(hintText: l10n.toHint, border: InputBorder.none),
                onChanged: _search, onSubmitted: _add,
              ),
            ),
          ]),
        ),
        const Divider(height: 1),
        Expanded(
          child: ListView(children: [
            for (final contact in _suggestions)
              ListTile(
                leading: ContactAvatar(title: contact.displayName ?? contact.address, address: contact.address, saved: contact.displayName != null, photoUri: contact.photoUri, size: 40),
                title: Text(contact.displayName ?? contact.address), subtitle: Text(formatNumber(contact.address)), onTap: () => _add(contact.address),
              ),
          ]),
        ),
        Composer(
          draftKey: 'new',
          initialText: widget.initialBody,
          group: _recipients.length > 1,
          enabled: _recipients.isNotEmpty || _to.text.trim().isNotEmpty,
          onSend: (body, sim, at) async {
            if (_to.text.trim().isNotEmpty) _add(_to.text);
            await ref.read(repositoryProvider).send(addresses: List.of(_recipients), body: body, subscriptionId: sim, at: at);
            if (context.mounted) context.go('/conversations');
          },
        ),
      ]),
    );
  }
}
