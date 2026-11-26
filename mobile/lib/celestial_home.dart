import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:timezone/timezone.dart' as tz;
import 'api.dart';
import 'ask_area.dart';
import 'birth_sheet.dart';
import 'celestial_widgets.dart';
import 'firebase_session.dart';
import 'l10n/app_localizations.dart';
import 'licensing.dart';
import 'local_profile_store.dart';
import 'place_lookup.dart';
import 'terms.dart';

class AuthUiState {
  const AuthUiState({
    required this.firebaseAvailable,
    required this.userPresent,
    required this.accountSignedIn,
    required this.phoneSignedIn,
    required this.googleSignedIn,
    this.accountLabel,
  });

  final bool firebaseAvailable;
  final bool userPresent;
  final bool accountSignedIn;
  final bool phoneSignedIn;
  final bool googleSignedIn;
  final String? accountLabel;
}

class CelestialHome extends StatefulWidget {
  const CelestialHome(
      {super.key,
      required this.api,
      required this.locale,
      required this.muted,
      required this.onLanguageChanged,
      required this.onMutedChanged,
      this.authStateProvider,
      this.startOtp,
      this.confirmOtp,
      this.signInWithGoogle,
      this.signOut});
  final AstroplanApiClient api;
  final Locale locale;
  final bool muted;
  final Future<void> Function(Locale) onLanguageChanged;
  final Future<void> Function(bool, AppLocalizations) onMutedChanged;
  final AuthUiState Function()? authStateProvider;
  final Future<PhoneAuthResult> Function(String rawPhone,
      {int? forceResendingToken})? startOtp;
  final Future<PhoneAuthResult> Function(
      {required String verificationId, required String smsCode})? confirmOtp;
  final Future<bool> Function()? signInWithGoogle;
  final Future<void> Function()? signOut;
  @override
  State<CelestialHome> createState() => _CelestialHomeState();
}

class _CelestialHomeState extends State<CelestialHome> {
  int tab = 0, epoch = 0;
  final annualAnchor = GlobalKey();
  bool showChartDetails = false;
  int year = DateTime.now().year;
  bool d9 = false,
      consentRecorded = false,
      notificationBusy = false,
      authBusy = false,
      _savedAdult = true,
      _savedParental = false;
  Json? profile, partner;
  final data = <String, Json>{};
  final errors = <String, Object>{};
  final pending = <String>{};
  final versions = <String, int>{};
  final answers = <Json>[];
  final chatThread = <Json>[];
  final question = TextEditingController();
  StreamSubscription<void>? _authSub;
  Timer? _authWait;
  bool _authSettled = false;
  String? selectedArea;
  bool askUnmatched = false;
  AppLocalizations get t => AppLocalizations.of(context)!;
  AstroplanApiClient get api => widget.api;
  AuthUiState get _authState =>
      widget.authStateProvider?.call() ??
      AuthUiState(
        firebaseAvailable: firebaseAvailable,
        userPresent: firebaseUserPresent,
        accountSignedIn: isAccountSignedIn,
        phoneSignedIn: isPhoneSignedIn,
        googleSignedIn: isGoogleSignedIn,
        accountLabel: currentAccountLabel,
      );
  bool get _firebaseEnabled => _authState.firebaseAvailable;
  bool get _userPresent => _authState.userPresent;
  bool get _accountSignedIn => _authState.accountSignedIn;
  bool get _phoneSignedIn => _authState.phoneSignedIn;
  bool get _googleSignedIn => _authState.googleSignedIn;
  String? get _accountLabel => _authState.accountLabel;
  Json get details => {...?profile, 'language': widget.locale.languageCode};
  bool get accountReady => api.authenticated && consentRecorded;
  String get targetDate {
    final zone =
        data['chart']?['resolved_timezone'] ?? profile?['timezone_override'];
    DateTime date = DateTime.now();
    if (zone is String) {
      try {
        date = tz.TZDateTime.now(tz.getLocation(zone));
      } catch (_) {/* Server reports invalid zones separately. */}
    }
    return DateFormat('yyyy-MM-dd').format(date);
  }

  Map<String, String> get targetQuery =>
      profile?['timezone_override'] != null || data['chart'] != null
          ? {'target_date': targetDate}
          : {};
  @override
  void initState() {
    super.initState();
    _authSettled = !_firebaseEnabled || _userPresent;
    if (_firebaseEnabled && !_authSettled) {
      _authWait = Timer(const Duration(seconds: 3), () {
        if (!mounted) return;
        setState(() => _authSettled = true);
      });
    }
    _authSub = watchAccount()?.listen((_) {
      if (!mounted) return;
      final signedIn = _accountSignedIn;
      _authWait?.cancel();
      setState(() => _authSettled = true);
      if (signedIn && profile == null) {
        _restoreSavedProfile();
      }
    });
    if (!_firebaseEnabled || _accountSignedIn) {
      _restoreSavedProfile();
    }
  }

  Future<void> _saveLocalSnapshot({required bool syncedToServer}) async {
    final self = profile;
    if (self == null) return;
    try {
      await LocalProfileStore.save(SavedProfileBundle(
        self: self,
        partner: partner,
        adult: _savedAdult,
        parental: _savedParental,
        consentRecorded: consentRecorded,
        syncedToServer: syncedToServer,
        accountId: api.userId,
      ));
    } catch (_) {
      // In-memory state stays usable even if device storage fails.
    }
  }

  Future<bool> _syncProfileToServer({
    required Json self,
    Json? partnerChart,
    required bool adult,
    required bool parental,
  }) async {
    if (!api.authenticated) return false;
    try {
      await api.post(
          '/privacy/consent',
          {
            if (api.userId != null) 'user_id': api.userId,
            'dpdp_consent_granted': true,
            'age_verified_18_plus': adult,
            'parental_consent_verified': !adult && parental,
            'preferred_language': widget.locale.languageCode,
          },
          protected: true);
      final selfSaved = await _persistChart(
        self,
        adult: adult,
        parental: parental,
        gender: self['gender']?.toString(),
        maritalStatus: self['marital_status']?.toString(),
        occupation: self['occupation']?.toString(),
      );
      var partnerSaved = true;
      if (partnerChart != null) {
        partnerSaved = await _persistChart(
          partnerChart,
          adult: adult,
          parental: parental,
          isPartner: true,
          partnerPermission: true,
        );
      }
      return selfSaved && partnerSaved;
    } catch (_) {
      return false;
    }
  }

  Future<void> _restoreSavedProfile({bool overwrite = false}) async {
    final generation = epoch;
    SavedProfileBundle? local;
    try {
      local = await LocalProfileStore.load(accountId: api.userId);
    } catch (_) {
      local = null;
    }
    if (!mounted || epoch != generation) return;

    if (local != null && (overwrite || profile == null)) {
      final selfMap = await _resolveSaved(local.self) ?? local.self;
      if (!mounted || epoch != generation) return;
      Json? partnerMap;
      if (local.partner != null) {
        partnerMap = await _resolveSaved(local.partner!) ?? local.partner;
        if (!mounted || epoch != generation) return;
      }
      setState(() {
        profile = selfMap;
        partner = partnerMap;
        consentRecorded = local!.consentRecorded;
        _savedAdult = local.adult;
        _savedParental = local.parental;
      });
      _loadProfile();
      if (partnerMap != null) _loadMatch();
    }

    if (!api.authenticated) return;
    try {
      final saved = await api.get('/user/profile', protected: true);
      if (!mounted || epoch != generation) return;
      final serverHasSelf =
          saved['saved'] == true && saved['self_chart'] is Map;
      if (serverHasSelf) {
        final rawSelf = {
          ...jsonMap(saved['self_chart']),
          if (saved['gender'] != null)
            'gender': saved['gender']
          else if (local?.self['gender'] != null)
            'gender': local!.self['gender'],
          if (saved['marital_status'] != null)
            'marital_status': saved['marital_status']
          else if (local?.self['marital_status'] != null)
            'marital_status': local!.self['marital_status'],
          if (saved['occupation'] != null)
            'occupation': saved['occupation']
          else if (local?.self['occupation'] != null)
            'occupation': local!.self['occupation'],
        };
        final selfMap = await _resolveSaved(rawSelf) ?? rawSelf;
        if (!mounted || epoch != generation) return;
        Json? partnerMap;
        if (saved['partner_chart'] is Map) {
          final rawPartner = jsonMap(saved['partner_chart']);
          partnerMap = await _resolveSaved(rawPartner) ?? rawPartner;
          if (!mounted || epoch != generation) return;
        }

        if (local != null && !local.syncedToServer && !overwrite) {
          final synced = await _syncProfileToServer(
            self: profile ?? local.self,
            partnerChart: partner ?? local.partner,
            adult: _savedAdult,
            parental: _savedParental,
          );
          if (!mounted || epoch != generation) return;
          if (synced) {
            setState(() => consentRecorded = true);
            await _saveLocalSnapshot(syncedToServer: true);
          }
          return;
        }

        if (local == null || overwrite) {
          setState(() {
            profile = selfMap;
            partner = partnerMap;
            consentRecorded = saved['dpdp_consent_granted'] == true;
            _savedAdult = saved['age_verified_18_plus'] != false;
            _savedParental = saved['parental_consent_verified'] == true;
          });
          await _saveLocalSnapshot(syncedToServer: true);
          _loadProfile();
          if (partnerMap != null) _loadMatch();
        } else {
          final nextPartner = partner ?? partnerMap;
          final nextConsent =
              consentRecorded || saved['dpdp_consent_granted'] == true;
          final hadPartner = partner != null;
          if (nextPartner != partner || nextConsent != consentRecorded) {
            setState(() {
              partner = nextPartner;
              consentRecorded = nextConsent;
            });
            await _saveLocalSnapshot(syncedToServer: true);
            if (!hadPartner && nextPartner != null) _loadMatch();
          }
        }
      } else if (profile != null) {
        final synced = await _syncProfileToServer(
          self: profile!,
          partnerChart: partner,
          adult: _savedAdult,
          parental: _savedParental,
        );
        if (!mounted || epoch != generation) return;
        if (synced) {
          setState(() => consentRecorded = true);
          await _saveLocalSnapshot(syncedToServer: true);
        }
      }
    } catch (_) {
      // Keep locally restored profile intact if the server is waking up or offline.
    }
  }

