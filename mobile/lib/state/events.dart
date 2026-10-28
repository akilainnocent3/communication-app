import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../platform/telephony_api.g.dart';
import 'chat.dart';
import 'threads.dart';

/// Turns native events into precise refreshes: the named thread's row and, if it is open, that chat. Events are
/// coalesced for 250 ms (a multipart SMS, a send with its status reports and a delivery arrive in bursts). An event
/// without a thread (an outside change to the message store, already debounced natively) refreshes the list's newest
/// page and the open chats. The app's own writes (mark read, archive…) update state directly and raise no event.
class EventRouter {
  EventRouter(this.ref, {Stream<TelephonyEvent>? source, this.window = const Duration(milliseconds: 250)}) {
    _subscription = (source ?? events()).listen(_on);
  }

  final Ref ref;
  final Duration window;
  late final StreamSubscription<TelephonyEvent> _subscription;
  final Set<int> _threads = {};
  bool _everything = false;
  bool _names = false;
  Timer? _timer;
  /// Non-thread events the app reacts to (revoked, launch): handled by the app shell.
  final StreamController<TelephonyEvent> _other = StreamController.broadcast();
  Stream<TelephonyEvent> get other => _other.stream;

  void _on(TelephonyEvent event) {
    switch (event.type) {
      case 'message_received' || 'message_changed' || 'send_state':
        if (event.threadId != null) {
          _threads.add(event.threadId!);
        } else {
          _everything = true;
        }
      case 'contacts_changed':
        _names = true;
      default:
        _other.add(event);
        return;
    }
    _timer ??= Timer(window, _flush);
  }

  Future<void> _flush() async {
    _timer = null;
    final threads = Set.of(_threads);
    final everything = _everything;
    final names = _names;
    _threads.clear();
    _everything = false;
    _names = false;
    final list = ref.read(threadsProvider.notifier);
    if (everything) await list.refresh();
    for (final id in threads) {
      await list.refreshThread(id);
    }
    if (names) await list.refreshNames();
    for (final id in Set.of(openChats)) {
      if (everything || threads.contains(id)) await ref.read(chatProvider(id).notifier).refreshLatest();
    }
  }

  void dispose() {
    _timer?.cancel();
    _subscription.cancel();
    _other.close();
  }
}

final eventRouterProvider = Provider<EventRouter>((ref) {
  final router = EventRouter(ref);
  ref.onDispose(router.dispose);
  return router;
});
