import 'package:astroplan/firebase_session.dart';
import 'package:astroplan/local_profile_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('indian and international mobile numbers become E.164', () {
    expect(normalizeE164Phone('9876543210'), '+919876543210');
    expect(normalizeE164Phone('9225529390'), '+919225529390');
    expect(normalizeE164Phone('09876543210'), '+919876543210');
    expect(normalizeE164Phone('91 98765 43210'), '+919876543210');
    expect(normalizeE164Phone('+91 98765 43210'), '+919876543210');
    expect(normalizeE164Phone('+14155552671'), '+14155552671');
    expect(normalizeE164Phone('+1 (415) 555-2671'), '+14155552671');
    expect(normalizeE164Phone('12345'), isNull);
    expect(normalizeE164Phone('+00123456789'), isNull);
  });

  test('phone failures before an OTP stay classifiable without raw text', () {
    expect(
      classifyPhoneFailure(
          'internal-error', 'An internal error has occurred. [ BILLING_NOT_ENABLED ]'),
      'billing-not-enabled',
    );
    expect(
      classifyPhoneFailure(
          'operation-not-allowed',
          'SMS unable to be sent until this region enabled by the app developer.'),
      'operation-not-allowed',
    );
    expect(
      classifyPhoneFailure(
          'unknown', 'This app is not authorized to use Firebase Authentication.'),
      'app-not-authorized',
    );
    expect(
      classifyPhoneFailure('missing-client-identifier',
          'This request is missing a valid app identifier, meaning Play Integrity checks were unsuccessful.'),
      'missing-client-identifier',
    );
    expect(classifyPhoneFailure('invalid-phone-number', 'bad number'),
        'invalid-phone-number');
  });

  test('local profile store scopes by account and clears cleanly', () async {
    const bundleA = SavedProfileBundle(
      self: {
        'name': 'User A',
        'birth_date': '1991-05-12',
        'birth_time': '06:30',
        'place_name': 'Pune',
        'country': 'India',
        'gender': 'female',
        'marital_status': 'married',
        'occupation': 'business',
      },
      partner: {
        'name': 'Partner A',
        'birth_date': '1990-02-04',
        'birth_time': '11:15',
        'place_name': 'Mumbai',
        'country': 'India',
      },
      adult: true,
      parental: false,
      consentRecorded: true,
      syncedToServer: true,
      accountId: 'uid-a',
    );
    await LocalProfileStore.save(bundleA);

    final loadedA = await LocalProfileStore.load(accountId: 'uid-a');
    expect(loadedA, isNotNull);
    expect(loadedA!.self['name'], 'User A');
    expect(loadedA.self['gender'], 'female');
    expect(loadedA.partner?['name'], 'Partner A');
    expect(loadedA.consentRecorded, true);

    // A different signed-in account must never inherit uid-a's cached profile.
    final loadedB = await LocalProfileStore.load(accountId: 'uid-b');
    expect(loadedB, isNull);

    // Offline/unauthenticated launch still finds the saved profile.
    final loadedOffline = await LocalProfileStore.load();
    expect(loadedOffline?.self['name'], 'User A');

    await LocalProfileStore.clearAll();
    expect(await LocalProfileStore.load(accountId: 'uid-a'), isNull);
    expect(await LocalProfileStore.load(), isNull);
  });
}
