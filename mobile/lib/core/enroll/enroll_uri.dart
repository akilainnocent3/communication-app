/// Parses what an enrollment QR code or pasted code contains: `cmsms://enroll?server=https://…&token=…`.
class EnrollTarget {
  const EnrollTarget({required this.server, required this.token});
  final Uri server;
  final String token;
}

class EnrollUriException implements Exception {
  const EnrollUriException(this.code);

  /// `invalid`, `not_https` or `untrusted_server`.
  final String code;
  @override
  String toString() => 'EnrollUriException($code)';
}

final _token = RegExp(r'^[A-Za-z0-9_-]{32,100}$');

/// Only HTTPS servers whose host is in the build's allow-list are accepted (exact host match, no wildcards).
EnrollTarget parseEnrollTarget(String raw, {required List<String> allowedHosts, String? defaultServer}) {
  final text = raw.trim();
  Uri? server;
  String? token;
  if (text.startsWith('cmsms://')) {
    final uri = Uri.tryParse(text);
    if (uri == null || uri.host != 'enroll') throw const EnrollUriException('invalid');
    server = Uri.tryParse(uri.queryParameters['server'] ?? '');
    token = uri.queryParameters['token'];
  } else {
    token = text;
    server = defaultServer == null ? null : Uri.tryParse(defaultServer);
  }
  if (token == null || !_token.hasMatch(token)) throw const EnrollUriException('invalid');
  if (server == null || server.host.isEmpty) throw const EnrollUriException('invalid');
  if (server.scheme != 'https') throw const EnrollUriException('not_https');
  if (server.userInfo.isNotEmpty || !allowedHosts.contains(server.host.toLowerCase())) throw const EnrollUriException('untrusted_server');
  return EnrollTarget(server: Uri(scheme: 'https', host: server.host, port: server.hasPort ? server.port : null), token: token);
}

/// The chosen server for a typed short code: HTTPS, an exact allow-listed host, no user info.
Uri allowedServer(String host, {required List<String> allowedHosts}) {
  final server = Uri.tryParse('https://${host.trim()}');
  if (server == null || server.host.isEmpty) throw const EnrollUriException('invalid');
  if (server.userInfo.isNotEmpty || !allowedHosts.contains(server.host.toLowerCase())) throw const EnrollUriException('untrusted_server');
  return Uri(scheme: 'https', host: server.host, port: server.hasPort ? server.port : null);
}
