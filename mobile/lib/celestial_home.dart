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
import 'l10n/app_localizations.dart';
import 'licensing.dart';
import 'terms.dart';

class CelestialHome extends StatefulWidget {
  const CelestialHome(
      {super.key,
      required this.api,
      required this.locale,
      required this.muted,
      required this.onLanguageChanged,
      required this.onMutedChanged});
  final AstroplanApiClient api;
  final Locale locale;
  final bool muted;
  final Future<void> Function(Locale) onLanguageChanged;
  final Future<void> Function(bool, AppLocalizations) onMutedChanged;
  @override
  State<CelestialHome> createState() => _CelestialHomeState();
}

class _CelestialHomeState extends State<CelestialHome> {
  int tab = 0, epoch = 0;
  final annualAnchor = GlobalKey();
  bool showChartDetails = false;
  int year = DateTime.now().year;
  bool d9 = false, consentRecorded = false, notificationBusy = false;
  Json? profile, partner;
  final data = <String, Json>{};
  final errors = <String, Object>{};
  final pending = <String>{};
  final versions = <String, int>{};
  final answers = <Json>[];
  final question = TextEditingController();
  String? selectedArea;
  bool askUnmatched = false;
  AppLocalizations get t => AppLocalizations.of(context)!;
  AstroplanApiClient get api => widget.api;
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
    question.dispose();
    super.dispose();
  }

  Future<Json?> load(String key, Future<Json> Function() request,
      {bool keepPrevious = false}) async {
    final generation = epoch;
    final version = (versions[key] ?? 0) + 1;
    versions[key] = version;
    setState(() {
      pending.add(key);
      errors.remove(key);
      if (!keepPrevious) data.remove(key);
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
      question.clear();
      selectedArea = null;
      askUnmatched = false;
      d9 = false;
    });
  }

  Future<void> editBirth({bool forPartner = false}) async {
    final result = await goldSheet<BirthSubmission>(context,
        title: forPartner ? t.partnerDetails : t.birthDetails,
        child: BirthForm(
            initial: forPartner ? partner : profile, partner: forPartner));
    if (result == null || !mounted) return;
    if (forPartner) {
      if (!result.partnerPermission || profile == null) return;
      setState(() {
        partner = result.details;
        data.remove('match');
        errors.remove('match');
      });
      _loadMatch();
      return;
    }
    // Invalidate all in-flight responses before accepting a different person's details.
    clearSession();
    setState(() => profile = result.details);
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
        setState(() => consentRecorded = response != null);
      }
    }
  }

  void _loadProfile() {
    if (profile == null) return;
    final body = details;
    final query = targetQuery;
    load('chart', () => api.post('/chart', body)).then((chart) {
      if (!mounted) return;
      load('dasha', () => api.post('/dasha', body, query: query));
      load('daily',
          () => api.post('/readings/daily-insight', body, query: query));
      load('areas', () => api.post('/readings/life-areas', body, query: query));
      if (chart == null) return;
      load(
          'sky',
          () => api.fetchAndCacheDailyPanchang(targetDate,
              placeName: shown(profile?['place_name']),
              latitude: number(chart['resolved_latitude']),
              longitude: number(chart['resolved_longitude'])));
    });
  }

  void _loadMatch() {
    if (profile == null || partner == null) return;
    load(
        'match',
        () => api.post('/matching/ashtakoota', {
              'profile_a': details,
              'profile_b': {
                ...partner!,
                'language': widget.locale.languageCode
              },
              'partner_consent_confirmed': true,
              'already_married': partner?['already_married'] == true,
            }));
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
    });
    if (!accountReady) return;
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
  Widget status(String key) {
    if (pending.contains(key)) {
      return Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Semantics(
              label: t.loadingLabel,
              liveRegion: true,
              child: const LinearProgressIndicator(
                  minHeight: 2, color: gold, backgroundColor: panel)));
    }
    if (errors[key] != null) {
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
        gap(12),
        note(t.sessionPrivacy),
      ]));
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
    final areas = jsonMap(data['areas']?['life_areas']);
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
        status('chart'),
        if (errors['chart'] != null)
          TextButton(onPressed: editBirth, child: Text(t.birthDetails)),
        note(t.dayBasis),
        gap(),
        status('daily'),
        if (data['daily'] case final statement?)
          StatementPanel(statement: statement, title: t.dayFeelTitle),
        gap(),
        status('areas'),
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
            icon: Icon(
                showChartDetails ? Icons.expand_less : Icons.expand_more,
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
    setState(() {
      pending.add('annual-pdf');
      errors.remove('annual-pdf');
    });
    try {
      final bytes = await api.postBytes(
          '/reports/annual-forecast/pdf', details,
          query: {'forecast_year': '$year'});
      final dir = await getTemporaryDirectory();
      final file = File('${dir.path}/astroplan-$year.pdf');
      await file.writeAsBytes(bytes, flush: true);
      if (!mounted) return;
      await Share.shareXFiles(
        [XFile(file.path, mimeType: 'application/pdf', name: 'astroplan-$year.pdf')],
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
        status('areas'),
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
                if (y == null || y == year || pending.contains('annual')) return;
                setState(() => year = y);
                openAnnual(y);
              }),
          gap(12),
          FilledButton(
              onPressed: pending.contains('annual') ? null : () => openAnnual(year),
              child: Text(t.annualAction)),
          gap(8),
          OutlinedButton.icon(
              onPressed: pending.contains('annual-pdf') ? null : saveAnnualPdf,
              icon: const Icon(Icons.picture_as_pdf_outlined, size: 18),
              label: Text(t.annualPdfAction)),
          status('annual-pdf'),
        ])),
        Column(key: annualAnchor, crossAxisAlignment: CrossAxisAlignment.start, children: [
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
              if (q['active_dasha'] != null)
                Padding(
                    padding: const EdgeInsets.all(10),
                    child: note('${t.dashaLabel}: ${shown(q['active_dasha'])}')),
              if (q['key_transit_note'] != null)
                Padding(
                    padding: const EdgeInsets.fromLTRB(10, 0, 10, 8),
                    child: note(shown(q['key_transit_note']))),
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
    };
    final statements =
        jsonRows(jsonMap(data['areas']?['life_areas'])[selectedArea]);
    final birth = namedNakshatra(data['chart']?['moon_nakshatra']);
    final today = namedNakshatra(data['sky']?['nakshatra']);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (closed)
        Opacity(
            opacity: .55,
            child: GoldPanel(
                key: const Key('ask_hold'), child: note(t.askHold))),
      if (askUnmatched && response == null)
        GoldPanel(child: note(t.uncoveredLabel)),
      if (selectedArea != null) ...[
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
    };
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      PageHeading(t.tabAsk, t.askTitle, t.askDescription),
      if (profile == null) ...[onboarding(), gap()],
      if (!api.authenticated) ...[
        GoldPanel(child: note(t.authError)),
        gap()
      ] else if (profile != null && !consentRecorded) ...[
        note(t.consentError),
        gap()
      ],
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
        Wrap(
            spacing: 6,
            runSpacing: 4,
            children: [
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
                onPressed: chartReady &&
                        !pending.contains('ask') &&
                        questionReady
                    ? ask
                    : null,
                icon: const Icon(Icons.arrow_forward, size: 18),
                label: Text(t.askAction))),
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
          else
            Text(shown(partner?['name']), style: serif(24)),
          gap(16),
          FilledButton.icon(
              key: const Key('add_partner'),
              onPressed: pending.contains('match')
                  ? null
                  : () => editBirth(forPartner: true),
              icon: const Icon(Icons.person_add_alt_1, size: 18),
              label: Text(t.addPartner)),
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

  Future<void> privacySheet() => goldSheet<void>(context,
      title: t.privacyLabel,
      child: StatefulBuilder(
          builder: (sheetContext, update) =>
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
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
                                  await api.syncNotificationMute(!enabled);
                                } catch (_) {
                                  if (mounted) toast(t.notificationSyncFailure);
                                }
                              }
                            } catch (_) {
                              if (mounted) toast(t.notificationFailure);
                            }
                            notificationBusy = false;
                            if (sheetContext.mounted) update(() {});
                          }),
                const Divider(),
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
                          () => api.get('/privacy/export', protected: true),
                          (result) => SelectableText(
                              const JsonEncoder.withIndent('  ')
                                  .convert(result)));
                    }),
                ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.delete_outline, color: gold),
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
                    onTap: () {
                      Navigator.pop(sheetContext);
                      clearSession();
                    }),
                ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.info_outline, color: gold),
                    title: Text(t.aboutLabel),
                    onTap: () {
                      Navigator.pop(sheetContext);
                      showRemote(
                          t.aboutLabel,
                          () => api.get('/trust/about-predictions',
                              query: {'lang': widget.locale.languageCode}),
                          (result) => Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    for (final key in [
                                      'calculations_note',
                                      'interpretations_note',
                                      'ledger_methodology',
                                      'professional_advice_disclaimer'
                                    ])
                                      if (result[key] != null) ...[
                                        Text(shown(result[key]),
                                            style:
                                                const TextStyle(height: 1.6)),
                                        gap(14)
                                      ],
                                    if (result['grievance_officer'] is Map)
                                      SelectableText(
                                          jsonMap(result['grievance_officer'])
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
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(t.sourceOfferNote,
                                    style: const TextStyle(height: 1.6)),
                                gap(14),
                                const SelectableText(kSourceOfferUrl),
                                gap(14),
                                const SelectableText(kSourceOfferLicense),
                              ]));
                    }),
                ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.menu_book_outlined, color: gold),
                    title: Text(t.glossaryLabel),
                    onTap: () {
                      Navigator.pop(sheetContext);
                      showRemote(
                          t.glossaryLabel,
                          () => api.get('/glossary',
                              query: {'lang': widget.locale.languageCode}),
                          (result) => Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    for (final value in result.values) ...[
                                      Text(shown(value),
                                          style: const TextStyle(height: 1.6)),
                                      const Divider(height: 28)
                                    ],
                                  ]));
                    }),
              ]))).then((_) {});
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
                          label: t.loadingLabel,
                          slowLabel: t.loadingSlowLabel)
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
      if (!mounted) return;
      clearSession();
      toast(t.erasedLabel);
    } catch (error) {
      if (mounted) toast(friendlyError(t, error));
    }
  }

  @override
  Widget build(BuildContext context) {
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
                  Expanded(child: Text(t.appTitle, style: serif(27))),
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
                  IconButton(
                      key: const Key('profile_button'),
                      tooltip: t.birthDetails,
                      onPressed: editBirth,
                      style: IconButton.styleFrom(
                          backgroundColor: gold.withValues(alpha: .13),
                          foregroundColor: gold),
                      icon: const Icon(Icons.person_outline, size: 22)),
                  IconButton(
                      tooltip: t.privacyLabel,
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