  Future<bool> _persistChart(Json chartDetails,
      {required bool adult,
      required bool parental,
      bool isPartner = false,
      bool partnerPermission = false,
      String? gender,
      String? maritalStatus,
      String? occupation}) async {
    if (!api.authenticated) return false;
    try {
      await api.post(
          '/user/chart',
          {
            if (api.userId != null) 'user_id': api.userId,
            'details': {
              ...chartDetails,
              'language': widget.locale.languageCode,
            },
            'dpdp_consent_granted': true,
            'age_verified_18_plus': adult,
            'parental_consent_verified': !adult && parental,
            'is_third_party_chart': isPartner,
            'third_party_permission_confirmed': isPartner && partnerPermission,
            'already_married': chartDetails['already_married'] == true,
            if (!isPartner && (gender ?? chartDetails['gender']) != null)
              'gender': gender ?? chartDetails['gender'],
            if (!isPartner &&
                (maritalStatus ?? chartDetails['marital_status']) != null)
              'marital_status': maritalStatus ?? chartDetails['marital_status'],
            if (!isPartner &&
                (occupation ?? chartDetails['occupation']) != null)
              'occupation': occupation ?? chartDetails['occupation'],
          },
          protected: true);
      return true;
    } catch (_) {
      // Local persistence keeps details safe even if background sync fails.
      return false;
    }
  }

  bool _sameBirth(Json? left, Json? right) {
    if (left == null || right == null) return false;
    return left['name'] == right['name'] &&
        left['birth_date'] == right['birth_date'] &&
        left['birth_time'] == right['birth_time'] &&
        left['place_name'] == right['place_name'];
  }

  void _applyRestoredProfile({
    required Json selfMap,
    required Json? partnerMap,
    required bool consent,
    required bool adult,
    required bool parental,
    required bool syncedToServer,
  }) {
    final same = _sameBirth(profile, selfMap);
    if (!same && profile != null) {
      epoch++;
      data.clear();
      errors.clear();
      pending.clear();
      versions.clear();
      answers.clear();
      chatThread.clear();
    }
    setState(() {
      profile = selfMap;
      partner = partnerMap ?? partner;
      consentRecorded = consent;
      _savedAdult = adult;
      _savedParental = parental;
    });
    unawaited(_saveLocalSnapshot(syncedToServer: syncedToServer));
    if (!same || data['chart'] == null) _loadProfile();
    if (partnerMap != null && (!same || data['match'] == null)) _loadMatch();
  }

  Future<void> _reconcileAfterAccountSignIn({
    Json? previousProfile,
    Json? previousPartner,
  }) async {
    final generation = epoch;
    if (api.authenticated) {
      try {
        final saved = await api.get('/user/profile', protected: true);
        if (!mounted || epoch != generation) return;
        if (saved['saved'] == true && saved['self_chart'] is Map) {
          final rawSelf = {
            ...jsonMap(saved['self_chart']),
            if (saved['gender'] != null) 'gender': saved['gender'],
            if (saved['marital_status'] != null)
              'marital_status': saved['marital_status'],
            if (saved['occupation'] != null) 'occupation': saved['occupation'],
          };
          final selfMap = await _resolveSaved(rawSelf) ?? rawSelf;
          if (!mounted || epoch != generation) return;
          Json? partnerMap;
          if (saved['partner_chart'] is Map) {
            final rawPartner = jsonMap(saved['partner_chart']);
            partnerMap = await _resolveSaved(rawPartner) ?? rawPartner;
            if (!mounted || epoch != generation) return;
          }
          _applyRestoredProfile(
            selfMap: selfMap,
            partnerMap: partnerMap,
            consent: saved['dpdp_consent_granted'] == true,
            adult: saved['age_verified_18_plus'] != false,
            parental: saved['parental_consent_verified'] == true,
            syncedToServer: true,
          );
          return;
        }
      } catch (_) {
        // Fall through to local store or active session migration.
      }
    }

    final local = await LocalProfileStore.load(accountId: api.userId);
    if (!mounted || epoch != generation) return;
    if (local != null) {
      final selfMap = await _resolveSaved(local.self) ?? local.self;
      if (!mounted || epoch != generation) return;
      Json? partnerMap;
      if (local.partner != null) {
        partnerMap = await _resolveSaved(local.partner!) ?? local.partner;
        if (!mounted || epoch != generation) return;
      }
      _applyRestoredProfile(
        selfMap: selfMap,
        partnerMap: partnerMap,
        consent: local.consentRecorded,
        adult: local.adult,
        parental: local.parental,
        syncedToServer: false,
      );
      final synced = await _syncProfileToServer(
        self: selfMap,
        partnerChart: partnerMap,
        adult: local.adult,
        parental: local.parental,
      );
      if (mounted && synced) {
        setState(() => consentRecorded = true);
        await _saveLocalSnapshot(syncedToServer: true);
      }
      return;
    }

    if (previousProfile != null) {
      setState(() {
        profile = previousProfile;
        partner = previousPartner;
      });
      await _saveLocalSnapshot(syncedToServer: false);
      final synced = await _syncProfileToServer(
        self: previousProfile,
        partnerChart: previousPartner,
        adult: _savedAdult,
        parental: _savedParental,
      );
      if (mounted && synced) {
        setState(() => consentRecorded = true);
        await _saveLocalSnapshot(syncedToServer: true);
      }
    }
  }

  Future<void> _handleGoogleSignIn() async {
    if (authBusy) return;
    final previousProfile = profile;
    final previousPartner = partner;
    setState(() => authBusy = true);
    var signedInOk = false;
    try {
      signedInOk = await (widget.signInWithGoogle ?? signInWithGoogleAccount)();
      if (!mounted) return;
      if (!signedInOk) {
        toast(t.googleSignInFailed);
        return;
      }
      await _reconcileAfterAccountSignIn(
        previousProfile: previousProfile,
        previousPartner: previousPartner,
      );
      if (mounted) setState(() {});
    } catch (_) {
      if (mounted && !signedInOk) toast(t.googleSignInFailed);
    } finally {
      if (mounted) setState(() => authBusy = false);
    }
  }

  Future<void> _handleSignOut() async {
    if (authBusy) return;
    setState(() => authBusy = true);
    try {
      await (widget.signOut ?? signOutToAnonymous)();
      await LocalProfileStore.clearAll();
      if (!mounted) return;
      clearSession();
    } finally {
      if (mounted) setState(() => authBusy = false);
    }
  }

