import 'dart:math';

/// Exponential backoff with full jitter. Never a tight loop: the shortest wait is `base`.
class Backoff {
  Backoff({this.base = const Duration(seconds: 2), this.cap = const Duration(minutes: 5), Random? random}) : _random = random ?? Random();
  final Duration base;
  final Duration cap;
  final Random _random;
  int _failures = 0;

  int get failures => _failures;
  void reset() => _failures = 0;

  Duration next() {
    final ceiling = min(cap.inMilliseconds, base.inMilliseconds * pow(2, _failures).toInt());
    _failures = min(_failures + 1, 20);
    return Duration(milliseconds: max(base.inMilliseconds, _random.nextInt(ceiling + 1)));
  }
}
