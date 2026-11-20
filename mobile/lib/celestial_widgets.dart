import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'api.dart';
import 'l10n/app_localizations.dart';

const ink = Color(0xFFFBF7ED);
const gold = Color(0xFFEBCB86);
const muted = Color(0xFF98A4BD);
const night = Color(0xFF050812);
const panel = Color(0xFF10182B);
const hairline = Color(0x2EEBCB86);
const bodyInk = Color(0xFFC7D0E2);

ThemeData celestialTheme() {
  final base = ThemeData.dark(useMaterial3: true);
  return base.copyWith(
    scaffoldBackgroundColor: night,
    colorScheme: const ColorScheme.dark(
        primary: gold,
        onPrimary: night,
        secondary: gold,
        surface: panel,
        onSurface: ink,
        error: Color(0xFFE6A2A7)),
    textTheme: base.textTheme.apply(bodyColor: bodyInk, displayColor: ink),
    dividerColor: const Color(0x18FFFFFF),
    appBarTheme:
        const AppBarTheme(backgroundColor: Colors.transparent, elevation: 0),
    bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: panel,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
            side: BorderSide(color: hairline))),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: const Color(0xFF090F1D),
      labelStyle: const TextStyle(color: muted, fontSize: 13),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 16),
      border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: hairline)),
      enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: hairline)),
      focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: gold)),
    ),
    filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
            minimumSize: const Size(0, 48),
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            textStyle:
                const TextStyle(fontSize: 13, fontWeight: FontWeight.w700))),
    outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
            minimumSize: const Size(0, 46),
            side: const BorderSide(color: hairline),
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(14)))),
    chipTheme: base.chipTheme.copyWith(
        side: const BorderSide(color: hairline),
        backgroundColor: panel,
        labelStyle: const TextStyle(color: muted, fontSize: 12)),
  );
}

TextStyle serif(double size, {Color color = ink}) => TextStyle(
    fontFamily: 'Georgia',
    fontFamilyFallback: const ['Noto Serif', 'serif'],
    fontSize: size,
    height: 1.15,
    color: color,
    fontWeight: FontWeight.w400,
    letterSpacing: -.4);

Json jsonMap(dynamic value) =>
    value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};
List<Json> jsonRows(dynamic value) =>
    value is List ? value.whereType<Map>().map(jsonMap).toList() : [];
double? number(dynamic value) => value is num ? value.toDouble() : null;
String shown(dynamic value) =>
    value == null || value.toString().isEmpty ? '—' : value.toString();
String degrees(dynamic value) =>
    number(value) == null ? '—' : '${number(value)!.toStringAsFixed(2)}°';
String planetName(AppLocalizations t, dynamic name) {
  const names = [
    'Sun',
    'Moon',
    'Mars',
    'Mercury',
    'Jupiter',
    'Venus',
    'Saturn',
    'Rahu',
    'Ketu'
  ];
  final index = names.indexOf(name.toString());
  return index < 0 ? shown(name) : t.planetNames.split('|')[index];
}

String signName(AppLocalizations t, dynamic index, dynamic fallback) {
  final i = number(index)?.toInt();
  return i != null && i >= 1 && i <= 12
      ? t.zodiacNames.split('|')[i - 1]
      : shown(fallback);
}

String gradeName(AppLocalizations t, dynamic grade) => switch (grade) {
      'likely' => t.likelyLabel,
      'supported' => t.supportedLabel,
      'weak' => t.weakLabel,
      'contested' => t.contestedLabel,
      _ => shown(grade),
    };
String friendlyError(AppLocalizations t, Object error) {
  if (error is! ApiFailure) return t.serviceError;
  if (error.status == 429) return t.quotaError;
  return switch (error.code) {
    'auth_required' ||
    'missing_bearer_token' ||
    'invalid_firebase_token' =>
      t.authError,
    'network_unavailable' => t.networkError,
    'invalid_response' => t.invalidResponseError,
    'ask_disabled' => t.askDisabledError,
    'ask_quota_exceeded' || 'quota_exceeded' => t.quotaError,
    'ambiguous_location' || 'geocoder_unavailable' => t.locationError,
    'unknown_timezone' => t.timezoneError,
    _ => t.serviceError,
  };
}

