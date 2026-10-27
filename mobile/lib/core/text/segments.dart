/// How the carrier splits a text: 160/153 GSM-7 septets or 70/67 UCS-2 units per (multipart) segment.
/// Mirrors the server (modules/sms/services/text.py) and the admin composer.
const _gsm7Basic = '@£\$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !"#¤%&\'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà';
const _gsm7Extended = '^{}\\[~]|€\f';

class SegmentInfo {
  const SegmentInfo({required this.gsm7, required this.units, required this.segments, required this.perSegment, required this.remaining});
  final bool gsm7;
  final int units;
  final int segments;
  final int perSegment;
  final int remaining;
}

SegmentInfo segmentInfo(String text) {
  final runes = text.runes.map(String.fromCharCode).toList();
  final gsm = runes.every((ch) => _gsm7Basic.contains(ch) || _gsm7Extended.contains(ch));
  final units = gsm ? runes.fold<int>(0, (sum, ch) => sum + (_gsm7Extended.contains(ch) ? 2 : 1)) : text.length; // UTF-16 code units
  final single = gsm ? 160 : 70;
  final multi = gsm ? 153 : 67;
  if (units <= single) return SegmentInfo(gsm7: gsm, units: units, segments: 1, perSegment: single, remaining: single - units);
  final segments = (units / multi).ceil();
  return SegmentInfo(gsm7: gsm, units: units, segments: segments, perSegment: multi, remaining: segments * multi - units);
}

String withSignature(String body, {required bool enabled, String? signature}) {
  final sig = (signature ?? '').trim();
  if (!enabled || sig.isEmpty || body.trimRight().endsWith(sig)) return body;
  return '${body.trimRight()}\n$sig';
}
