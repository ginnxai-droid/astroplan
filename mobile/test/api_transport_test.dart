import 'dart:io';

import 'package:astroplan/api.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('redirects never receive authenticated follow-up requests', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final paths = <String>[];
    final subscription = server.listen((request) async {
      paths.add(request.uri.path);
      if (request.uri.path == '/v1/redirect') {
        request.response.statusCode = 302;
        request.response.headers.set('location', '/sink');
      } else {
        request.response.write('{}');
      }
      await request.response.close();
    });
    final api = AstroplanApiClient(
        baseUrl: 'http://127.0.0.1:${server.port}/v1', userId: 'qa-user');
    try {
      await expectLater(
          api.get('/redirect', protected: true), throwsA(isA<ApiFailure>()));
      expect(paths, ['/v1/redirect']);
    } finally {
      api.close();
      await subscription.cancel();
      await server.close(force: true);
    }
  });
}