class SlowLoadHint extends StatefulWidget {
  const SlowLoadHint(
      {super.key,
      required this.label,
      required this.slowLabel,
      this.delay = const Duration(seconds: 4)});
  final String label;
  final String slowLabel;
  final Duration delay;

  @override
  State<SlowLoadHint> createState() => _SlowLoadHintState();
}

class _SlowLoadHintState extends State<SlowLoadHint> {
  Timer? _timer;
  var _slow = false;

  @override
  void initState() {
    super.initState();
    _timer = Timer(widget.delay, () {
      if (mounted) setState(() => _slow = true);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) =>
      Text(_slow ? widget.slowLabel : widget.label);
}

class GoldPanel extends StatelessWidget {
  const GoldPanel(
      {super.key, required this.child, this.padding = 18, this.accent = false});
  final Widget child;
  final double padding;
  final bool accent;
  @override
  Widget build(BuildContext context) => Container(
      width: double.infinity,
      padding: EdgeInsets.all(padding),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: accent ? hairline : const Color(0x16FFFFFF)),
        gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: accent
                ? const [Color(0xFF1B2439), Color(0xFF0D1424)]
                : const [panel, Color(0xFF0B1220)]),
        boxShadow: accent
            ? const [
                BoxShadow(
                    color: Color(0x25000000),
                    blurRadius: 24,
                    offset: Offset(0, 12))
              ]
            : null,
      ),
      child: child);
}

class Eyebrow extends StatelessWidget {
  const Eyebrow(this.text, {super.key});
  final String text;
  @override
  Widget build(BuildContext context) => Text(text.toUpperCase(),
      style: const TextStyle(
          color: gold,
          fontSize: 10,
          letterSpacing: 1.7,
          fontWeight: FontWeight.w600));
}

class PageHeading extends StatelessWidget {
  const PageHeading(this.kicker, this.title, this.description, {super.key});
  final String kicker, title, description;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.only(top: 12, bottom: 20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Eyebrow(kicker),
        const SizedBox(height: 8),
        Text(title, style: serif(31)),
        const SizedBox(height: 10),
        Text(description,
            style: const TextStyle(color: muted, fontSize: 13, height: 1.6))
      ]));
}

class FactRow extends StatelessWidget {
  const FactRow(this.label, this.value, {super.key});
  final String label, value;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 9),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: const TextStyle(color: muted, fontSize: 11)),
        const SizedBox(height: 5),
        SelectableText(value,
            style: const TextStyle(color: ink, fontSize: 14, height: 1.5)),
      ]));
}

class MotionEntry extends StatelessWidget {
  const MotionEntry({super.key, required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) => TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: MediaQuery.disableAnimationsOf(context)
          ? Duration.zero
          : const Duration(milliseconds: 460),
      curve: Curves.easeOutCubic,
      builder: (_, value, child) => Opacity(
          opacity: value,
          child: Transform.translate(
              offset: Offset(0, 12 * (1 - value)), child: child)),
      child: child);
}

Future<T?> goldSheet<T>(BuildContext context,
    {required String title, required Widget child}) {
  final t = AppLocalizations.of(context)!;
  return showModalBottomSheet<T>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      sheetAnimationStyle: MediaQuery.disableAnimationsOf(context)
          ? AnimationStyle.noAnimation
          : null,
      builder: (sheetContext) => Padding(
          padding: EdgeInsets.only(
              bottom: MediaQuery.viewInsetsOf(sheetContext).bottom),
          child: ConstrainedBox(
              constraints: BoxConstraints(
                  maxHeight: MediaQuery.sizeOf(sheetContext).height * .9),
              child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
                  child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Center(
                            child: Container(
                                width: 32,
                                height: 3,
                                decoration: BoxDecoration(
                                    color: hairline,
                                    borderRadius: BorderRadius.circular(4)))),
                        const SizedBox(height: 12),
                        Row(children: [
                          Expanded(child: Text(title, style: serif(27))),
                          IconButton(
                              key: const Key('close_sheet'),
                              tooltip: t.closeLabel,
                              onPressed: () => Navigator.pop(sheetContext),
                              icon: const Icon(Icons.close, size: 20))
                        ]),
                        const SizedBox(height: 12),
                        child,
                      ])))));
}

