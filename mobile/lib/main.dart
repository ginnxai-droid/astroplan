import 'package:flutter/material.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:timezone/data/latest_all.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;
import 'api.dart';
import 'celestial_home.dart';
import 'celestial_widgets.dart';
import 'l10n/app_localizations.dart';
export 'api.dart';

const String kClosedBetaScheduleTz = 'Asia/Kolkata';
const TimeOfDay kDefaultNotificationTime = TimeOfDay(hour: 7, minute: 30);
const int kDailyInsightNotificationId = 1001;

abstract class DailyInsightNotifier {
  Future<void> scheduleDailyLocalInsight(
      {required int hour,
      required int minute,
      required String title,
      required String body});
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
    if (_initialized) return;
    await _plugin.initialize(const InitializationSettings(
      android: AndroidInitializationSettings('@mipmap/ic_launcher'),
      iOS: DarwinInitializationSettings(
          requestAlertPermission: false,
          requestBadgePermission: false,
          requestSoundPermission: false),
    ));
    _initialized = true;
  }

  @override
  Future<void> scheduleDailyLocalInsight(
      {required int hour,
      required int minute,
      required String title,
      required String body}) async {
    await _ensureInitialized();
    final allowed = await _plugin
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.requestNotificationsPermission();
    if (allowed == false) throw StateError('notification_permission_denied');
    final iosAllowed = await _plugin
        .resolvePlatformSpecificImplementation<
            IOSFlutterLocalNotificationsPlugin>()
        ?.requestPermissions(alert: true, badge: true, sound: true);
    if (iosAllowed == false) throw StateError('notification_permission_denied');
    final location = tz.getLocation(kClosedBetaScheduleTz);
    final now = tz.TZDateTime.now(location);
    var when =
        tz.TZDateTime(location, now.year, now.month, now.day, hour, minute);
    if (!when.isAfter(now)) {
      when = tz.TZDateTime(
          location, now.year, now.month, now.day + 1, hour, minute);
    }
    await _plugin.zonedSchedule(
        kDailyInsightNotificationId,
        title,
        body,
        when,
        NotificationDetails(
            android: AndroidNotificationDetails(
                'astroplan_daily_insight', title,
                importance: Importance.defaultImportance,
                priority: Priority.defaultPriority),
            iOS: const DarwinNotificationDetails()),
        androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
        matchDateTimeComponents: DateTimeComponents.time);
  }

  @override
  Future<void> cancelDailyInsight() async {
    await _ensureInitialized();
    await _plugin.cancel(kDailyInsightNotificationId);
  }
}

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(AstroplanApp(notifier: FlutterLocalNotificationNotifier()));
}

class AstroplanApp extends StatefulWidget {
  const AstroplanApp({super.key, this.notifier, this.api});
  final DailyInsightNotifier? notifier;
  final AstroplanApiClient? api;
  @override
  State<AstroplanApp> createState() => _AstroplanAppState();
}

class _AstroplanAppState extends State<AstroplanApp> {
  late final AstroplanApiClient _api;
  late final DailyInsightNotifier _notifier;
  Locale _locale = const Locale('en');
  bool _muted = true;
  @override
  void initState() {
    super.initState();
    tzdata.initializeTimeZones();
    _api = widget.api ?? AstroplanApiClient();
    _notifier = widget.notifier ?? FlutterLocalNotificationNotifier();
    _loadPreferences();
  }

  Future<void> _loadPreferences() async {
    final prefs = await SharedPreferences.getInstance();
    if (!mounted) return;
    final lang = prefs.getString('preferred_lang');
    setState(() {
      _muted = prefs.getBool('notifications_muted') ?? true;
      if (['en', 'hi', 'mr'].contains(lang)) _locale = Locale(lang!);
    });
  }

  Future<void> _changeLanguage(Locale locale) async {
    setState(() => _locale = locale);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('preferred_lang', locale.languageCode);
  }

  Future<void> _setMuted(bool muted, AppLocalizations t) async {
    if (muted) {
      await _notifier.cancelDailyInsight();
    } else {
      await _notifier.scheduleDailyLocalInsight(
          hour: kDefaultNotificationTime.hour,
          minute: kDefaultNotificationTime.minute,
          title: t.appTitle,
          body: t.notificationBody);
    }
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('notifications_muted', muted);
    if (mounted) setState(() => _muted = muted);
  }

  @override
  void dispose() {
    if (widget.api == null) _api.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
        debugShowCheckedModeBanner: false,
        onGenerateTitle: (context) => AppLocalizations.of(context)!.appTitle,
        locale: _locale,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        theme: celestialTheme(),
        home: CelestialHome(
            api: _api,
            locale: _locale,
            muted: _muted,
            onLanguageChanged: _changeLanguage,
            onMutedChanged: _setMuted),
      );
}
