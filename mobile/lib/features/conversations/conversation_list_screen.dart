import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/conversations_repository.dart';
import '../../l10n/app_localizations.dart';
import '../../providers.dart';
import '../common/widgets.dart';

/// Conversation list: pinned first, unread in bold with a count, swipe to archive, multi-select actions.
class ConversationListScreen extends ConsumerStatefulWidget {
  const ConversationListScreen({super.key, required this.folder});
  final Folder folder;
  @override
  ConsumerState<ConversationListScreen> createState() => _ConversationListScreenState();
}

class _ConversationListScreenState extends ConsumerState<ConversationListScreen> {
  final Set<int> _selected = {};
  String _query = '';
  bool _searching = false;

  void _reload() => ref.read(refreshTickProvider.notifier).bump();

  Future<void> _bulk(Future<void> Function(ConversationsRepository repo, ConversationItem item) action, List<ConversationItem> items) async {
    final repo = ref.read(repositoryProvider);
    for (final item in items.where((i) => _selected.contains(i.thread.threadId))) {
      await action(repo, item);
    }
    setState(_selected.clear);
    _reload();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final list = ref.watch(conversationsProvider((widget.folder, _query)));
    final items = list.value ?? const <ConversationItem>[];
    final selecting = _selected.isNotEmpty;
    final title = switch (widget.folder) { Folder.inbox => l10n.conversations, Folder.archived => l10n.archived, Folder.spam => l10n.spamBlocked };
    return Scaffold(
      appBar: selecting
          ? AppBar(
              leading: IconButton(icon: const Icon(Icons.close), tooltip: l10n.cancel, onPressed: () => setState(_selected.clear)),
              title: Text(l10n.selectedCount(_selected.length)),
              actions: [
                IconButton(tooltip: l10n.markRead, icon: const Icon(Icons.mark_chat_read_outlined), onPressed: () => _bulk((r, i) => r.markRead(i.thread.threadId), items)),
                IconButton(tooltip: l10n.pin, icon: const Icon(Icons.push_pin_outlined), onPressed: () => _bulk((r, i) => r.setPinned(i.thread.threadId, !i.pinned), items)),
                IconButton(
                  tooltip: widget.folder == Folder.archived ? l10n.unarchive : l10n.archive, icon: const Icon(Icons.archive_outlined),
                  onPressed: () => _bulk((r, i) => r.setArchived(i.thread.threadId, widget.folder != Folder.archived), items),
                ),
                PopupMenuButton<String>(
                  onSelected: (value) async {
                    switch (value) {
                      case 'mute': await _bulk((r, i) => r.setMuted(i.thread.threadId, !i.muted), items);
                      case 'spam': await _bulk((r, i) => r.setSpam(i.thread.threadId, widget.folder != Folder.spam), items);
                      case 'block': await _bulk((r, i) => r.block(i.thread.addresses, blocked: !i.blocked), items);
                      case 'delete':
                        final ok = await showDialog<bool>(context: context, builder: (context) => AlertDialog(
                          content: Text(l10n.deleteConfirm(_selected.length)),
                          actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: Text(l10n.cancel)), FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(l10n.delete))],
                        ));
                        if (ok == true) await _bulk((r, i) => r.delete(i.thread.threadId), items);
                    }
                  },
                  itemBuilder: (_) => [
                    PopupMenuItem(value: 'mute', child: Text(l10n.mute)),
                    PopupMenuItem(value: 'spam', child: Text(widget.folder == Folder.spam ? l10n.unblock : l10n.moveToSpam)),
                    PopupMenuItem(value: 'block', child: Text(l10n.block)),
                    PopupMenuItem(value: 'delete', child: Text(l10n.delete)),
                  ],
                ),
              ],
            )
          : AppBar(
              title: _searching
                  ? TextField(autofocus: true, decoration: InputDecoration(hintText: l10n.searchHint, border: InputBorder.none), onChanged: (value) => setState(() => _query = value))
                  : Text(title),
              actions: [
                IconButton(tooltip: l10n.searchHint, icon: Icon(_searching ? Icons.close : Icons.search), onPressed: () => setState(() { _searching = !_searching; _query = ''; })),
                PopupMenuButton<String>(
                  onSelected: (route) => context.push(route),
                  itemBuilder: (_) => [
                    if (widget.folder != Folder.archived) PopupMenuItem(value: '/archived', child: Text(l10n.archived)),
                    if (widget.folder != Folder.spam) PopupMenuItem(value: '/spam', child: Text(l10n.spamBlocked)),
                    PopupMenuItem(value: '/settings', child: Text(l10n.settings)),
                  ],
                ),
              ],
            ),
      body: Column(children: [
        const DefaultAppBanner(),
        Expanded(
          child: RefreshIndicator(
            onRefresh: () async => _reload(),
            child: list.isLoading && items.isEmpty
                ? const Center(child: CircularProgressIndicator())
                : items.isEmpty
                    ? ListView(children: [
                        const SizedBox(height: 120),
                        const Icon(Icons.forum_outlined, size: 56),
                        const SizedBox(height: 12),
                        Center(child: Text(l10n.noConversations, style: Theme.of(context).textTheme.titleMedium)),
                        Center(child: Padding(padding: const EdgeInsets.all(8), child: Text(l10n.noConversationsBody, textAlign: TextAlign.center))),
                      ])
                    : ListView.builder(
                        itemCount: items.length,
                        itemBuilder: (context, index) => _Row(
                          item: items[index],
                          selected: _selected.contains(items[index].thread.threadId),
                          onTap: () => selecting
                              ? setState(() => _selected.contains(items[index].thread.threadId) ? _selected.remove(items[index].thread.threadId) : _selected.add(items[index].thread.threadId))
                              : context.push('/chat/${items[index].thread.threadId}'),
                          onLongPress: () => setState(() => _selected.add(items[index].thread.threadId)),
                          onArchive: () async {
                            final repo = ref.read(repositoryProvider);
                            final id = items[index].thread.threadId;
                            await repo.setArchived(id, widget.folder != Folder.archived);
                            _reload();
                            if (!context.mounted) return;
                            ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                              content: Text(widget.folder == Folder.archived ? l10n.unarchive : l10n.archive),
                              action: SnackBarAction(label: l10n.undo, onPressed: () async { await repo.setArchived(id, widget.folder == Folder.archived); _reload(); }),
                            ));
                          },
                        ),
                      ),
          ),
        ),
      ]),
      floatingActionButton: widget.folder == Folder.inbox && !selecting
          ? FloatingActionButton.extended(onPressed: () => context.push('/compose'), icon: const Icon(Icons.chat_outlined), label: Text(l10n.startChat))
          : null,
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.item, required this.selected, required this.onTap, required this.onLongPress, required this.onArchive});
  final ConversationItem item;
  final bool selected;
  final VoidCallback onTap;
  final VoidCallback onLongPress;
  final VoidCallback onArchive;

  @override
  Widget build(BuildContext context) {
    final unread = item.thread.unreadCount > 0;
    final theme = Theme.of(context);
    final weight = unread ? FontWeight.w700 : FontWeight.w400;
    return Dismissible(
      key: ValueKey(item.thread.threadId),
      background: Container(color: theme.colorScheme.primaryContainer, alignment: Alignment.centerLeft, padding: const EdgeInsets.only(left: 24), child: const Icon(Icons.archive_outlined)),
      secondaryBackground: Container(color: theme.colorScheme.primaryContainer, alignment: Alignment.centerRight, padding: const EdgeInsets.only(right: 24), child: const Icon(Icons.archive_outlined)),
      confirmDismiss: (_) async { onArchive(); return false; },
      child: ListTile(
        selected: selected,
        onTap: onTap,
        onLongPress: onLongPress,
        leading: selected ? CircleAvatar(radius: 22, child: Icon(Icons.check, color: theme.colorScheme.onPrimaryContainer)) : ContactAvatar(title: item.title, address: item.thread.addresses.first, saved: item.saved),
        title: Row(children: [
          Expanded(child: Text(item.title, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontWeight: weight))),
          if (item.pinned) const Padding(padding: EdgeInsets.only(left: 4), child: Icon(Icons.push_pin, size: 14)),
          if (item.muted) const Padding(padding: EdgeInsets.only(left: 4), child: Icon(Icons.notifications_off_outlined, size: 14)),
          Padding(padding: const EdgeInsets.only(left: 8), child: Text(listTime(context, item.thread.date), style: theme.textTheme.bodySmall?.copyWith(fontWeight: weight))),
        ]),
        subtitle: Row(children: [
          Expanded(child: Text(item.thread.snippet, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontWeight: weight, color: unread ? theme.colorScheme.onSurface : null))),
          if (unread)
            Container(
              margin: const EdgeInsets.only(left: 8),
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
              decoration: BoxDecoration(color: theme.colorScheme.primary, borderRadius: BorderRadius.circular(10)),
              child: Text('${item.thread.unreadCount}', style: TextStyle(color: theme.colorScheme.onPrimary, fontSize: 11, fontWeight: FontWeight.w700)),
            ),
        ]),
      ),
    );
  }
}
