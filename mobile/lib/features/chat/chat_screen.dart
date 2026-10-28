import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/perf.dart';
import '../../core/text/phone_format.dart';
import '../../l10n/app_localizations.dart';
import '../../platform/telephony_api.g.dart';
import '../../providers.dart';
import '../../state/chat.dart';
import '../../state/threads.dart';
import '../../ui/skin/tokens.dart';
import '../common/widgets.dart';
import '../compose/composer.dart';
import 'message_bubble.dart';

/// One conversation. The title is the saved contact name (number underneath); messages come from the cache on the
/// first frame, then the newest 50 from the phone, and older pages of 50 as the user scrolls up (the reversed list
/// keeps its position when older messages are added above).
class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key, required this.threadId});
  final int threadId;
  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _scroll = ScrollController();
  bool _markedRead = false;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.extentAfter < 800) ref.read(chatProvider(widget.threadId).notifier).loadOlder();
    });
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  /// Off the UI path, and only when something is unread.
  void _markRead(List<ProviderMessage> messages) {
    if (_markedRead) return;
    _markedRead = true;
    final item = ref.read(threadsProvider.notifier).byId(widget.threadId);
    final unread = (item?.thread.unreadCount ?? 0) > 0 || messages.any((m) => !m.read && !m.outbound);
    if (unread) ref.read(threadsProvider.notifier).markRead([widget.threadId]);
  }

  Future<void> _actions(ProviderMessage message, bool starred) async {
    final l10n = AppLocalizations.of(context);
    final chat = ref.read(chatProvider(widget.threadId).notifier);
    final choice = await showModalBottomSheet<String>(context: context, showDragHandle: true, builder: (context) => SafeArea(child: Column(mainAxisSize: MainAxisSize.min, children: [
      ListTile(leading: const Icon(Icons.copy), title: Text(l10n.copy), onTap: () => Navigator.pop(context, 'copy')),
      if (message.body.isNotEmpty) ListTile(leading: const Icon(Icons.text_fields), title: Text(l10n.selectText), onTap: () => Navigator.pop(context, 'select')),
      ListTile(leading: const Icon(Icons.forward), title: Text(l10n.forward), onTap: () => Navigator.pop(context, 'forward')),
      ListTile(leading: Icon(starred ? Icons.star : Icons.star_border), title: Text(starred ? l10n.unstar : l10n.star), onTap: () => Navigator.pop(context, 'star')),
      ListTile(leading: const Icon(Icons.info_outline), title: Text(l10n.details), onTap: () => Navigator.pop(context, 'details')),
      ListTile(leading: const Icon(Icons.delete_outline), title: Text(l10n.delete), onTap: () => Navigator.pop(context, 'delete')),
    ])));
    if (!mounted || choice == null) return;
    switch (choice) {
      case 'copy':
        await Clipboard.setData(ClipboardData(text: message.body));
      case 'select':
        await showDialog<void>(context: context, builder: (context) => AlertDialog(
          content: SelectableText(message.body, autofocus: true, style: const TextStyle(fontSize: 16)),
          actions: [TextButton(onPressed: () => Navigator.pop(context), child: Text(l10n.done))],
        ));
      case 'forward':
        await context.push('/compose', extra: message.body);
      case 'star':
        await chat.toggleStar(message);
      case 'delete':
        await chat.delete(message);
      case 'details':
        final sims = ref.read(simsProvider).value ?? const <SimInfo>[];
        final sim = sims.where((s) => s.subscriptionId == message.subscriptionId).firstOrNull;
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
  }

  void _openImage(MmsPartData part) {
    final px = (MediaQuery.sizeOf(context).longestSide * MediaQuery.devicePixelRatioOf(context)).round().clamp(320, 1024);
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(backgroundColor: Colors.black, foregroundColor: Colors.white),
      body: Center(child: InteractiveViewer(child: ThumbnailImage(uri: part.uri!, px: px, fit: BoxFit.contain, placeholder: const CircularProgressIndicator()))),
    )));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final tokens = SkinTokens.of(context);
    final chat = ref.watch(chatProvider(widget.threadId));
    final item = ref.watch(threadItemProvider(widget.threadId));
    final messages = chat.messages;
    if (messages.isNotEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        Perf.end('chat_open');
        _markRead(messages);
      });
    }
    final addresses = item?.thread.addresses ?? (messages.isNotEmpty ? messages.first.addresses : const <String>[]);
    final title = item?.title ?? addresses.map(formatNumber).join(', ');
    final subtitle = item != null && item.saved ? item.subtitle : '';
    return Scaffold(
      backgroundColor: tokens.pageBackground,
      appBar: AppBar(
        titleSpacing: 0,
        title: Row(children: [
          if (addresses.isNotEmpty) ContactAvatar(title: title, address: addresses.first, saved: item?.saved ?? false, photoUri: item?.photoUri, size: 36),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
              Text(title.isEmpty ? l10n.conversations : title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
              if (subtitle.isNotEmpty) Text(subtitle, maxLines: 1, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.bodySmall),
            ]),
          ),
        ]),
      ),
      body: Column(children: [
        const DefaultAppBanner(),
        Expanded(
          // No spinner: with a cache the messages are there on the first frame; without one this stays empty for the
          // few milliseconds the provider takes.
          child: ListView.builder(
            controller: _scroll,
            reverse: true,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            itemCount: messages.length + (chat.loadingOlder ? 1 : 0),
            itemBuilder: (context, index) {
              if (index == messages.length) return const Padding(padding: EdgeInsets.all(16), child: Center(child: SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2))));
              final message = messages[index];
              final older = index + 1 < messages.length ? messages[index + 1] : null;
              final showDay = older == null || !sameDay(older.date, message.date);
              final starred = chat.starred.contains(message.providerId);
              return Padding(
                key: ValueKey('${message.kind}:${message.providerId}'),
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Column(children: [
                  if (showDay)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      child: Text(dayLabel(context, message.date), style: Theme.of(context).textTheme.labelMedium?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
                    ),
                  Align(
                    alignment: message.outbound ? Alignment.centerRight : Alignment.centerLeft,
                    child: MessageBubble(
                      message: message, isAdmin: chat.admin.containsKey(message.providerId), adminName: chat.admin[message.providerId], starred: starred,
                      onLongPress: () => _actions(message, starred),
                      onRetry: () => ref.read(repositoryProvider).send(addresses: message.addresses, body: message.body, subscriptionId: message.subscriptionId),
                      onOpenImage: _openImage,
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
          defaultSim: messages.isNotEmpty ? messages.first.subscriptionId : null,
          onSend: (body, sim, at) async {
            await ref.read(repositoryProvider).send(addresses: addresses, body: body, subscriptionId: sim, at: at);
          },
        ),
      ]),
    );
  }
}
