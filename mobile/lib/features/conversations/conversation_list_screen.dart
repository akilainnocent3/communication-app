import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/perf.dart';
import '../../core/text/phone_format.dart';
import '../../data/conversations_repository.dart';
import '../../l10n/app_localizations.dart';
import '../../platform/telephony_api.g.dart';
import '../../providers.dart';
import '../../state/threads.dart';
import '../../ui/skin/tokens.dart';
import '../../ui/widgets/badges.dart';
import '../common/widgets.dart';
import 'list_header.dart';

/// Conversation list: pinned first, unread in bold with a count, swipe actions, multi-select, search. Draws the
/// encrypted cache on the first frame; rows change one at a time as events arrive.
class ConversationListScreen extends ConsumerStatefulWidget {
  const ConversationListScreen({super.key, required this.folder});
  final Folder folder;
  @override
  ConsumerState<ConversationListScreen> createState() => _ConversationListScreenState();
}

class _ConversationListScreenState extends ConsumerState<ConversationListScreen> {
  final Set<int> _selected = {};
  final _search = TextEditingController();
  bool _searching = false;
  String _query = '';
  Timer? _debounce;
  int _searchGeneration = 0;
  List<ProviderMessage> _messageHits = const [];
  bool _moreHits = false;

  @override
  void dispose() {
    _debounce?.cancel();
    _search.dispose();
    super.dispose();
  }

  void _toggleSearch() => setState(() {
        _searching = !_searching;
        _query = '';
        _search.clear();
        _messageHits = const [];
        _searchGeneration++;
      });

