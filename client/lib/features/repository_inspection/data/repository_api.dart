import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'models/ai_explanation.dart';
import 'models/project_report.dart';

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
    _validateRepositoryUrl(repositoryUrl);
    final response = await _post('/api/v1/repositories/inspect', {
      'url': repositoryUrl,
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
        'The API could not be reached. Check your connection and try again.',
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

void _validateRepositoryUrl(String value) {
  final uri = Uri.tryParse(value.trim());
  final parts =
      uri?.pathSegments.where((part) => part.isNotEmpty).toList() ?? [];
  if (uri == null ||
      uri.scheme != 'https' ||
      uri.host.toLowerCase() != 'github.com' ||
      parts.length != 2) {
    throw const ApiException(
      'Enter a public GitHub URL like https://github.com/owner/repository.',
    );
  }
}

String _messageForStatus(int statusCode) => switch (statusCode) {
  400 || 422 => 'The repository URL is not valid.',
  404 => 'Repository not found or not public.',
  409 => 'This repository is empty and cannot be analyzed yet.',
  429 => 'GitHub is rate-limiting requests. Try again later.',
  502 => 'The GitHub service returned an invalid response.',
  503 => 'The GitHub service is temporarily unavailable.',
  _ => 'The API returned an unexpected error ($statusCode).',
};
