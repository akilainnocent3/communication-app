import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';

import 'errors.dart';
import 'transport.dart';

/// Signs with the non-exportable Keystore key (ECDSA P-256 / SHA-256, DER signature).
abstract class DeviceSigner {
  Future<Uint8List> sign(Uint8List message);
}

String _nonce() {
  final random = Random.secure();
  return base64Url.encode(List<int>.generate(18, (_) => random.nextInt(256))).replaceAll('=', '');
}

String _sha256Hex(List<int> data) => sha256.convert(data).toString();

/// `CMSMS-<PURPOSE>-1\n<field>\n…`: a signature for one purpose can never be replayed as another.
Uint8List canonical(String purpose, List<String> fields) => Uint8List.fromList(utf8.encode(['CMSMS-$purpose-1', ...fields].join('\n')));

const tokenPath = '/api/v1/device/auth/token/';

/// The phone-facing API (/api/v1/device/…). Short-lived access tokens are minted on demand from a signed request;
/// no long-lived bearer secret is ever stored on the phone.
class DeviceApi {
  DeviceApi({required this.transport, required this.server, required this.signer, required this.appVersion, this.deviceId, DateTime Function()? clock})
      : _clock = clock ?? DateTime.now;

  final HttpTransport transport;
  final Uri server;
  final DeviceSigner signer;
  final String appVersion;
  String? deviceId;
  final DateTime Function() _clock;
  String? _token;
  DateTime _expires = DateTime.fromMillisecondsSinceEpoch(0);

  Uri _url(String path, [Map<String, String>? query]) => server.replace(path: '/api/v1/device/$path', queryParameters: query);
  int get _now => _clock().millisecondsSinceEpoch ~/ 1000;

  Future<Map<String, dynamic>> _decode(TransportResponse response) async {
    Map<String, dynamic> data = const {};
    if (response.body.isNotEmpty) {
      try {
        final decoded = jsonDecode(utf8.decode(response.body));
        if (decoded is Map<String, dynamic>) data = decoded;
      } on FormatException {
        data = const {};
      }
    }
    if (response.status >= 200 && response.status < 300) return data;
    final code = (data['code'] as String?) ?? 'http_${response.status}';
    if (code == 'device_revoked') throw const DeviceRevoked();
    if (code == 'device_suspended') throw const DeviceSuspended();
    if (response.status == 426) throw const UpgradeRequired();
    throw ApiException(response.status, code, (data['detail'] as String?) ?? '');
  }

  Future<Map<String, dynamic>> _post(Uri url, Object body, {Map<String, String> headers = const {}}) async {
    final response = await transport.send('POST', url, headers: {'Content-Type': 'application/json', 'Accept': 'application/json', ...headers}, body: Uint8List.fromList(utf8.encode(jsonEncode(body))));
    return _decode(response);
  }

  // --- Enrollment (public endpoints) ------------------------------------------------------------------------

  /// Exchanges an 8-character short code for the invite's token (single use; throttled per IP and globally).
  Future<String> resolveShortCode(String code) async => (await _post(_url('enroll/resolve/'), {'code': code}))['token'] as String;

  Future<Map<String, dynamic>> enrollInfo(String token) async =>
      _decode(await transport.send('GET', _url('enroll/info/', {'token': token}), headers: const {'Accept': 'application/json'}));

  /// `publicKeySpki` is base64 DER. Signs CMSMS-ENROLL-1 / sha256(token) / sha256(spki) / time / nonce.
  Future<Map<String, dynamic>> enroll({
    required String token, required String publicKeySpki, required List<String> attestationChain, required Map<String, dynamic> device,
    required List<Map<String, dynamic>> sims, required String noticeText, String integrityToken = '',
  }) async {
    final timestamp = _now;
    final nonce = _nonce();
    final fingerprint = _sha256Hex(base64.decode(publicKeySpki));
    final message = canonical('ENROLL', [_sha256Hex(utf8.encode(token)), fingerprint, '$timestamp', nonce]);
    final signature = base64.encode(await signer.sign(message));
    final data = await _post(_url('enroll/'), {
      'token': token, 'public_key': publicKeySpki, 'signature': signature, 'timestamp': timestamp, 'nonce': nonce,
      'attestation_chain': attestationChain, 'integrity_token': integrityToken, 'app_version': appVersion, 'device': device, 'sims': sims,
      'notice_accepted': true, 'notice_text': noticeText,
    });
    deviceId = data['device_id'] as String;
    _token = data['access_token'] as String;
    _expires = _clock().add(Duration(seconds: (data['expires_in'] as int) - 30));
    return data;
  }

