import 'package:firebase_auth/firebase_auth.dart';

/// Signs in anonymously (G5) and returns a Firebase ID token for the API.
Future<String?> anonymousFirebaseToken() async {
  final auth = FirebaseAuth.instance;
  try {
    final user = auth.currentUser ?? (await auth.signInAnonymously()).user;
    return user?.getIdToken();
  } on FirebaseAuthException {
    return null;
  }
}