  /// The cache answers at once (titles, numbers, snippets); message bodies are searched natively 250 ms after the
  /// last keystroke, and an answer for an older query is dropped.
  void _onQuery(String value) {
    setState(() => _query = value.trim().toLowerCase());
    _debounce?.cancel();
    final generation = ++_searchGeneration;
    if (_query.length < 2) {
      setState(() => _messageHits = const []);
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 250), () => _searchBodies(generation, offset: 0));
  }

  Future<void> _searchBodies(int generation, {required int offset}) async {
    final hits = await ref.read(repositoryProvider).searchMessages(_query, offset: offset);
    if (!mounted || generation != _searchGeneration) return;
    setState(() {
      _messageHits = offset == 0 ? hits : [..._messageHits, ...hits];
      _moreHits = hits.length == 30;
    });
  }

  Future<void> _bulk(Future<void> Function(ThreadsController threads, List<ConversationItem> items) action, List<ConversationItem> items) async {
    final chosen = items.where((i) => _selected.contains(i.id)).toList();
    setState(_selected.clear);
    await action(ref.read(threadsProvider.notifier), chosen);
  }

  void _open(ConversationItem item) {
    Perf.start('chat_open');
    context.push('/chat/${item.id}');
  }

  Future<void> _swipe(ConversationItem item, SwipeAction action) async {
    final l10n = AppLocalizations.of(context);
    final threads = ref.read(threadsProvider.notifier);
    HapticFeedback.lightImpact();
    switch (action) {
      case SwipeAction.archive:
        final archive = widget.folder != Folder.archived;
        await threads.setArchived([item.id], archive);
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(archive ? l10n.archive : l10n.unarchive),
          action: SnackBarAction(label: l10n.undo, onPressed: () => threads.setArchived([item.id], !archive)),
        ));
      case SwipeAction.read:
        await threads.markRead([item.id]);
      case SwipeAction.delete:
        if (await _confirmDelete(1)) await threads.delete([item.id]);
      case SwipeAction.none:
        break;
    }
  }

  Future<bool> _confirmDelete(int count) async {
    final l10n = AppLocalizations.of(context);
    return await showDialog<bool>(context: context, builder: (context) => AlertDialog(
          content: Text(l10n.deleteConfirm(count)),
          actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: Text(l10n.cancel)), FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(l10n.delete))],
        )) == true;
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final tokens = SkinTokens.of(context);
    final items = ref.watch(folderProvider(widget.folder));
    final loaded = ref.watch(threadsProvider.select((s) => s.loaded));
    final compact = ref.watch(settingsProvider.select((s) => s['density'] == 'compact'));
    final selecting = _selected.isNotEmpty;
    final visible = _searching && _query.isNotEmpty ? items.where((i) => i.matches(_query)).toList() : items;
    if (items.isNotEmpty) WidgetsBinding.instance.addPostFrameCallback((_) => Perf.mark('list_visible'));
    final title = switch (widget.folder) { Folder.inbox => l10n.conversations, Folder.archived => l10n.archived, Folder.spam => l10n.spamBlocked };
    final extent = tokens.rowExtent(compact: compact, textScale: MediaQuery.textScalerOf(context).scale(1));
    final unread = items.where((i) => i.thread.unreadCount > 0).length;

    final List<Widget> header;
    if (selecting) {
      header = [_selectionBar(l10n, items)];
    } else if (_searching) {
      header = [
        SliverAppBar(
          pinned: true,
          leading: BackButton(onPressed: _toggleSearch),
          title: TextField(controller: _search, autofocus: true, decoration: InputDecoration(hintText: l10n.searchHint, border: InputBorder.none), onChanged: _onQuery),
        ),
      ];
    } else {
      header = ListHeader.slivers(
        context: context, title: widget.folder == Folder.inbox ? l10n.appTitle : title, subtitle: unread > 0 ? l10n.unreadConversations(unread) : null,
        inbox: widget.folder == Folder.inbox, onSearch: _toggleSearch, menu: _menu(l10n),
      );
    }

    return Scaffold(
      backgroundColor: tokens.pageBackground,
      floatingActionButton: widget.folder == Folder.inbox && !selecting && !_searching ? ComposeButton(label: l10n.startChat, onPressed: () => context.push('/compose')) : null,
      body: NotificationListener<ScrollNotification>(
        onNotification: (n) {
          if (n.metrics.extentAfter < extent * 15) ref.read(threadsProvider.notifier).loadMore();
          return false;
        },
        child: RefreshIndicator(
          onRefresh: () async {
            ref.read(repositoryProvider).phone.syncNow();
            await ref.read(threadsProvider.notifier).refresh();
          },
          edgeOffset: MediaQuery.paddingOf(context).top + kToolbarHeight,
          child: CustomScrollView(slivers: [
            ...header,
            const SliverToBoxAdapter(child: DefaultAppBanner()),
            if (tokens.tabs && widget.folder == Folder.inbox && !selecting && !_searching) SliverToBoxAdapter(child: _Tabs(onContacts: () => context.push('/compose'))),
            if (loaded && visible.isEmpty && _messageHits.isEmpty)
              SliverFillRemaining(hasScrollBody: false, child: _Empty(searching: _searching))
            else
              _rows(visible, tokens, extent),
            if (_searching && _messageHits.isNotEmpty) ...[
              SliverToBoxAdapter(child: Padding(padding: const EdgeInsets.fromLTRB(20, 20, 20, 8), child: Text(l10n.messagesSection, style: Theme.of(context).textTheme.titleSmall))),
              SliverList.builder(
                itemCount: _messageHits.length,
                itemBuilder: (context, index) => _MessageHit(message: _messageHits[index], onTap: () => context.push('/chat/${_messageHits[index].threadId}')),
              ),
              if (_moreHits) SliverToBoxAdapter(child: TextButton(onPressed: () => _searchBodies(_searchGeneration, offset: _messageHits.length), child: Text(l10n.moreResults))),
            ],
            const SliverToBoxAdapter(child: SizedBox(height: 96)),
          ]),
        ),
      ),
    );
  }

  Widget _rows(List<ConversationItem> items, SkinTokens tokens, double extent) {
    final list = SliverFixedExtentList.builder(
      itemExtent: extent,
      itemCount: items.length,
      itemBuilder: (context, index) {
        final item = items[index];
        return _Row(
          key: ValueKey(item.id),
          item: item,
          selected: _selected.contains(item.id),
          first: index == 0,
          last: index == items.length - 1,
          onTap: () => _selected.isNotEmpty ? setState(() => _selected.contains(item.id) ? _selected.remove(item.id) : _selected.add(item.id)) : _open(item),
          onLongPress: () => setState(() => _selected.add(item.id)),
          onSwipe: (action) => _swipe(item, action),
        );
      },
    );
    if (!tokens.groupedList) return list;
    return SliverPadding(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 0),
      sliver: DecoratedSliver(
        decoration: BoxDecoration(color: tokens.listSurface, borderRadius: BorderRadius.circular(tokens.listRadius)),
        sliver: list,
      ),
    );
  }

  Widget _menu(AppLocalizations l10n) => PopupMenuButton<String>(
        icon: const Icon(Icons.more_vert),
        onSelected: (route) => context.push(route),
        itemBuilder: (_) => [
          if (widget.folder != Folder.archived) PopupMenuItem(value: '/archived', child: Text(l10n.archived)),
          if (widget.folder != Folder.spam) PopupMenuItem(value: '/spam', child: Text(l10n.spamBlocked)),
          PopupMenuItem(value: '/settings', child: Text(l10n.settings)),
        ],
      );

  Widget _selectionBar(AppLocalizations l10n, List<ConversationItem> items) => SliverAppBar(
        pinned: true,
        leading: IconButton(icon: const Icon(Icons.close), tooltip: l10n.cancel, onPressed: () => setState(_selected.clear)),
        title: Text(l10n.selectedCount(_selected.length)),
        actions: [
          IconButton(tooltip: l10n.markRead, icon: const Icon(Icons.mark_chat_read_outlined), onPressed: () => _bulk((t, c) => t.markRead(c.map((i) => i.id)), items)),
          IconButton(
            tooltip: l10n.pin, icon: const Icon(Icons.push_pin_outlined),
            onPressed: () => _bulk((t, c) => t.setPinned(c.map((i) => i.id), !c.every((i) => i.pinned)), items),
          ),
          IconButton(
            tooltip: widget.folder == Folder.archived ? l10n.unarchive : l10n.archive, icon: const Icon(Icons.archive_outlined),
            onPressed: () => _bulk((t, c) => t.setArchived(c.map((i) => i.id), widget.folder != Folder.archived), items),
          ),
          PopupMenuButton<String>(
            onSelected: (value) async {
              switch (value) {
                case 'mute': await _bulk((t, c) => t.setMuted(c.map((i) => i.id), !c.every((i) => i.muted)), items);
                case 'spam': await _bulk((t, c) => t.setSpam(c.map((i) => i.id), widget.folder != Folder.spam), items);
                case 'block': await _bulk((t, c) => t.block(c, blocked: !c.every((i) => i.blocked)), items);
                case 'delete':
                  if (await _confirmDelete(_selected.length)) await _bulk((t, c) => t.delete(c.map((i) => i.id)), items);
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
      );
}

class _Tabs extends StatelessWidget {
  const _Tabs({required this.onContacts});
  final VoidCallback onContacts;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final scheme = Theme.of(context).colorScheme;
    Widget tab(String label, bool active, VoidCallback? onTap) => Expanded(
          child: InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(20),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 10),
              child: Column(children: [
                Text(label, style: TextStyle(fontWeight: active ? FontWeight.w700 : FontWeight.w500, color: active ? scheme.onSurface : scheme.onSurfaceVariant)),
                const SizedBox(height: 4),
                Container(height: 3, width: 28, decoration: BoxDecoration(color: active ? scheme.onSurface : Colors.transparent, borderRadius: BorderRadius.circular(2))),
              ]),
            ),
          ),
        );
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 0, 24, 6),
      child: Row(children: [tab(l10n.conversations, true, null), tab(l10n.contacts, false, onContacts)]),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({super.key, required this.item, required this.selected, required this.first, required this.last, required this.onTap, required this.onLongPress, required this.onSwipe});
  final ConversationItem item;
  final bool selected;
  final bool first;
  final bool last;
  final VoidCallback onTap;
  final VoidCallback onLongPress;
  final void Function(SwipeAction action) onSwipe;

  static IconData _icon(SwipeAction action) => switch (action) {
        SwipeAction.archive => Icons.archive_outlined,
        SwipeAction.delete => Icons.delete_outline,
        SwipeAction.read => Icons.mark_chat_read_outlined,
        SwipeAction.none => Icons.block,
      };

  @override
  Widget build(BuildContext context) {
    final tokens = SkinTokens.of(context);
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final unread = item.thread.unreadCount > 0;
    final weight = unread ? FontWeight.w700 : tokens.rowTitleWeight;
    Widget background(SwipeAction action, Alignment alignment) => Container(
          color: action == SwipeAction.delete ? scheme.errorContainer : scheme.primaryContainer,
          alignment: alignment,
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Icon(_icon(action), color: action == SwipeAction.delete ? scheme.onErrorContainer : scheme.onPrimaryContainer),
        );
    final corner = Radius.circular(tokens.groupedList ? tokens.listRadius : 0);
    final row = Material(
      color: selected ? scheme.secondaryContainer.withValues(alpha: 0.6) : tokens.listSurface,
      // One UI's rounded container: the first and last rows carry its corners (ripples stay inside).
      borderRadius: BorderRadius.vertical(top: first ? corner : Radius.zero, bottom: last ? corner : Radius.zero),
      clipBehavior: tokens.groupedList && (first || last) ? Clip.antiAlias : Clip.none,
      child: InkWell(
        onTap: onTap,
        onLongPress: onLongPress,
        child: Padding(
          padding: const EdgeInsets.only(left: 16),
          child: Row(children: [
            selected
                ? SizedBox.square(dimension: tokens.avatarSize, child: CircleAvatar(backgroundColor: scheme.primary, child: Icon(Icons.check, color: scheme.onPrimary)))
                : ContactAvatar(title: item.title, address: item.thread.addresses.first, saved: item.saved, photoUri: item.photoUri),
            const SizedBox(width: 14),
            Expanded(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  border: tokens.dividers && !last ? Border(bottom: BorderSide(color: scheme.outlineVariant.withValues(alpha: 0.5), width: 0.5)) : null,
                ),
                child: Padding(
                  padding: const EdgeInsets.only(right: 16),
                  child: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      Expanded(child: Text(item.title, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: tokens.rowTitleSize, fontWeight: weight, color: scheme.onSurface))),
                      if (item.pinned) Padding(padding: const EdgeInsets.only(left: 4), child: Icon(Icons.push_pin, size: 14, color: scheme.onSurfaceVariant)),
                      if (item.muted) Padding(padding: const EdgeInsets.only(left: 4), child: Icon(Icons.notifications_off_outlined, size: 14, color: scheme.onSurfaceVariant)),
                      Padding(
                        padding: const EdgeInsets.only(left: 8),
                        child: Text(listTime(context, item.thread.date), style: theme.textTheme.bodySmall?.copyWith(fontWeight: unread ? FontWeight.w700 : null, color: unread ? tokens.badge : scheme.onSurfaceVariant)),
                      ),
                    ]),
                    const SizedBox(height: 3),
                    Row(children: [
                      Expanded(
                        child: Text(item.thread.snippet, maxLines: 1, overflow: TextOverflow.ellipsis,
                            style: TextStyle(fontSize: tokens.snippetSize, fontWeight: unread ? FontWeight.w600 : FontWeight.w400, color: unread ? scheme.onSurface : scheme.onSurfaceVariant)),
                      ),
                      if (unread) Padding(padding: const EdgeInsets.only(left: 8), child: UnreadBadge(count: item.thread.unreadCount)),
                    ]),
                  ]),
                ),
              ),
            ),
          ]),
        ),
      ),
    );
    if (tokens.swipeLeft == SwipeAction.none && tokens.swipeRight == SwipeAction.none) return row;
    return Dismissible(
      key: ValueKey('swipe-${item.id}'),
      direction: tokens.swipeRight == SwipeAction.none ? DismissDirection.endToStart : tokens.swipeLeft == SwipeAction.none ? DismissDirection.startToEnd : DismissDirection.horizontal,
      background: background(tokens.swipeRight, Alignment.centerLeft),
      secondaryBackground: background(tokens.swipeLeft, Alignment.centerRight),
      confirmDismiss: (direction) async {
        onSwipe(direction == DismissDirection.startToEnd ? tokens.swipeRight : tokens.swipeLeft);
        return false;
      },
      child: row,
    );
  }
}

class _MessageHit extends StatelessWidget {
  const _MessageHit({required this.message, required this.onTap});
  final ProviderMessage message;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => ListTile(
        onTap: onTap,
        leading: const Icon(Icons.chat_bubble_outline),
        title: Text(message.addresses.map(formatNumber).join(', '), maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Text(message.body, maxLines: 2, overflow: TextOverflow.ellipsis),
        trailing: Text(listTime(context, message.date), style: Theme.of(context).textTheme.bodySmall),
      );
}

class _Empty extends StatelessWidget {
  const _Empty({required this.searching});
  final bool searching;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
        Icon(searching ? Icons.search_off : Icons.forum_outlined, size: 56, color: Theme.of(context).colorScheme.onSurfaceVariant),
        const SizedBox(height: 12),
        Text(searching ? l10n.noResults : l10n.noConversations, style: Theme.of(context).textTheme.titleMedium, textAlign: TextAlign.center),
        if (!searching) Padding(padding: const EdgeInsets.all(8), child: Text(l10n.noConversationsBody, textAlign: TextAlign.center)),
      ]),
    );
  }
}