  @override
  void didUpdateWidget(covariant CelestialHome oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.locale != widget.locale) {
      epoch++;
      data.clear();
      errors.clear();
      pending.clear();
      versions.clear();
      answers.clear();
      if (profile != null) _loadProfile();
      if (partner != null) _loadMatch();
    }
  }

  @override
  void dispose() {
    epoch++;
    _authWait?.cancel();
    _authSub?.cancel();
    question.dispose();
    super.dispose();
  }

  Future<Json?> load(String key, Future<Json> Function() request,
      {bool keepPrevious = false}) async {
    final generation = epoch;
    final version = (versions[key] ?? 0) + 1;
    versions[key] = version;
    final retain = keepPrevious || data.containsKey(key);
    setState(() {
      pending.add(key);
      errors.remove(key);
      if (!retain) data.remove(key);
    });
    try {
      final result = await request();
      if (!mounted || epoch != generation || versions[key] != version) {
        return null;
      }
      setState(() {
        data[key] = result;
        pending.remove(key);
      });
      return result;
    } catch (error) {
      if (!mounted || epoch != generation || versions[key] != version) {
        return null;
      }
      setState(() {
        errors[key] = error;
        pending.remove(key);
      });
      return null;
    }
  }

  void clearSession() {
    epoch++;
    setState(() {
      profile = null;
      partner = null;
      consentRecorded = false;
      data.clear();
      errors.clear();
      pending.clear();
      versions.clear();
      answers.clear();
      chatThread.clear();
      question.clear();
      selectedArea = null;
      askUnmatched = false;
      d9 = false;
    });
  }

  Future<Json?> _resolveSaved(Json source) {
    return resolveUpdatedPlace(source, search: _searchPlaces);
  }

  Future<List<Json>> _searchPlaces(String query) async {
    final hits = await api.searchPlaces(query);
    if (hits.isNotEmpty || api.localDevelopment) return hits;
    final remote = await searchPlacesOnDevice(query);
    return remote;
  }

  Future<void> editBirth(
      {bool forPartner = false, bool preConsented = false}) async {
    final initialData = forPartner ? partner : profile;
    final result = await goldSheet<BirthSubmission>(context,
        title: forPartner ? t.partnerDetails : t.birthDetails,
        child: BirthForm(
            initial: initialData,
            partner: forPartner,
            preConsented: preConsented && initialData != null,
            initialAdult: _savedAdult,
            initialParental: _savedParental,
            placeSearch: _searchPlaces));
    if (result == null || !mounted) return;
    if (forPartner) {
      if (!result.partnerPermission || profile == null) return;
      final enriched = await _resolveSaved(result.details);
      if (!mounted) return;
      if (enriched == null) {
        setState(
            () => errors['match'] = const ApiFailure('ambiguous_location'));
        return;
      }
      setState(() {
        partner = enriched;
        data.remove('match');
        errors.remove('match');
      });
      await _saveLocalSnapshot(syncedToServer: false);
      _loadMatch();
      if (api.authenticated) {
        final adult = _savedAdult || result.adult;
        final parental = _savedParental || result.parental;
        var saved = false;
        if (consentRecorded) {
          saved = await _persistChart(enriched,
              adult: adult,
              parental: parental,
              isPartner: true,
              partnerPermission: true);
        } else if (profile != null) {
          saved = await _syncProfileToServer(
            self: profile!,
            partnerChart: enriched,
            adult: adult,
            parental: parental,
          );
          if (saved && mounted) setState(() => consentRecorded = true);
        }
        if (saved && mounted) {
          await _saveLocalSnapshot(syncedToServer: true);
        }
      }
      return;
    }
    // Invalidate all in-flight responses before accepting a different person's details.
    final enriched = await _resolveSaved(result.details);
    if (!mounted) return;
    if (enriched == null) {
      setState(() => errors['chart'] = const ApiFailure('ambiguous_location'));
      return;
    }
    clearSession();
    setState(() {
      profile = enriched;
      _savedAdult = result.adult;
      _savedParental = result.parental;
    });
    await _saveLocalSnapshot(syncedToServer: false);
    _loadProfile();
    if (api.authenticated) {
      final generation = epoch;
      final response = await load(
          'consent',
          () => api.post(
              '/privacy/consent',
              {
                if (api.userId != null) 'user_id': api.userId,
                'dpdp_consent_granted': true,
                'age_verified_18_plus': result.adult,
                'parental_consent_verified': result.parental,
                'preferred_language': widget.locale.languageCode,
              },
              protected: true));
      if (mounted && epoch == generation) {
        final ok = response != null;
        setState(() => consentRecorded = ok);
        if (ok) {
          final chartSaved = await _persistChart(enriched,
              adult: result.adult,
              parental: result.parental,
              gender: result.gender,
              maritalStatus: result.maritalStatus,
              occupation: result.occupation);
          if (mounted && epoch == generation) {
            await _saveLocalSnapshot(syncedToServer: chartSaved);
          }
        }
      }
    }
  }

  Future<Json> _postDetails(String path,
      {Map<String, String> query = const {}}) async {
    try {
      return await api.post(path, details, query: query);
    } on ApiFailure catch (error) {
      final missingCoordinates =
          profile?['latitude'] == null || profile?['longitude'] == null;
      if (!missingCoordinates ||
          (error.code != 'geocoder_unavailable' &&
              error.code != 'ambiguous_location')) {
        rethrow;
      }
      final resolved = await _resolveSaved({...?profile});
      if (resolved == null || !mounted) rethrow;
      setState(() => profile = resolved);
      await _saveLocalSnapshot(syncedToServer: false);
      if (accountReady) {
        final saved = await _persistChart(details,
            adult: _savedAdult, parental: _savedParental);
        if (saved && mounted) await _saveLocalSnapshot(syncedToServer: true);
      }
      return api.post(path, details, query: query);
    }
  }

  void _loadProfile() {
    if (profile == null) return;
    () async {
      final next = await _resolveSaved(profile!);
      if (!mounted || profile == null) return;
      if (next == null) {
        setState(
            () => errors['chart'] = const ApiFailure('ambiguous_location'));
        return;
      }
      if (next['latitude'] != profile?['latitude'] ||
          next['longitude'] != profile?['longitude']) {
        setState(() => profile = next);
        await _saveLocalSnapshot(syncedToServer: false);
      }
      if (!mounted) return;
      load('chart', () async {
        await api.waitUntilAwake();
        return _postDetails('/chart');
      }).then((chart) {
        if (!mounted || chart == null) return;
        final query = targetQuery;
        load('dasha', () => _postDetails('/dasha', query: query));
        load('daily',
            () => _postDetails('/readings/daily-insight', query: query));
        load('areas', () => _postDetails('/readings/life-areas', query: query));
        load(
            'sky',
            () => api.fetchAndCacheDailyPanchang(targetDate,
                placeName: shown(profile?['place_name']),
                latitude: number(chart['resolved_latitude']),
                longitude: number(chart['resolved_longitude'])));
      });
    }();
  }

  void _loadMatch() {
    if (profile == null || partner == null) return;
    () async {
      final self = await _resolveSaved(profile!);
      final other = await _resolveSaved(partner!);
      if (!mounted || profile == null || partner == null) return;
      if (self == null || other == null) {
        setState(
            () => errors['match'] = const ApiFailure('ambiguous_location'));
        return;
      }
      setState(() {
        profile = self;
        partner = other;
      });
      load(
          'match',
          () => api.post('/matching/ashtakoota', {
                'profile_a': {...self, 'language': widget.locale.languageCode},
                'profile_b': {...other, 'language': widget.locale.languageCode},
                'partner_consent_confirmed': true,
                'already_married': other['already_married'] == true,
              }));
    }();
  }

  void _loadCalibration() {
    if (!accountReady || pending.contains('calibration')) return;
    load(
        'calibration',
        () => api.get('/ledger/calibration',
            query: {
              if (api.userId != null) 'user_id': api.userId!,
              'lang': widget.locale.languageCode,
            },
            protected: true));
  }

  Future<void> ask() async {
    final text = question.text.trim();
    if (pending.contains('ask') ||
        data['chart'] == null ||
        text.runes.length < 3 ||
        text.runes.length > 280) {
      return;
    }
    FocusScope.of(context).unfocus();
    final area = classifyLifeArea(text);
    setState(() {
      selectedArea = area;
      askUnmatched = !accountReady && area == null;
      chatThread.add({
        'role': 'user',
        'text': text,
        'at': DateTime.now().toIso8601String(),
      });
    });
    if (!accountReady) {
      if (area == null) {
        setState(() {
          chatThread.add({
            'role': 'assistant',
            'text': t.chatUncovered,
            'at': DateTime.now().toIso8601String(),
          });
        });
      }
      return;
    }
    final result = await load(
        'ask',
        () => api.post(
            '/readings/ask',
            {
              'details': details,
              'question': text,
              'target_date': targetDate,
            },
            protected: true));
    if (result == null || !mounted) return;
    final statement = jsonMap(result['statement']);
    if (AstroplanApiClient.safeStatement(statement) &&
        result['ledger_entry_id'] is String &&
        (result['ledger_entry_id'] as String).isNotEmpty) {
      setState(() => answers.insert(0, {...result, 'question': text}));
      _loadCalibration();
      return;
    }
    if (jsonMap(result['coverage'])['status'] == 'uncovered') {
      setState(() {
        chatThread.add({
          'role': 'assistant',
          'text': t.chatUncovered,
          'at': DateTime.now().toIso8601String(),
        });
      });
    }
  }

  Future<void> _afterPhoneSignedIn() async {
    final previousProfile = profile;
    final previousPartner = partner;
    await _reconcileAfterAccountSignIn(
      previousProfile: previousProfile,
      previousPartner: previousPartner,
    );
    if (mounted) setState(() {});
  }

  Future<void> phoneLoginSheet() =>
      goldSheet<void>(context, title: t.phoneSignIn,
          child: PhoneAuthPanel(
            startOtp: widget.startOtp,
            confirmOtp: widget.confirmOtp,
            onSignedIn: () async {
              if (mounted) Navigator.of(context).pop();
              await _afterPhoneSignedIn();
            },
          ));

  Future<void> accountSheet() async {
    final action = await goldSheet<String>(context,
        title: t.accountTitle,
        child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (_accountSignedIn && _accountLabel != null) ...[
                Text(t.googleSignedInAs(_accountLabel!),
                    style: const TextStyle(
                        color: gold, fontSize: 13, fontWeight: FontWeight.w500)),
                gap(10),
              ],
              if (!_phoneSignedIn) ...[
                note(t.phoneLinkHint),
                gap(14),
                SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                        key: const Key('phone_sign_in_account'),
                        onPressed: authBusy
                            ? null
                            : () => Navigator.pop(context, 'phone'),
                        icon: const Icon(Icons.sms_outlined, size: 18),
                        label: Text(t.phoneSignIn))),
                gap(12),
              ],
              if (!_googleSignedIn) ...[
                SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                        key: const Key('google_sign_in_account'),
                        onPressed: authBusy
                            ? null
                            : () => Navigator.pop(context, 'google'),
                        icon: const Icon(Icons.login, size: 18),
                        label: Text(t.googleSignIn))),
                gap(12),
              ],
              if (_accountSignedIn) ...[
                const Divider(),
                ListTile(
                    key: const Key('sign_out_account'),
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.logout, color: gold),
                    title: Text(t.signOutLabel),
                    onTap: () => Navigator.pop(context, 'sign_out')),
              ],
            ]));
    if (!mounted || action == null) return;
    if (action == 'phone') {
      await phoneLoginSheet();
    } else if (action == 'google') {
      await _handleGoogleSignIn();
    } else if (action == 'sign_out') {
      await _handleSignOut();
    }
  }

  Future<void> mark(Json answer, String outcome) async {
    final id = answer['ledger_entry_id'] as String;
    final key = 'mark:$id';
    if (pending.contains(key) || !accountReady) return;
    final result = await load(
        key,
        () => api.post(
            '/ledger/${Uri.encodeComponent(id)}/mark', {'outcome': outcome},
            protected: true));
    if (result != null && mounted) {
      setState(() {
        answer['mark'] = result;
      });
      _loadCalibration();
    }
  }

  void toast(String text) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  Widget gap([double height = 14]) => SizedBox(height: height);
  Widget note(String text) => Text(text,
      style: const TextStyle(color: muted, fontSize: 12, height: 1.6));
  Widget status(String key, {List<String> hideWhenSameAs = const []}) {
    if (pending.contains(key)) {
      return Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Semantics(
              label: t.loadingSlowLabel,
              liveRegion: true,
              child: Column(children: [
                const LinearProgressIndicator(
                    minHeight: 2, color: gold, backgroundColor: panel),
                const SizedBox(height: 8),
                SlowLoadHint(
                    label: t.loadingLabel, slowLabel: t.loadingSlowLabel),
              ])));
    }
    if (errors[key] != null) {
      final message = friendlyError(t, errors[key]!);
      final duplicated = hideWhenSameAs.any((other) =>
          errors[other] != null && friendlyError(t, errors[other]!) == message);
      if (duplicated) return const SizedBox.shrink();
      return Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: GoldPanel(
              child: Text(friendlyError(t, errors[key]!),
                  style:
                      const TextStyle(color: Color(0xFFE6A2A7), height: 1.5))));
    }
    return const SizedBox.shrink();
  }

  Widget onboarding() => GoldPanel(
      accent: true,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(t.beginTitle, style: serif(24)),
        gap(10),
        note(t.beginBody),
        gap(16),
        SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
                onPressed: editBirth,
                icon: const Icon(Icons.add, size: 18),
                label: Text(t.birthDetails))),
        if (_firebaseEnabled && !_phoneSignedIn) ...[
          gap(10),
          SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                  key: const Key('phone_sign_in_onboarding'),
                  onPressed: authBusy ? null : phoneLoginSheet,
                  icon: const Icon(Icons.sms_outlined, size: 18),
                  label: Text(t.phoneSignIn))),
        ],
        gap(12),
        note(t.sessionPrivacy),
      ]));

  Widget savedProfileCard({required String keyPrefix}) {
    final p = profile;
    if (p == null) return const SizedBox.shrink();
    final timeRaw = shown(p['birth_time']);
    final timeClean = RegExp(r'^\d{2}:\d{2}:00$').hasMatch(timeRaw)
        ? timeRaw.substring(0, 5)
        : timeRaw;
    final summary =
        '${shown(p['birth_date'])} · $timeClean · ${shown(p['place_name'])}, ${shown(p['country'])}';
    final account = _accountLabel;
    return GoldPanel(
        padding: 14,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Text(shown(p['name']), style: serif(21)),
                  gap(4),
                  note(summary),
                  if (account != null) ...[
                    gap(4),
                    Eyebrow(t.googleSignedInAs(account)),
                  ] else if (accountReady) ...[
                    gap(4),
                    Eyebrow(t.savedProfileNote),
                  ],
                ])),
            const SizedBox(width: 10),
            OutlinedButton.icon(
                key: Key('${keyPrefix}_edit_details'),
                onPressed: () => editBirth(preConsented: consentRecorded),
                icon: const Icon(Icons.edit_outlined, size: 16),
                label: Text(t.editDetailsLabel)),
          ]),
          if (_firebaseEnabled && (!_phoneSignedIn || !_googleSignedIn)) ...[
            gap(10),
            Wrap(spacing: 8, runSpacing: 8, children: [
              if (!_phoneSignedIn)
                OutlinedButton.icon(
                    key: Key('${keyPrefix}_phone_sign_in'),
                    onPressed: authBusy ? null : phoneLoginSheet,
                    icon: const Icon(Icons.sms_outlined, size: 18),
                    label: Text(t.phoneSignIn)),
              if (!_googleSignedIn)
                OutlinedButton.icon(
                    key: Key('${keyPrefix}_google_sign_in'),
                    onPressed: authBusy ? null : _handleGoogleSignIn,
                    icon: const Icon(Icons.account_circle_outlined, size: 18),
                    label: Text(t.googleSignIn)),
            ]),
          ],
        ]));
  }

  double? get natalMoon {
    for (final p in jsonRows(data['chart']?['planets'])) {
      if (p['planet'] == 'Moon') return number(p['longitude']);
    }
    return null;
  }

  void showSky() => goldSheet(context,
      title: t.skyTitle,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        note(t.skyDescription),
        gap(12),
        SkyDial(panchang: data['sky'], natalMoon: natalMoon, detailed: true),
        if (data['sky'] case final p?) ...[
          FactRow(
              p['reference_kind'] == 'sunrise' ? t.sunriseMoon : t.fallbackMoon,
              '${astroTerm(t.localeName, p['moon_sign_name'])} · ${degrees(p['moon_degree_in_sign'])} · ${astroTerm(t.localeName, p['nakshatra'])} · ${t.padaLabel} ${shown(p['moon_nakshatra_pada'])}'),
          FactRow(t.moonLongitude, degrees(p['moon_longitude'])),
          FactRow(t.sunLongitude, degrees(p['sun_longitude'])),
          if (number(p['phase_illumination']) case final fraction?)
            FactRow(
                t.illuminationLabel, '${(fraction * 100).toStringAsFixed(1)}%'),
          FactRow(t.birthMoon, degrees(natalMoon)),
          FactRow(t.sourceTime, shown(p['reference_datetime'])),
          FactRow(t.methodLabel, shown(jsonMap(p['location'])['timezone'])),
          if (p['reference_kind'] != 'sunrise' ||
              p['slot_math_fallback'] == true)
            note(t.fallbackNote),
          if (p['_offline'] == true)
            FactRow(t.cachedAt, shown(p['_cached_at'])),
        ] else
          note(t.beginBody),
      ]));
  Widget today() {
    final p = data['sky'];
    final d = data['dasha'];
    final areas =
        jsonMap(data['areas']?['daily_areas'] ?? data['areas']?['life_areas']);
    const dayAreas = [
      ('relationships', 'inner'),
      ('career', 'work'),
      ('finances', 'money'),
      ('home', 'home'),
    ];
    String areaTitle(String key) => switch (key) {
          'inner' => t.innerLifeTitle,
          'work' => t.workTitle,
          'money' => t.moneyTitle,
          _ => t.homeDayTitle,
        };
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Eyebrow(p == null
          ? DateFormat.yMMMMd(widget.locale.languageCode).format(DateTime.now())
          : '${shown(p['date'])} · ${astroTerm(t.localeName, p['vara'])}'),
      gap(10),
      Text(t.dayTitle, style: serif(34)),
      gap(10),
      note(t.dayIntro),
      gap(18),
      if (profile == null)
        onboarding()
      else ...[
        savedProfileCard(keyPrefix: 'today'),
        gap(),
        status('chart'),
        if (errors['chart'] != null)
          TextButton(onPressed: editBirth, child: Text(t.editDetailsLabel)),
        note(t.dayBasis),
        gap(),
        status('daily', hideWhenSameAs: const ['chart']),
        if (data['daily'] case final statement?)
          StatementPanel(statement: statement, title: t.dayFeelTitle),
        gap(),
        status('areas', hideWhenSameAs: const ['chart', 'daily']),
        for (final area in dayAreas) ...[
          for (final statement in jsonRows(areas[area.$1])) ...[
            StatementPanel(statement: statement, title: areaTitle(area.$2)),
            gap(),
          ],
        ],
        if (p != null) ...[
          GoldPanel(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                Eyebrow(t.timingTitle),
                gap(12),
                _fact(t.beginWindowLabel, shown(p['abhijit_muhurat'])),
                gap(6),
                note(t.beginWindowNote),
                gap(14),
                _fact(t.waitWindowLabel, shown(p['rahu_kaal'])),
                gap(6),
                note(t.waitWindowNote),
              ])),
          gap(),
        ],
        status('sky'),
        TextButton.icon(
            onPressed: () =>
                setState(() => showChartDetails = !showChartDetails),
            icon: Icon(showChartDetails ? Icons.expand_less : Icons.expand_more,
                size: 18),
            label: Text(t.chartDetailsLabel)),
        if (showChartDetails) ...[
          note(t.chartDetailsNote),
          gap(12),
          Center(
              child: SizedBox(
                  width: 180,
                  child: InkWell(
                      onTap: showSky,
                      borderRadius: BorderRadius.circular(140),
                      child: SkyDial(panchang: p, natalMoon: natalMoon)))),
          gap(),
          if (p != null)
            GoldPanel(
                padding: 15,
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _fact(t.tithiLabel, astroTerm(t.localeName, p['tithi'])),
                      gap(12),
                      _fact(t.nakshatraLabel,
                          '${astroTerm(t.localeName, p['nakshatra'])} · ${t.padaLabel} ${shown(p['moon_nakshatra_pada'])}'),
                      gap(12),
                      _fact(t.sunriseLabel, shown(p['sunrise_local'])),
                      gap(8),
                      note(
                          '${t.sourceTime}: ${shown(p['reference_datetime'])}'),
                      if (p['reference_kind'] != 'sunrise' ||
                          p['slot_math_fallback'] == true)
                        note(t.fallbackNote),
                      if (p['_offline'] == true) ...[
                        gap(8),
                        Eyebrow(t.offlineCachedBadge),
                        note('${t.cachedAt}: ${shown(p['_cached_at'])}')
                      ],
                    ])),
          gap(),
          status('dasha'),
          if (d != null)
            GoldPanel(
                child: InkWell(
                    onTap: showDasha,
                    child: Row(children: [
                      const Icon(Icons.timelapse, color: gold, size: 28),
                      const SizedBox(width: 14),
                      Expanded(
                          child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                            Eyebrow(t.dashaLabel),
                            gap(6),
                            Text(
                                '${planetName(t, d['active_mahadasha'])} · ${planetName(t, d['active_antardasha'])}',
                                style: serif(20)),
                            gap(4),
                            note(
                                '${t.endsLabel}: ${shown(d['antardasha_end_date'])}')
                          ])),
                      const Icon(Icons.arrow_forward, color: gold, size: 18),
                    ]))),
        ],
        if (errors['consent'] != null) ...[gap(), note(t.consentError)],
        gap(),
        OutlinedButton.icon(
            onPressed: _loadProfile,
            icon: const Icon(Icons.refresh, size: 18),
            label: Text(t.refreshLabel)),
      ],
    ]);
  }

  Widget _fact(String label, String value) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label.toUpperCase(),
            style:
                const TextStyle(color: muted, letterSpacing: 1, fontSize: 10)),
        gap(6),
        Text(value, style: serif(16)),
      ]);
  void revealAnnual() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final target = annualAnchor.currentContext;
      if (target == null || !mounted) return;
      Scrollable.ensureVisible(target,
          alignment: 0.04,
          duration: const Duration(milliseconds: 280),
          curve: Curves.easeOut);
    });
  }

  Future<void> openAnnual(int forecastYear) async {
    if (profile != null) {
      final next = await _resolveSaved(profile!);
      if (!mounted) return;
      if (next == null) {
        setState(
            () => errors['annual'] = const ApiFailure('ambiguous_location'));
        return;
      }
      if (next['latitude'] != profile?['latitude']) {
        setState(() => profile = next);
      }
    }
    final future = load(
        'annual',
        () => api.post('/reports/annual-forecast', details,
            query: {'forecast_year': '$forecastYear'}),
        keepPrevious: true);
    revealAnnual();
    await future;
    revealAnnual();
  }

  Future<void> saveAnnualPdf() async {
    if (pending.contains('annual-pdf') || profile == null) return;
    final next = await _resolveSaved(profile!);
    if (!mounted || profile == null) return;
    if (next == null) {
      setState(
          () => errors['annual-pdf'] = const ApiFailure('ambiguous_location'));
      return;
    }
    if (next['latitude'] != profile?['latitude']) {
      setState(() => profile = next);
    }
    setState(() {
      pending.add('annual-pdf');
      errors.remove('annual-pdf');
    });
    try {
      final bytes = await api.postBytes('/reports/annual-forecast/pdf', details,
          query: {'forecast_year': '$year'});
      final dir = await getTemporaryDirectory();
      final file = File('${dir.path}/astroplan-$year.pdf');
      await file.writeAsBytes(bytes, flush: true);
      if (!mounted) return;
      await Share.shareXFiles(
        [
          XFile(file.path,
              mimeType: 'application/pdf', name: 'astroplan-$year.pdf')
        ],
      );
    } catch (error) {
      if (mounted) setState(() => errors['annual-pdf'] = error);
    } finally {
      if (mounted) setState(() => pending.remove('annual-pdf'));
    }
  }

  void showDasha() {
    final d = data['dasha'];
    if (d == null) return;
    goldSheet(context,
        title: t.dashaTimeline,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          FactRow(t.mahadashaLabel, planetName(t, d['active_mahadasha'])),
          FactRow(t.antardashaLabel,
              '${planetName(t, d['active_antardasha'])} · ${shown(d['antardasha_end_date'])}'),
          FactRow(
              t.pratyantarLabel, planetName(t, d['active_pratyantardasha'])),
          for (final row in jsonRows(d['timeline'])) ...[
            const Divider(),
            FactRow(planetName(t, row['mahadasha_lord']),
                '${shown(row['start_date'])} — ${shown(row['end_date'])}')
          ],
        ]));
  }

  Widget chart() {
    final c = data['chart'];
    final areas = jsonMap(data['areas']?['life_areas']);
    final labels = {
      'career': t.careerLabel,
      'relationships': t.relationshipsLabel,
      'finances': t.financesLabel,
      'home': t.homeLabel
    };
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      PageHeading(t.tabChart, t.chartTitle, t.chartDescription),
      if (profile == null)
        onboarding()
      else ...[
        savedProfileCard(keyPrefix: 'chart'),
        gap(),
        status('chart'),
        if (c != null) ...[
          SegmentedButton<bool>(
              showSelectedIcon: false,
              segments: [
                ButtonSegment(value: false, label: Text(t.d1Label)),
                ButtonSegment(value: true, label: Text(t.d9Label))
              ],
              selected: {d9},
              onSelectionChanged: (v) => setState(() => d9 = v.first)),
          gap(),
          GoldPanel(
              accent: true,
              padding: 14,
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Container(
                          width: 52,
                          height: 52,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              border: Border.all(color: hairline),
                              gradient: const RadialGradient(
                                  center: Alignment(-.4, -.4),
                                  colors: [Color(0xFF8A7858), panel])),
                          child: Text(
                              d9
                                  ? t.d9Label.split(' · ').first
                                  : t.d1Label.split(' · ').first,
                              style: serif(18))),
                      const SizedBox(width: 14),
                      Expanded(
                          child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                            Eyebrow(t.lagnaLabel),
                            gap(5),
                            Text(
                                signName(
                                    t,
                                    c[d9
                                        ? 'navamsa_lagna_sign_index'
                                        : 'lagna_sign_index'],
                                    c[d9
                                        ? 'navamsa_lagna_sign_name'
                                        : 'lagna_sign_name']),
                                style: serif(24)),
                            if (!d9)
                              Text(degrees(c['lagna_degree']),
                                  style: const TextStyle(
                                      color: muted, fontSize: 12))
                          ]))
                    ]),
                    gap(10),
                    NorthIndianChart(chart: c, navamsa: d9),
                    const Divider(),
                    _fact(t.birthMoon,
                        '${signName(t, c['moon_sign_index'], c['moon_sign_name'])} · ${astroTerm(t.localeName, c['moon_nakshatra'])}'),
                    gap(12),
                    TextButton.icon(
                        onPressed: () => showPlacements(c),
                        icon: const Icon(Icons.arrow_outward, size: 16),
                        label: Text(t.placementsLabel)),
                    if (c['boundary_warning'] != null)
                      note(shown(c['boundary_warning'])),
                  ])),
          gap(),
          if (c['disclaimer'] != null) note(shown(c['disclaimer'])),
          gap(),
        ],
        status('areas', hideWhenSameAs: const ['chart']),
        if (errors['chart'] != null || errors['areas'] != null) ...[
          FilledButton.icon(
              onPressed: pending.contains('chart') ? null : _loadProfile,
              icon: const Icon(Icons.refresh),
              label: Text(t.refreshLabel)),
          gap(),
        ],
        Eyebrow(t.lifeAreasLabel),
        gap(12),
        for (final area in labels.entries) ...[
          for (final statement in jsonRows(areas[area.key])) ...[
            StatementPanel(statement: statement, title: area.value),
            gap()
          ],
        ],
        if (jsonRows(data['areas']?['yogas_and_doshas']).isNotEmpty) ...[
          Eyebrow(t.yogasLabel),
          gap(12),
          for (final s in jsonRows(data['areas']?['yogas_and_doshas'])) ...[
            StatementPanel(statement: s, title: t.yogasLabel),
            gap()
          ]
        ],
        GoldPanel(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Eyebrow(t.yearLabel),
          gap(8),
          Text(t.annualTitle, style: serif(26)),
          gap(12),
          note(t.annualCaution),
          gap(16),
          DropdownButtonFormField<int>(
              key: const Key('forecast_year'),
              initialValue: year,
              decoration: InputDecoration(labelText: t.yearLabel),
              items: List.generate(6, (i) => DateTime.now().year - 1 + i)
                  .map((y) => DropdownMenuItem(value: y, child: Text('$y')))
                  .toList(),
              onChanged: (y) {
                if (y == null || y == year || pending.contains('annual')) {
                  return;
                }
                setState(() => year = y);
                openAnnual(y);
              }),
          gap(12),
          FilledButton(
              onPressed:
                  pending.contains('annual') ? null : () => openAnnual(year),
              child: Text(t.annualAction)),
          gap(8),
          OutlinedButton.icon(
              onPressed: pending.contains('annual-pdf') ? null : saveAnnualPdf,
              icon: const Icon(Icons.picture_as_pdf_outlined, size: 18),
              label: Text(t.annualPdfAction)),
          status('annual-pdf'),
        ])),
        Column(
            key: annualAnchor,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              status('annual'),
              if (data['annual'] case final annual?) ...[
                gap(),
                StatementPanel(
                    statement: jsonMap(annual['overview']),
                    title: shown(annual['year'])),
                for (final q in jsonRows(annual['quarters'])) ...[
                  gap(),
                  StatementPanel(
                      statement: jsonMap(q['theme_statement']),
                      title: shown(q['quarter'])),
                ],
              ],
            ]),
        gap(),
        OutlinedButton.icon(
            onPressed: editBirth,
            icon: const Icon(Icons.edit_outlined, size: 18),
            label: Text(t.birthDetails)),
      ],
    ]);
  }

  void showPlacements(Json c) => goldSheet(context,
      title: t.placementsLabel,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        note(d9 ? t.d9Label : t.d1Label),
        for (final p in jsonRows(c['planets'])) ...[
          const Divider(),
          FactRow(planetName(t, p['planet']),
              '${t.signLabel}: ${signName(t, p[d9 ? 'navamsa_sign_index' : 'sign_index'], p[d9 ? 'navamsa_sign_name' : 'sign_name'])}'),
          if (!d9) ...[
            Text(
                '${degrees(p['degree_in_sign'])} · ${t.houseLabel} ${shown(p['house'])}'),
            note(
                '${astroTerm(t.localeName, p['nakshatra_name'])} · ${t.padaLabel} ${shown(p['pada'])}')
          ],
          if (p['is_retrograde'] == true) note(t.retrogradeLabel),
        ],
        const Divider(),
        FactRow(t.sourceTime, shown(c['utc_datetime'])),
        FactRow(t.methodLabel, shown(c['resolved_timezone'])),
      ]));
  String? namedNakshatra(dynamic value) {
    final text = value?.toString().trim() ?? '';
    if (text.isEmpty) return null;
    return astroTerm(t.localeName, text);
  }

  void chooseArea(String area) => setState(() {
        selectedArea = area;
        askUnmatched = false;
      });

  Widget askKundali() {
    final response = data['ask'];
    final closed = selectedArea == null &&
        !askUnmatched &&
        response == null &&
        !pending.contains('ask') &&
        errors['ask'] == null;
    final labels = {
      'career': t.careerLabel,
      'relationships': t.relationshipsLabel,
      'finances': t.financesLabel,
      'home': t.homeLabel,
      'others': t.othersLabel,
    };
    final statements =
        jsonRows(jsonMap(data['areas']?['life_areas'])[selectedArea]);
    final birth = namedNakshatra(data['chart']?['moon_nakshatra']);
    final today = namedNakshatra(data['sky']?['nakshatra']);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (closed)
        Opacity(
            opacity: .55,
            child:
                GoldPanel(key: const Key('ask_hold'), child: note(t.askHold))),
      if (askUnmatched && response == null)
        GoldPanel(child: note(t.uncoveredLabel)),
      if (selectedArea == 'others') ...[
        Eyebrow(t.askFromKundali),
        gap(8),
        GoldPanel(child: note(t.othersHint)),
      ] else if (selectedArea != null) ...[
        Eyebrow(t.askFromKundali),
        gap(8),
        if (birth != null) note(t.askBirthNakshatra(birth)),
        if (today != null) note(t.askTodayNakshatra(today)),
        gap(8),
        status('areas'),
        if (statements.isEmpty &&
            !pending.contains('areas') &&
            errors['areas'] == null)
          GoldPanel(child: note(t.uncoveredLabel))
        else
          for (final statement in statements) ...[
            StatementPanel(
                statement: statement,
                title: labels[selectedArea] ?? t.askFromKundali),
            gap(),
          ],
      ],
    ]);
  }

  Widget askPage() {
    final response = data['ask'];
    final chartReady = data['chart'] != null;
    final questionReady = question.text.trim().runes.length >= 3 &&
        question.text.trim().runes.length <= 280;
    final choices = {
      'career': t.careerLabel,
      'relationships': t.relationshipsLabel,
      'finances': t.financesLabel,
      'home': t.homeLabel,
      'others': t.othersLabel,
    };
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      PageHeading(t.tabAsk, t.chatTitle, t.chatDescription),
      if (profile == null) ...[onboarding(), gap()],
      if (!api.authenticated) ...[
        GoldPanel(child: note(t.authError)),
        gap()
      ] else if (profile != null && !consentRecorded) ...[
        note(t.consentError),
        gap()
      ],
      if (chatThread.isEmpty)
        GoldPanel(child: note(t.chatEmpty))
      else
        for (final message in chatThread) ...[
          gap(8),
          Align(
              alignment: message['role'] == 'user'
                  ? Alignment.centerRight
                  : Alignment.centerLeft,
              child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 520),
                  child: GoldPanel(
                      accent: message['role'] == 'assistant',
                      padding: 12,
                      child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Eyebrow(message['role'] == 'user'
                                ? t.chatYou
                                : t.chatAstroplan),
                            gap(6),
                            Text(shown(message['text']),
                                style: const TextStyle(height: 1.55)),
                          ])))),
        ],
      gap(),
      GoldPanel(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        TextField(
            key: const Key('ask_question'),
            controller: question,
            maxLength: 280,
            minLines: 2,
            maxLines: 5,
            textInputAction: TextInputAction.send,
            decoration: InputDecoration(labelText: t.questionLabel),
            onChanged: (_) => setState(() {}),
            onSubmitted: (_) => ask()),
        gap(10),
        Wrap(spacing: 6, runSpacing: 4, children: [
          for (final choice in choices.entries)
            ChoiceChip(
                key: Key('ask_area_${choice.key}'),
                label: Text(choice.value),
                selected: selectedArea == choice.key,
                onSelected: chartReady ? (_) => chooseArea(choice.key) : null,
                labelStyle: TextStyle(
                    color: !chartReady
                        ? muted
                        : selectedArea == choice.key
                            ? night
                            : ink,
                    fontSize: 12),
                selectedColor: gold,
                backgroundColor: const Color(0xFF0A1020),
                disabledColor: const Color(0xFF0A1020),
                side: BorderSide(
                    color: chartReady && selectedArea != choice.key
                        ? hairline
                        : const Color(0x14FFFFFF))),
        ]),
        gap(12),
        SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
                key: const Key('ask_submit'),
                onPressed:
                    chartReady && !pending.contains('ask') && questionReady
                        ? ask
                        : null,
                icon: const Icon(Icons.send, size: 18),
                label: Text(t.chatSend))),
      ])),
      status('ask'),
      gap(),
      askKundali(),
      if (response != null) ...[
        if (jsonMap(response['coverage'])['status'] == 'uncovered')
          GoldPanel(child: note(t.uncoveredLabel))
        else if (response['statement'] != null)
          StatementPanel(
              statement: jsonMap(response['statement']), title: t.dailyHeading)
        else
          GoldPanel(child: note(t.invalidResponseError)),
        for (final s in jsonRows(response['context'])) ...[
          gap(),
          StatementPanel(statement: s, title: t.contextLabel)
        ],
        if (response['ledger_entry_id'] != null &&
            AstroplanApiClient.safeStatement(
                jsonMap(response['statement']))) ...[
          gap(),
          Eyebrow(t.ledgerRecorded)
        ],
        if (response['disclaimer'] != null) ...[
          gap(),
          note(shown(response['disclaimer']))
        ],
      ],
    ]);
  }

  Widget matchPage() {
    final match = data['match'];
    final score = number(match?['total_score']),
        max = number(match?['max_score']);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      PageHeading(t.tabMatch, t.matchTitle, t.matchDescription),
      if (profile == null)
        onboarding()
      else ...[
        GoldPanel(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Eyebrow(t.partnerDetails),
          gap(10),
          if (partner == null)
            note(t.matchEmpty)
          else ...[
            Text(shown(partner?['name']), style: serif(24)),
            gap(4),
            note(
                '${shown(partner?['birth_date'])} · ${shown(partner?['birth_time'])} · ${shown(partner?['place_name'])}, ${shown(partner?['country'])}'),
          ],
          gap(16),
          FilledButton.icon(
              key: const Key('add_partner'),
              onPressed: pending.contains('match')
                  ? null
                  : () => editBirth(
                      forPartner: true, preConsented: partner != null),
              icon: Icon(
                  partner == null
                      ? Icons.person_add_alt_1
                      : Icons.edit_outlined,
                  size: 18),
              label: Text(partner == null ? t.addPartner : t.editPartnerLabel)),
        ])),
        status('match'),
        if (match != null) ...[
          for (final person in jsonRows(match['people'])) ...[
            gap(),
            GoldPanel(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Eyebrow(shown(person['role'])),
                  gap(8),
                  Text(shown(person['name']), style: serif(24)),
                  gap(8),
                  note(shown(person['birth'])),
                ])),
          ],
          for (final section in jsonRows(match['sections'])) ...[
            gap(),
            GoldPanel(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Eyebrow(shown(section['title'])),
                  gap(8),
                  Text(shown(section['text']),
                      style: const TextStyle(color: ink, height: 1.65)),
                ])),
          ],
        ],
        if (match != null && score != null && max != null && max > 0) ...[
          gap(),
          GoldPanel(
              accent: true,
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Center(
                        child: SizedBox(
                            width: 165,
                            height: 165,
                            child:
                                Stack(alignment: Alignment.center, children: [
                              SizedBox.expand(
                                  child: CircularProgressIndicator(
                                      value: (score / max).clamp(0, 1),
                                      strokeWidth: 6,
                                      color: gold,
                                      backgroundColor:
                                          const Color(0x15FFFFFF))),
                              Column(mainAxisSize: MainAxisSize.min, children: [
                                Text('$score', style: serif(44)),
                                gap(4),
                                Text('/ $max',
                                    style: const TextStyle(color: muted)),
                                gap(8),
                                Eyebrow(t.ashtakootaLabel)
                              ]),
                            ]))),
                    gap(24),
                    for (final row in jsonRows(match['koota_breakdown'])) ...[
                      InkWell(
                          onTap: () => goldSheet(context,
                              title: shown(row['koota']),
                              child: Text(shown(row['meaning']),
                                  style: const TextStyle(height: 1.6))),
                          child: Padding(
                              padding: const EdgeInsets.symmetric(vertical: 10),
                              child: Row(children: [
                                Expanded(
                                    child: Text(shown(row['koota']),
                                        style: const TextStyle(color: ink))),
                                Text(
                                    '${shown(row['scored'])} / ${shown(row['max_points'])}',
                                    style: const TextStyle(color: gold)),
                                const SizedBox(width: 8),
                                const Icon(Icons.info_outline,
                                    color: muted, size: 16)
                              ]))),
                      const Divider(height: 1),
                    ],
                    gap(16),
                    Eyebrow(t.limitationsLabel),
                    gap(8),
                    note(shown(match['method_limitations_note'])),
                  ])),
        ],
        gap(),
        note(t.sessionPrivacy),
      ],
    ]);
  }

  Widget ledgerPage() {
    final calibration = data['calibration'];
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      PageHeading(t.tabLedger, t.ledgerTitle, t.ledgerDescription),
      if (!accountReady)
        GoldPanel(child: note(api.authenticated ? t.consentError : t.authError))
      else ...[
        status('calibration'),
        if (calibration != null)
          GoldPanel(
              accent: true,
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Wrap(spacing: 28, runSpacing: 22, children: [
                      _fact(t.registeredLabel,
                          shown(calibration['total_pre_registered'])),
                      _fact(t.resolvedLabel,
                          shown(calibration['total_outcomes_logged'])),
                      _fact(
                          t.brierLabel,
                          calibration['brier_calibration_score'] == null
                              ? t.noScore
                              : shown(calibration['brier_calibration_score'])),
                    ]),
                    gap(18),
                    const Divider(),
                    Wrap(spacing: 18, runSpacing: 12, children: [
                      for (final pair in [
                        ('hit', t.hitLabel),
                        ('miss', t.missLabel),
                        ('ambiguous', t.ambiguousLabel)
                      ])
                        _fact(pair.$2,
                            shown(jsonMap(calibration['counts'])[pair.$1]))
                    ]),
                    gap(12),
                    note(t.ledgerDescription),
                    if (calibration['methodology_statement'] != null)
                      note(shown(calibration['methodology_statement'])),
                  ])),
        gap(),
        OutlinedButton.icon(
            onPressed:
                pending.contains('calibration') ? null : _loadCalibration,
            icon: const Icon(Icons.refresh, size: 18),
            label: Text(t.refreshLabel)),
      ],
      gap(22),
      Eyebrow(t.sessionEntries),
      gap(10),
      note(t.sessionEntriesNote),
      gap(16),
      if (answers.isEmpty) GoldPanel(child: note(t.noEntries)),
      for (final answer in answers) ...[
        StatementPanel(
            statement: jsonMap(answer['statement']),
            title: shown(answer['question'])),
        gap(8),
        GoldPanel(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Eyebrow(t.outcomeLabel),
          gap(10),
          if (jsonMap(answer['mark'])['observable_outcome_criteria'] != null)
            FactRow(t.criteriaLabel,
                shown(jsonMap(answer['mark'])['observable_outcome_criteria']))
          else
            note(t.criteriaUnavailable),
          gap(8),
          Wrap(spacing: 7, children: [
            for (final pair in [
              ('hit', t.hitLabel),
              ('miss', t.missLabel),
              ('ambiguous', t.ambiguousLabel)
            ])
              ChoiceChip(
                  label: Text(pair.$2),
                  selected: jsonMap(answer['mark'])['user_outcome'] == pair.$1,
                  onSelected:
                      pending.contains('mark:${answer['ledger_entry_id']}') ||
                              !accountReady
                          ? null
                          : (_) => mark(answer, pair.$1))
          ]),
          status('mark:${answer['ledger_entry_id']}'),
        ])),
        gap(20),
      ],
    ]);
  }

  Future<void> languageSheet() async {
    final selected = await goldSheet<String>(context,
        title: t.languageLabel,
        child: Column(children: [
          for (final pair in [
            ('en', t.englishLabel),
            ('hi', t.hindiLabel),
            ('mr', t.marathiLabel)
          ])
            ListTile(
                title: Text(pair.$2),
                trailing: widget.locale.languageCode == pair.$1
                    ? const Icon(Icons.check, color: gold)
                    : null,
                onTap: () => Navigator.pop(context, pair.$1)),
        ]));
    if (selected != null && mounted) {
      await widget.onLanguageChanged(Locale(selected));
    }
  }

  Future<void> privacySheet() => goldSheet<String>(context,
          title: t.privacyLabel,
          child: StatefulBuilder(
              builder: (sheetContext, update) => Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        note(t.sessionPrivacy),
                        gap(12),
                        SwitchListTile(
                            key: const Key('mute_notifications_toggle'),
                            contentPadding: EdgeInsets.zero,
                            title: Text(t.notificationsLabel),
                            subtitle: Text(t.notificationTime),
                            value: !widget.muted,
                            onChanged: notificationBusy
                                ? null
                                : (enabled) async {
                                    update(() => notificationBusy = true);
                                    try {
                                      await widget.onMutedChanged(!enabled, t);
                                      if (accountReady) {
                                        try {
                                          await api
                                              .syncNotificationMute(!enabled);
                                        } catch (_) {
                                          if (mounted) {
                                            toast(t.notificationSyncFailure);
                                          }
                                        }
                                      }
                                    } catch (_) {
                                      if (mounted) toast(t.notificationFailure);
                                    }
                                    notificationBusy = false;
                                    if (sheetContext.mounted) update(() {});
                                  }),
                        const Divider(),
                        if (_firebaseEnabled) ...[
                          if (_accountSignedIn && _accountLabel != null)
                            note(t.googleSignedInAs(_accountLabel!)),
                          if (!_phoneSignedIn)
                            ListTile(
                                key: const Key('phone_sign_in_profile'),
                                contentPadding: EdgeInsets.zero,
                                leading:
                                    const Icon(Icons.sms_outlined, color: gold),
                                title: Text(t.phoneSignIn),
                                subtitle: Text(t.phoneSignInHint),
                                onTap: () =>
                                    Navigator.pop(sheetContext, 'phone')),
                          if (!_googleSignedIn)
                            ListTile(
                                contentPadding: EdgeInsets.zero,
                                leading: const Icon(Icons.login, color: gold),
                                title: Text(t.googleSignIn),
                                subtitle: Text(t.googleSignInHint),
                                onTap: () {
                                  Navigator.pop(sheetContext);
                                  _handleGoogleSignIn();
                                }),
                          if (_accountSignedIn)
                            ListTile(
                                contentPadding: EdgeInsets.zero,
                                leading: const Icon(Icons.logout, color: gold),
                                title: Text(t.signOutLabel),
                                onTap: () {
                                  Navigator.pop(sheetContext);
                                  _handleSignOut();
                                }),
                          const Divider(),
                        ],
                        if (!api.authenticated) note(t.authError),
                        ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: const Icon(Icons.data_object, color: gold),
                            title: Text(t.exportLabel),
                            enabled: api.authenticated,
                            onTap: () {
                              Navigator.pop(sheetContext);
                              showRemote(
                                  t.exportLabel,
                                  () => api.get('/privacy/export',
                                      protected: true),
                                  (result) => SelectableText(
                                      const JsonEncoder.withIndent('  ')
                                          .convert(result)));
                            }),
                        ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading:
                                const Icon(Icons.delete_outline, color: gold),
                            title: Text(t.deleteLabel),
                            enabled: api.authenticated,
                            onTap: () {
                              Navigator.pop(sheetContext);
                              confirmErase();
                            }),
                        ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: const Icon(Icons.restart_alt, color: gold),
                            title: Text(t.clearSession),
                            onTap: () async {
                              Navigator.pop(sheetContext);
                              await LocalProfileStore.clearAll();
                              if (mounted) clearSession();
                            }),
                        ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading:
                                const Icon(Icons.info_outline, color: gold),
                            title: Text(t.aboutLabel),
                            onTap: () {
                              Navigator.pop(sheetContext);
                              showRemote(
                                  t.aboutLabel,
                                  () => api.get('/trust/about-predictions',
                                          query: {
                                            'lang': widget.locale.languageCode
                                          }),
                                  (result) => Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            for (final key in [
                                              'calculations_note',
                                              'interpretations_note',
                                              'ledger_methodology',
                                              'professional_advice_disclaimer'
                                            ])
                                              if (result[key] != null) ...[
                                                Text(shown(result[key]),
                                                    style: const TextStyle(
                                                        height: 1.6)),
                                                gap(14)
                                              ],
                                            if (result['grievance_officer']
                                                is Map)
                                              SelectableText(jsonMap(result[
                                                      'grievance_officer'])
                                                  .values
                                                  .map(shown)
                                                  .join(' · ')),
                                          ]));
                            }),
                        ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: const Icon(Icons.code, color: gold),
                            title: Text(t.sourceOfferLabel),
                            onTap: () {
                              Navigator.pop(sheetContext);
                              goldSheet(context,
                                  title: t.sourceOfferLabel,
                                  child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(t.sourceOfferNote,
                                            style:
                                                const TextStyle(height: 1.6)),
                                        gap(14),
                                        const SelectableText(kSourceOfferUrl),
                                        gap(14),
                                        const SelectableText(
                                            kSourceOfferLicense),
                                      ]));
                            }),
                        ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: const Icon(Icons.menu_book_outlined,
                                color: gold),
                            title: Text(t.glossaryLabel),
                            onTap: () {
                              Navigator.pop(sheetContext);
                              showRemote(
                                  t.glossaryLabel,
                                  () => api.get('/glossary', query: {
                                        'lang': widget.locale.languageCode
                                      }),
                                  (result) => Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            for (final value
                                                in result.values) ...[
                                              Text(shown(value),
                                                  style: const TextStyle(
                                                      height: 1.6)),
                                              const Divider(height: 28)
                                            ],
                                          ]));
                            }),
                      ]))).then((action) async {
        if (action == 'phone' && mounted) await phoneLoginSheet();
      });
  void showRemote(String title, Future<Json> Function() request,
      Widget Function(Json) content) {
    final response = request();
    goldSheet(context,
        title: title,
        child: FutureBuilder<Json>(
            future: response,
            builder: (context, snapshot) {
              if (snapshot.hasError) {
                return Text(friendlyError(t, snapshot.error!));
              }
              if (!snapshot.hasData) {
                return Padding(
                    padding: const EdgeInsets.all(30),
                    child: Column(children: [
                      const LinearProgressIndicator(),
                      gap(),
                      SlowLoadHint(
                          label: t.loadingLabel, slowLabel: t.loadingSlowLabel)
                    ]));
              }
              return content(snapshot.data!);
            }));
  }

  Future<void> confirmErase() async {
    final confirmed = await goldSheet<bool>(context,
        title: t.deleteTitle,
        child: Column(children: [
          Text(t.deleteBody, style: const TextStyle(height: 1.6)),
          gap(20),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: Text(t.deleteLabel)),
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: Text(t.cancelLabel)),
        ]));
    if (confirmed != true || !mounted) return;
    try {
      await api.delete('/privacy/delete');
      await LocalProfileStore.clearAll();
      if (!mounted) return;
      clearSession();
      toast(t.erasedLabel);
    } catch (error) {
      if (mounted) toast(friendlyError(t, error));
    }
  }

  Widget phoneGate() => Scaffold(
      resizeToAvoidBottomInset: true,
      body: Container(
          decoration: const BoxDecoration(
              gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFF0D1427), Color(0xFF080D1C), night],
                  stops: [0, .45, 1])),
          child: SafeArea(
              child: SingleChildScrollView(
                  keyboardDismissBehavior:
                      ScrollViewKeyboardDismissBehavior.onDrag,
                  padding: const EdgeInsets.fromLTRB(20, 12, 20, 36),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                Row(children: [
                  const Spacer(),
                  OutlinedButton(
                      key: const Key('language_selector'),
                      onPressed: languageSheet,
                      style: OutlinedButton.styleFrom(
                          minimumSize: const Size(44, 36),
                          padding: const EdgeInsets.symmetric(horizontal: 10),
                          shape: const StadiumBorder()),
                      child: Text(widget.locale.languageCode.toUpperCase(),
                          style: const TextStyle(
                              fontSize: 10, letterSpacing: 1.2))),
                ]),
                const SizedBox(height: 8),
                Text(t.appTitle, style: serif(27)),
                const SizedBox(height: 14),
                Text(t.phoneGateTitle, style: serif(28)),
                const SizedBox(height: 10),
                note(t.phoneGateBody),
                const SizedBox(height: 18),
                GoldPanel(
                    accent: true,
                    child: PhoneAuthPanel(
                        startOtp: widget.startOtp,
                        confirmOtp: widget.confirmOtp,
                        onSignedIn: _afterPhoneSignedIn)),
                gap(18),
                Row(children: [
                  const Expanded(child: Divider()),
                  Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      child: note(t.orDividerLabel)),
                  const Expanded(child: Divider()),
                ]),
                gap(16),
                SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                        key: const Key('google_sign_in_gate'),
                        onPressed: authBusy ? null : _handleGoogleSignIn,
                        icon: const Icon(Icons.login, size: 18),
                        label: Text(t.googleSignIn))),
              ])))));

  Widget sessionSplash() => const Scaffold(
      body: DecoratedBox(
          decoration: BoxDecoration(
              gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFF0D1427), Color(0xFF080D1C), night],
                  stops: [0, .45, 1])),
          child: Center(
              child: SizedBox(
                  width: 28,
                  height: 28,
                  child: CircularProgressIndicator(strokeWidth: 2)))));

  @override
  Widget build(BuildContext context) {
    if (_firebaseEnabled && !_authSettled) return sessionSplash();
    if (_firebaseEnabled && !_accountSignedIn) return phoneGate();
    final labels = [t.tabToday, t.tabChart, t.tabAsk, t.tabMatch, t.tabLedger];
    const icons = [
      Icons.wb_sunny_outlined,
      Icons.auto_awesome_mosaic_outlined,
      Icons.chat_bubble_outline,
      Icons.favorite_border,
      Icons.fact_check_outlined
    ];
    return Scaffold(
      body: Container(
          decoration: const BoxDecoration(
              gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFF0D1427), Color(0xFF080D1C), night],
                  stops: [0, .45, 1])),
          child: SafeArea(
              child: Column(children: [
            Padding(
                padding: const EdgeInsets.fromLTRB(20, 6, 14, 4),
                child: Row(children: [
                  Expanded(
                      child: Text(t.appTitle,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: serif(27))),
                  OutlinedButton(
                      key: const Key('language_selector'),
                      onPressed: languageSheet,
                      style: OutlinedButton.styleFrom(
                          minimumSize: const Size(44, 36),
                          padding: const EdgeInsets.symmetric(horizontal: 10),
                          shape: const StadiumBorder()),
                      child: Text(widget.locale.languageCode.toUpperCase(),
                          style: const TextStyle(
                              fontSize: 10, letterSpacing: 1.2))),
                  const SizedBox(width: 6),
                  if (_firebaseEnabled) ...[
                    IconButton(
                        key: const Key('account_button'),
                        tooltip: t.accountTitle,
                        visualDensity: VisualDensity.compact,
                        onPressed: accountSheet,
                        style: IconButton.styleFrom(
                            backgroundColor: gold.withValues(alpha: .10),
                            foregroundColor: gold),
                        icon: Icon(
                            _phoneSignedIn
                                ? Icons.verified_user_outlined
                                : Icons.sms_outlined,
                            size: 20)),
                    const SizedBox(width: 4),
                  ],
                  IconButton(
                      key: const Key('profile_button'),
                      tooltip: t.birthDetails,
                      visualDensity: VisualDensity.compact,
                      onPressed: editBirth,
                      style: IconButton.styleFrom(
                          backgroundColor: gold.withValues(alpha: .13),
                          foregroundColor: gold),
                      icon: const Icon(Icons.person_outline, size: 22)),
                  IconButton(
                      tooltip: t.privacyLabel,
                      visualDensity: VisualDensity.compact,
                      onPressed: privacySheet,
                      icon: const Icon(Icons.more_horiz, color: muted)),
                ])),
            if (api.localDevelopment)
              Padding(
                  padding: const EdgeInsets.only(top: 4, bottom: 6),
                  child: Text(t.localBeta,
                      style: const TextStyle(
                          color: gold, fontSize: 10, letterSpacing: .4))),
            Expanded(
              child: AnimatedSwitcher(
                  duration: MediaQuery.disableAnimationsOf(context)
                      ? Duration.zero
                      : const Duration(milliseconds: 240),
                  child: SingleChildScrollView(
                      key: ValueKey('tab:$tab'),
                      padding: const EdgeInsets.fromLTRB(20, 0, 20, 28),
                      child: Center(
                          child: ConstrainedBox(
                              constraints: const BoxConstraints(maxWidth: 620),
                              child: MotionEntry(
                                  key: ValueKey('entry:$tab'),
                                  child: switch (tab) {
                                    0 => today(),
                                    1 => chart(),
                                    2 => askPage(),
                                    3 => matchPage(),
                                    _ => ledgerPage()
                                  }))))),
            ),
          ]))),
      bottomNavigationBar: Container(
          decoration: const BoxDecoration(
              color: Color(0xFF080D18),
              border: Border(top: BorderSide(color: Color(0x16FFFFFF)))),
          child: SafeArea(
              top: false,
              child: SizedBox(
                  height: 72,
                  child: Row(
                      children: List.generate(
                          5,
                          (i) => Expanded(
                              child: Semantics(
                                  selected: tab == i,
                                  child: InkWell(
                                      key: Key('tab_$i'),
                                      onTap: () {
                                        FocusScope.of(context).unfocus();
                                        setState(() => tab = i);
                                        if (i == 4) _loadCalibration();
                                      },
                                      child: Column(
                                          mainAxisAlignment:
                                              MainAxisAlignment.center,
                                          children: [
                                            AnimatedContainer(
                                                duration: MediaQuery
                                                        .disableAnimationsOf(
                                                            context)
                                                    ? Duration.zero
                                                    : const Duration(
                                                        milliseconds: 220),
                                                padding:
                                                    const EdgeInsets.symmetric(
                                                        horizontal: 10,
                                                        vertical: 5),
                                                decoration: BoxDecoration(
                                                    color: tab == i
                                                        ? gold.withValues(
                                                            alpha: .09)
                                                        : Colors.transparent,
                                                    borderRadius:
                                                        BorderRadius.circular(
                                                            12)),
                                                child: Icon(icons[i],
                                                    color:
                                                        tab == i ? gold : muted,
                                                    size: 21)),
                                            const SizedBox(height: 3),
                                            Text(labels[i],
                                                style: TextStyle(
                                                    color:
                                                        tab == i ? gold : muted,
                                                    fontSize: 10)),
                                            const SizedBox(height: 5),
                                            Container(
                                                width: 16,
                                                height: 2,
                                                color: tab == i
                                                    ? gold
                                                    : Colors.transparent),
                                          ]))))))))),
    );
  }
}

