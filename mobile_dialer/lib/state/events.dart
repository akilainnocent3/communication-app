import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/phone/phone_screen.dart';
import '../platform/telephony_api.g.dart';

/// Turns native events into refreshes: calls_changed (a call ended, the call log or the call-back tasks changed) and
/// contacts_changed reload the Phone screens' data, coalesced for 250 ms. Everything else (sync_state, launch) goes to
/// the app shell.
class EventRouter {
  EventRouter(this.ref, {Stream<TelephonyEvent>? source, this.window = const Duration(milliseconds: 250)}) {
    _subscription = (source ?? events()).listen(_on);
  }

  final Ref ref;
  final Duration window;
  late final StreamSubscription<TelephonyEvent> _subscription;
  bool _calls = false;
  bool _contacts = false;
  Timer? _timer;
  final StreamController<TelephonyEvent> _other = StreamController.broadcast();
  Stream<TelephonyEvent> get other => _other.stream;

  void _on(TelephonyEvent event) {
    switch (event.type) {
      case 'calls_changed':
        _calls = true;
      case 'contacts_changed':
        _contacts = true;
      default:
        _other.add(event);
        return;
    }
    _timer ??= Timer(window, _flush);
  }

  void _flush() {
    _timer = null;
    if (_calls) ref.invalidate(recentsProvider);
    if (_contacts) ref.invalidate(phoneContactsProvider);
    _calls = false;
    _contacts = false;
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
