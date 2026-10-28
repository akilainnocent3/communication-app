import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/text/segments.dart';
import '../../data/conversations_repository.dart';
import '../../l10n/app_localizations.dart';
import '../../platform/telephony_api.g.dart';
import '../../providers.dart';
import '../../ui/skin/tokens.dart';

typedef SendCallback = Future<void> Function(String body, int? subscriptionId, DateTime? at);

/// Text field with the GSM-7/UCS-2 segment counter, SIM picker (dual SIM), quick replies and scheduled send. The
/// draft is saved per conversation.
class Composer extends ConsumerStatefulWidget {
  const Composer({super.key, required this.draftKey, required this.onSend, this.defaultSim, this.enabled = true, this.group = false, this.initialText});
  final String? initialText;
  final String draftKey;
  final SendCallback onSend;
  final int? defaultSim;
  final bool enabled;
  final bool group;
  @override
  ConsumerState<Composer> createState() => _ComposerState();
}

class _ComposerState extends ConsumerState<Composer> {
  final _controller = TextEditingController();
  int? _sim;
  bool _sending = false;
  // Kept so dispose() can save the draft without touching `ref` (unsafe once the widget is unmounting).
  late final ConversationsRepository _repository = ref.read(repositoryProvider);

  @override
  void initState() {
    super.initState();
    _sim = widget.defaultSim;
    if (widget.initialText != null) _controller.text = widget.initialText!;
    _repository.draft(widget.draftKey).then((value) {
      if (value != null && mounted && _controller.text.isEmpty) setState(() => _controller.text = value);
    });
  }

  @override
  void dispose() {
    _repository.saveDraft(widget.draftKey, _controller.text);
    _controller.dispose();
    super.dispose();
  }

  Future<void> _send({DateTime? at}) async {
    final body = _controller.text.trim();
    if (body.isEmpty || _sending) return;
    setState(() => _sending = true);
    try {
      await widget.onSend(body, _sim, at);
      _controller.clear();
      await _repository.saveDraft(widget.draftKey, '');
    } on SendRefused {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppLocalizations.of(context).sendRefused)));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _schedule() async {
    final now = DateTime.now();
    final date = await showDatePicker(context: context, firstDate: now, lastDate: now.add(const Duration(days: 30)), initialDate: now);
    if (date == null || !mounted) return;
    final time = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(now.add(const Duration(hours: 1))));
    if (time == null) return;
    final at = DateTime(date.year, date.month, date.day, time.hour, time.minute);
    if (at.isAfter(now)) {
      await _send(at: at);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppLocalizations.of(context).scheduledFor(DateFormat.yMMMd().add_Hm().format(at)))));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final tokens = SkinTokens.of(context);
    final scheme = Theme.of(context).colorScheme;
    final sims = ref.watch(simsProvider).value ?? const <SimInfo>[];
    final replies = ref.watch(quickRepliesProvider).value ?? const [];
    final info = segmentInfo(_controller.text);
    final sim = sims.where((s) => s.subscriptionId == (_sim ?? sims.where((s) => s.isDefault).firstOrNull?.subscriptionId)).firstOrNull;
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(8, 4, 8, 8),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          if (_controller.text.isNotEmpty)
            Align(
              alignment: Alignment.centerRight,
              child: Padding(
                padding: const EdgeInsets.only(right: 56, bottom: 2),
                child: Text(widget.group ? l10n.mmsWillSend : l10n.segments(info.segments, info.remaining), style: Theme.of(context).textTheme.labelSmall),
              ),
            ),
          Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
            PopupMenuButton<String>(
              icon: Icon(tokens.composePlusButton ? Icons.add : Icons.add_circle_outline),
              tooltip: l10n.attach,
              enabled: widget.enabled,
              onSelected: (value) {
                if (value == 'schedule') {
                  _schedule();
                } else if (value.startsWith('reply:')) {
                  setState(() => _controller.text = '${_controller.text}${_controller.text.isEmpty ? '' : ' '}${value.substring(6)}');
                }
              },
              itemBuilder: (_) => [
                PopupMenuItem(value: 'schedule', child: Text(l10n.scheduleSend)),
                for (final reply in replies) PopupMenuItem(value: 'reply:${reply['body']}', child: Text('${l10n.quickReplies}: ${reply['title']}')),
              ],
            ),
            Expanded(
              child: TextField(
                controller: _controller,
                enabled: widget.enabled,
                minLines: 1,
                maxLines: 6,
                maxLength: 5000,
                buildCounter: (_, {required currentLength, required isFocused, maxLength}) => null,
                textCapitalization: TextCapitalization.sentences,
                onChanged: (_) => setState(() {}),
                decoration: InputDecoration(
                  hintText: l10n.messageHint,
                  filled: true,
                  fillColor: tokens.composeField,
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(tokens.composeFieldRadius), borderSide: BorderSide.none),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  suffixIcon: sims.length > 1
                      ? PopupMenuButton<int>(
                          tooltip: l10n.chooseSim,
                          onSelected: (value) => setState(() => _sim = value),
                          itemBuilder: (_) => [for (final s in sims) PopupMenuItem(value: s.subscriptionId, child: Text('SIM ${s.slot + 1} · ${s.carrier}'))],
                          child: Padding(padding: const EdgeInsets.all(12), child: Text('SIM ${(sim?.slot ?? 0) + 1}', style: Theme.of(context).textTheme.labelMedium)),
                        )
                      : null,
                ),
              ),
            ),
            const SizedBox(width: 4),
            if (tokens.sendFilled)
              IconButton.filled(
                tooltip: l10n.send,
                style: IconButton.styleFrom(backgroundColor: tokens.outgoing, foregroundColor: tokens.onOutgoing),
                onPressed: widget.enabled && _controller.text.trim().isNotEmpty && !_sending ? () => _send() : null,
                icon: const Icon(Icons.send),
              )
            else
              IconButton(
                tooltip: l10n.send,
                color: tokens.outgoing,
                disabledColor: scheme.onSurfaceVariant.withValues(alpha: 0.5),
                onPressed: widget.enabled && _controller.text.trim().isNotEmpty && !_sending ? () => _send() : null,
                icon: const Icon(Icons.send),
              ),
          ]),
        ]),
      ),
    );
  }
}
