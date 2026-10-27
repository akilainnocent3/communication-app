import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/text/phone_format.dart';
import '../../l10n/app_localizations.dart';
import '../../platform/telephony_api.g.dart';
import '../../providers.dart';
import '../common/widgets.dart';
import '../compose/composer.dart';
import 'message_bubble.dart';

final _adminProvider = FutureProvider.family<Map<int, String?>, int>((ref, threadId) async {
  final messages = await ref.watch(messagesProvider(threadId).future);
  return ref.watch(repositoryProvider).adminSent(messages);
});

final _starredProvider = FutureProvider<Set<int>>((ref) {
  ref.watch(refreshTickProvider);
  return ref.watch(repositoryProvider).starred('sms');
});

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key, required this.threadId});
  final int threadId;
  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  @override
  void initState() {
    super.initState();
    ref.read(repositoryProvider).markRead(widget.threadId);
  }

  Future<void> _actions(ProviderMessage message, bool starred) async {
    final l10n = AppLocalizations.of(context);
    final repo = ref.read(repositoryProvider);
    final choice = await showModalBottomSheet<String>(context: context, builder: (context) => SafeArea(child: Column(mainAxisSize: MainAxisSize.min, children: [
      ListTile(leading: const Icon(Icons.copy), title: Text(l10n.copy), onTap: () => Navigator.pop(context, 'copy')),
      ListTile(leading: const Icon(Icons.forward), title: Text(l10n.forward), onTap: () => Navigator.pop(context, 'forward')),
      ListTile(leading: Icon(starred ? Icons.star : Icons.star_border), title: Text(starred ? l10n.unstar : l10n.star), onTap: () => Navigator.pop(context, 'star')),
      ListTile(leading: const Icon(Icons.info_outline), title: Text(l10n.details), onTap: () => Navigator.pop(context, 'details')),
      ListTile(leading: const Icon(Icons.delete_outline), title: Text(l10n.delete), onTap: () => Navigator.pop(context, 'delete')),
    ])));
    if (!mounted || choice == null) return;
    switch (choice) {
      case 'copy':
        await Clipboard.setData(ClipboardData(text: message.body));
      case 'forward':
        if (mounted) await context.push('/compose', extra: message.body);
      case 'star':
        await repo.setStarred(message, !starred);
      case 'delete':
        await ref.read(servicesProvider).phone.deleteMessage(message.kind, message.providerId);
      case 'details':
        final sims = ref.read(simsProvider).value ?? const <SimInfo>[];
        final sim = sims.where((s) => s.subscriptionId == message.subscriptionId).firstOrNull;
        if (!mounted) return;
        await showDialog<void>(context: context, builder: (context) => AlertDialog(
          title: Text(l10n.details),
          content: Text([
            '${message.outbound ? l10n.detailsSent : l10n.detailsReceived}: ${DateFormat.yMMMd().add_Hm().format(DateTime.fromMillisecondsSinceEpoch(message.date))}',
            '${l10n.detailsFrom}: ${message.addresses.map(formatNumber).join(', ')}',
            if (sim != null) '${l10n.detailsSim}: SIM ${sim.slot + 1} · ${sim.carrier}',
            if (message.outbound) '${l10n.detailsStatus}: ${statusText(l10n, message.status)}',
          ].join('\n')),
        ));
    }
    ref.read(refreshTickProvider.notifier).bump();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final messages = ref.watch(messagesProvider(widget.threadId));
    final admin = ref.watch(_adminProvider(widget.threadId)).value ?? const {};
    final starred = ref.watch(_starredProvider).value ?? const <int>{};
    final list = messages.value ?? const <ProviderMessage>[];
    final addresses = list.isNotEmpty ? list.first.addresses : const <String>[];
    final title = addresses.map(formatNumber).join(', ');
    return Scaffold(
      appBar: AppBar(title: Text(title.isEmpty ? l10n.conversations : title, overflow: TextOverflow.ellipsis)),
      body: Column(children: [
        const DefaultAppBanner(),
        Expanded(
          child: messages.isLoading && list.isEmpty
              ? const Center(child: CircularProgressIndicator())
              : ListView.builder(
                  reverse: true,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  itemCount: list.length,
                  itemBuilder: (context, index) {
                    final message = list[index];
                    final older = index + 1 < list.length ? list[index + 1] : null;
                    final day = DateTime.fromMillisecondsSinceEpoch(message.date);
                    final showDay = older == null || DateTime.fromMillisecondsSinceEpoch(older.date).day != day.day;
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Column(children: [
                        if (showDay)
                          Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Text(listTime(context, message.date), style: Theme.of(context).textTheme.labelMedium)),
                        Align(
                          alignment: message.outbound ? Alignment.centerRight : Alignment.centerLeft,
                          child: MessageBubble(
                            message: message, isAdmin: admin.containsKey(message.providerId), adminName: admin[message.providerId], starred: starred.contains(message.providerId),
                            onLongPress: () => _actions(message, starred.contains(message.providerId)),
                            onRetry: () => ref.read(repositoryProvider).send(addresses: message.addresses, body: message.body, subscriptionId: message.subscriptionId),
                          ),
                        ),
                      ]),
                    );
                  },
                ),
        ),
        Composer(
          draftKey: 'thread:${widget.threadId}',
          group: addresses.length > 1,
          defaultSim: list.isNotEmpty ? list.first.subscriptionId : null,
          onSend: (body, sim, at) async {
            await ref.read(repositoryProvider).send(addresses: addresses, body: body, subscriptionId: sim, at: at);
            ref.read(refreshTickProvider.notifier).bump();
          },
        ),
      ]),
    );
  }
}
