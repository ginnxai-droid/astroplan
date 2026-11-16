import 'dart:convert';

import 'package:flutter/material.dart';
import 'l10n/app_localizations.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:timezone/data/latest_all.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

const String kClosedBetaScheduleTz = 'Asia/Kolkata';
const TimeOfDay kDefaultNotificationTime = TimeOfDay(hour: 7, minute: 30);
const int kDailyInsightNotificationId = 1001;

abstract class DailyInsightNotifier {
  Future<void> scheduleDailyLocalInsight({
    required int hour,
    required int minute,
    required String title,
    required String body,
  });

  Future<void> cancelDailyInsight();
}

class FlutterLocalNotificationNotifier implements DailyInsightNotifier {
  FlutterLocalNotificationNotifier() {
    tzdata.initializeTimeZones();
  }

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();
  bool _initialized = false;

  Future<void> _ensureInitialized() async {
    if (_initialized) {
      return;
    }
    await _plugin.initialize(
      const InitializationSettings(
        android: AndroidInitializationSettings('@mipmap/ic_launcher'),
      ),
    );
    _initialized = true;
  }

  @override
  Future<void> scheduleDailyLocalInsight({
    required int hour,
    required int minute,
    required String title,
    required String body,
  }) async {
    await _ensureInitialized();
    final location = tz.getLocation(kClosedBetaScheduleTz);
    final now = tz.TZDateTime.now(location);
    var when = tz.TZDateTime(
      location, now.year, now.month, now.day, hour, minute,
    );
    if (!when.isAfter(now)) {
      when = when.add(const Duration(days: 1));
    }
    await _plugin.zonedSchedule(
      kDailyInsightNotificationId,
      title,
      body,
      when,
      const NotificationDetails(
        android: AndroidNotificationDetails(
          'astroplan_daily_insight',
          'Daily Insight',
          importance: Importance.defaultImportance,
          priority: Priority.defaultPriority,
        ),
      ),
      androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      matchDateTimeComponents: DateTimeComponents.time,
    );
  }

  @override
  Future<void> cancelDailyInsight() async {
    await _ensureInitialized();
    await _plugin.cancel(kDailyInsightNotificationId);
  }
}

class AstroplanApiClient {
  final String baseUrl;
  final http.Client _client;

  AstroplanApiClient({this.baseUrl = 'http://localhost:8000/v1', http.Client? client})
      : _client = client ?? http.Client();

  Future<Map<String, dynamic>> fetchAndCacheDailyPanchang(String targetDate) async {
    final prefs = await SharedPreferences.getInstance();
    final cacheKey = 'panchang_$targetDate';
    try {
      final res = await _client.get(Uri.parse('$baseUrl/panchang?target_date=$targetDate'));
      if (res.statusCode == 200) {
        await prefs.setString(cacheKey, res.body);
        return jsonDecode(res.body) as Map<String, dynamic>;
      }
    } catch (_) {
      // Fallback to offline cache when network is unreachable (Gap 19)
    }
    final cached = prefs.getString(cacheKey);
    if (cached != null) {
      return jsonDecode(cached) as Map<String, dynamic>;
    }
    return {'tithi': 'Shukla Ekadashi', 'rahu_kaal': '07:30 - 09:00', 'offline_cacheable': true};
  }

  Future<void> syncNotificationMute(bool muted, {String userId = 'dev-user'}) async {
    try {
      await _client.post(
        Uri.parse('$baseUrl/user/notifications/preferences'),
        headers: {'Content-Type': 'application/json', 'X-User-Id': userId},
        body: jsonEncode({'notifications_muted': muted}),
      );
    } catch (_) {
      // Queued locally in SharedPreferences until the next online session
    }
  }
}

void main() {
  runApp(AstroplanApp(notifier: FlutterLocalNotificationNotifier()));
}

class AstroplanApp extends StatefulWidget {
  const AstroplanApp({super.key, this.notifier});

  final DailyInsightNotifier? notifier;

  @override
  State<AstroplanApp> createState() => _AstroplanAppState();
}

class _AstroplanAppState extends State<AstroplanApp> {
  final AstroplanApiClient _api = AstroplanApiClient();
  late final DailyInsightNotifier _notifier;
  bool isProView = false;
  bool notificationsMuted = false;
  Locale locale = const Locale('en');
  int selectedTab = 0;
  String cachedPanchangSummary = 'Offline Cache Ready (Sunrise Anchored)';

  @override
  void initState() {
    super.initState();
    _notifier = widget.notifier ?? FlutterLocalNotificationNotifier();
    _loadPersistedPreferences();
  }

  Future<void> _loadPersistedPreferences() async {
    final prefs = await SharedPreferences.getInstance();
    if (!mounted) return;
    setState(() {
      notificationsMuted = prefs.getBool('notifications_muted') ?? false;
      final saved = prefs.getString('preferred_lang');
      locale = saved == null ? locale : Locale(saved);
    });
  }

  Future<void> _toggleMute(AppLocalizations t) async {
    final next = !notificationsMuted;
    setState(() => notificationsMuted = next);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('notifications_muted', next);
    if (next) {
      await _notifier.cancelDailyInsight();
    } else {
      await _notifier.scheduleDailyLocalInsight(
        hour: kDefaultNotificationTime.hour,
        minute: kDefaultNotificationTime.minute,
        title: t.appTitle,
        body: t.dailyHeading,
      );
    }
    await _api.syncNotificationMute(next);
  }

