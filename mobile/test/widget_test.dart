import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:astroplan/main.dart';

class _RecordingNotifier implements DailyInsightNotifier {
  final List<String> calls = [];

  @override
  Future<void> scheduleDailyLocalInsight({
    required int hour,
    required int minute,
    required String title,
    required String body,
  }) async {
    calls.add('schedule $hour:$minute $title');
  }

  @override
  Future<void> cancelDailyInsight() async {
    calls.add('cancel');
  }
}

void main() {
  testWidgets(
    'ARB localization, 4-tab IndexedStack, Why this? modal, and local-notification mute toggle',
    (WidgetTester tester) async {
      SharedPreferences.setMockInitialValues({'notifications_muted': true});
      final notifier = _RecordingNotifier();
      await tester.pumpWidget(AstroplanApp(notifier: notifier));
      await tester.pumpAndSettle();

      expect(find.text('Astroplan'), findsOneWidget);
      expect(find.textContaining('Simple View:'), findsOneWidget);

      await tester.tap(find.byKey(const Key('why_this_button')));
      await tester.pumpAndSettle();
      expect(find.text('Rule ID: RULE_PARASHARI_CAREER_10H'), findsOneWidget);

      await tester.tapAt(const Offset(400, 40));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('mute_notifications_toggle')));
      await tester.pumpAndSettle();
      expect(notifier.calls.single, startsWith('schedule 7:30 Astroplan'));
    },
  );
}