class StatementPanel extends StatefulWidget {
  const StatementPanel(
      {super.key, required this.statement, required this.title});
  final Json statement;
  final String title;
  @override
  State<StatementPanel> createState() => _StatementPanelState();
}

class _StatementPanelState extends State<StatementPanel> {
  bool pro = false;
  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    if (!AstroplanApiClient.safeStatement(widget.statement)) {
      return GoldPanel(child: Text(t.invalidResponseError));
    }
    final why = jsonMap(widget.statement['why_this']);
    return GoldPanel(
        accent: true,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Wrap(
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 12,
              runSpacing: 8,
              children: [
                Eyebrow(widget.title),
                SegmentedButton<bool>(
                    showSelectedIcon: false,
                    style: const ButtonStyle(
                        visualDensity: VisualDensity.compact,
                        textStyle:
                            WidgetStatePropertyAll(TextStyle(fontSize: 11))),
                    segments: [
                      ButtonSegment(value: false, label: Text(t.simpleLabel)),
                      ButtonSegment(value: true, label: Text(t.proLabel))
                    ],
                    selected: {pro},
                    onSelectionChanged: (v) => setState(() => pro = v.first))
              ]),
          const SizedBox(height: 15),
          AnimatedSize(
              duration: MediaQuery.disableAnimationsOf(context)
                  ? Duration.zero
                  : const Duration(milliseconds: 200),
              child: Text(
                  shown(widget.statement[pro ? 'pro_text' : 'simple_text']),
                  style:
                      const TextStyle(color: ink, fontSize: 16, height: 1.65))),
          const SizedBox(height: 8),
          TextButton.icon(
              key: const Key('why_this_button'),
              onPressed: () => goldSheet(context,
                  title: t.whyThisLabel,
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        for (final row in [
                          (t.ruleLabel, why['rule_id']),
                          (t.evidenceLabel, why['placement_evidence']),
                          (t.sourceLabel, why['classical_source']),
                          (t.gradeLabel, why['strength_grade']),
                          (t.traditionLabel, why['tradition']),
                          (t.methodLabel, why['method_note']),
                          (t.timeWindowLabel, widget.statement['time_window']),
                        ])
                          if (row.$2 != null) ...[
                            FactRow(row.$1, shown(row.$2)),
                            const Divider()
                          ],
                        Text(t.trustNote,
                            style: const TextStyle(
                                color: muted, fontSize: 12, height: 1.5)),
                      ])),
              icon: const Icon(Icons.arrow_outward, size: 16),
              label: Text(t.whyThisLabel)),
          const Divider(),
          Text(gradeName(t, why['strength_grade']),
              style: const TextStyle(color: Color(0xFFAFE1BC), fontSize: 12)),
          if (widget.statement['time_window'] != null)
            Padding(
                padding: const EdgeInsets.only(top: 5),
                child: Text(shown(widget.statement['time_window']),
                    style: const TextStyle(color: muted, fontSize: 11))),
        ]));
  }
}

/// Draws only geometry; the server supplies every position and phase value.
class SkyDial extends StatelessWidget {
  const SkyDial(
      {super.key,
      required this.panchang,
      required this.natalMoon,
      this.detailed = false});
  final Json? panchang;
  final double? natalMoon;
  final bool detailed;
  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    final p = panchang ?? {};
    final moon = number(p['moon_longitude']);
    final nak = shown(p['nakshatra']);
    final label = moon == null
        ? t.skyEmpty
        : '${p['reference_kind'] == 'sunrise' ? t.sunriseMoon : t.fallbackMoon}: $nak · ${degrees(moon)}';
    return Semantics(
        label: label,
        image: true,
        child: AspectRatio(
            aspectRatio: 1,
            child: Stack(alignment: Alignment.center, children: [
              Positioned.fill(
                  child: CustomPaint(
                      painter: _SkyPainter(
                          moon: moon,
                          natal: natalMoon,
                          illumination: number(p['phase_illumination']),
                          signs: detailed ? t.zodiacNames.split('|') : null,
                          nakshatras:
                              detailed ? t.nakshatraNames.split('|') : null))),
              FractionallySizedBox(
                  widthFactor: detailed ? .48 : .6,
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    Text(moon == null ? t.skyEmpty : nak,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                            color: gold,
                            fontSize: detailed ? 14 : 15,
                            letterSpacing: .4,
                            fontWeight: FontWeight.w600)),
                    if (moon != null) ...[
                      const SizedBox(height: 6),
                      Text(
                          '${t.padaLabel} ${shown(p['moon_nakshatra_pada'])} · ${shown(p['moon_sign_name'])}',
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: bodyInk, fontSize: 10)),
                      const SizedBox(height: 5),
                      Text(degrees(p['moon_degree_in_sign']),
                          style: const TextStyle(color: muted, fontSize: 11)),
                    ],
                  ])),
            ])));
  }
}

