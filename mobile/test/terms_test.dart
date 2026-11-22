import 'package:astroplan/terms.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Hindi and Marathi terms keep the English name in brackets', () {
    expect(astroTerm('mr', 'Pisces'), 'मीन (Pisces)');
    expect(astroTerm('mr', 'Aries'), 'मेष (Aries)');
    expect(astroTerm('hi', 'Aries'), 'मेष (Aries)');
    expect(astroTerm('mr', 'Libra'), 'तूळ (Libra)');
    expect(astroTerm('hi', 'Libra'), 'तुला (Libra)');
    expect(astroTerm('mr', 'Sunday'), 'रविवार (Sunday)');
    expect(astroTerm('hi', 'Tuesday'), 'मंगलवार (Tuesday)');
    expect(astroTerm('mr', 'Tuesday'), 'मंगळवार (Tuesday)');
    expect(astroTerm('mr', 'Vyatipata'), 'व्यतिपात (Vyatipata)');
    expect(astroTerm('hi', 'Shukla Trayodashi'), 'शुक्ल त्रयोदशी (Shukla Trayodashi)');
    expect(astroTerm('en', 'Pisces'), 'Pisces');
    expect(astroTerm('mr', 'not-a-term'), 'not-a-term');
  });
}
