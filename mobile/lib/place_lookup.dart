import 'dart:convert';

import 'package:http/http.dart' as http;

class ResolvedPlace {
  const ResolvedPlace(
      {required this.latitude, required this.longitude, this.timezone});
  final double latitude;
  final double longitude;
  final String? timezone;
}

/// Device-side place lookup used when the server geocoder is unreachable.
Future<ResolvedPlace?> resolvePlaceOnDevice(String place, String country,
    {http.Client? client}) async {
  final trimmedPlace = place.trim();
  final trimmedCountry = country.trim();
  if (trimmedPlace.length < 2) return null;
  final name = trimmedCountry.isEmpty
      ? trimmedPlace
      : '$trimmedPlace, $trimmedCountry';
  final uri = Uri.https('geocoding-api.open-meteo.com', '/v1/search', {
    'name': name,
    'count': '5',
    'language': 'en',
    'format': 'json',
  });
  final http.Client httpClient = client ?? http.Client();
  final close = client == null;
  try {
    final response =
        await httpClient.get(uri).timeout(const Duration(seconds: 12));
    if (response.statusCode != 200) return null;
    final decoded = jsonDecode(response.body);
    if (decoded is! Map) return null;
    final results = decoded['results'];
    if (results is! List) return null;
    Map<dynamic, dynamic>? best;
    for (final row in results) {
      if (row is! Map) continue;
      final rowCountry =
          '${row['country'] ?? ''} ${row['country_code'] ?? ''}'.toLowerCase();
      if (trimmedCountry.isNotEmpty &&
          rowCountry.contains(trimmedCountry.toLowerCase())) {
        best = row;
        break;
      }
      best ??= row;
    }
    if (best == null) return null;
    final lat = best['latitude'];
    final lon = best['longitude'];
    if (lat is! num || lon is! num) return null;
    final timezone = best['timezone'];
    return ResolvedPlace(
        latitude: lat.toDouble(),
        longitude: lon.toDouble(),
        timezone: timezone is String && timezone.isNotEmpty ? timezone : null);
  } catch (_) {
    return null;
  } finally {
    if (close) httpClient.close();
  }
}

Future<List<Map<String, dynamic>>> searchPlacesOnDevice(String query,
    {http.Client? client}) async {
  final trimmed = query.trim();
  if (trimmed.length < 2) return const [];
  final uri = Uri.https('geocoding-api.open-meteo.com', '/v1/search', {
    'name': trimmed,
    'count': '6',
    'language': 'en',
    'format': 'json',
  });
  final http.Client httpClient = client ?? http.Client();
  final close = client == null;
  try {
    final response =
        await httpClient.get(uri).timeout(const Duration(seconds: 8));
    if (response.statusCode != 200) return const [];
    final decoded = jsonDecode(response.body);
    if (decoded is! Map) return const [];
    final results = decoded['results'];
    if (results is! List) return const [];
    return [
      for (final row in results)
        if (row is Map && row['latitude'] is num && row['longitude'] is num)
          {
            'name': row['name']?.toString() ?? trimmed,
            'country': row['country']?.toString() ?? '',
            'display_name': [
              row['name'],
              row['admin1'],
              row['country'],
            ].whereType<String>().where((part) => part.trim().isNotEmpty).join(', '),
            'latitude': row['latitude'],
            'longitude': row['longitude'],
            if (row['timezone'] is String) 'timezone_iana': row['timezone'],
          }
    ];
  } catch (_) {
    return const [];
  } finally {
    if (close) httpClient.close();
  }
}

/// Fills latitude, longitude, and timezone when a birth record only has a place name.
Future<Map<String, dynamic>> attachCoordinates(
    Map<String, dynamic> details) async {
  final lat = details['latitude'];
  final lon = details['longitude'];
  if (lat is num && lon is num) return details;
  final place = details['place_name']?.toString() ?? '';
  final country = details['country']?.toString() ?? '';
  final hit = await resolvePlaceOnDevice(place, country);
  if (hit == null) return details;
  final zone = details['timezone_override']?.toString().trim() ?? '';
  return {
    ...details,
    'latitude': hit.latitude,
    'longitude': hit.longitude,
    if (zone.isEmpty && hit.timezone != null) 'timezone_override': hit.timezone,
  };
}
