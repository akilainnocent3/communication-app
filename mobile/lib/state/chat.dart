import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/conversations_repository.dart';
import '../platform/telephony_api.g.dart';
import '../providers.dart';

class ChatState {
  const ChatState({this.messages = const [], this.loaded = false, this.hasOlder = true, this.loadingOlder = false, this.admin = const {}, this.starred = const {}});

  /// Newest first (the chat list is reversed).
  final List<ProviderMessage> messages;
  /// true once the cache or the provider answered: never a spinner when the cache has the conversation.
  final bool loaded;
  final bool hasOlder;
  final bool loadingOlder;
  /// provider id → admin name, for "Sent by admin".
  final Map<int, String?> admin;
  final Set<int> starred;

  ChatState copyWith({List<ProviderMessage>? messages, bool? loaded, bool? hasOlder, bool? loadingOlder, Map<int, String?>? admin, Set<int>? starred}) => ChatState(
        messages: messages ?? this.messages, loaded: loaded ?? this.loaded, hasOlder: hasOlder ?? this.hasOlder, loadingOlder: loadingOlder ?? this.loadingOlder,
        admin: admin ?? this.admin, starred: starred ?? this.starred,
      );
}

/// Threads with an open chat, so events refresh only chats that exist.
final openChats = <int>{};

/// One conversation: cached newest messages on the first frame, then the provider's newest 50, older pages of 50 as
/// the user scrolls up. Disposed when the chat closes (nothing stays cached in memory per opened conversation).
class ChatController extends Notifier<ChatState> {
  ChatController(this.threadId);
  final int threadId;

  ConversationsRepository get _repo => ref.read(repositoryProvider);

  @override
  ChatState build() {
    openChats.add(threadId);
    ref.onDispose(() => openChats.remove(threadId));
    Future.microtask(_start);
    return const ChatState();
  }

  Future<void> _start() async {
    final cached = await _repo.cachedMessages(threadId);
    if (!ref.mounted) return;
    if (cached.isNotEmpty) state = state.copyWith(messages: cached, loaded: true);
    final starred = await _repo.starred('sms');
    if (!ref.mounted) return;
    state = state.copyWith(starred: starred);
    await refreshLatest();
  }

  /// The newest page replaces the newest window; older pages already loaded stay where they are.
  Future<void> refreshLatest() async {
    final latest = await _repo.messages(threadId);
    if (!ref.mounted) return;
    final oldest = latest.isEmpty ? null : latest.last.date;
    final older = oldest == null ? <ProviderMessage>[] : state.messages.where((m) => m.date < oldest).toList();
    final messages = [...latest, ...older];
    state = state.copyWith(messages: messages, loaded: true, hasOlder: state.messages.length > latest.length ? state.hasOlder : latest.length == ConversationsRepository.messagePage);
    final admin = await _repo.adminSent(messages);
    if (ref.mounted) state = state.copyWith(admin: admin);
  }

  Future<void> loadOlder() async {
    if (state.loadingOlder || !state.hasOlder || state.messages.isEmpty) return;
    state = state.copyWith(loadingOlder: true);
    try {
      final page = await _repo.messages(threadId, before: state.messages.last.date);
      if (!ref.mounted) return;
      final seen = {for (final m in state.messages) '${m.kind}:${m.providerId}'};
      final messages = [...state.messages, ...page.where((m) => !seen.contains('${m.kind}:${m.providerId}'))];
      state = state.copyWith(messages: messages, hasOlder: page.length == ConversationsRepository.messagePage);
      final admin = await _repo.adminSent(page);
      if (ref.mounted) state = state.copyWith(admin: {...state.admin, ...admin});
    } finally {
      if (ref.mounted) state = state.copyWith(loadingOlder: false);
    }
  }

  Future<void> toggleStar(ProviderMessage message) async {
    final starred = !state.starred.contains(message.providerId);
    state = state.copyWith(starred: starred ? {...state.starred, message.providerId} : (Set.of(state.starred)..remove(message.providerId)));
    await _repo.setStarred(message, starred);
  }

  Future<void> delete(ProviderMessage message) async {
    state = state.copyWith(messages: state.messages.where((m) => !(m.kind == message.kind && m.providerId == message.providerId)).toList());
    await _repo.phone.deleteMessage(message.kind, message.providerId);
  }
}

final chatProvider = NotifierProvider.autoDispose.family<ChatController, ChatState, int>(ChatController.new);
