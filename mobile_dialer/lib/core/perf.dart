import 'package:flutter/foundation.dart';
import 'package:flutter/scheduler.dart';

/// Timings for docs/sms-mobile-performance.md, printed to logcat as `cm.perf …` in profile and debug builds only
/// (never in release). Only names, counts and milliseconds: never text, names or numbers.
class Perf {
  static bool get enabled => kProfileMode || kDebugMode;
  static final Map<String, Stopwatch> _running = {};
  static final Set<String> _once = {};
  static final List<FrameTiming> _frames = [];
  static bool _watching = false;

  static void log(String line) {
    if (enabled) debugPrint('cm.perf $line');
  }

  /// A point in time; the measuring script lines it up with logcat's activity START line.
  static void mark(String name, {bool once = true}) {
    if (!enabled || (once && !_once.add(name))) return;
    log('mark $name');
  }

  static void start(String name) {
    if (enabled) _running[name] = Stopwatch()..start();
  }

  static void end(String name) {
    final watch = _running.remove(name);
    if (watch != null) log('span $name ${watch.elapsedMicroseconds / 1000} ms');
  }

  /// Frame build/raster times, summarised after each burst of frames (scrolling, opening a screen).
  static void watchFrames() {
    if (!enabled || _watching) return;
    _watching = true;
    SchedulerBinding.instance.addTimingsCallback((timings) {
      _frames.addAll(timings);
      _flush ??= Future<void>.delayed(const Duration(seconds: 2), _summarise);
    });
  }

  static Future<void>? _flush;

  static void _summarise() {
    _flush = null;
    if (_frames.length < 10) return _frames.clear();
    List<double> ms(Duration Function(FrameTiming) pick) => _frames.map((f) => pick(f).inMicroseconds / 1000).toList()..sort();
    final build = ms((f) => f.buildDuration);
    final raster = ms((f) => f.rasterDuration);
    double at(List<double> values, double q) => values[((values.length - 1) * q).round()];
    final slowBuild = build.where((v) => v > 16).length;
    final slowRaster = raster.where((v) => v > 16).length;
    log('frames n=${_frames.length} build_p50=${at(build, .5)} build_p90=${at(build, .9)} build_max=${build.last} build_over16=$slowBuild '
        'raster_p50=${at(raster, .5)} raster_p90=${at(raster, .9)} raster_max=${raster.last} raster_over16=$slowRaster');
    _frames.clear();
  }
}
