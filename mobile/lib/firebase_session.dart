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

/// Starts phone OTP. Returns the verificationId, or null on failure/cancel.
Future<String?> startPhoneOtp(String e164Phone) async {
  if (!firebaseAvailable) return null;
  final phone = e164Phone.trim();
  if (!RegExp(r'^\+[1-9]\d{7,14}$').hasMatch(phone)) return null;
  final auth = FirebaseAuth.instance;
  String? verificationId;
  Object? failure;
  await auth.verifyPhoneNumber(
    phoneNumber: phone,
    timeout: const Duration(seconds: 60),
    verificationCompleted: (credential) async {
      try {
        final current = auth.currentUser;
        if (current != null && current.isAnonymous) {
          try {
            await current.linkWithCredential(credential);
            return;
          } on FirebaseAuthException {
            // Fall through to sign-in below.
          }
        }
        await auth.signInWithCredential(credential);
      } catch (e) {
        failure = e;
      }
    },
    verificationFailed: (e) {
      failure = e;
    },
    codeSent: (id, _) {
      verificationId = id;
    },
    codeAutoRetrievalTimeout: (id) {
      verificationId ??= id;
    },
  );
  if (failure != null) return null;
  return verificationId;
}

/// Confirms the SMS/WhatsApp OTP against [verificationId].
Future<bool> confirmPhoneOtp(
    {required String verificationId, required String smsCode}) async {
  if (!firebaseAvailable) return false;
  final code = smsCode.trim();
  if (code.length < 4 || code.length > 8) return false;
  final auth = FirebaseAuth.instance;
  final credential = PhoneAuthProvider.credential(
      verificationId: verificationId, smsCode: code);
  try {
    final current = auth.currentUser;
    if (current != null && current.isAnonymous) {
      try {
        await current.linkWithCredential(credential);
        return true;
      } on FirebaseAuthException catch (e) {
        if (e.code == 'credential-already-in-use' ||
            e.code == 'provider-already-linked') {
          final signedIn = await auth.signInWithCredential(credential);
          return signedIn.user != null;
        }
        rethrow;
      }
    }
    final signedIn = await auth.signInWithCredential(credential);
    return signedIn.user != null;
  } on FirebaseAuthException {
    return false;
  } catch (_) {
    return false;
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
