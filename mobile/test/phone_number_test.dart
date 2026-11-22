import 'package:astroplan/firebase_session.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('indian mobile numbers become E.164', () {
    expect(normalizeE164Phone('9876543210'), '+919876543210');
    expect(normalizeE164Phone('91 98765 43210'), '+919876543210');
    expect(normalizeE164Phone('+14155552671'), '+14155552671');
    expect(normalizeE164Phone('12345'), isNull);
  });
}
