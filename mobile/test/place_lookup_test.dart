import 'dart:convert';

import 'package:astroplan/place_lookup.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('a city name is resolved before the chart request', () async {
    final client = MockClient((request) async {
      expect(request.url.host, 'geocoding-api.open-meteo.com');
      expect(request.url.queryParameters['name'], 'Pune, india');
      return http.Response(
          jsonEncode({
            'results': [
              {
                'name': 'Pune',
                'latitude': 18.51957,
                'longitude': 73.85535,
                'timezone': 'Asia/Kolkata',
                'country': 'India',
                'country_code': 'IN',
              }
            ]
          }),
          200);
    });
    final hit = await resolvePlaceOnDevice('Pune', 'india', client: client);
    expect(hit?.latitude, closeTo(18.51957, 0.0001));
    expect(hit?.timezone, 'Asia/Kolkata');
    final attached = await attachCoordinates({
      'place_name': 'Pune',
      'country': 'India',
      'latitude': 18.52,
      'longitude': 73.85,
    });
    expect(attached['latitude'], 18.52);
  });
}
