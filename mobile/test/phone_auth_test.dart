import 'dart:convert';

import 'package:astroplan/celestial_home.dart';
import 'package:astroplan/firebase_session.dart';
import 'package:astroplan/l10n/app_localizations.dart';
import 'package:astroplan/local_profile_store.dart';
import 'package:astroplan/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _SilentNotifier implements DailyInsightNotifier {
  @override
  Future<void> cancelDailyInsight() async {}

  @override
  Future<void> scheduleDailyLocalInsight(
      {required int hour,
      required int minute,
      required String title,
      required String body}) async {}
}

AstroplanApiClient _stubApi() => AstroplanApiClient(
      baseUrl: 'http://localhost:8000/v1',
      userId: 'google-uid',
      client: MockClient((request) async {
        if (request.url.path == '/v1/user/profile') {
          return http.Response(jsonEncode({'saved': false}), 200,
              headers: {'content-type': 'application/json'});
        }
        return http.Response('{}', 200,
            headers: {'content-type': 'application/json'});
      }),
    );

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('phoneAuthMessage maps every code to clean plain-language copy',
      (tester) async {
    late AppLocalizations t;
    await tester.pumpWidget(MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Builder(builder: (context) {
        t = AppLocalizations.of(context)!;
        return const SizedBox.shrink();
      }),
    ));
    await tester.pumpAndSettle();

    for (final code in [
      'invalid_phone_number',
      'invalid-phone-number',
      'invalid_otp',
      'invalid-verification-code',
      'session-expired',
      'otp_timeout',
      'too-many-requests',
      'network-request-failed',
      'operation-not-allowed',
      'firebase_unavailable',
      'weird_raw_internal_error_code',
    ]) {
      final msg = phoneAuthMessage(t, code);
      expect(msg.trim(), isNotEmpty);
      expect(msg, isNot(contains('_')));
      expect(msg, isNot(contains('firebase')));
      expect(msg, isNot(contains('http')));
    }
    expect(phoneAuthMessage(t, 'invalid_phone_number'), t.phoneInvalidNumber);
    expect(phoneAuthMessage(t, 'invalid-verification-code'), t.phoneInvalidCode);
    expect(phoneAuthMessage(t, 'too-many-requests'), t.phoneTryLater);
    expect(phoneAuthMessage(t, 'network-request-failed'), t.networkError);
  });

  testWidgets(
      'PhoneAuthPanel handles send, edit reset, resend, errors, and verify cleanly',
      (tester) async {
    var signedInCalls = 0;
    final resendTokensPassed = <int?>[];
    await tester.pumpWidget(MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: PhoneAuthPanel(
            startOtp: (rawPhone, {int? forceResendingToken}) async {
              resendTokensPassed.add(forceResendingToken);
              if (rawPhone.trim() == '123') {
                return const PhoneAuthResult(
                    errorMessage: 'invalid_phone_number');
              }
              return const PhoneAuthResult(
                  verificationId: 'ver-1', resendToken: 77);
            },
            confirmOtp: (
                {required String verificationId,
                required String smsCode}) async {
              if (smsCode.trim() != '123456') {
                return const PhoneAuthResult(
                    errorMessage: 'invalid-verification-code');
              }
              return const PhoneAuthResult(signedIn: true);
            },
            onSignedIn: () async {
              signedInCalls++;
            },
          ),
        ),
      ),
    ));
    await tester.pumpAndSettle();

    // Invalid phone shows plain-language error (never raw code).
    await tester.enterText(find.byKey(const Key('phone_number')), '123');
    await tester.tap(find.byKey(const Key('phone_otp_action')));
    await tester.pumpAndSettle();
    expect(find.text('Enter a valid mobile number.'), findsOneWidget);
    expect(find.textContaining('invalid_phone_number'), findsNothing);

    // Valid phone sends OTP and reveals OTP input + Resend OTP.
    await tester.enterText(find.byKey(const Key('phone_number')), '9876543210');
    await tester.tap(find.byKey(const Key('phone_otp_action')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('otp_code')), findsOneWidget);
    expect(find.text('Verify & continue'), findsOneWidget);
    expect(find.byKey(const Key('phone_resend_otp')), findsOneWidget);

    // Resend OTP passes the stored resendToken.
    await tester.tap(find.byKey(const Key('phone_resend_otp')));
    await tester.pumpAndSettle();
    expect(resendTokensPassed.last, 77);

    // Editing phone number resets verification stage back to Send OTP.
    await tester.enterText(find.byKey(const Key('phone_number')), '9876543211');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('otp_code')), findsNothing);
    expect(find.text('Send OTP'), findsOneWidget);

    // Send again, try wrong OTP, then right OTP.
    await tester.tap(find.byKey(const Key('phone_otp_action')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('otp_code')), '000000');
    await tester.tap(find.byKey(const Key('phone_otp_action')));
    await tester.pumpAndSettle();
    expect(
        find.text('That code is not right. Please try again.'), findsOneWidget);
    expect(signedInCalls, 0);

    await tester.enterText(find.byKey(const Key('otp_code')), '123456');
    await tester.tap(find.byKey(const Key('phone_otp_action')));
    await tester.pumpAndSettle();
    expect(signedInCalls, 1);
  });

  testWidgets(
      'launch gate prioritizes Mobile OTP above Google Sign-In and stays reachable with keyboard open',
      (tester) async {
    tester.view.physicalSize = const Size(360, 640);
    tester.view.devicePixelRatio = 1;
    tester.view.viewInsets = const FakeViewPadding(bottom: 280);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetViewInsets);

    var state = const AuthUiState(
      firebaseAvailable: true,
      userPresent: true,
      accountSignedIn: false,
      phoneSignedIn: false,
      googleSignedIn: false,
    );

    await tester.pumpWidget(AstroplanApp(
      api: _stubApi(),
      notifier: _SilentNotifier(),
      authStateProvider: () => state,
      startOtp: (rawPhone, {int? forceResendingToken}) async =>
          const PhoneAuthResult(verificationId: 'ver-gate'),
      confirmOtp: ({required String verificationId, required String smsCode}) async {
        state = const AuthUiState(
          firebaseAvailable: true,
          userPresent: true,
          accountSignedIn: true,
          phoneSignedIn: true,
          googleSignedIn: false,
          accountLabel: '+919876543210',
        );
        return const PhoneAuthResult(signedIn: true);
      },
    ));
    await tester.pumpAndSettle();

    // Primary flow is Mobile Number + OTP; Google Sign-In is secondary below it.
    expect(find.byKey(const Key('phone_number')), findsOneWidget);
    expect(find.byKey(const Key('phone_otp_action')), findsOneWidget);
    expect(find.byKey(const Key('google_sign_in_gate')), findsOneWidget);
    final phoneY = tester.getTopLeft(find.byKey(const Key('phone_otp_action'))).dy;
    final googleY =
        tester.getTopLeft(find.byKey(const Key('google_sign_in_gate'))).dy;
    expect(phoneY, lessThan(googleY));

    // Action button scrolls cleanly into view and works even with keyboard open.
    await tester.enterText(find.byKey(const Key('phone_number')), '9876543210');
    await tester.ensureVisible(find.byKey(const Key('phone_otp_action')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('phone_otp_action')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('otp_code')), findsOneWidget);

    await tester.enterText(find.byKey(const Key('otp_code')), '654321');
    await tester.ensureVisible(find.byKey(const Key('phone_otp_action')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('phone_otp_action')));
    await tester.pumpAndSettle();

    // Entered app after OTP verification.
    expect(find.text('Today'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'Google-signed-in user sees Mobile OTP option in top bar, onboarding, profile card, and sign out clears cache',
      (tester) async {
    await LocalProfileStore.save(const SavedProfileBundle(
      self: {
        'name': 'Google User',
        'birth_date': '1993-08-15',
        'birth_time': '07:45',
        'place_name': 'Pune',
        'country': 'India',
        'latitude': 18.5204,
        'longitude': 73.8567,
        'timezone_override': 'Asia/Kolkata',
      },
      adult: true,
      parental: false,
      consentRecorded: true,
      syncedToServer: true,
      accountId: 'google-uid',
    ));

    var state = const AuthUiState(
      firebaseAvailable: true,
      userPresent: true,
      accountSignedIn: true,
      phoneSignedIn: false,
      googleSignedIn: true,
      accountLabel: 'user@example.com',
    );

    await tester.pumpWidget(AstroplanApp(
      api: _stubApi(),
      notifier: _SilentNotifier(),
      authStateProvider: () => state,
      signOut: () async {
        state = const AuthUiState(
          firebaseAvailable: true,
          userPresent: true,
          accountSignedIn: false,
          phoneSignedIn: false,
          googleSignedIn: false,
        );
      },
    ));
    await tester.pumpAndSettle();

    // Saved profile card shows Mobile OTP login button even when signed in via Google.
    expect(find.text('Google User'), findsOneWidget);
    expect(find.byKey(const Key('today_phone_sign_in')), findsOneWidget);

    // Top bar Account button opens Account & mobile login sheet with Mobile OTP & Sign out.
    expect(find.byKey(const Key('account_button')), findsOneWidget);
    await tester.tap(find.byKey(const Key('account_button')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('phone_sign_in_account')), findsOneWidget);
    expect(find.textContaining('user@example.com'), findsWidgets);

    // Explicit Sign Out clears locally cached birth details and returns to phone gate.
    await tester.tap(find.byKey(const Key('sign_out_account')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('phone_number')), findsOneWidget);
    expect(await LocalProfileStore.load(accountId: 'google-uid'), isNull);
    expect(await LocalProfileStore.load(), isNull);
  });
}