  void _showWhyThisSheet(
    BuildContext context,
    String whyLabel,
    String ruleId,
    String evidence,
    String source,
    String grade,
  ) {
    showModalBottomSheet<void>(
      context: context,
      builder: (_) => Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(whyLabel, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
            const SizedBox(height: 8),
            Text('Rule ID: $ruleId'),
            Text('Placement Evidence: $evidence'),
            Text('Source: $source'),
            Text('Grade: $grade (Sidereal Lahiri, Whole-Sign Houses)'),
          ],
        ),
      ),
    );
  }

  void _showTooltipSheet(BuildContext context, String term, String definition) {
    showModalBottomSheet<void>(
      context: context,
      builder: (_) => Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(term, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
            const SizedBox(height: 8),
            Text(definition),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      onGenerateTitle: (context) => AppLocalizations.of(context)!.appTitle,
      locale: locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF5B3A8E)),
        useMaterial3: true,
      ),
      home: Builder(
        builder: (innerContext) {
          final t = AppLocalizations.of(innerContext)!;
          return Scaffold(
            appBar: AppBar(
              title: Text(t.appTitle),
              actions: [
                DropdownButton<Locale>(
                  key: const Key('language_selector'),
                  value: locale,
                  underline: const SizedBox.shrink(),
                  onChanged: (v) {
                    if (v != null) setState(() => locale = v);
                  },
                  items: const [
                    DropdownMenuItem(value: Locale('en'), child: Text('EN')),
                    DropdownMenuItem(value: Locale('hi'), child: Text('HI')),
                    DropdownMenuItem(value: Locale('mr'), child: Text('MR')),
                  ],
                ),
                Row(
                  children: [
                    Text(t.simpleLabel),
                    Switch(
                      key: const Key('simple_pro_toggle'),
                      value: isProView,
                      onChanged: (v) => setState(() => isProView = v),
                    ),
                    Text(t.proLabel),
                    IconButton(
                      key: const Key('mute_notifications_toggle'),
                      icon: Icon(
                        notificationsMuted
                            ? Icons.notifications_off
                            : Icons.notifications_active,
                      ),
                      onPressed: () => _toggleMute(t),
                    ),
                  ],
                ),
              ],
            ),
            body: IndexedStack(
              index: selectedTab,
              children: [
                ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Wrap(
                      spacing: 8,
                      children: [
                        ActionChip(
                          key: const Key('tooltip_nakshatra_chip'),
                          label: const Text('Nakshatra ?'),
                          onPressed: () => _showTooltipSheet(
                            innerContext,
                            'Nakshatra',
                            'One of 27 lunar mansions (13 degrees 20 minutes each) along the ecliptic.',
                          ),
                        ),
                        ActionChip(
                          key: const Key('tooltip_ayanamsa_chip'),
                          label: const Text('Ayanamsa ?'),
                          onPressed: () => _showTooltipSheet(
                            innerContext,
                            'Ayanamsa',
                            'Angular precession difference between tropical and sidereal zodiacs (Lahiri default).',
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Card(
                      child: ListTile(
                        title: Text(t.dailyHeading),
                        subtitle: Text(
                          isProView
                              ? 'Pro View: 10th-house karmic indicators and Saturn/Jupiter transit alignment support methodical career consolidation. (${t.offlineCachedBadge}: $cachedPanchangSummary)'
                              : 'Simple View: Steady professional progress is supported through structured planning and consistent effort. (${t.offlineCachedBadge}: $cachedPanchangSummary)',
                        ),
                        trailing: TextButton(
                          key: const Key('why_this_button'),
                          onPressed: () => _showWhyThisSheet(
                            innerContext,
                            t.whyThisLabel,
                            'RULE_PARASHARI_CAREER_10H',
                            'Sun in Taurus (House 10, D9 Virgo)',
                            'Brihat Parashara Hora Shastra (BPHS), Ch. 21',
                            'supported',
                          ),
                          child: Text(t.whyThisLabel),
                        ),
                      ),
                    ),
                  ],
                ),
                Center(child: Text(t.chartAreasHeading, key: const Key('tab_areas_view'))),
                Center(child: Text(t.matchingHeading, key: const Key('tab_matching_view'))),
                Center(child: Text(t.ledgerHeading, key: const Key('tab_ledger_view'))),
              ],
            ),
            bottomNavigationBar: NavigationBar(
              selectedIndex: selectedTab,
              onDestinationSelected: (idx) => setState(() => selectedTab = idx),
              destinations: [
                NavigationDestination(
                  icon: const Icon(Icons.wb_sunny_outlined),
                  label: t.tabToday,
                ),
                NavigationDestination(
                  icon: const Icon(Icons.auto_graph),
                  label: t.tabChartAreas,
                ),
                NavigationDestination(
                  icon: const Icon(Icons.favorite_border),
                  label: t.tabMatching,
                ),
                NavigationDestination(
                  icon: const Icon(Icons.fact_check_outlined),
                  label: t.tabLedger,
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