String phoneAuthMessage(AppLocalizations t, String? code, {bool sending = false}) {
  switch (code) {
    case 'invalid_phone_number':
    case 'invalid-phone-number':
    case 'missing-phone-number':
      return t.phoneInvalidNumber;
    case 'invalid_otp':
    case 'invalid-verification-code':
    case 'invalid-verification-id':
    case 'missing-verification-code':
    case 'missing-verification-id':
    case 'session-expired':
      return t.phoneInvalidCode;
    case 'otp_timeout':
    case 'too-many-requests':
    case 'quota-exceeded':
      return t.phoneTryLater;
    case 'network-request-failed':
      return t.networkError;
    case 'billing-not-enabled':
    case 'operation-not-allowed':
    case 'app-not-authorized':
    case 'missing-client-identifier':
    case 'missing-app-credential':
    case 'invalid-app-credential':
    case 'captcha-check-failed':
      return t.phoneSmsNotSent;
    default:
      return sending ? t.phoneSmsNotSent : t.phoneSignInFailed;
  }
}

class PhoneAuthPanel extends StatefulWidget {
  const PhoneAuthPanel({
    super.key,
    required this.onSignedIn,
    this.startOtp,
    this.confirmOtp,
  });
  final Future<void> Function() onSignedIn;
  final Future<PhoneAuthResult> Function(String rawPhone,
      {int? forceResendingToken})? startOtp;
  final Future<PhoneAuthResult> Function(
      {required String verificationId, required String smsCode})? confirmOtp;

