import 'package:cm_sms/core/enroll/enroll_uri.dart';
import 'package:cm_sms/core/text/otp.dart';
import 'package:cm_sms/core/text/phone_format.dart';
import 'package:cm_sms/core/text/segments.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('segment counter (matches the server)', () {
    test('GSM-7 single and multipart', () {
      expect(segmentInfo('a' * 160).segments, 1);
      expect(segmentInfo('a' * 161).segments, 2);
      expect(segmentInfo('a' * 306).segments, 2);
      expect(segmentInfo('a' * 307).segments, 3);
      expect(segmentInfo('a' * 150).remaining, 10);
    });
    test('extension characters cost two septets', () {
      final info = segmentInfo('€' * 80);
      expect(info.gsm7, isTrue);
      expect(info.units, 160);
    });
    test('UCS-2 for emoji and non-GSM characters', () {
      final info = segmentInfo('Habari 😊');
      expect(info.gsm7, isFalse);
      expect(info.units, 9);
      expect(segmentInfo('ш' * 71).segments, 2);
      expect(segmentInfo('ш' * 71).perSegment, 67);
    });
    test('signature is appended once', () {
      expect(withSignature('Asante', enabled: true, signature: '- HQ'), 'Asante\n- HQ');
      expect(withSignature('Asante\n- HQ', enabled: true, signature: '- HQ'), 'Asante\n- HQ');
      expect(withSignature('Asante', enabled: false, signature: '- HQ'), 'Asante');
    });
  });

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

  group('one-time codes', () {
    test('finds codes next to code words', () {
      expect(extractOtp('G-482913 is your Google verification code.'), '482913');
      expect(extractOtp('Your WhatsApp code: 123-456'), '123456');
      expect(extractOtp('Msimbo wako ni 4821'), '4821');
      expect(extractOtp('Bei ni 19500 kwa mfuko'), isNull);
    });
  });

  group('enrollment QR codes', () {
    const token = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJ0123456';
    const hosts = ['sms.company.co.tz'];
    test('accepts an allowed HTTPS server', () {
      final target = parseEnrollTarget('cmsms://enroll?server=https%3A%2F%2Fsms.company.co.tz&token=$token', allowedHosts: hosts);
      expect(target.server.toString(), 'https://sms.company.co.tz');
      expect(target.token, token);
    });
    test('refuses other servers, plain HTTP and look-alikes', () {
      expect(() => parseEnrollTarget('cmsms://enroll?server=https://evil.example&token=$token', allowedHosts: hosts), throwsA(isA<EnrollUriException>().having((e) => e.code, 'code', 'untrusted_server')));
      expect(() => parseEnrollTarget('cmsms://enroll?server=http://sms.company.co.tz&token=$token', allowedHosts: hosts), throwsA(isA<EnrollUriException>().having((e) => e.code, 'code', 'not_https')));
      expect(() => parseEnrollTarget('cmsms://enroll?server=https://sms.company.co.tz.evil.example&token=$token', allowedHosts: hosts), throwsA(isA<EnrollUriException>()));
      expect(() => parseEnrollTarget('cmsms://enroll?server=https://user@sms.company.co.tz&token=$token', allowedHosts: hosts), throwsA(isA<EnrollUriException>()));
      expect(() => parseEnrollTarget('cmsms://enroll?server=https://sms.company.co.tz&token=short', allowedHosts: hosts), throwsA(isA<EnrollUriException>()));
    });
    test('a pasted code uses the single allowed server', () {
      expect(parseEnrollTarget(token, allowedHosts: hosts, defaultServer: 'https://sms.company.co.tz').server.host, 'sms.company.co.tz');
    });
  });
}
