/// Errors the sync engine and UI react to. Messages never contain message text or full numbers.
class ApiException implements Exception {
  const ApiException(this.status, this.code, this.detail);
  final int status;
  final String code;
  final String detail;
  bool get retryable => status == 0 || status == 408 || status == 429 || status >= 500;
  @override
  String toString() => 'ApiException($status, $code)';
}

/// The administrator removed this phone: wipe credentials, key and sync data.
class DeviceRevoked extends ApiException {
  const DeviceRevoked() : super(401, 'device_revoked', 'This phone was removed by your administrator.');
}

/// Paused by the administrator: keep data, stop syncing, retry slowly.
class DeviceSuspended extends ApiException {
  const DeviceSuspended() : super(403, 'device_suspended', 'This phone was paused by your administrator.');
}

class UpgradeRequired extends ApiException {
  const UpgradeRequired() : super(426, 'upgrade_required', 'Install the latest version of the app.');
}
