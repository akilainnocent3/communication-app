import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/text/phone_format.dart';
import '../../providers.dart';
import '../skin/tokens.dart';

/// Coloured initials (or "#" for an unsaved number), stable per address; the contact photo instead when there is
/// one and photos are on. The photo is a small JPEG decoded at display size; initials show until it arrives.
class ContactAvatar extends ConsumerWidget {
  const ContactAvatar({super.key, required this.title, required this.address, this.saved = false, this.photoUri, this.size});
  final String title;
  final String address;
  final bool saved;
  final String? photoUri;
  final double? size;

  static int hue(String address) => address.codeUnits.fold<int>(0, (h, c) => (h * 31 + c) & 0x7fffffff) % 360;

  static String label(String title, String address, bool saved) {
    final words = title.trim().split(RegExp(r'\s+')).where((w) => w.isNotEmpty).toList();
    if (saved && words.isNotEmpty) return (words.first[0] + (words.length > 1 ? words.last[0] : '')).toUpperCase();
    return addressKind(address) == AddressKind.alphanumeric && address.isNotEmpty ? address.substring(0, 1).toUpperCase() : '#';
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = SkinTokens.of(context);
    final side = size ?? tokens.avatarSize;
    final showPhotos = ref.watch(settingsProvider.select((s) => s['show_photos'] != '0'));
    final shape = tokens.avatarShape == AvatarShape.circle ? const CircleBorder() : RoundedRectangleBorder(borderRadius: BorderRadius.circular(side * 0.3));
    final initials = Center(
      child: Text(label(title, address, saved), style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: side * 0.38), textScaler: TextScaler.noScaling),
    );
    final px = (side * MediaQuery.devicePixelRatioOf(context)).round();
    return SizedBox.square(
      dimension: side,
      child: Material(
        shape: shape,
        clipBehavior: Clip.antiAlias,
        color: HSLColor.fromAHSL(1, hue(address).toDouble(), 0.5, 0.42).toColor(),
        child: photoUri != null && showPhotos ? ThumbnailImage(uri: photoUri!, px: px, placeholder: initials) : initials,
      ),
    );
  }
}

/// A native thumbnail (MMS part or contact photo), decoded at [px] and cached in memory (ThumbnailCache).
class ThumbnailImage extends ConsumerStatefulWidget {
  const ThumbnailImage({super.key, required this.uri, required this.px, required this.placeholder, this.fit = BoxFit.cover});
  final String uri;
  final int px;
  final Widget placeholder;
  final BoxFit fit;
  @override
  ConsumerState<ThumbnailImage> createState() => _ThumbnailImageState();
}

class _ThumbnailImageState extends ConsumerState<ThumbnailImage> {
  Future<dynamic>? _future;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _future ??= ref.read(thumbnailCacheProvider).load(widget.uri, widget.px);
  }

  @override
  Widget build(BuildContext context) {
    final cache = ref.read(thumbnailCacheProvider);
    if (cache.has(widget.uri, widget.px)) return _image(cache.peek(widget.uri, widget.px));
    return FutureBuilder(future: _future, builder: (context, snapshot) => _image(snapshot.data));
  }

  Widget _image(dynamic bytes) => bytes == null
      ? widget.placeholder
      : Image.memory(bytes, cacheWidth: widget.px, fit: widget.fit, gaplessPlayback: true, filterQuality: FilterQuality.medium, errorBuilder: (_, _, _) => widget.placeholder);
}
