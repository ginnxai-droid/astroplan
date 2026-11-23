import 'dart:convert';

import 'package:http/http.dart' as http;

class ResolvedPlace {
  const ResolvedPlace(
      {required this.latitude, required this.longitude, this.timezone});
  final double latitude;
  final double longitude;
  final String? timezone;
}

const _countryAliases = {
  'usa': 'united states',
  'us': 'united states',
  'u s': 'united states',
  'u s a': 'united states',
  'america': 'united states',
  'united states of america': 'united states',
  'uk': 'united kingdom',
  'u k': 'united kingdom',
  'britain': 'united kingdom',
  'great britain': 'united kingdom',
  'england': 'united kingdom',
  'uae': 'united arab emirates',
  'u a e': 'united arab emirates',
  'bharat': 'india',
  'hindustan': 'india',
  'russia': 'russian federation',
  'south korea': 'korea republic of',
  'republic of korea': 'korea republic of',
  'czechia': 'czech republic',
};

const _accents = {
  'à': 'a',
  'á': 'a',
  'â': 'a',
  'ã': 'a',
  'ä': 'a',
  'å': 'a',
  'è': 'e',
  'é': 'e',
  'ê': 'e',
  'ë': 'e',
  'ì': 'i',
  'í': 'i',
  'î': 'i',
  'ï': 'i',
  'ò': 'o',
  'ó': 'o',
  'ô': 'o',
  'õ': 'o',
  'ö': 'o',
  'ù': 'u',
  'ú': 'u',
  'û': 'u',
  'ü': 'u',
  'ý': 'y',
  'ÿ': 'y',
  'ñ': 'n',
  'ç': 'c',
  'ø': 'o',
  'ß': 'ss',
  'æ': 'ae',
  'œ': 'oe',
};

String foldPlace(String value) {
  final buffer = StringBuffer();
  for (final rune in value.toLowerCase().runes) {
    final char = String.fromCharCode(rune);
    buffer.write(_accents[char] ?? char);
  }
  return buffer.toString().replaceAll(RegExp(r'[^a-z0-9]'), '');
}

String canonicalCountry(String value) {
  final buffer = StringBuffer();
  for (final rune in value.toLowerCase().runes) {
    final char = String.fromCharCode(rune);
    final folded = _accents[char] ?? char;
    buffer.write(RegExp(r'[a-z\s]').hasMatch(folded) ? folded : ' ');
  }
  final text = buffer.toString().replaceAll(RegExp(r'\s+'), ' ').trim();
  return _countryAliases[text] ?? text;
}

bool sameCountry(String left, String right) {
  final a = canonicalCountry(left);
  final b = canonicalCountry(right);
  if (a.isEmpty || b.isEmpty) return false;
  if (a == b) return true;
  final short = a.length <= b.length ? a : b;
  final long = a.length <= b.length ? b : a;
  return short.length >= 4 &&
      (long.startsWith('$short ') || long.endsWith(' $short'));
}

String placeNameOf(Map<dynamic, dynamic> hit) {
  final name = hit['name']?.toString().trim() ?? '';
  if (name.isNotEmpty) return name;
  final display = hit['display_name']?.toString() ?? '';
  return display.split(',').first.trim();
}

String countryOf(Map<dynamic, dynamic> hit) {
  final explicit = hit['country']?.toString().trim() ?? '';
  if (explicit.isNotEmpty) return explicit;
  final parts = (hit['display_name']?.toString() ?? '')
      .split(',')
      .map((part) => part.trim())
      .where((part) => part.isNotEmpty)
      .toList();
  return parts.length >= 2 ? parts.last : '';
}

