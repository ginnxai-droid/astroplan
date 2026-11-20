import 'package:astroplan/celestial_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('a slow request switches the loading copy to a waking-up hint',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
            body: SlowLoadHint(label: 'Loading', slowLabel: 'Waking up'))));
    expect(find.text('Loading'), findsOneWidget);
    expect(find.text('Waking up'), findsNothing);

    await tester.pump(const Duration(seconds: 5));

    expect(find.text('Waking up'), findsOneWidget);
    expect(find.text('Loading'), findsNothing);
  });

  testWidgets('a fast response never shows the waking-up hint',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
            body: SlowLoadHint(label: 'Loading', slowLabel: 'Waking up'))));
    await tester.pump(const Duration(seconds: 1));
    expect(find.text('Loading'), findsOneWidget);
    expect(find.text('Waking up'), findsNothing);
  });
}
