import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/services.dart';
import 'data/conversations_repository.dart';
import 'platform/telephony_api.g.dart';

/// Overridden in main() with the opened services.
final servicesProvider = Provider<AppServices>((ref) => throw UnimplementedError('servicesProvider must be overridden'));

final repositoryProvider = Provider<ConversationsRepository>((ref) {
  final services = ref.watch(servicesProvider);
  return ConversationsRepository(phone: services.phone, db: services.db);
});

final conversationsProvider = FutureProvider.family<List<ConversationItem>, (Folder, String)>((ref, args) {
  ref.watch(refreshTickProvider);
  return ref.watch(repositoryProvider).list(args.$1, query: args.$2);
});

final messagesProvider = FutureProvider.family<List<ProviderMessage>, int>((ref, threadId) {
  ref.watch(refreshTickProvider);
  return ref.watch(repositoryProvider).messages(threadId);
});

final simsProvider = FutureProvider<List<SimInfo>>((ref) => ref.watch(servicesProvider).phone.sims());

/// Bumped whenever the native layer reports a change (new message, send state), so lists reload.
class RefreshTick extends Notifier<int> {
  @override
  int build() => 0;
  void bump() => state++;
}

final refreshTickProvider = NotifierProvider<RefreshTick, int>(RefreshTick.new);

/// Quick replies synced from the admin (GET /device/config/), cached in the database.
final quickRepliesProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final services = ref.watch(servicesProvider);
  final api = services.api;
  if (api == null) return const [];
  try {
    final config = await api.config();
    return (config['quick_replies'] as List).cast<Map<String, dynamic>>();
  } on Exception {
    return const [];
  }
});
