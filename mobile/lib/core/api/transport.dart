import 'dart:typed_data';

import '../../platform/telephony_api.g.dart';

class TransportResponse {
  const TransportResponse(this.status, this.body);
  final int status;
  final Uint8List body;
}

/// Every HTTPS request goes through this. Production uses the native OkHttp client (certificate pinning, TLS 1.2+,
/// no cleartext); tests use a fake.
abstract class HttpTransport {
  Future<TransportResponse> send(String method, Uri url, {Map<String, String> headers = const {}, Uint8List? body});
}

class NativeHttpTransport implements HttpTransport {
  NativeHttpTransport(this._api);
  final TelephonyHostApi _api;

  @override
  Future<TransportResponse> send(String method, Uri url, {Map<String, String> headers = const {}, Uint8List? body}) async {
    final response = await _api.http(HttpRequestData(method: method, url: url.toString(), headers: headers, body: body));
    return TransportResponse(response.status, response.body);
  }
}
