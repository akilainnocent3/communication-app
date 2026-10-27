import 'dart:convert';

import 'package:cm_sms/core/api/device_api.dart';
import 'package:cm_sms/core/api/errors.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

void main() {
  final server = Uri.parse('https://sms.company.co.tz');
  final now = DateTime.utc(2026, 10, 27, 12);

  test('enroll signs token hash, key fingerprint, time and nonce', () async {
    final signer = FakeSigner();
    final transport = FakeTransport((method, url, headers, body) => (201, {'device_id': 'abc', 'device_code': 'DEV-AAAA-BBBB', 'name': 'Desk', 'access_token': 't1', 'expires_in': 900, 'options': {}}));
    final api = DeviceApi(transport: transport, server: server, signer: signer, appVersion: '1.0.0', clock: () => now);
    await api.enroll(token: 'tok', publicKeySpki: 'AQID', attestationChain: const [], device: const {}, sims: const [], noticeText: 'notice');
    final lines = signer.signed.single.split('\n');
    expect(lines[0], 'CMSMS-ENROLL-1');
    expect(lines[1], sha256.convert(utf8.encode('tok')).toString());
    expect(lines[2], sha256.convert(base64.decode('AQID')).toString());
    expect(lines[3], '${now.millisecondsSinceEpoch ~/ 1000}');
    expect(api.deviceId, 'abc');
    final body = transport.requests.single.$4 as Map;
    expect(body['notice_accepted'], true);
    expect(body['signature'], 'AQID');
  });

  test('access tokens are minted with a proof-of-possession signature and reused until they expire', () async {
    var minted = 0;
    final signer = FakeSigner();
    final transport = FakeTransport((method, url, headers, body) {
      if (url.path == tokenPath) return (200, {'access_token': 'token-${++minted}', 'expires_in': 900});
      return (200, {'status': 'active'});
    });
    final api = DeviceApi(transport: transport, server: server, signer: signer, appVersion: '1.0.0', deviceId: 'dev-1', clock: () => now);
    await api.heartbeat({'is_default_sms_app': true});
    await api.heartbeat({'is_default_sms_app': true});
    expect(minted, 1);
    expect(signer.signed.single.split('\n').sublist(0, 4), ['CMSMS-AUTH-1', 'POST', tokenPath, 'dev-1']);
    final heartbeat = transport.requests.last;
    expect(heartbeat.$3['Authorization'], 'Bearer token-1');
    expect(heartbeat.$3['X-CM-App-Version'], '1.0.0');
  });

  test('an expired token is refreshed once', () async {
    var minted = 0;
    var calls = 0;
    final transport = FakeTransport((method, url, headers, body) {
      if (url.path == tokenPath) return (200, {'access_token': 'token-${++minted}', 'expires_in': 900});
      calls++;
      return calls == 1 ? (401, {'code': 'token_expired', 'detail': ''}) : (200, {'ok': true});
    });
    final api = DeviceApi(transport: transport, server: server, signer: FakeSigner(), appVersion: '1.0.0', deviceId: 'dev-1', clock: () => now);
    expect(await api.config(), {'ok': true});
    expect(minted, 2);
  });

  test('revoked, suspended and too-old apps are typed errors', () async {
    for (final (status, code, type) in [(401, 'device_revoked', DeviceRevoked), (403, 'device_suspended', DeviceSuspended), (426, 'upgrade_required', UpgradeRequired)]) {
      final transport = FakeTransport((method, url, headers, body) => url.path == tokenPath ? (200, {'access_token': 't', 'expires_in': 900}) : (status, {'code': code, 'detail': ''}));
      final api = DeviceApi(transport: transport, server: server, signer: FakeSigner(), appVersion: '1.0.0', deviceId: 'dev-1', clock: () => now);
      await expectLater(api.config(), throwsA(isA<ApiException>().having((e) => e.runtimeType, 'type', type)));
    }
  });

  test('canonical strings refuse nothing but separate purposes', () {
    expect(String.fromCharCodes(canonical('AUTH', ['a', 'b'])), 'CMSMS-AUTH-1\na\nb');
  });
}
