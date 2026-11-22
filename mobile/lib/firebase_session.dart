import 'package:firebase_auth/firebase_auth.dart';

Future<User?> _anonymousUser() async {
  final auth = FirebaseAuth.instance;
  return auth.currentUser ?? (await auth.signInAnonymously()).user;
}

/// Stable account id for consent. The API compares this with the token subject.
Future<String?> anonymousFirebaseUid() async {
  try {
    final user = await _anonymousUser();
    final uid = user?.uid;
    if (uid == null || uid.length < 2) return null;
    return uid;
  } on FirebaseAuthException {
    return null;
  }
}

/// Signs in anonymously (G5) and returns a Firebase ID token for the API.
Future<String?> anonymousFirebaseToken() async {
  try {
    final user = await _anonymousUser();
    final token = await user?.getIdToken();
    return token;
  } on FirebaseAuthException {
    return null;
  }
}
