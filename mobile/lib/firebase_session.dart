import 'dart:async';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';

bool get firebaseAvailable => Firebase.apps.isNotEmpty;

Future<User?> _ensureSessionUser() async {
  if (!firebaseAvailable) return null;
  final auth = FirebaseAuth.instance;
  return auth.currentUser ?? (await auth.signInAnonymously()).user;
}

String? currentFirebaseUidSync() {
  if (!firebaseAvailable) return null;
  final uid = FirebaseAuth.instance.currentUser?.uid;
  if (uid == null || uid.length < 2) return null;
  return uid;
}

bool get isGoogleSignedIn {
  if (!firebaseAvailable) return false;
  final user = FirebaseAuth.instance.currentUser;
  if (user == null || user.isAnonymous) return false;
  return user.providerData.any((p) => p.providerId == 'google.com') ||
      (user.email?.isNotEmpty ?? false);
}

bool get isPhoneSignedIn {
  if (!firebaseAvailable) return false;
  final user = FirebaseAuth.instance.currentUser;
  if (user == null || user.isAnonymous) return false;
  return user.providerData.any((p) => p.providerId == 'phone') ||
      (user.phoneNumber?.isNotEmpty ?? false);
}

String? get currentAccountLabel {
  if (!firebaseAvailable) return null;
  final user = FirebaseAuth.instance.currentUser;
  if (user == null || user.isAnonymous) return null;
  final phone = user.phoneNumber?.trim();
  if (phone != null && phone.isNotEmpty) return phone;
  final email = user.email?.trim();
  if (email != null && email.isNotEmpty) return email;
  final name = user.displayName?.trim();
  if (name != null && name.isNotEmpty) return name;
  return user.uid;
}

/// Stable account id for consent. The API compares this with the token subject.
Future<String?> anonymousFirebaseUid() async {
  try {
    final user = await _ensureSessionUser();
    final uid = user?.uid;
    if (uid == null || uid.length < 2) return null;
    return uid;
  } on FirebaseAuthException {
    return null;
  }
}

/// Returns a fresh Firebase ID token for the active user (Google, phone, or anonymous).
Future<String?> anonymousFirebaseToken() async {
  try {
    final user = await _ensureSessionUser();
    return await user?.getIdToken();
  } on FirebaseAuthException {
    return null;
  }
}

/// Signs in with Google, upgrading an anonymous Firebase session when possible.
Future<bool> signInWithGoogleAccount() async {
  if (!firebaseAvailable) return false;
  final auth = FirebaseAuth.instance;
  final provider = GoogleAuthProvider()..addScope('email');
  try {
    final current = auth.currentUser;
    if (current != null && current.isAnonymous) {
      try {
        final linked = await current.linkWithProvider(provider);
        return linked.user != null;
      } on FirebaseAuthException catch (e) {
        if (e.code == 'canceled' || e.code == 'web-context-canceled') {
          return false;
        }
        final cred = e.credential;
        if (cred != null) {
          final signedIn = await auth.signInWithCredential(cred);
          return signedIn.user != null;
        }
      }
    }
    final result = await auth.signInWithProvider(provider);
    return result.user != null;
  } on FirebaseAuthException {
    return false;
  } catch (_) {
    return false;
  }
}

/// Account changes, including the moment a phone credential is linked.
Stream<void>? watchAccount() {
  if (!firebaseAvailable) return null;
  return FirebaseAuth.instance.authStateChanges().map((_) {});
}

/// Accepts a 10-digit Indian mobile, 91…, or a full E.164 number.
String? normalizeE164Phone(String raw) {
  final trimmed = raw.trim();
  final digits = trimmed.replaceAll(RegExp(r'\D'), '');
  if (digits.length == 10) return '+91$digits';
  if (digits.length == 12 && digits.startsWith('91')) return '+$digits';
  if (RegExp(r'^\+[1-9]\d{7,14}$').hasMatch(trimmed)) return trimmed;
  return null;
}

class PhoneAuthResult {
  const PhoneAuthResult(
      {this.verificationId, this.errorMessage, this.signedIn = false});
  final String? verificationId;
  final String? errorMessage;
  final bool signedIn;
}