  @override
  State<PhoneAuthPanel> createState() => _PhoneAuthPanelState();
}

class _PhoneAuthPanelState extends State<PhoneAuthPanel> {
  final phoneController = TextEditingController();
  final otpController = TextEditingController();
  String verificationId = '';
  int? resendToken;
  String? errorText;
  bool busy = false;

  @override
  void dispose() {
    phoneController.dispose();
    otpController.dispose();
    super.dispose();
  }

  Future<void> sendCode({bool resend = false}) async {
    FocusScope.of(context).unfocus();
    setState(() {
      busy = true;
      errorText = null;
    });
    final start = widget.startOtp ?? startPhoneOtp;
    final result = await start(
      phoneController.text,
      forceResendingToken: resend ? resendToken : null,
    );
    if (!mounted) return;
    if (result.signedIn) {
      await widget.onSignedIn();
      if (mounted) setState(() => busy = false);
      return;
    }
    setState(() {
      busy = false;
      verificationId = result.verificationId ?? '';
      resendToken = result.resendToken ?? resendToken;
      errorText = result.verificationId == null
          ? phoneAuthMessage(AppLocalizations.of(context)!, result.errorMessage,
              sending: true)
          : null;
    });
  }

  Future<void> verifyCode() async {
    FocusScope.of(context).unfocus();
    setState(() {
      busy = true;
      errorText = null;
    });
    final confirm = widget.confirmOtp ?? confirmPhoneOtp;
    final result = await confirm(
        verificationId: verificationId, smsCode: otpController.text);
    if (!mounted) return;
    if (!result.signedIn) {
      setState(() {
        busy = false;
        errorText = phoneAuthMessage(
            AppLocalizations.of(context)!, result.errorMessage);
      });
      return;
    }
    await widget.onSignedIn();
    if (mounted) setState(() => busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(t.phoneSignInHint,
          style: const TextStyle(color: muted, fontSize: 12, height: 1.6)),
      const SizedBox(height: 14),
      TextField(
          key: const Key('phone_number'),
          controller: phoneController,
          keyboardType: TextInputType.phone,
          autofillHints: const [AutofillHints.telephoneNumber],
          textInputAction: TextInputAction.done,
          onChanged: (_) {
            if (verificationId.isNotEmpty || errorText != null) {
              setState(() {
                verificationId = '';
                resendToken = null;
                otpController.clear();
                errorText = null;
              });
            }
          },
          onSubmitted: (_) {
            if (verificationId.isEmpty && !busy) sendCode();
          },
          decoration: InputDecoration(
              labelText: t.phoneNumberLabel, hintText: t.phoneNumberHint)),
      if (verificationId.isNotEmpty) ...[
        const SizedBox(height: 12),
        TextField(
            key: const Key('otp_code'),
            controller: otpController,
            keyboardType: TextInputType.number,
            autofillHints: const [AutofillHints.oneTimeCode],
            textInputAction: TextInputAction.done,
            onSubmitted: (_) {
              if (!busy) verifyCode();
            },
            decoration:
                InputDecoration(labelText: t.otpLabel, hintText: t.otpHint)),
      ],
      if (errorText != null) ...[
        const SizedBox(height: 12),
        Text(errorText!,
            style: const TextStyle(color: Color(0xFFE6A2A7), height: 1.5)),
      ],
      const SizedBox(height: 16),
      SizedBox(
          width: double.infinity,
          child: FilledButton(
              key: const Key('phone_otp_action'),
              onPressed: busy
                  ? null
                  : (verificationId.isEmpty ? sendCode : verifyCode),
              child: Text(verificationId.isEmpty
                  ? t.sendOtpAction
                  : t.verifyOtpAction))),
      if (verificationId.isNotEmpty) ...[
        const SizedBox(height: 8),
        Align(
            alignment: Alignment.centerRight,
            child: TextButton(
                key: const Key('phone_resend_otp'),
                onPressed: busy ? null : () => sendCode(resend: true),
                child: Text(t.resendOtpAction))),
      ],
    ]);
  }
}