  // --- Access tokens -----------------------------------------------------------------------------------------

  Future<String> _accessToken({bool force = false}) async {
    if (!force && _token != null && _clock().isBefore(_expires)) return _token!;
    final id = deviceId;
    if (id == null) throw const ApiException(0, 'not_enrolled', 'This phone is not enrolled.');
    final timestamp = _now;
    final nonce = _nonce();
    final signature = base64.encode(await signer.sign(canonical('AUTH', ['POST', tokenPath, id, '$timestamp', nonce])));
    final data = await _post(server.replace(path: tokenPath), {'device_id': id, 'timestamp': timestamp, 'nonce': nonce, 'signature': signature});
    _token = data['access_token'] as String;
    _expires = _clock().add(Duration(seconds: (data['expires_in'] as int) - 30));
    return _token!;
  }

  void forgetToken() {
    _token = null;
    _expires = DateTime.fromMillisecondsSinceEpoch(0);
  }

  Future<Map<String, dynamic>> _authorized(String method, String path, {Object? json, Uint8List? raw, String? contentType}) async {
    for (var attempt = 0; attempt < 2; attempt++) {
      final token = await _accessToken(force: attempt > 0);
      final headers = {'Authorization': 'Bearer $token', 'X-CM-App-Version': appVersion, 'Accept': 'application/json'};
      Uint8List? body = raw;
      if (json != null) {
        headers['Content-Type'] = 'application/json';
        body = Uint8List.fromList(utf8.encode(jsonEncode(json)));
      } else if (contentType != null) {
        headers['Content-Type'] = contentType;
      }
      final response = await transport.send(method, _url(path), headers: headers, body: body);
      if (response.status == 401 && attempt == 0) {
        try {
          await _decode(response);
        } on DeviceRevoked {
          rethrow;
        } on ApiException catch (error) {
          if (error.code == 'token_expired' || error.code == 'invalid_token') {
            forgetToken();
            continue;
          }
          rethrow;
        }
      }
      return _decode(response);
    }
    throw const ApiException(401, 'invalid_token', 'Could not authenticate.');
  }

  // --- Phone API ---------------------------------------------------------------------------------------------

  Future<Map<String, dynamic>> heartbeat(Map<String, dynamic> state) => _authorized('POST', 'heartbeat/', json: state);
  Future<Map<String, dynamic>> config() => _authorized('GET', 'config/');
  Future<void> registerPushToken(String token) => _authorized('POST', 'push-token/', json: {'token': token});

  /// Returns {acked_seq, processed, skipped, rejected}.
  Future<Map<String, dynamic>> syncEvents(List<Map<String, dynamic>> events) => _authorized('POST', 'sync/events/', json: {'events': events});

  Future<Map<String, dynamic>> claimOutbox({int limit = 10}) => _authorized('POST', 'outbox/claim/', json: {'limit': limit});

  Future<Map<String, dynamic>> reportStatus({List<Map<String, dynamic>> reports = const [], List<Map<String, dynamic>> commandAcks = const []}) =>
      _authorized('POST', 'outbox/status/', json: {'reports': reports, 'command_acks': commandAcks});

  /// One chunk of an MMS part (multipart/form-data). Resume from the server's `received_bytes` on 409.
  Future<Map<String, dynamic>> uploadChunk({required int providerId, required int date, required int seq, required int offset, required Uint8List chunk}) {
    final boundary = 'cm${_nonce()}';
    final builder = BytesBuilder();
    void field(String name, String value) => builder.add(utf8.encode('--$boundary\r\nContent-Disposition: form-data; name="$name"\r\n\r\n$value\r\n'));
    field('kind', 'mms');
    field('provider_id', '$providerId');
    field('date', '$date');
    field('seq', '$seq');
    field('offset', '$offset');
    builder.add(utf8.encode('--$boundary\r\nContent-Disposition: form-data; name="chunk"; filename="chunk"\r\nContent-Type: application/octet-stream\r\n\r\n'));
    builder.add(chunk);
    builder.add(utf8.encode('\r\n--$boundary--\r\n'));
    return _authorized('POST', 'sync/media/', raw: builder.toBytes(), contentType: 'multipart/form-data; boundary=$boundary');
  }
}