String _phoneFailure(Object error) {
  if (error is FirebaseAuthException) {
    final message = error.message?.trim();
    if (message != null && message.isNotEmpty) return message;
    return error.code;
  }
  return 'phone_auth_failed';
}

Future<bool> _signInWithPhoneCredential(PhoneAuthCredential credential) async {
  final auth = FirebaseAuth.instance;
  final current = auth.currentUser;
  if (current != null &&
      !current.providerData.any((provider) => provider.providerId == 'phone')) {
    try {
      final linked = await current.linkWithCredential(credential);
      return linked.user != null;
    } on FirebaseAuthException catch (error) {
      if (error.code != 'credential-already-in-use' &&
          error.code != 'provider-already-linked') {
        rethrow;
      }
    }
  }
  final signedIn = await auth.signInWithCredential(credential);
  return signedIn.user != null;
}

/// Starts phone OTP and waits until Firebase reports a code, a failure, or instant verification.
Future<PhoneAuthResult> startPhoneOtp(String rawPhone) async {
  if (!firebaseAvailable) {
    return const PhoneAuthResult(errorMessage: 'firebase_unavailable');
  }
  final phone = normalizeE164Phone(rawPhone);
  if (phone == null) {
    return const PhoneAuthResult(errorMessage: 'invalid_phone_number');
  }
  final auth = FirebaseAuth.instance;
  final completer = Completer<PhoneAuthResult>();
  try {
    await auth.verifyPhoneNumber(
      phoneNumber: phone,
      timeout: const Duration(seconds: 60),
      verificationCompleted: (credential) async {
        try {
          final ok = await _signInWithPhoneCredential(credential);
          if (!completer.isCompleted) {
            completer.complete(PhoneAuthResult(
                signedIn: ok,
                errorMessage: ok ? null : 'phone_sign_in_failed'));
          }
        } catch (error) {
          if (!completer.isCompleted) {
            completer.complete(
                PhoneAuthResult(errorMessage: _phoneFailure(error)));
          }
        }
      },
      verificationFailed: (error) {
        if (!completer.isCompleted) {
          completer.complete(
              PhoneAuthResult(errorMessage: _phoneFailure(error)));
        }
      },
      codeSent: (id, _) {
        if (!completer.isCompleted) {
          completer.complete(PhoneAuthResult(verificationId: id));
        }
      },
      codeAutoRetrievalTimeout: (id) {
        if (!completer.isCompleted) {
          completer.complete(PhoneAuthResult(verificationId: id));
        }
      },
    );
  } on FirebaseAuthException catch (error) {
    return PhoneAuthResult(errorMessage: _phoneFailure(error));
  } catch (error) {
    return PhoneAuthResult(errorMessage: _phoneFailure(error));
  }
  return completer.future.timeout(
    const Duration(seconds: 75),
    onTimeout: () => const PhoneAuthResult(errorMessage: 'otp_timeout'),
  );
}

/// Confirms the SMS OTP against [verificationId].
Future<PhoneAuthResult> confirmPhoneOtp(
    {required String verificationId, required String smsCode}) async {
  if (!firebaseAvailable) {
    return const PhoneAuthResult(errorMessage: 'firebase_unavailable');
  }
  final code = smsCode.trim();
  if (code.length < 4 || code.length > 8) {
    return const PhoneAuthResult(errorMessage: 'invalid_otp');
  }
  final credential = PhoneAuthProvider.credential(
      verificationId: verificationId, smsCode: code);
  try {
    final ok = await _signInWithPhoneCredential(credential);
    return PhoneAuthResult(
        signedIn: ok, errorMessage: ok ? null : 'phone_sign_in_failed');
  } on FirebaseAuthException catch (error) {
    return PhoneAuthResult(errorMessage: _phoneFailure(error));
  } catch (error) {
    return PhoneAuthResult(errorMessage: _phoneFailure(error));
  }
}

/// Signs out of Google/phone and creates a fresh anonymous session.
Future<void> signOutToAnonymous() async {
  if (!firebaseAvailable) return;
  final auth = FirebaseAuth.instance;
  await auth.signOut();
  try {
    await auth.signInAnonymously();
  } on FirebaseAuthException {
    // Will retry lazily on next API call.
  }
}
