/// Display formatting and address keys for numbers, short codes and sender IDs (on-phone mirror of the server's
/// modules/devices/services/phone.py; the server stays authoritative).
final _letters = RegExp(r'[A-Za-z]');

enum AddressKind { number, shortCode, alphanumeric }

AddressKind addressKind(String raw) {
  final value = raw.trim();
  if (_letters.hasMatch(value)) return AddressKind.alphanumeric;
  final digits = value.replaceAll(RegExp(r'\D'), '');
  if (digits.length <= 6 && !value.startsWith('+')) return AddressKind.shortCode;
  return AddressKind.number;
}

/// E.164 for numbers using the SIM's country calling code (default Tanzania, +255); null for non-numbers.
String? toE164(String raw, {String countryCode = '255'}) {
  if (addressKind(raw) != AddressKind.number) return null;
  var digits = raw.trim().replaceAll(RegExp(r'[^\d+]'), '');
  if (digits.startsWith('+')) return digits.length >= 8 ? digits : null;
  if (digits.startsWith('00')) return '+${digits.substring(2)}';
  if (digits.startsWith('0')) digits = digits.substring(1);
  if (digits.startsWith(countryCode)) return '+$digits';
  return digits.length >= 7 ? '+$countryCode$digits' : null;
}

/// "+255 754 210 331" for Tanzanian numbers, grouped in threes for others; anything else unchanged.
String formatNumber(String raw) {
  final e164 = toE164(raw);
  if (e164 == null) return raw.trim();
  if (e164.startsWith('+255') && e164.length == 13) return '+255 ${e164.substring(4, 7)} ${e164.substring(7, 10)} ${e164.substring(10)}';
  final rest = e164.substring(1);
  final groups = <String>[];
  for (var i = 0; i < rest.length; i += 3) {
    groups.add(rest.substring(i, i + 3 > rest.length ? rest.length : i + 3));
  }
  return '+${groups.join(' ')}';
}

/// For logs: "+2557•••••331". Never log a full number.
String maskNumber(String value) {
  final v = value.trim();
  if (v.isEmpty) return '-';
  if (_letters.hasMatch(v)) return v.length <= 2 ? v : '${v.substring(0, 2)}${'•' * (v.length - 2)}';
  final head = v.startsWith('+') ? 5 : 2;
  if (v.length <= head + 3) return '${v.substring(0, 1)}${'•' * (v.length - 1)}';
  return '${v.substring(0, head)}${'•' * (v.length - head - 3)}${v.substring(v.length - 3)}';
}
