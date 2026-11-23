import 'dart:convert';

import 'package:astroplan/place_lookup.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('each updated place resolves in the country the user entered', () async {
    final directory = {
      'London': [
        {
          'name': 'London',
          'latitude': 42.98,
          'longitude': -81.25,
          'timezone': 'America/Toronto',
          'country': 'Canada',
          'admin1': 'Ontario',
        },
        {
          'name': 'London',
          'latitude': 51.51,
          'longitude': -0.13,
          'timezone': 'Europe/London',
          'country': 'United Kingdom',
          'admin1': 'England',
        },
      ],
      'Tokyo': [
        {
          'name': 'Tokyo',
          'latitude': 35.68,
          'longitude': 139.69,
          'timezone': 'Asia/Tokyo',
          'country': 'Japan',
        }
      ],
      'Nairobi': [
        {
          'name': 'Nairobi',
          'latitude': -1.28,
          'longitude': 36.82,
          'timezone': 'Africa/Nairobi',
          'country': 'Kenya',
        }
      ],
    };
    final client = MockClient((request) async {
      final name = request.url.queryParameters['name'] ?? '';
      return http.Response(
          jsonEncode({'results': directory[name] ?? const []}), 200);
    });

    final london = await resolvePlaceOnDevice('London', 'UK', client: client);
    final canada =
        await resolvePlaceOnDevice('London', 'Canada', client: client);
    final tokyo = await resolvePlaceOnDevice('Tokyo', 'Japan', client: client);
    final nairobi =
        await resolvePlaceOnDevice('Nairobi', 'Kenya', client: client);
    final wrong = await resolvePlaceOnDevice('Tokyo', 'Kenya', client: client);

    expect(london?.timezone, 'Europe/London');
    expect(canada?.timezone, 'America/Toronto');
    expect(tokyo?.latitude, closeTo(35.68, 0.01));
    expect(nairobi?.timezone, 'Africa/Nairobi');
    expect(wrong, isNull);

    final kept = await attachCoordinates({
      'place_name': 'Tokyo',
      'country': 'Japan',
      'latitude': 35.0,
      'longitude': 139.0,
    });
    expect(kept['latitude'], 35.0);

    final fromSearch = await resolveUpdatedPlace(
      {'place_name': 'Nairobi', 'country': 'Kenya'},
      search: (query) async => [
        {
          'name': 'Nairobi',
          'country': 'Kenya',
          'latitude': -1.28,
          'longitude': 36.82,
          'timezone_iana': 'Africa/Nairobi',
        }
      ],
    );
    expect(fromSearch?['latitude'], -1.28);
    expect(fromSearch?['timezone_override'], 'Africa/Nairobi');
  });

  test('a display name without a country field still matches its last segment',
      () {
    final chosen = choosePlace([
      {
        'display_name': 'Pune, Maharashtra, India',
        'latitude': 18.52,
        'longitude': 73.85,
        'timezone_iana': 'Asia/Kolkata',
      },
      {
        'display_name': 'Pune, New Caledonia',
        'latitude': -22.27,
        'longitude': 166.44,
      },
    ], place: 'Pune', country: 'India');
    expect(chosen?['latitude'], 18.52);
  });
}
