import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'models/ai_explanation.dart';
import 'models/project_report.dart';
import 'repository_url.dart';

abstract interface class RepositoryApi {
  Future<ProjectReport> inspect(String repositoryUrl);

  Future<AiExplanationResponse> explain(ProjectReport report);
}

class HttpRepositoryApi implements RepositoryApi {
  HttpRepositoryApi({required this.baseUrl, http.Client? client})
    : _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;

  @override
  Future<ProjectReport> inspect(String repositoryUrl) async {
    final repository = RepositoryUrl.tryParse(repositoryUrl);
    if (repository == null) {
      throw const ApiException(invalidUrlMessage);
    }
    final response = await _post('/api/v1/repositories/inspect', {
      'url': repository.url,
    }, timeout: const Duration(seconds: 45));
    return ProjectReport.fromJson(response);
  }

  @override
  Future<AiExplanationResponse> explain(ProjectReport report) async {
    final response = await _post('/api/v1/repositories/explain', {
      'report': report.toJson(),
    });
    return AiExplanationResponse.fromJson(response);
  }

  Future<Map<String, dynamic>> _post(
    String path,
    Map<String, dynamic> body,
    {Duration timeout = const Duration(seconds: 20)}
  ) async {
    try {
      final response = await _client
          .post(
            Uri.parse('$baseUrl$path'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(body),
          )
          .timeout(timeout);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw ApiException(_messageForStatus(response.statusCode));
      }
      final decoded = jsonDecode(response.body);
      if (decoded is! Map<String, dynamic>) {
        throw const ApiException('The server returned an invalid report.');
      }
      return decoded;
    } on ApiException {
      rethrow;
    } on TimeoutException {
      throw const ApiException(
        'Inspection is taking longer than expected. Please try again.',
      );
    } on FormatException {
      throw const ApiException('The server returned an invalid report.');
    } on Exception catch (_) {
      throw const ApiException(
        'Could not connect to the inspector. If you are offline, the sample report still works.',
      );
    }
  }
}

class ApiException implements Exception {
  const ApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

const invalidUrlMessage =
    'Enter a public GitHub URL like https://github.com/owner/repository (or just owner/repository).';

String _messageForStatus(int statusCode) => switch (statusCode) {
  400 || 422 => 'The repository URL is not valid.',
  404 => 'Repository not found or not public.',
  409 => 'This repository is empty and cannot be analyzed yet.',
  429 => 'GitHub is limiting requests right now. Try again in a few minutes.',
  500 => 'The analysis failed on the server. Please try again.',
  502 => 'The GitHub service returned an invalid response.',
  503 => 'The GitHub service is temporarily unavailable.',
  _ => 'The API returned an unexpected error ($statusCode).',
};
