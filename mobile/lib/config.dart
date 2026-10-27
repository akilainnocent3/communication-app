/// Build-time configuration (`--dart-define=…`). Nothing here is secret.
class AppConfig {
  const AppConfig({required this.allowedServerHosts, required this.pinnedSpki, required this.fcmEnabled, required this.appVersion});

  /// Hosts a QR code or typed code may point this phone at. Anything else is refused, so a malicious QR code can
  /// never redirect the phone's messages to another server.
  final List<String> allowedServerHosts;

  /// Base64 SHA-256 SPKI pins (at least two: current and backup). Enforced natively by OkHttp.
  final List<String> pinnedSpki;
  final bool fcmEnabled;
  final String appVersion;

  static AppConfig fromEnvironment() => AppConfig(
        allowedServerHosts: _list(const String.fromEnvironment('ALLOWED_SERVER_HOSTS')),
        pinnedSpki: _list(const String.fromEnvironment('PINNED_SPKI')),
        fcmEnabled: const bool.fromEnvironment('FCM_ENABLED'),
        appVersion: const String.fromEnvironment('APP_VERSION', defaultValue: '1.0.0'),
      );

  static List<String> _list(String value) => value.split(',').map((item) => item.trim().toLowerCase()).where((item) => item.isNotEmpty).toList();
}
