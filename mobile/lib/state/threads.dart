import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/conversations_repository.dart';
import '../platform/telephony_api.g.dart';
import '../providers.dart';

class ThreadsState {
  const ThreadsState({this.items = const [], this.loaded = false, this.hasMore = true, this.loadingMore = false});

  /// Every conversation loaded so far (all folders), pinned first then newest.
  final List<ConversationItem> items;
  /// true once the cache or the provider answered (until then the list shows nothing rather than "no messages").
  final bool loaded;
  final bool hasMore;
  final bool loadingMore;

  ThreadsState copyWith({List<ConversationItem>? items, bool? loaded, bool? hasMore, bool? loadingMore}) =>
      ThreadsState(items: items ?? this.items, loaded: loaded ?? this.loaded, hasMore: hasMore ?? this.hasMore, loadingMore: loadingMore ?? this.loadingMore);
}

/// The conversation list, app-wide and incremental: the encrypted cache on the first frame, then the provider's
/// newest page (50) reconciled in, older pages on scroll, and single rows replaced when an event names their thread.
/// Nothing here reloads the whole list because something happened to one conversation.
class ThreadsController extends Notifier<ThreadsState> {
  int _providerCount = 0;
  Future<void>? _refreshing;

  ConversationsRepository get _repo => ref.read(repositoryProvider);

  @override
  ThreadsState build() {
    Future.microtask(_start);
    return const ThreadsState();
  }

  Future<void> _start() async {
    final cached = await _repo.cached();
    if (cached.isNotEmpty) state = state.copyWith(items: cached, loaded: true);
    await refresh();
  }

  /// Names already known for these numbers (from the cache), so a refreshed row never flickers back to a number.
  Map<String, ContactInfo> get _known => {
        for (final i in state.items)
          if (i.saved && i.thread.addresses.length == 1) i.thread.addresses.first: ContactInfo(address: i.thread.addresses.first, displayName: i.title, photoUri: i.photoUri),
      };

  /// Re-reads the newest page from the provider. Threads newer than the page's oldest that it no longer has are gone.
  Future<void> refresh() => _refreshing ??= _refresh().whenComplete(() => _refreshing = null);

  Future<void> _refresh() async {
    final page = await _repo.page(0, known: _known);
    _providerCount = page.length;
    _merge(page, authoritative: true);
    state = state.copyWith(loaded: true, hasMore: page.length == ConversationsRepository.pageSize);
    final named = await _repo.withNames(page);
    _merge(named, authoritative: false);
    await _repo.saveToCache(named);
    await _repo.pruneCache(named);
  }

  Future<void> loadMore() async {
    if (state.loadingMore || !state.hasMore) return;
    state = state.copyWith(loadingMore: true);
    try {
      final page = await _repo.page(_providerCount, known: _known);
      _providerCount += page.length;
      _merge(page, authoritative: false);
      final named = await _repo.withNames(page);
      _merge(named, authoritative: false);
      await _repo.saveToCache(named);
      state = state.copyWith(hasMore: page.length == ConversationsRepository.pageSize);
    } finally {
      state = state.copyWith(loadingMore: false);
    }
  }

  void _merge(List<ConversationItem> page, {required bool authoritative}) {
    final byId = {for (final i in state.items) i.id: i};
    if (authoritative && page.isNotEmpty) {
      final oldest = page.map((i) => i.thread.date).reduce((a, b) => a < b ? a : b);
      final ids = {for (final i in page) i.id};
      byId.removeWhere((id, item) => item.thread.date >= oldest && !ids.contains(id));
    }
    for (final item in page) {
      byId[item.id] = item;
    }
    state = state.copyWith(items: byId.values.toList()..sort(compareItems));
  }

  /// One conversation changed (a message arrived, a send finished, it was read elsewhere).
  Future<void> refreshThread(int threadId) async {
    final item = await _repo.refreshThread(threadId);
    final rest = state.items.where((i) => i.id != threadId);
    state = state.copyWith(items: [...rest, ?item]..sort(compareItems), loaded: true);
  }

  /// The address book changed: names and photos again, for what is loaded.
  Future<void> refreshNames() async {
    final named = await _repo.withNames(state.items);
    state = state.copyWith(items: named..sort(compareItems));
    await _repo.saveToCache(named);
  }

  void _update(Iterable<int> ids, ConversationItem Function(ConversationItem) change) {
    final set = ids.toSet();
    state = state.copyWith(items: [for (final i in state.items) set.contains(i.id) ? change(i) : i]..sort(compareItems));
  }

  Future<void> setPinned(Iterable<int> ids, bool value) async {
    _update(ids, (i) => i.copyWith(pinned: value));
    for (final id in ids) {
      await _repo.setPinned(id, value);
    }
  }

  Future<void> setArchived(Iterable<int> ids, bool value) async {
    _update(ids, (i) => i.copyWith(archived: value));
    for (final id in ids) {
      await _repo.setArchived(id, value);
    }
  }

  Future<void> setMuted(Iterable<int> ids, bool value) async {
    _update(ids, (i) => i.copyWith(muted: value));
    for (final id in ids) {
      await _repo.setMuted(id, value);
    }
  }

  Future<void> setSpam(Iterable<int> ids, bool value) async {
    _update(ids, (i) => i.copyWith(spam: value || i.blocked));
    for (final id in ids) {
      await _repo.setSpam(id, value);
    }
  }

  Future<void> block(List<ConversationItem> items, {required bool blocked}) async {
    for (final item in items) {
      await _repo.block(item.thread.addresses, blocked: blocked);
    }
    _update(items.map((i) => i.id), (i) => i.copyWith(blocked: blocked, spam: blocked));
  }

  /// Marks read off the UI path, and only when something is unread (no provider write, no sync event otherwise).
  Future<void> markRead(Iterable<int> ids) async {
    final unread = state.items.where((i) => ids.contains(i.id) && i.thread.unreadCount > 0).toList();
    if (unread.isEmpty) return;
    _update(unread.map((i) => i.id), (i) => i.copyWith(thread: _withUnread(i.thread, 0)));
    for (final item in unread) {
      await _repo.markRead(item.id);
    }
    await _repo.saveToCache(state.items.where((i) => unread.any((u) => u.id == i.id)).toList());
  }

  Future<void> delete(Iterable<int> ids) async {
    final set = ids.toSet();
    state = state.copyWith(items: state.items.where((i) => !set.contains(i.id)).toList());
    for (final id in set) {
      await _repo.delete(id);
    }
  }

  ConversationItem? byId(int threadId) => state.items.where((i) => i.id == threadId).firstOrNull;
}

ThreadSummary _withUnread(ThreadSummary t, int unread) =>
    ThreadSummary(threadId: t.threadId, addresses: t.addresses, snippet: t.snippet, date: t.date, unreadCount: unread, messageCount: t.messageCount, hasMms: t.hasMms);

final threadsProvider = NotifierProvider<ThreadsController, ThreadsState>(ThreadsController.new);

/// One folder's rows. Rebuilds only when the rows of that folder change.
final folderProvider = Provider.autoDispose.family<List<ConversationItem>, Folder>((ref, folder) {
  final items = ref.watch(threadsProvider.select((s) => s.items));
  return [for (final i in items) if (i.inFolder(folder)) i];
});

/// One row, for screens that show a single conversation (chat title, unread state).
final threadItemProvider = Provider.autoDispose.family<ConversationItem?, int>((ref, threadId) =>
    ref.watch(threadsProvider.select((s) => s.items.where((i) => i.id == threadId).firstOrNull)));
