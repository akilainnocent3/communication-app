/// Finds a one-time code in a message so the notification and chat can offer "Copy code" (like Google Messages).
final _keyword = RegExp(r'(code|otp|pin|verification|verify|msimbo|nambari ya siri|neno la siri)', caseSensitive: false);
final _code = RegExp(r'(?<![\d-])(G-)?(\d{3}[- ]\d{3}|\d{4,8})(?![\d-])');

String? extractOtp(String body) {
  if (!_keyword.hasMatch(body)) return null;
  final match = _code.firstMatch(body);
  if (match == null) return null;
  return match.group(2)!.replaceAll(RegExp(r'[- ]'), '');
}
