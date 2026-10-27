import 'dart:async';

import '../../platform/telephony_api.g.dart';
import '../services.dart';
import 'backoff.dart';
import 'sync_engine.dart';

Stream<TelephonyEvent> telephonyEvents() => events();

/// The sync loop that runs inside the native foreground service (headless Flutter engine). Triggers: native events
/// (a message arrived, a send changed state, the network came back, an FCM wake-up, "Sync now"), and a poll timer
/// as a fallback when FCM is not configured. Failures back off exponentially with jitter.
class BackgroundSync {
  BackgroundSync(this.services, {Stream<TelephonyEvent>? events}) : _events = events ?? telephonyEvents();

  final AppServices services;
  final Stream<TelephonyEvent> _events;
  final Backoff _backoff = Backoff();
  Timer? _timer;
  StreamSubscription<TelephonyEvent>? _subscription;
  Duration _poll = const Duration(seconds: 20);
  bool _stopped = false;

  void start() {
    _subscription = _events.listen((event) {
      if (const {'message_received', 'message_changed', 'send_state', 'network', 'outbox_changed', 'sync_requested', 'push'}.contains(event.type)) {
        if (event.type == 'network' && event.state == 'lost') return;
        _schedule(Duration.zero, forceHeartbeat: event.type == 'network');
      }
    });
    _schedule(Duration.zero, forceHeartbeat: true);
  }

  void stop() {
    _stopped = true;
    _timer?.cancel();
    _subscription?.cancel();
  }

  void _schedule(Duration delay, {bool forceHeartbeat = false}) {
    if (_stopped) return;
    _timer?.cancel();
    _timer = Timer(delay, () => _run(forceHeartbeat: forceHeartbeat));
  }

  Future<void> _run({bool forceHeartbeat = false}) async {
    final engine = services.engine;
    if (engine == null) return stop();
    final result = await engine.runOnce(forceHeartbeat: forceHeartbeat);
    switch (result) {
      case SyncResult.ok:
        _backoff.reset();
        _schedule(_poll);
      case SyncResult.revoked:
        await services.wipe();
        stop();
        await services.host.stopSyncService();
      case SyncResult.suspended:
      case SyncResult.upgradeRequired:
        _schedule(const Duration(minutes: 15));
      case SyncResult.offline:
        _schedule(_backoff.next());
      case SyncResult.notEnrolled:
        stop();
    }
  }

  set pollInterval(Duration value) => _poll = value;
}