class _SkyPainter extends CustomPainter {
  _SkyPainter(
      {required this.moon,
      required this.natal,
      this.illumination,
      this.signs,
      this.nakshatras});
  final double? moon, natal, illumination;
  final List<String>? signs, nakshatras;
  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final r = size.shortestSide * .46;
    Offset at(double radius, double degrees) {
      final a = (degrees - 90) * math.pi / 180;
      return c + Offset(math.cos(a), math.sin(a)) * radius;
    }

    final line = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = .8
      ..color = hairline;
    canvas.drawCircle(
        c,
        r * .65,
        Paint()
          ..shader = RadialGradient(
                  colors: [gold.withValues(alpha: .08), Colors.transparent])
              .createShader(Rect.fromCircle(center: c, radius: r * .65)));
    for (final radius in [r, r * .89, r * .74]) {
      canvas.drawCircle(c, radius, line);
    }
    for (var i = 0; i < 12; i++) {
      canvas.drawLine(at(r, i * 30), at(r * .91, i * 30),
          line..color = const Color(0x40FFFFFF));
      if (signs != null) {
        _rotatedText(
            canvas, at(r * .95, i * 30 + 15), signs![i], i * 30 + 15, 8, muted);
      }
    }
    for (var i = 0; i < 27; i++) {
      final start = i * 360 / 27;
      final angle = (start - 90) * math.pi / 180;
      if (i.isEven) {
        final path = Path()
          ..arcTo(Rect.fromCircle(center: c, radius: r * .89), angle,
              2 * math.pi / 27, true)
          ..arcTo(Rect.fromCircle(center: c, radius: r * .74),
              angle + 2 * math.pi / 27, -2 * math.pi / 27, false)
          ..close();
        canvas.drawPath(path, Paint()..color = const Color(0x09FFFFFF));
      }
      canvas.drawLine(at(r * .74, start), at(r * .89, start),
          line..color = i % 9 == 0 ? gold.withValues(alpha: .55) : hairline);
      if (nakshatras != null) {
        _rotatedText(canvas, at(r * .815, start + 360 / 54), nakshatras![i],
            start + 360 / 54, 6, gold.withValues(alpha: .7));
      }
    }
    if (moon != null) {
      final sector = (moon! / (360 / 27)).floor();
      for (final radius in [r * .925, r * .70]) {
        canvas.drawArc(
            Rect.fromCircle(center: c, radius: radius),
            (sector * 360 / 27 - 89.2) * math.pi / 180,
            (360 / 27 - 1.6) * math.pi / 180,
            false,
            line
              ..color = gold
              ..strokeWidth = 1.8);
      }
      final m = at(r * .815, moon!);
      canvas.drawCircle(
          m,
          10,
          Paint()
            ..color = gold.withValues(alpha: .16)
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8));
      canvas.drawCircle(m, 7, Paint()..color = gold);
      canvas.drawCircle(
          m,
          7,
          Paint()
            ..style = PaintingStyle.stroke
            ..color = ink
            ..strokeWidth = .6);
    }
    if (natal != null) {
      final n = at(r * .815, natal!);
      canvas.drawCircle(n, 4, Paint()..color = panel);
      canvas.drawCircle(
          n,
          4,
          Paint()
            ..style = PaintingStyle.stroke
            ..color = const Color(0xFF9EB4DC)
            ..strokeWidth = 1.2);
    }
  }

  void _rotatedText(Canvas canvas, Offset at, String text, double angle,
      double fontSize, Color color) {
    final tp = TextPainter(
        text: TextSpan(
            text: text, style: TextStyle(fontSize: fontSize, color: color)),
        textDirection: TextDirection.ltr)
      ..layout();
    canvas.save();
    canvas.translate(at.dx, at.dy);
    canvas.rotate(
        (angle > 90 && angle < 270 ? angle + 180 : angle) * math.pi / 180);
    final scale = math.min(1.0, 34 / math.max(1, tp.width));
    canvas.scale(scale);
    tp.paint(canvas, Offset(-tp.width / 2, -tp.height / 2));
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _SkyPainter old) =>
      moon != old.moon ||
      natal != old.natal ||
      signs != old.signs ||
      nakshatras != old.nakshatras;
}

