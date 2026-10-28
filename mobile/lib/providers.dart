import 'dart:typed_data';

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

final simsProvider = FutureProvider<List<SimInfo>>((ref) => ref.watch(repositoryProvider).phone.sims());

/// Quick replies synced from the admin by the native engine (cached in the encrypted database). Never a server call.
final quickRepliesProvider = FutureProvider.autoDispose<List<Map<String, dynamic>>>((ref) => ref.watch(repositoryProvider).quickReplies());

/// Phone-side settings (`setting.*` in the encrypted database), loaded before the first frame and written through.
class SettingsController extends Notifier<Map<String, String>> {
  @override
  Map<String, String> build() {
    try {
      return Map.of(ref.watch(servicesProvider).settings);
    } on Object {
      return {}; // widget tests without services
    }
  }

  Future<void> set(String key, String value) async {
    state = {...state, key: value};
    await ref.read(servicesProvider).db.setValue('setting.$key', value);
    if (key == 'secure_screen') await ref.read(servicesProvider).host.setSecureScreen(value == '1');
  }

  bool flag(String key, {bool fallback = false}) {
    final value = state[key];
    return value == null || value.isEmpty ? fallback : value == '1';
  }
}

final settingsProvider = NotifierProvider<SettingsController, Map<String, String>>(SettingsController.new);

/// Persisted text size (0.85–1.4).
final textScaleProvider = Provider<double>((ref) => double.tryParse(ref.watch(settingsProvider.select((s) => s['text_scale'] ?? '')) ?? '')?.clamp(0.85, 1.4) ?? 1.0);

/// Small JPEGs from the native layer (MMS parts, contact photos), decoded at display size. Kept in a small LRU so
/// scrolling back does not ask again; the bytes never leave memory.
class ThumbnailCache {
  ThumbnailCache(this.repository);
  final ConversationsRepository repository;
  static const _capacity = 120;
  final _entries = <String, Uint8List?>{};
  final _pending = <String, Future<Uint8List?>>{};

  Uint8List? peek(String uri, int px) => _entries['$px:$uri'];
  bool has(String uri, int px) => _entries.containsKey('$px:$uri');

  Future<Uint8List?> load(String uri, int px) {
    final key = '$px:$uri';
    if (_entries.containsKey(key)) {
      final value = _entries.remove(key);
      _entries[key] = value; // most recently used last
      return Future.value(value);
    }
    return _pending[key] ??= repository.phone.thumbnail(uri, px).catchError((Object _) => null).then((bytes) {
      _pending.remove(key);
      _entries[key] = bytes;
      while (_entries.length > _capacity) {
        _entries.remove(_entries.keys.first);
      }
      return bytes;
    });
  }

  void clear() => _entries.clear();
}

final thumbnailCacheProvider = Provider<ThumbnailCache>((ref) => ThumbnailCache(ref.watch(repositoryProvider)));
