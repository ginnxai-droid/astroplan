import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';

class SavedProfileBundle {
  const SavedProfileBundle({
    required this.self,
    this.partner,
    required this.adult,
    required this.parental,
    required this.consentRecorded,
    this.syncedToServer = false,
    this.accountId,
    this.updatedAt,
  });

  final Json self;
  final Json? partner;
  final bool adult;
  final bool parental;
  final bool consentRecorded;
  final bool syncedToServer;
  final String? accountId;
  final String? updatedAt;

  Json toJson() => {
        'self': self,
        if (partner != null) 'partner': partner,
        'adult': adult,
        'parental': parental,
        'consent_recorded': consentRecorded,
        'synced_to_server': syncedToServer,
        if (accountId != null && accountId!.isNotEmpty) 'account_id': accountId,
        'updated_at': updatedAt ?? DateTime.now().toUtc().toIso8601String(),
      };

  static SavedProfileBundle? fromJson(dynamic raw) {
    if (raw is! Map) return null;
    final map = Map<String, dynamic>.from(raw);
    final rawSelf = map['self'];
    if (rawSelf is! Map) return null;
    final selfMap = Map<String, dynamic>.from(rawSelf);
    if ((selfMap['name']?.toString().trim() ?? '').isEmpty ||
        (selfMap['birth_date']?.toString().trim() ?? '').isEmpty ||
        (selfMap['birth_time']?.toString().trim() ?? '').isEmpty) {
      return null;
    }
    final rawPartner = map['partner'];
    final partnerMap =
        rawPartner is Map ? Map<String, dynamic>.from(rawPartner) : null;
    return SavedProfileBundle(
      self: selfMap,
      partner: partnerMap,
      adult: map['adult'] != false,
      parental: map['parental'] == true,
      consentRecorded: map['consent_recorded'] == true,
      syncedToServer: map['synced_to_server'] == true,
      accountId: map['account_id']?.toString(),
      updatedAt: map['updated_at']?.toString(),
    );
  }
}

class LocalProfileStore {
  static const String keyPrefix = 'astroplan_profile_v1_';
  static const String defaultKey = '${keyPrefix}default';

  static String _keyFor(String accountId) => '$keyPrefix$accountId';

  static SavedProfileBundle? _decode(String? raw) {
    if (raw == null || raw.isEmpty) return null;
    try {
      return SavedProfileBundle.fromJson(jsonDecode(raw));
    } catch (_) {
      return null;
    }
  }

  static Future<void> save(SavedProfileBundle bundle) async {
    final prefs = await SharedPreferences.getInstance();
    final encoded = jsonEncode(bundle.toJson());
    final uid = bundle.accountId?.trim();
    if (uid != null && uid.isNotEmpty) {
      await prefs.setString(_keyFor(uid), encoded);
    }
    await prefs.setString(defaultKey, encoded);
  }

  static Future<SavedProfileBundle?> load({String? accountId}) async {
    final prefs = await SharedPreferences.getInstance();
    final uid = accountId?.trim();
    if (uid != null && uid.isNotEmpty) {
      final scoped = _decode(prefs.getString(_keyFor(uid)));
      if (scoped != null) return scoped;
      final fallback = _decode(prefs.getString(defaultKey));
      if (fallback != null) {
        final owner = fallback.accountId?.trim();
        if (owner == null || owner.isEmpty || owner == uid) {
          return fallback;
        }
      }
      return null;
    }
    return _decode(prefs.getString(defaultKey));
  }

  static Future<void> clearAll() async {
    final prefs = await SharedPreferences.getInstance();
    for (final key in prefs.getKeys().toList()) {
      if (key.startsWith(keyPrefix)) {
        await prefs.remove(key);
      }
    }
  }
}
