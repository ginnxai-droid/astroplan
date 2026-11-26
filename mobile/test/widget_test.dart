import 'dart:async';
import 'dart:convert';
import 'package:astroplan/celestial_widgets.dart';
import 'package:astroplan/l10n/app_localizations.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:astroplan/main.dart';

class RecordingNotifier implements DailyInsightNotifier {
  final List<String> calls = [];
  @override
  Future<void> scheduleDailyLocalInsight(
      {required int hour,
      required int minute,
      required String title,
      required String body}) async {
    calls.add('schedule $hour:$minute');
  }

  @override
  Future<void> cancelDailyInsight() async {
    calls.add('cancel');
  }
}

Json verifiedStatement(String text) => {
      'statement_id': 'test-statement',
      'category': 'career',
      'simple_text': text,
      'pro_text': 'Technical: $text',
      'safety_verified': true,
      'time_window': 'Test quarter',
      'why_this': {
        'rule_id': 'TEST_CAREER_01',
        'placement_evidence': 'Saturn in house 10',
        'classical_source': 'Test source, chapter 4',
        'strength_grade': 'supported',
        'tradition': 'Parashari',
        'method_note': 'Lahiri, whole-sign houses',
      },
    };

Json chartFixture() => {
      'resolved_latitude': 18.5204,
      'resolved_longitude': 73.8567,
      'resolved_timezone': 'Asia/Kolkata',
      'utc_datetime': '1990-01-02T02:45:00Z',
      'lagna_sign_index': 4,
      'lagna_sign_name': 'Cancer',
      'lagna_degree': 10.2,
      'navamsa_lagna_sign_index': 7,
      'navamsa_lagna_sign_name': 'Libra',
      'moon_sign_index': 2,
      'moon_sign_name': 'Taurus',
      'moon_nakshatra': 'Rohini',
      'planets': [
        {
          'planet': 'Moon',
          'longitude': 42.0,
          'sign_index': 2,
          'sign_name': 'Taurus',
          'degree_in_sign': 12.0,
          'house': 11,
          'nakshatra_name': 'Rohini',
          'pada': 1,
          'navamsa_sign_index': 3,
          'navamsa_sign_name': 'Gemini',
          'is_retrograde': false
        },
        {
          'planet': 'Saturn',
          'longitude': 281.0,
          'sign_index': 10,
          'sign_name': 'Capricorn',
          'degree_in_sign': 11.0,
          'house': 7,
          'nakshatra_name': 'Shravana',
          'pada': 1,
          'navamsa_sign_index': 1,
          'navamsa_sign_name': 'Aries',
          'is_retrograde': true
        },
      ],
    };

http.Response reply(Json value, [int status = 200]) =>
    http.Response(jsonEncode(value), status,
        headers: {'content-type': 'application/json; charset=utf-8'});

