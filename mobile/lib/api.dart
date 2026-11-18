import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

typedef Json = Map<String, dynamic>;

class ApiFailure implements Exception {
  const ApiFailure(this.code, [this.status]);
  final String code;
  final int? status;

  @override
  String toString() => code;
}

class AstroplanApiClient {
  AstroplanApiClient({
    String? baseUrl,
    http.Client? client,
    String? userId,
    Future<String?> Function()? tokenProvider,
  })  : baseUrl = baseUrl ?? _defaultBaseUrl,
        _client = client ?? http.Client(),
        _userId = userId ?? _configuredUser,
        _tokenProvider = tokenProvider;

  static const _configuredBase = String.fromEnvironment('ASTRO_API_BASE_URL');
  static const _configuredUser = String.fromEnvironment('ASTRO_DEV_USER');
  static String get _defaultBaseUrl {
    if (_configuredBase.isNotEmpty) return _configuredBase;
    if (!kDebugMode) return '';
    return defaultTargetPlatform == TargetPlatform.android && !kIsWeb
        ? 'http://10.0.2.2:8000/v1'
        : 'http://localhost:8000/v1';
  }

  final String baseUrl;
  final http.Client _client;
  final String _userId;
  final Future<String?> Function()? _tokenProvider;

  bool get _loopback => const {'localhost', '127.0.0.1', '10.0.2.2', '::1'}
      .contains(Uri.tryParse(baseUrl)?.host);
  bool get localDevelopment =>
      kDebugMode && _loopback && _tokenProvider == null;
  bool get authenticated =>
      _tokenProvider != null || (localDevelopment && _userId.isNotEmpty);
  String? get userId => authenticated && _userId.isNotEmpty ? _userId : null;

  Uri _uri(String path, Map<String, String> query) {
    final base = Uri.tryParse(baseUrl);
    if (base == null ||
        !base.hasAuthority ||
        !const ['http', 'https'].contains(base.scheme)) {
      throw const ApiFailure('server_not_configured');
    }
    if (base.scheme != 'https' && !(kDebugMode && _loopback)) {
      throw const ApiFailure('secure_connection_required');
    }
    return Uri.parse('${baseUrl.replaceFirst(RegExp(r'/$'), '')}$path')
        .replace(queryParameters: query.isEmpty ? null : query);
  }

  Future<Map<String, String>> _headers(bool protected) async {
    final headers = <String, String>{'Content-Type': 'application/json'};
    if (!protected) return headers;
    if (!authenticated) throw const ApiFailure('auth_required');
    if (_tokenProvider != null) {
      final token = await _tokenProvider();
      if (token == null || token.isEmpty) {
        throw const ApiFailure('auth_required');
      }
      headers['Authorization'] = 'Bearer $token';
    } else {
      headers['X-User-Id'] = _userId;
    }
    return headers;
  }

  Json _decode(http.Response response) {
    dynamic decoded;
    try {
      decoded = jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw ApiFailure('invalid_response', response.statusCode);
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = decoded is Map ? decoded['detail'] : null;
      final code = detail is Map && detail['error'] is String
          ? detail['error'] as String
          : response.statusCode == 401
              ? 'auth_required'
              : 'request_failed';
      throw ApiFailure(code, response.statusCode);
    }
    if (decoded is! Json) throw const ApiFailure('invalid_response');
    return decoded;
  }

  Future<Json> _send(String method, String path, Json? body,
      Map<String, String> query, bool protected) async {
    final uri = _uri(path, query);
    final headers = await _headers(protected);
    try {
      final request = http.Request(method, uri)
        ..followRedirects = false
        ..headers.addAll(headers);
      if (body != null) request.body = jsonEncode(body);
      final response = await _client
          .send(request)
          .then(http.Response.fromStream)
          .timeout(const Duration(seconds: 25));
      return _decode(response);
    } on http.ClientException {
      throw const ApiFailure('network_unavailable');
    } on TimeoutException {
      throw const ApiFailure('network_unavailable');
    }
  }

  Future<Json> get(String path,
          {Map<String, String> query = const {}, bool protected = false}) =>
      _send('GET', path, null, query, protected);
  Future<Json> post(String path, Json body,
          {Map<String, String> query = const {}, bool protected = false}) =>
      _send('POST', path, body, query, protected);
  Future<void> delete(String path, {bool protected = true}) async {
    await _send('DELETE', path, null, const {}, protected);
    if (path != '/privacy/delete') return;
    final prefs = await SharedPreferences.getInstance();
    for (final key in prefs.getKeys().toList()) {
      if (key.startsWith('panchang_v2_')) await prefs.remove(key);
    }
  }

  Future<Json> fetchAndCacheDailyPanchang(
    String targetDate, {
    String placeName = 'Pune',
    double? latitude,
    double? longitude,
  }) async {
    final query = <String, String>{
      'target_date': targetDate,
      'place_name': placeName,
      if (latitude != null) 'lat': '$latitude',
      if (longitude != null) 'lon': '$longitude',
    };
    final key = 'panchang_v2_${_uri('/panchang', query)}';
    final prefs = await SharedPreferences.getInstance();
    try {
      final data = await get('/panchang', query: query);
      final savedAt = DateTime.now().toUtc().toIso8601String();
      await prefs.setString(
          key, jsonEncode({'data': data, 'saved_at': savedAt}));
      return {...data, '_offline': false, '_cached_at': savedAt};
    } on ApiFailure catch (error) {
      if (error.code != 'network_unavailable') rethrow;
      final raw = prefs.getString(key);
      if (raw == null) rethrow;
      try {
        final envelope = jsonDecode(raw) as Json;
        final saved = DateTime.parse(envelope['saved_at'] as String);
        final data = envelope['data'] as Json;
        final ttl = ((data['cache_ttl_seconds'] as num?)?.toInt() ?? 86400)
            .clamp(0, 86400);
        final age = DateTime.now().toUtc().difference(saved);
        if (age.isNegative || age.inSeconds >= ttl) rethrow;
        return {...data, '_offline': true, '_cached_at': envelope['saved_at']};
      } on FormatException {
        throw error;
      } on TypeError {
        throw error;
      }
    }
  }

  Future<void> syncNotificationMute(bool muted, {String? userId}) async {
    await post(
        '/user/notifications/preferences', {'notifications_muted': muted},
        protected: true);
  }

  static bool safeStatement(Json statement) {
    final why = statement['why_this'];
    return statement['safety_verified'] == true &&
        ['simple_text', 'pro_text'].every((key) =>
            statement[key] is String &&
            (statement[key] as String).trim().isNotEmpty) &&
        why is Map &&
        const {'likely', 'supported', 'weak', 'contested'}
            .contains(why['strength_grade']) &&
        ['rule_id', 'placement_evidence', 'classical_source', 'strength_grade']
            .every((key) =>
                why[key] is String && (why[key] as String).trim().isNotEmpty);
  }

  void close() => _client.close();
}
