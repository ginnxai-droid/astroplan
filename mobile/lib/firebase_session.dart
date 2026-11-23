import 'dart:async';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';

bool get firebaseAvailable => Firebase.apps.isNotEmpty;

/// A real login, phone or Google. Anonymous sessions still see the login screen.
bool get isAccountSignedIn {
  if (!firebaseAvailable) return false;
  final user = FirebaseAuth.instance.currentUser;
  return user != null && !user.isAnonymous;
}

bool get firebaseUserPresent {
  if (!firebaseAvailable) return false;
  return FirebaseAuth.instance.currentUser != null;
}

Future<User?> _restoredCurrentUser(FirebaseAuth auth) async {
  final existing = auth.currentUser;
  if (existing != null) return existing;
  // Persistence can arrive after the first read. Wait so a saved login is not
  // replaced by a new anonymous session.
  final pending = Completer<User?>();
  var sawSignedOut = false;
  final sub = auth.authStateChanges().listen((user) {
    if (pending.isCompleted) return;
    if (user != null) {
      pending.complete(user);
      return;
    }
    if (sawSignedOut) return;
    sawSignedOut = true;
    Future<void>.delayed(const Duration(milliseconds: 400), () {
      if (!pending.isCompleted) pending.complete(auth.currentUser);
    });
  }, onError: (Object _) {
    if (!pending.isCompleted) pending.complete(auth.currentUser);
  });
  try {
    return await pending.future.timeout(
      const Duration(seconds: 2),
      onTimeout: () => auth.currentUser,
    );
  } finally {
    await sub.cancel();
  }
}

Future<User?> _ensureSessionUser() async {
  if (!firebaseAvailable) return null;
  final auth = FirebaseAuth.instance;
  final restored = await _restoredCurrentUser(auth);
  if (restored != null) return restored;
  return (await auth.signInAnonymously()).user;
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

String? get currentPhoneNumber {
  if (!firebaseAvailable) return null;
  final user = FirebaseAuth.instance.currentUser;
  if (user == null || user.isAnonymous) return null;
  final phone = user.phoneNumber?.trim();
  if (phone != null && phone.isNotEmpty) return phone;
  return null;
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

/// Account changes, including the moment a phone or Google credential is linked.
Stream<void>? watchAccount() {
  if (!firebaseAvailable) return null;
  return FirebaseAuth.instance.userChanges().map((_) {});
}

/// Accepts a 10-digit Indian mobile, 0/91-prefixed Indian mobile, or an international E.164 number.
String? normalizeE164Phone(String raw) {
  final trimmed = raw.trim();
  final digits = trimmed.replaceAll(RegExp(r'\D'), '');
  if (trimmed.startsWith('+')) {
    if (RegExp(r'^[1-9]\d{7,14}$').hasMatch(digits)) return '+$digits';
    return null;
  }
  if (digits.length == 10 && RegExp(r'^[1-9]\d{9}$').hasMatch(digits)) {
    return '+91$digits';
  }
  if (digits.length == 11 &&
      digits.startsWith('0') &&
      RegExp(r'^[1-9]\d{9}$').hasMatch(digits.substring(1))) {
    return '+91${digits.substring(1)}';
  }
  if (digits.length == 12 && digits.startsWith('91')) return '+$digits';
  return null;
}

class PhoneAuthResult {
  const PhoneAuthResult(
      {this.verificationId,
      this.resendToken,
      this.errorMessage,
      this.signedIn = false});
  final String? verificationId;
  final int? resendToken;
  final String? errorMessage;
  final bool signedIn;
}

String _phoneFailure(Object error) {
  if (error is FirebaseAuthException) {
    final code = error.code.trim();
    if (code.isNotEmpty) return code;
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
Future<PhoneAuthResult> startPhoneOtp(String rawPhone,
    {int? forceResendingToken}) async {
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
      forceResendingToken: forceResendingToken,
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
      codeSent: (id, resendToken) {
        if (!completer.isCompleted) {
          completer.complete(
              PhoneAuthResult(verificationId: id, resendToken: resendToken));
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