class ApiHarness {
  final requests = <http.Request>[];
  FutureOr<http.Response?> Function(http.Request)? override;
  late final api = AstroplanApiClient(
      baseUrl: 'http://localhost:8000/v1',
      userId: 'test-user',
      wakeGap: Duration.zero,
      client: MockClient((request) async {
        requests.add(request);
        final custom = await override?.call(request);
        if (custom != null) return custom;
        return switch (request.url.path) {
          '/v1/chart' => reply(chartFixture()),
          '/v1/dasha' => reply({
              'active_mahadasha': 'Saturn',
              'active_antardasha': 'Mercury',
              'timeline': []
            }),
          '/v1/readings/daily-insight' =>
            reply(verifiedStatement('A verified daily reflection.')),
          '/v1/readings/life-areas' => reply({
              'life_areas': {
                'career': [verifiedStatement('A verified career reflection.')]
              }
            }),
          '/v1/panchang' => reply({
              'date': request.url.queryParameters['target_date'],
              'moon_longitude': 123.5,
              'sun_longitude': 205.0,
              'moon_sign_name': 'Leo',
              'moon_degree_in_sign': 3.5,
              'moon_nakshatra_pada': 2,
              'nakshatra': 'Magha',
              'vara': 'Monday',
              'reference_kind': 'sunrise',
              'reference_datetime': '2026-11-16T06:40:00+05:30',
              'phase_illumination': .6,
              'sunrise_local': '06:40',
              'sunset_local': '18:00',
              'rahu_kaal': '08:00 - 09:30',
              'abhijit_muhurat': '12:00 - 12:40',
              'tithi': 'Shukla Saptami',
              'location': {'timezone': 'Asia/Kolkata'},
            }),
          '/v1/privacy/consent' => reply({'consent_recorded': true}),
          '/v1/readings/ask' => reply({
              'coverage': {'status': 'answered', 'area': 'career'},
              'statement': verifiedStatement('A verified answer.'),
              'ledger_entry_id': 'entry-42'
            }),
          '/v1/ledger/calibration' => reply({
              'total_pre_registered': 17,
              'total_outcomes_logged': 9,
              'counts': {'hit': 4, 'miss': 3, 'ambiguous': 2},
              'brier_calibration_score': .3125,
              'methodology_statement': 'Server calibration method.'
            }),
          '/v1/ledger/entry-42/mark' => reply({
              'user_outcome': jsonDecode(request.body)['outcome'],
              'observable_outcome_criteria': 'Actual server criterion.'
            }),
          '/v1/matching/ashtakoota' => reply({
              'total_score': 23.5,
              'max_score': 36,
              'koota_breakdown': [
                {
                  'koota': 'Tara',
                  'scored': 2,
                  'max_points': 3,
                  'meaning': 'Server meaning.'
                }
              ],
              'method_limitations_note': 'Server limitations.'
            }),
          '/v1/reports/annual-forecast' => reply({
              'year': int.parse(request.url.queryParameters['forecast_year']!),
              'overview': verifiedStatement('A verified annual overview.'),
              'quarters': [
                {
                  'quarter': 'Q1',
                  'theme_statement':
                      verifiedStatement('A coarse quarter theme.'),
                  'active_dasha': 'Saturn'
                }
              ]
            }),
          '/v1/privacy/export' =>
            reply({'user_id': 'test-user', 'ledger_entries': []}),
          '/v1/privacy/delete' => reply({'deleted': true}),
          '/v1/health' => reply({'status': 'ok', 'version': '3.6.0'}),
          _ => reply({}),
        };
      }));
  List<http.Request> at(String path) =>
      requests.where((r) => r.url.path == '/v1$path').toList();
}

Future<void> tapVisible(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

Future<void> fillBirth(WidgetTester tester,
    {String name = 'Test Person', String country = 'India',
    bool partner = false}) async {
  for (final entry in {
    'name': name,
    'birth_date': '1990-01-02',
    'birth_time': '08:15',
    'place_name': 'Pune',
    'country': country,
    'latitude': '18.5204',
    'longitude': '73.8567',
    'timezone_override': 'Asia/Kolkata',
    'uncertainty_minutes': '10',
  }.entries) {
    await tester.ensureVisible(find.byKey(Key(entry.key)));
    await tester.enterText(find.byKey(Key(entry.key)), entry.value);
  }
  tester.testTextInput.hide();
  final genderFinder = find.byKey(const Key('gender'));
  if (!partner && genderFinder.evaluate().isNotEmpty) {
    final genderField =
        tester.widget<DropdownButtonFormField<String>>(genderFinder);
    if (genderField.initialValue == null) {
      final scrollable = find.byType(Scrollable).last;
      Future<void> pick(Key key, String label) async {
        await tester.scrollUntilVisible(find.byKey(key), 120,
            scrollable: scrollable);
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(key));
        await tester.pumpAndSettle();
        await tester.tap(find.text(label).last);
        await tester.pumpAndSettle();
      }

      await pick(const Key('gender'), 'Male');
      await pick(const Key('marital_status'), 'Single');
      await pick(const Key('occupation'), 'Employee');
    }
  }
  final scrollable = find.byType(Scrollable).last;
  await tester.scrollUntilVisible(find.byKey(const Key('dpdp_consent')), 120,
      scrollable: scrollable);
  await tester.pumpAndSettle();
  await tapVisible(tester, find.byKey(const Key('dpdp_consent')));
  await tapVisible(tester, find.byKey(const Key('adult_consent')));
  if (partner) {
    await tapVisible(tester, find.byKey(const Key('partner_consent')));
  }
}

