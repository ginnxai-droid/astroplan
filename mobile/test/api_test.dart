import 'dart:async';
import 'dart:convert';

import 'package:astroplan/api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('offline without cached panchang never invents astronomical data',
      () async {
    final api = AstroplanApiClient(
        client: MockClient((_) async => throw http.ClientException('offline')));
    await expectLater(
        api.fetchAndCacheDailyPanchang('2026-11-17'), throwsException);
  });

  test('an actual offline cache is explicitly labeled', () async {
    var offline = false;
    final api = AstroplanApiClient(client: MockClient((_) async {
      if (offline) throw http.ClientException('offline');
      return http.Response(
          jsonEncode({
            'date': '2026-11-17',
            'tithi': 'Fixture tithi',
            'cache_ttl_seconds': 86400
          }),
          200);
    }));
    final online = await api.fetchAndCacheDailyPanchang('2026-11-17');
    expect(online['_offline'], false);
    offline = true;
    final cached = await api.fetchAndCacheDailyPanchang('2026-11-17');
    expect(cached['tithi'], 'Fixture tithi');
    expect(cached['_offline'], true);
    expect(cached['_cached_at'], isA<String>());
  });

  test('HTTP errors must not silently serve old success data', () async {
    var status = 200;
    final api = AstroplanApiClient(
        client: MockClient((_) async => http.Response(
            status == 200
                ? '{"date":"2026-11-17","tithi":"Original"}'
                : '{"detail":{"error":"invalid_place"}}',
            status)));
    await api.fetchAndCacheDailyPanchang('2026-11-17');
    status = 422;
    await expectLater(
        api.fetchAndCacheDailyPanchang('2026-11-17'), throwsException);
  });

  test('unauthenticated protected calls never reach the network', () async {
    var sent = false;
    final api = AstroplanApiClient(client: MockClient((_) async {
      sent = true;
      return http.Response('{}', 200);
    }));
    await expectLater(
        api.post('/readings/ask', {}, protected: true),
        throwsA(
            isA<ApiFailure>().having((e) => e.code, 'code', 'auth_required')));
    expect(sent, false);
  });

  test('development identity cannot be sent to a remote backend', () async {
    final api = AstroplanApiClient(
        baseUrl: 'https://example.test/v1',
        userId: 'local-user',
        client: MockClient((_) async => http.Response('{}', 200)));
    expect(api.localDevelopment, false);
    await expectLater(api.post('/readings/ask', {}, protected: true),
        throwsA(isA<ApiFailure>()));
  });

  test('Ask keeps canonical request and surfaces quota without retry',
      () async {
    final requests = <http.Request>[];
    final api = AstroplanApiClient(
        baseUrl: 'https://example.test/v1',
        userId: 'test-user',
        tokenProvider: () async => 'test-id-token',
        client: MockClient((request) async {
          requests.add(request);
          return http.Response(
              '{"detail":{"error":"ask_quota_exhausted"}}', 429);
        }));
    await expectLater(
        api.post(
            '/readings/ask',
            {
              'question': 'career',
              'details': {'language': 'mr'}
            },
            protected: true),
        throwsA(isA<ApiFailure>()
            .having((e) => e.code, 'code', 'ask_quota_exhausted')));
    expect(requests.length, 1);
    expect(requests.single.headers['Authorization'], 'Bearer test-id-token');
    expect(requests.single.headers.containsKey('X-User-Id'), false);
    expect(jsonDecode(requests.single.body), {
      'question': 'career',
      'details': {'language': 'mr'}
    });
  });

  test('unsafe and incomplete statements cannot enter the reading UI', () {
    final statement = <String, dynamic>{
      'safety_verified': true,
      'simple_text': 'Canonical',
      'pro_text': 'Detailed',
      'why_this': {
        'rule_id': 'RULE',
        'placement_evidence': 'Moon 12',
        'classical_source': 'Source',
        'strength_grade': 'supported'
      }
    };
    expect(AstroplanApiClient.safeStatement(statement), true);
    expect(
        AstroplanApiClient.safeStatement(
            {...statement, 'safety_verified': false}),
        false);
    expect(AstroplanApiClient.safeStatement({...statement, 'why_this': {}}),
        false);
  });

  test('unrecognized evidence grade cannot be rendered as approved', () {
    expect(
        AstroplanApiClient.safeStatement({
          'safety_verified': true,
          'simple_text': 'Text',
          'pro_text': 'Text',
          'why_this': {
            'rule_id': 'R1',
            'placement_evidence': 'Moon',
            'classical_source': 'Source',
            'strength_grade': 'guaranteed'
          },
        }),
        false);
  });

  test('cache is scoped to selected coordinates', () async {
    var offline = false;
    final api = AstroplanApiClient(client: MockClient((_) async {
      if (offline) throw http.ClientException('offline');
      return http.Response('{"tithi":"Original"}', 200);
    }));
    await api.fetchAndCacheDailyPanchang('2026-11-17',
        latitude: 18.52, longitude: 73.85);
    offline = true;
    await expectLater(
        api.fetchAndCacheDailyPanchang('2026-11-17',
            latitude: 28.61, longitude: 77.2),
        throwsException);
  });

  testWidgets('a stalled connection times out without retrying Ask',
      (tester) async {
    final pending = Completer<http.Response>();
    var calls = 0;
    final api = AstroplanApiClient(
        userId: 'qa-user',
        client: MockClient((_) {
          calls++;
          return pending.future;
        }));
    Object? error;
    unawaited(
        api.post('/readings/ask', {}, protected: true).catchError((Object e) {
      error = e;
      return <String, dynamic>{};
    }));
    await tester.pump();
    await tester.pump(const Duration(seconds: 26));
    expect(error,
        isA<ApiFailure>().having((e) => e.code, 'code', 'network_unavailable'));
    expect(calls, 1);
    pending.complete(http.Response('{}', 200));
    await tester.pump();
  });

  test('expired cache is not presented as today data', () async {
    var offline = false;
    final api = AstroplanApiClient(client: MockClient((_) async {
      if (offline) throw http.ClientException('offline');
      return http.Response('{"tithi":"Original"}', 200);
    }));
    await api.fetchAndCacheDailyPanchang('2026-11-17');
    final prefs = await SharedPreferences.getInstance();
    final key = prefs.getKeys().single;
    final cached = jsonDecode(prefs.getString(key)!) as Map<String, dynamic>;
    cached['saved_at'] = '2000-01-01T00:00:00Z';
    await prefs.setString(key, jsonEncode(cached));
    offline = true;
    await expectLater(api.fetchAndCacheDailyPanchang('2026-11-17'),
        throwsA(isA<ApiFailure>()));
  });

  test('malformed successful response is not a reading', () async {
    final api = AstroplanApiClient(
        client: MockClient((_) async => http.Response('not-json', 200)));
    await expectLater(
        api.get('/chart'),
        throwsA(isA<ApiFailure>()
            .having((e) => e.code, 'code', 'invalid_response')));
  });

  test('notification errors are reported instead of pretending to queue',
      () async {
    final api = AstroplanApiClient(
        userId: 'qa-user',
        client: MockClient((_) async =>
            http.Response('{"detail":{"error":"user_not_found"}}', 404)));
    await expectLater(
        api.syncNotificationMute(true),
        throwsA(
            isA<ApiFailure>().having((e) => e.code, 'code', 'user_not_found')));
  });

  test('confirmed account deletion also removes local panchang caches',
      () async {
    final api = AstroplanApiClient(
        userId: 'qa-user',
        client: MockClient((request) async => http.Response(
            request.method == 'DELETE'
                ? '{"status":"erased"}'
                : '{"tithi":"Original"}',
            200)));
    await api.fetchAndCacheDailyPanchang('2026-11-17',
        latitude: 18.52, longitude: 73.85);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('preferred_lang', 'mr');
    expect(prefs.getKeys().where((key) => key.startsWith('panchang_v2_')),
        isNotEmpty);
    await api.delete('/privacy/delete');
    expect(prefs.getKeys().where((key) => key.startsWith('panchang_v2_')),
        isEmpty);
    expect(prefs.getString('preferred_lang'), 'mr');
  });

  test('failed account deletion reports the error and keeps local state',
      () async {
    final api = AstroplanApiClient(
        userId: 'qa-user',
        client: MockClient((request) async => request.method == 'DELETE'
            ? http.Response('{"detail":{"error":"erase_failed"}}', 500)
            : http.Response('{"tithi":"Original"}', 200)));
    await api.fetchAndCacheDailyPanchang('2026-11-17');
    await expectLater(
        api.delete('/privacy/delete'),
        throwsA(
            isA<ApiFailure>().having((e) => e.code, 'code', 'erase_failed')));
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getKeys().where((key) => key.startsWith('panchang_v2_')),
        isNotEmpty);
  });

  test('cache cannot cross backend instances', () async {
    final original = AstroplanApiClient(
        baseUrl: 'http://localhost:8000/v1',
        client: MockClient(
            (_) async => http.Response('{"tithi":"Original"}', 200)));
    await original.fetchAndCacheDailyPanchang('2026-11-17');
    final other = AstroplanApiClient(
        baseUrl: 'http://localhost:8001/v1',
        client: MockClient((_) async => throw http.ClientException('offline')));
    await expectLater(
        other.fetchAndCacheDailyPanchang('2026-11-17'), throwsException);
  });
}