class NorthIndianChart extends StatelessWidget {
  const NorthIndianChart(
      {super.key, required this.chart, required this.navamsa});
  final Json chart;
  final bool navamsa;
  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context)!;
    final lagna =
        number(chart[navamsa ? 'navamsa_lagna_sign_index' : 'lagna_sign_index'])
            ?.toInt();
    if (lagna == null) {
      return Padding(padding: const EdgeInsets.all(20), child: Text(t.noScore));
    }
    final houses = <int, List<String>>{};
    for (final p in jsonRows(chart['planets'])) {
      final sign =
          number(p[navamsa ? 'navamsa_sign_index' : 'sign_index'])?.toInt();
      if (sign == null) continue;
      final house = (sign - lagna) % 12 + 1;
      houses
          .putIfAbsent(house, () => [])
          .add(planetName(t, p['planet']).characters.take(2).toString());
    }
    return Semantics(
        image: true,
        label: '${navamsa ? t.d9Label : t.d1Label} · ${t.placementsLabel}',
        child: AspectRatio(
            aspectRatio: 1,
            child: CustomPaint(
                painter: _ChartPainter(
                    lagna, houses, navamsa ? t.d9Label : t.d1Label))));
  }
}

class _ChartPainter extends CustomPainter {
  _ChartPainter(this.lagna, this.houses, this.label);
  final int lagna;
  final Map<int, List<String>> houses;
  final String label;
  static const centers = [
    Offset(.5, .25),
    Offset(.25, .12),
    Offset(.12, .25),
    Offset(.25, .5),
    Offset(.12, .75),
    Offset(.25, .88),
    Offset(.5, .75),
    Offset(.75, .88),
    Offset(.88, .75),
    Offset(.75, .5),
    Offset(.88, .25),
    Offset(.75, .12)
  ];
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.shortestSide - 12;
    canvas.save();
    canvas.translate(6, 6);
    final paint = Paint()
      ..color = hairline
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    canvas.drawRRect(
        RRect.fromRectAndRadius(
            Rect.fromLTWH(0, 0, w, w), const Radius.circular(12)),
        paint);
    canvas.drawLine(Offset.zero, Offset(w, w), paint);
    canvas.drawLine(Offset(w, 0), Offset(0, w), paint);
    canvas.drawPath(
        Path()
          ..moveTo(w / 2, 0)
          ..lineTo(w, w / 2)
          ..lineTo(w / 2, w)
          ..lineTo(0, w / 2)
          ..close(),
        paint);
    for (var i = 0; i < 12; i++) {
      final c = centers[i] * w;
      final names = houses[i + 1] ?? [];
      _text(canvas, c + const Offset(0, -13), '${(lagna + i - 1) % 12 + 1}',
          muted, 10);
      if (names.isNotEmpty) {
        _text(canvas, c + const Offset(0, 5), names.join('·'), gold, 11,
            maxWidth: w * .23);
      }
    }
    canvas.drawCircle(Offset(w / 2, w / 2), 21, Paint()..color = panel);
    canvas.drawCircle(Offset(w / 2, w / 2), 21, paint);
    _text(canvas, Offset(w / 2, w / 2), label.split(' · ').first, gold, 12);
    canvas.restore();
  }

  void _text(Canvas c, Offset p, String s, Color color, double fontSize,
      {double maxWidth = 100}) {
    final tp = TextPainter(
        text: TextSpan(
            text: s, style: TextStyle(color: color, fontSize: fontSize)),
        textAlign: TextAlign.center,
        textDirection: TextDirection.ltr)
      ..layout(maxWidth: maxWidth);
    tp.paint(c, p - Offset(tp.width / 2, tp.height / 2));
  }

  @override
  bool shouldRepaint(covariant _ChartPainter old) => true;
}