Future<void> startProfile(WidgetTester tester, ApiHarness harness) async {
  await tester.pumpWidget(
      AstroplanApp(api: harness.api, notifier: RecordingNotifier()));
  await tester.pumpAndSettle();
  await tapVisible(tester, find.byKey(const Key('profile_button')));
  await fillBirth(tester);
  await tapVisible(tester, find.byKey(const Key('calculate_chart')));
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  testWidgets('five native tabs start with honest empty onboarding',
      (tester) async {
    final notifier = RecordingNotifier();
    await tester.pumpWidget(AstroplanApp(notifier: notifier));
    await tester.pumpAndSettle();
    for (final tab in ['Today', 'Chart', 'Ask', 'Match', 'Ledger']) {
      expect(find.text(tab), findsOneWidget);
    }
    expect(find.text('Begin with your birth details'), findsOneWidget);
    expect(find.textContaining('Steady professional progress'), findsNothing);
    expect(notifier.calls, isEmpty);
  });
  testWidgets(
      'birth sheet never invents a date or time and consent is unchecked',
      (tester) async {
    await tester.pumpWidget(AstroplanApp(notifier: RecordingNotifier()));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('profile_button')));
    await tester.pumpAndSettle();
    final date =
        tester.widget<TextFormField>(find.byKey(const Key('birth_date')));
    final time =
        tester.widget<TextFormField>(find.byKey(const Key('birth_time')));
    expect(date.controller!.text, isEmpty);
    expect(time.controller!.text, isEmpty);
    for (final key in ['dpdp_consent', 'adult_consent', 'parental_consent']) {
      expect(
          tester.widget<CheckboxListTile>(find.byKey(Key(key))).value, false);
    }
    expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('calculate_chart')))
            .onPressed,
        isNull);
  });

  testWidgets(
      'consented profile sends real details and resolved Panchang coordinates',
      (tester) async {
    final h = ApiHarness();
    await startProfile(tester, h);
    for (final path in [
      '/chart',
      '/dasha',
      '/readings/daily-insight',
      '/readings/life-areas'
    ]) {
      expect(h.at(path), hasLength(1));
      final body = jsonDecode(h.at(path).single.body);
      expect(body['birth_time'], '08:15');
      expect(body['country'], 'India');
      expect(body['uncertainty_minutes'], 10);
      expect(body['node_type'], 'MEAN');
    }
    final consent = h.at('/privacy/consent').single;
    expect(consent.headers['X-User-Id'], 'test-user');
    expect(
        jsonDecode(consent.body), containsPair('dpdp_consent_granted', true));
    expect(
        jsonDecode(consent.body), containsPair('age_verified_18_plus', true));
    expect(jsonDecode(consent.body),
        containsPair('parental_consent_verified', false));
    final skyQuery = h.at('/panchang').single.url.queryParameters;
    expect(skyQuery['lat'], '18.5204');
    expect(skyQuery['lon'], '73.8567');
    expect(skyQuery['place_name'], 'Pune');
    expect(find.text('A verified daily reflection.'), findsOneWidget);
    await tapVisible(tester, find.text('Chart details'));
    final dial = tester.widget<SkyDial>(find.byType(SkyDial));
    expect(dial.panchang!['moon_longitude'], 123.5);
    expect(dial.natalMoon, 42.0);
    expect(h.requests.where((r) => r.url.path.contains('save')), isEmpty);
    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getString('astroplan_profile_v1_test-user');
    expect(stored, isNotNull);
    expect(stored, contains('Test Person'));
    expect(stored, contains('1990-01-02'));
  });

  testWidgets('country is mandatory and blocks chart calculation',
      (tester) async {
    final h = ApiHarness();
    await tester.pumpWidget(
        AstroplanApp(api: h.api, notifier: RecordingNotifier()));
    await tester.pumpAndSettle();
    await tapVisible(tester, find.byKey(const Key('profile_button')));
    await fillBirth(tester, country: '');
    await tapVisible(tester, find.byKey(const Key('calculate_chart')));
    expect(h.at('/chart'), isEmpty);
    expect(find.text('Enter a valid value.'), findsOneWidget);
  });

  testWidgets('safe statement opens exact evidence and rejects unsafe text',
      (tester) async {
    Future<void> render(Json statement) => tester.pumpWidget(MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
            body: SingleChildScrollView(
                child: StatementPanel(statement: statement, title: 'Test')))));
    await render(verifiedStatement('Safe server text.'));
    await tester.pumpAndSettle();
    await tapVisible(tester, find.byKey(const Key('why_this_button')));
    for (final exact in [
      'TEST_CAREER_01',
      'Saturn in house 10',
      'Test source, chapter 4',
      'supported'
    ]) {
      expect(find.text(exact), findsOneWidget);
    }
    await tapVisible(tester, find.byKey(const Key('close_sheet')));
    await render({
      ...verifiedStatement('Unsafe secret text.'),
      'safety_verified': false
    });
    await tester.pumpAndSettle();
    expect(find.text('Unsafe secret text.'), findsNothing);
    expect(find.byKey(const Key('why_this_button')), findsNothing);
    expect(find.textContaining('not return a verified result'), findsOneWidget);
  });

  testWidgets('Ask matches the API question length contract', (tester) async {
    final h = ApiHarness();
    await startProfile(tester, h);
    await tapVisible(tester, find.byKey(const Key('tab_2')));
    expect(
        tester
            .widget<TextField>(find.byKey(const Key('ask_question')))
            .maxLength,
        280);
    await tester.enterText(find.byKey(const Key('ask_question')), 'a');
    await tester.pump();
    expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('ask_submit')))
            .onPressed,
        isNull);
  });

  testWidgets('Ask keeps the kundali reading closed until an area is chosen',
      (tester) async {
    final h = ApiHarness();
    await startProfile(tester, h);
    await tapVisible(tester, find.byKey(const Key('tab_2')));
    expect(find.byKey(const Key('ask_hold')), findsOneWidget);
    expect(find.text('A verified career reflection.'), findsNothing);
    final field =
        tester.widget<TextField>(find.byKey(const Key('ask_question')));
    await tapVisible(tester, find.byKey(const Key('ask_area_career')));
    expect(find.text('A verified career reflection.'), findsOneWidget);
    expect(find.text('Birth Moon nakshatra: Rohini'), findsOneWidget);
    expect(find.text("Today's nakshatra: Magha"), findsOneWidget);
    expect(field.controller!.text, isEmpty);
    expect(h.at('/readings/ask'), isEmpty);
  });

  testWidgets('Ask still reads the kundali when consent was not recorded',
      (tester) async {
    final h = ApiHarness();
    h.override = (request) => request.url.path.endsWith('/privacy/consent')
        ? reply({'detail': {'error': 'request_failed'}}, 422)
        : null;
    await startProfile(tester, h);
    await tapVisible(tester, find.byKey(const Key('tab_2')));
    await tester.enterText(
        find.byKey(const Key('ask_question')), 'How is my career?');
    await tester.pump();
    expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('ask_submit')))
            .onPressed,
        isNotNull);
    await tapVisible(tester, find.byKey(const Key('ask_submit')));
    expect(find.text('A verified career reflection.'), findsOneWidget);
    expect(
        tester
            .widget<TextField>(find.byKey(const Key('ask_question')))
            .controller!
            .text,
        'How is my career?');
    expect(h.at('/readings/ask'), isEmpty);
  });

  for (final status in [503, 429]) {
    testWidgets(
        'Ask $status retains input, blocks double submit and never auto retries',
        (tester) async {
      final h = ApiHarness();
      final response = Completer<http.Response>();
      h.override = (request) =>
          request.url.path.endsWith('/readings/ask') ? response.future : null;
      await startProfile(tester, h);
      await tapVisible(tester, find.byKey(const Key('tab_2')));
      await tester.enterText(
          find.byKey(const Key('ask_question')), 'How is my career?');
      await tester.ensureVisible(find.byKey(const Key('ask_submit')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('ask_submit')));
      await tester.pump();
      expect(
          tester
              .widget<FilledButton>(find.byKey(const Key('ask_submit')))
              .onPressed,
          isNull);
      await tester.tap(find.byKey(const Key('ask_submit')));
      await tester.pump(const Duration(milliseconds: 500));
      expect(h.at('/readings/ask'), hasLength(1));
      response.complete(reply({
        'detail': {
          'error': status == 503 ? 'ask_disabled' : 'ask_quota_exceeded'
        }
      }, status));
      await tester.pumpAndSettle();
      expect(
          tester
              .widget<TextField>(find.byKey(const Key('ask_question')))
              .controller!
              .text,
          'How is my career?');
      expect(
          find.textContaining(
              status == 503 ? 'not enabled on this server' : 'question limit'),
          findsOneWidget);
      await tester.pump(const Duration(seconds: 30));
      expect(h.at('/readings/ask'), hasLength(1));
      expect(find.text('A verified answer.'), findsNothing);
      expect(h.at('/ledger/calibration'), isEmpty);
    });
  }

  testWidgets(
      'Ask answer and ledger use server metrics, actual id and mark criteria',
      (tester) async {
    final h = ApiHarness();
    await startProfile(tester, h);
    await tapVisible(tester, find.byKey(const Key('tab_2')));
    await tester.enterText(
        find.byKey(const Key('ask_question')), 'How is my career?');
    await tapVisible(tester, find.byKey(const Key('ask_submit')));
    expect(find.text('A verified answer.'), findsOneWidget);
    expect(h.at('/readings/ask').single.headers['X-User-Id'], 'test-user');
    await tapVisible(tester, find.byKey(const Key('tab_4')));
    expect(find.text('17'), findsOneWidget);
    expect(find.text('0.3125'), findsOneWidget);
    expect(
        find.textContaining('API has no entry-list endpoint'), findsOneWidget);
    await tapVisible(tester, find.widgetWithText(ChoiceChip, 'Hit'));
    expect(jsonDecode(h.at('/ledger/entry-42/mark').single.body),
        {'outcome': 'hit'});
    expect(find.text('Actual server criterion.'), findsOneWidget);
    expect(
        tester
            .widget<ChoiceChip>(find.widgetWithText(ChoiceChip, 'Hit'))
            .selected,
        true);
  });

  testWidgets(
      'partner permission is separate and matching renders real breakdown',
      (tester) async {
    final h = ApiHarness();
    await startProfile(tester, h);
    await tapVisible(tester, find.byKey(const Key('tab_3')));
    await tapVisible(tester, find.byKey(const Key('add_partner')));
    expect(
        tester
            .widget<CheckboxListTile>(find.byKey(const Key('partner_consent')))
            .value,
        false);
    await fillBirth(tester, name: 'Partner');
    expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('calculate_chart')))
            .onPressed,
        isNull);
    expect(h.at('/matching/ashtakoota'), isEmpty);
    await tapVisible(tester, find.byKey(const Key('partner_consent')));
    await tapVisible(tester, find.byKey(const Key('calculate_chart')));
    expect(
        jsonDecode(h.at('/matching/ashtakoota').single.body)[
            'partner_consent_confirmed'],
        true);
    expect(find.text('23.5'), findsOneWidget);
    expect(find.text('Server limitations.'), findsOneWidget);
    await tapVisible(tester, find.text('Tara'));
    expect(find.text('Server meaning.'), findsOneWidget);
  });

  testWidgets(
      'D9 consumes returned ascendant and annual uses selected real year',
      (tester) async {
    final h = ApiHarness();
    await startProfile(tester, h);
    await tapVisible(tester, find.byKey(const Key('tab_1')));
    await tapVisible(tester, find.text('D9 · Navamsa'));
    expect(
        tester.widget<NorthIndianChart>(find.byType(NorthIndianChart)).navamsa,
        true);
    expect(find.text('Libra'), findsOneWidget);
    await tapVisible(tester, find.text('Open annual reading'));
    expect(
        h
            .at('/reports/annual-forecast')
            .single
            .url
            .queryParameters['forecast_year'],
        '${DateTime.now().year}');
    expect(find.text('A verified annual overview.'), findsOneWidget);
    expect(find.text('A coarse quarter theme.'), findsOneWidget);
  });

  testWidgets(
      'language change clears old statements and refetches localized results',
      (tester) async {
    final h = ApiHarness();
    final localized = Completer<http.Response>();
    h.override = (r) => r.url.path.endsWith('/daily-insight') &&
            jsonDecode(r.body)['language'] == 'hi'
        ? localized.future
        : null;
    await startProfile(tester, h);
    await tapVisible(tester, find.byKey(const Key('language_selector')));
    await tester.tap(find.text('हिंदी'));
    await tester.pump(const Duration(seconds: 1));
    expect(find.text('A verified daily reflection.'), findsNothing);
    expect(jsonDecode(h.at('/readings/daily-insight').last.body)['language'],
        'hi');
    localized.complete(reply(verifiedStatement('सर्वर का हिंदी मार्गदर्शन।')));
    await tester.pumpAndSettle();
    expect(find.text('सर्वर का हिंदी मार्गदर्शन।'), findsOneWidget);
    expect((await SharedPreferences.getInstance()).getString('preferred_lang'),
        'hi');
  });

  testWidgets('profile replacement discards a late answer and clears question',
      (tester) async {
    final h = ApiHarness();
    final lateAnswer = Completer<http.Response>();
    h.override =
        (r) => r.url.path.endsWith('/readings/ask') ? lateAnswer.future : null;
    await startProfile(tester, h);
    await tapVisible(tester, find.byKey(const Key('tab_2')));
    await tester.enterText(
        find.byKey(const Key('ask_question')), 'How is my career?');
    await tester.ensureVisible(find.byKey(const Key('ask_submit')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('ask_submit')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('profile_button')));
    await tester.pump(const Duration(seconds: 1));
    // Hidden route animations settle while the sheet is open.
    await fillBirth(tester, name: 'Different Person');
    await tapVisible(tester, find.byKey(const Key('calculate_chart')));
    lateAnswer.complete(reply({
      'statement': verifiedStatement('Old private answer.'),
      'ledger_entry_id': 'old-entry'
    }));
    await tester.pumpAndSettle();
    expect(find.text('Old private answer.'), findsNothing);
    expect(
        tester
            .widget<TextField>(find.byKey(const Key('ask_question')))
            .controller!
            .text,
        isEmpty);
    await tapVisible(tester, find.byKey(const Key('tab_4')));
    expect(find.text('No recorded answers in this session.'), findsOneWidget);
  });

  testWidgets('independent endpoint failure never substitutes guidance',
      (tester) async {
    final h = ApiHarness();
    h.override = (r) => r.url.path.endsWith('/daily-insight')
        ? reply({'detail': 'failed'}, 502)
        : null;
    await startProfile(tester, h);
    expect(
        find.textContaining('No result has been substituted'), findsOneWidget);
    expect(find.text('A verified daily reflection.'), findsNothing);
    await tapVisible(tester, find.text('Chart details'));
    expect(tester.widget<SkyDial>(find.byType(SkyDial)).panchang, isNotNull);
    await tapVisible(tester, find.byKey(const Key('tab_1')));
    expect(find.text('A verified career reflection.'), findsOneWidget);
  });

  testWidgets('reminders require opt-in and schedule 07:30 then cancel',
      (tester) async {
    final notifier = RecordingNotifier();
    await tester.pumpWidget(AstroplanApp(notifier: notifier));
    await tester.pumpAndSettle();
    await tapVisible(tester, find.byTooltip('Privacy & reminders'));
    final toggle = find.byKey(const Key('mute_notifications_toggle'));
    expect(tester.widget<SwitchListTile>(toggle).value, false);
    await tapVisible(tester, toggle);
    expect(notifier.calls, ['schedule 7:30']);
    expect(tester.widget<SwitchListTile>(toggle).value, true);
    expect(
        (await SharedPreferences.getInstance()).getBool('notifications_muted'),
        false);
    await tapVisible(tester, toggle);
    expect(notifier.calls, ['schedule 7:30', 'cancel']);
    expect(
        (await SharedPreferences.getInstance()).getBool('notifications_muted'),
        true);
  });

  testWidgets(
      'privacy export is real and erase waits for explicit confirmation',
      (tester) async {
    final h = ApiHarness();
    await startProfile(tester, h);
    await tapVisible(tester, find.byTooltip('Privacy & reminders'));
    await tapVisible(tester, find.text('View my server data'));
    expect(h.at('/privacy/export'), hasLength(1));
    expect(find.textContaining('ledger_entries'), findsOneWidget);
    await tapVisible(tester, find.byKey(const Key('close_sheet')));
    await tapVisible(tester, find.byTooltip('Privacy & reminders'));
    await tapVisible(tester, find.text('Erase my server data'));
    expect(h.at('/privacy/delete'), isEmpty);
    await tapVisible(tester, find.text('Erase my server data'));
    expect(h.at('/privacy/delete').single.method, 'DELETE');
    expect(find.text('Begin with your birth details'), findsOneWidget);
  });

  testWidgets('about sheet links the AGPL source offer', (tester) async {
    final h = ApiHarness();
    await startProfile(tester, h);
    await tapVisible(tester, find.byTooltip('Privacy & reminders'));
    await tapVisible(tester, find.text('Source code & license'));
    expect(find.textContaining('AGPL-3.0'), findsWidgets);
    expect(find.textContaining('github.com/ginnxai-droid/astroplan'),
        findsOneWidget);
  });

  testWidgets('all tabs and birth form fit a narrow reduced-motion viewport',
      (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.accessibilityFeaturesTestValue =
        const FakeAccessibilityFeatures(disableAnimations: true);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
    await tester.pumpWidget(AstroplanApp(notifier: RecordingNotifier()));
    await tester.pumpAndSettle();
    for (var i = 0; i < 5; i++) {
      await tapVisible(tester, find.byKey(Key('tab_$i')));
      expect(tester.takeException(), isNull);
    }
    await tapVisible(tester, find.byKey(const Key('profile_button')));
    await fillBirth(tester);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'saved profile auto-loads on startup, edits cleanly, and uses daily_areas on Today',
      (tester) async {
    final h = ApiHarness();
    h.override = (r) {
      if (r.url.path == '/v1/user/profile') {
        return reply({
          'saved': true,
          'dpdp_consent_granted': true,
          'age_verified_18_plus': true,
          'self_chart': {
            'name': 'Saved User',
            'birth_date': '1992-04-18',
            'birth_time': '09:30:00',
            'place_name': 'Pune',
            'country': 'India',
            'latitude': 18.5204,
            'longitude': 73.8567,
            'timezone_override': 'Asia/Kolkata',
            'uncertainty_minutes': 5,
            'node_type': 'MEAN',
          },
        });
      }
      if (r.url.path == '/v1/readings/life-areas') {
        return reply({
          'life_areas': {
            'career': [verifiedStatement('Chart career multi-year analysis.')],
          },
          'daily_areas': {
            'career': [verifiedStatement('Today work transit guidance.')],
          },
        });
      }
      return null;
    };
    await tester.pumpWidget(
        AstroplanApp(api: h.api, notifier: RecordingNotifier()));
    await tester.pumpAndSettle();

    expect(find.text('Saved User'), findsOneWidget);
    expect(find.text('Today work transit guidance.'), findsOneWidget);
    expect(find.text('Chart career multi-year analysis.'), findsNothing);

    await tapVisible(tester, find.byKey(const Key('tab_1')));
    expect(find.text('Chart career multi-year analysis.'), findsOneWidget);

    await tapVisible(tester, find.byKey(const Key('chart_edit_details')));
    expect(
        tester
            .widget<TextFormField>(find.byKey(const Key('name')))
            .controller!
            .text,
        'Saved User');
    expect(
        tester
            .widget<TextFormField>(find.byKey(const Key('birth_time')))
            .controller!
            .text,
        '09:30');
    await tester.enterText(find.byKey(const Key('name')), 'Updated User');
    tester.testTextInput.hide();
    await tester.drag(
        find.byType(SingleChildScrollView).last, const Offset(0, -700));
    await tester.pumpAndSettle();
    await tapVisible(tester, find.byKey(const Key('calculate_chart')));

    expect(find.text('Updated User'), findsOneWidget);
    expect(h.at('/user/chart'), isNotEmpty);
    expect(jsonDecode(h.at('/user/chart').last.body)['details']['name'],
        'Updated User');
  });

  testWidgets(
      'birth details, partner, and demographics persist across app restart even if server resets',
      (tester) async {
    final h1 = ApiHarness();
    await startProfile(tester, h1);
    await tapVisible(tester, find.byKey(const Key('tab_3')));
    await tapVisible(tester, find.byKey(const Key('add_partner')));
    await fillBirth(tester, name: 'Saved Partner', partner: true);
    await tapVisible(tester, find.byKey(const Key('calculate_chart')));
    expect(find.text('Saved Partner'), findsOneWidget);

    // Unmount and mount a brand-new app instance against a server whose DB has no saved record.
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();

    final h2 = ApiHarness();
    h2.override = (r) => r.url.path == '/v1/user/profile'
        ? reply({'saved': false, 'user_id': 'test-user'})
        : null;
    await tester.pumpWidget(
        AstroplanApp(api: h2.api, notifier: RecordingNotifier()));
    await tester.pumpAndSettle();

    // Never re-prompts for birth details; restores self + partner immediately and re-syncs to server.
    expect(find.text('Begin with your birth details'), findsNothing);
    expect(find.text('Test Person'), findsOneWidget);
    expect(h2.at('/user/chart').length, greaterThanOrEqualTo(2));
    final selfUpload = h2
        .at('/user/chart')
        .firstWhere((r) => jsonDecode(r.body)['is_third_party_chart'] == false);
    final selfBody = jsonDecode(selfUpload.body);
    expect(selfBody['gender'], 'male');
    expect(selfBody['marital_status'], 'single');
    expect(selfBody['occupation'], 'employee');

    // Partner is also restored on Match tab.
    await tapVisible(tester, find.byKey(const Key('tab_3')));
    expect(find.text('Saved Partner'), findsOneWidget);

    // Edit details and confirm updated name persists across another restart even when server profile fails.
    await tapVisible(tester, find.byKey(const Key('tab_0')));
    await tapVisible(tester, find.byKey(const Key('today_edit_details')));
    await tester.enterText(find.byKey(const Key('name')), 'Edited Person');
    tester.testTextInput.hide();
    await tester.drag(
        find.byType(SingleChildScrollView).last, const Offset(0, -700));
    await tester.pumpAndSettle();
    await tapVisible(tester, find.byKey(const Key('calculate_chart')));
    expect(find.text('Edited Person'), findsOneWidget);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();

    final h3 = ApiHarness();
    h3.override = (r) => r.url.path == '/v1/user/profile'
        ? reply({'detail': {'error': 'service_unavailable'}}, 503)
        : null;
    await tester.pumpWidget(
        AstroplanApp(api: h3.api, notifier: RecordingNotifier()));
    await tester.pumpAndSettle();

    expect(find.text('Begin with your birth details'), findsNothing);
    expect(find.text('Edited Person'), findsOneWidget);
  });

  testWidgets('privacy erase clears local persistence across restart',
      (tester) async {
    final h1 = ApiHarness();
    await startProfile(tester, h1);
    final prefsBefore = await SharedPreferences.getInstance();
    expect(
        prefsBefore
            .getKeys()
            .where((k) => k.startsWith('astroplan_profile_v1_')),
        isNotEmpty);

    await tapVisible(tester, find.byTooltip('Privacy & reminders'));
    await tapVisible(tester, find.text('Erase my server data'));
    await tapVisible(tester, find.text('Erase my server data'));
    expect(find.text('Begin with your birth details'), findsOneWidget);

    final prefsAfter = await SharedPreferences.getInstance();
    expect(
        prefsAfter
            .getKeys()
            .where((k) => k.startsWith('astroplan_profile_v1_')),
        isEmpty);

    // Restarting after erase stays on empty onboarding.
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    final h2 = ApiHarness();
    await tester.pumpWidget(
        AstroplanApp(api: h2.api, notifier: RecordingNotifier()));
    await tester.pumpAndSettle();
    expect(find.text('Begin with your birth details'), findsOneWidget);
  });

  testWidgets(
      'a cold 502 then a later 200 does not surface the did not answer copy',
      (tester) async {
    SharedPreferences.setMockInitialValues({
      'astroplan_profile_v1_test-user': jsonEncode({
        'self': {
          'name': 'Amit Sakhare',
          'birth_date': '1980-03-17',
          'birth_time': '09:12',
          'place_name': 'Pune',
          'country': 'India',
          'latitude': 18.5204,
          'longitude': 73.8567,
          'timezone_override': 'Asia/Kolkata',
          'uncertainty_minutes': 0,
          'node_type': 'MEAN',
        },
        'adult': true,
        'parental': false,
        'consent_recorded': true,
        'synced_to_server': true,
        'account_id': 'test-user',
      }),
    });
    final h = ApiHarness();
    final healthGate = Completer<http.Response>();
    var healthCalls = 0;
    var chartCalls = 0;
    h.override = (request) {
      if (request.url.path == '/v1/health') {
        healthCalls++;
        if (healthCalls == 1) return reply({}, 502);
        return healthGate.future;
      }
      if (request.url.path == '/v1/chart') {
        chartCalls++;
        if (chartCalls == 1) return reply({}, 502);
      }
      return null;
    };
    await tester.pumpWidget(
        AstroplanApp(api: h.api, notifier: RecordingNotifier()));
    for (var i = 0; i < 40; i++) {
      await tester.pump(const Duration(milliseconds: 50));
      if (find.text('Opening your chart.').evaluate().isNotEmpty &&
          find.text('Amit Sakhare').evaluate().isNotEmpty) {
        break;
      }
    }

    expect(find.text('Amit Sakhare'), findsOneWidget);
    expect(find.text('Opening your chart.'), findsOneWidget);
    expect(find.textContaining('did not answer'), findsNothing);
    expect(find.textContaining('Tap Refresh'), findsNothing);
    expect(find.textContaining('asleep'), findsNothing);
    expect(find.textContaining('Waking up'), findsNothing);
    expect(find.textContaining('सर्व्हरने उत्तर दिले नाही'), findsNothing);
    expect(find.textContaining('झोपलेला'), findsNothing);
    expect(find.textContaining('रिफ्रेश दाबा'), findsNothing);
    expect(find.textContaining('Something went wrong'), findsNothing);
    expect(healthCalls, greaterThanOrEqualTo(2));

    healthGate.complete(reply({'status': 'ok', 'version': '3.6.0'}));
    await tester.pumpAndSettle();

    expect(find.text('A verified daily reflection.'), findsOneWidget);
    expect(find.text('Amit Sakhare'), findsOneWidget);
    expect(find.textContaining('did not answer'), findsNothing);
    expect(find.textContaining('Tap Refresh'), findsNothing);
    expect(find.textContaining('asleep'), findsNothing);
    expect(find.textContaining('सर्व्हरने उत्तर दिले नाही'), findsNothing);
    expect(find.textContaining('Something went wrong'), findsNothing);
    expect(chartCalls, greaterThanOrEqualTo(2));
    expect(tester.takeException(), isNull);
  });
}
