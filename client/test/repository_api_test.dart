import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'package:github_repo_inspector/features/repository_inspection/data/repository_api.dart';

class TimeoutHttpClient extends http.BaseClient {
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) {
    return Future<http.StreamedResponse>.error(
      TimeoutException('test timeout'),
    );
  }
}

void main() {
  test('inspection timeout uses a timeout-specific error', () async {
    final api = HttpRepositoryApi(
      baseUrl: 'http://localhost:8000',
      client: TimeoutHttpClient(),
    );

    expect(
      api.inspect('https://github.com/owner/repository'),
      throwsA(
        isA<ApiException>().having(
          (error) => error.message,
          'message',
          'Inspection is taking longer than expected. Please try again.',
        ),
      ),
    );
  });
}
