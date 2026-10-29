/// The 8-character enrollment short code (XXXX-XXXX, Crockford base32: 40 bits) typed instead of the 43-character
/// token. Crockford's reading rules apply: case-insensitive, O → 0, I and L → 1, dashes and spaces ignored. The
/// server resolves it (single use, 15 minutes, strictly throttled) to the invite's token.
const _alphabet = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

/// The canonical 8 characters, or null if [raw] is not a short code.
String? normaliseShortCode(String raw) {
  final text = raw.trim().toUpperCase().replaceAll(RegExp(r'[\s-]'), '').replaceAll('O', '0').replaceAll(RegExp('[IL]'), '1');
  if (text.length != 8 || text.split('').any((c) => !_alphabet.contains(c))) return null;
  return text;
}

String formatShortCode(String code) => code.length == 8 ? '${code.substring(0, 4)}-${code.substring(4)}' : code;
