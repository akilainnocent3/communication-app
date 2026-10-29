import 'package:ocm_phone/core/enroll/enroll_uri.dart';
import 'package:ocm_phone/core/enroll/short_code.dart';
import 'package:ocm_phone/core/text/phone_format.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('numbers', () {
    test('E.164 with the Tanzanian default', () {
      expect(toE164('0754 210 331'), '+255754210331');
      expect(toE164('+255754210331'), '+255754210331');
      expect(toE164('255754210331'), '+255754210331');
      expect(toE164('M-PESA'), isNull);
      expect(toE164('15300'), isNull);
    });
    test('display and kinds', () {
      expect(formatNumber('0754210331'), '+255 754 210 331');
      expect(formatNumber('M-PESA'), 'M-PESA');
      expect(addressKind('15300'), AddressKind.shortCode);
      expect(addressKind('GOOGLE'), AddressKind.alphanumeric);
    });
    test('masking for logs', () {
      expect(maskNumber('+255754210331'), '+2557•••••331');
      expect(maskNumber('M-PESA'), 'M-••••');
    });
  });

  group('enrollment QR codes', () {
    const token = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJ0123456';
    const hosts = ['sms.company.co.tz'];
    test('accepts an allowed HTTPS server', () {
      final target = parseEnrollTarget('ocmphone://enroll?server=https%3A%2F%2Fsms.company.co.tz&token=$token', allowedHosts: hosts);
      expect(target.server.toString(), 'https://sms.company.co.tz');
      expect(target.token, token);
    });
    test('refuses other servers, plain HTTP and look-alikes', () {
      expect(() => parseEnrollTarget('ocmphone://enroll?server=https://evil.example&token=$token', allowedHosts: hosts), throwsA(isA<EnrollUriException>().having((e) => e.code, 'code', 'untrusted_server')));
      expect(() => parseEnrollTarget('ocmphone://enroll?server=http://sms.company.co.tz&token=$token', allowedHosts: hosts), throwsA(isA<EnrollUriException>().having((e) => e.code, 'code', 'not_https')));
      expect(() => parseEnrollTarget('ocmphone://enroll?server=https://sms.company.co.tz.evil.example&token=$token', allowedHosts: hosts), throwsA(isA<EnrollUriException>()));
      expect(() => parseEnrollTarget('ocmphone://enroll?server=https://user@sms.company.co.tz&token=$token', allowedHosts: hosts), throwsA(isA<EnrollUriException>()));
      expect(() => parseEnrollTarget('ocmphone://enroll?server=https://sms.company.co.tz&token=short', allowedHosts: hosts), throwsA(isA<EnrollUriException>()));
    });
    test('an OCM Messages code (cmsms://) is not an OCM Phone code', () {
      expect(() => parseEnrollTarget('cmsms://enroll?server=https%3A%2F%2Fsms.company.co.tz&token=$token', allowedHosts: hosts), throwsA(isA<EnrollUriException>()));
    });
    test('a pasted code uses the single allowed server', () {
      expect(parseEnrollTarget(token, allowedHosts: hosts, defaultServer: 'https://sms.company.co.tz').server.host, 'sms.company.co.tz');
    });
  });

  group('enrollment short code', () {
    test('Crockford reading rules: case, dashes, O→0, I/L→1', () {
      expect(normaliseShortCode('7f3k-9q2m'), '7F3K9Q2M');
      expect(normaliseShortCode(' 7F3K 9Q2M '), '7F3K9Q2M');
      expect(normaliseShortCode('OIL1-ABCD'), '0111ABCD');
      expect(formatShortCode('7F3K9Q2M'), '7F3K-9Q2M');
    });
    test('anything else is not a short code (U is not in the alphabet; tokens are longer)', () {
      expect(normaliseShortCode('7F3K-9Q2U'), isNull);
      expect(normaliseShortCode('7F3K-9Q2'), isNull);
      expect(normaliseShortCode('a' * 43), isNull);
    });
    test('a typed short code can only be resolved on an allow-listed HTTPS server', () {
      expect(allowedServer('sms.company.co.tz', allowedHosts: ['sms.company.co.tz']).toString(), 'https://sms.company.co.tz');
      expect(() => allowedServer('evil.example', allowedHosts: ['sms.company.co.tz']), throwsA(isA<EnrollUriException>()));
      expect(() => allowedServer('user@sms.company.co.tz', allowedHosts: ['sms.company.co.tz']), throwsA(isA<EnrollUriException>()));
    });
  });
}