/// The hit for the place and country the user entered.
///
/// An exact city name wins. A single candidate is used only when
/// [allowOnlyCandidate] is set, which is the save path for names such as
/// Bombay that the directory lists as Mumbai. Several matches and no exact
/// name stay unresolved so the suggestion list can be used.
Map<String, dynamic>? choosePlace(List<Map<String, dynamic>> hits,
    {required String place,
    required String country,
    bool allowOnlyCandidate = false}) {
  final usable = [
    for (final hit in hits)
      if (hit['latitude'] is num && hit['longitude'] is num) hit
  ];
  final wantedCountry = country.trim();
  final pool = wantedCountry.isEmpty
      ? usable
      : [
          for (final hit in usable)
            if (sameCountry(countryOf(hit), wantedCountry)) hit
        ];
  if (wantedCountry.isNotEmpty && pool.isEmpty) return null;
  final wantedPlace = foldPlace(place);
  final exact = [
    for (final hit in pool)
      if (foldPlace(placeNameOf(hit)) == wantedPlace) hit
  ];
  if (exact.isNotEmpty) return exact.first;
  if (allowOnlyCandidate && pool.length == 1) return pool.first;
  return null;
}

/// Device-side place lookup used when the server geocoder is unreachable.
Future<ResolvedPlace?> resolvePlaceOnDevice(String place, String country,
    {http.Client? client}) async {
  final trimmedPlace = place.trim();
  final trimmedCountry = country.trim();
  if (trimmedPlace.length < 2) return null;
  final hits = await searchPlacesOnDevice(trimmedPlace, client: client);
  final chosen = choosePlace(hits,
      place: trimmedPlace, country: trimmedCountry, allowOnlyCandidate: true);
  if (chosen == null) return null;
  final zone = chosen['timezone_iana']?.toString();
  return ResolvedPlace(
      latitude: (chosen['latitude'] as num).toDouble(),
      longitude: (chosen['longitude'] as num).toDouble(),
      timezone: zone != null && zone.isNotEmpty ? zone : null);
}

Future<List<Map<String, dynamic>>> searchPlacesOnDevice(String query,
    {http.Client? client}) async {
  final trimmed = query.trim();
  if (trimmed.length < 2) return const [];
  final uri = Uri.https('geocoding-api.open-meteo.com', '/v1/search', {
    'name': trimmed,
    'count': '8',
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
            ]
                .whereType<String>()
                .where((part) => part.trim().isNotEmpty)
                .join(', '),
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

/// Fills coordinates for whatever place the user entered.
///
/// Coordinates already chosen from a suggestion are kept. Otherwise the
/// [search] results, then the device directory, are matched by city and
/// country. Null means the place was not matched and must not be charted.
Future<Map<String, dynamic>?> resolveUpdatedPlace(Map<String, dynamic> details,
    {Future<List<Map<String, dynamic>>> Function(String query)? search,
    http.Client? client}) async {
  final lat = details['latitude'];
  final lon = details['longitude'];
  if (lat is num && lon is num) return details;
  final place = details['place_name']?.toString().trim() ?? '';
  final country = details['country']?.toString().trim() ?? '';
  if (place.length < 2) return null;
  var hits = <Map<String, dynamic>>[];
  if (search != null) {
    try {
      hits = await search(place);
    } catch (_) {
      hits = [];
    }
  }
  if (hits.isEmpty) {
    hits = await searchPlacesOnDevice(place, client: client);
  }
  final chosen = choosePlace(hits,
      place: place, country: country, allowOnlyCandidate: true);
  if (chosen == null) return null;
  final zone = details['timezone_override']?.toString().trim() ?? '';
  final resolvedZone = chosen['timezone_iana']?.toString().trim() ?? '';
  final resolvedCountry = countryOf(chosen);
  return {
    ...details,
    'latitude': (chosen['latitude'] as num).toDouble(),
    'longitude': (chosen['longitude'] as num).toDouble(),
    if (zone.isEmpty && resolvedZone.isNotEmpty)
      'timezone_override': resolvedZone,
    if (country.isEmpty && resolvedCountry.isNotEmpty)
      'country': resolvedCountry,
  };
}

/// Fills latitude, longitude, and timezone when a birth record only has a place name.
Future<Map<String, dynamic>> attachCoordinates(Map<String, dynamic> details,
    {http.Client? client}) async {
  return await resolveUpdatedPlace(details, client: client) ?? details;
}
