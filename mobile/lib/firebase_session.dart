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

String? get currentAccountLabel {
  if (!firebaseAvailable) return null;
  final user = FirebaseAuth.instance.currentUser;
  if (user == null || user.isAnonymous) return null;
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

/// Returns a fresh Firebase ID token for the active user (Google or anonymous).
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

/// Signs out of Google and creates a fresh anonymous session.
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
