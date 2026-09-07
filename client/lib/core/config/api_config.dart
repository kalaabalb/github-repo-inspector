class ApiConfig {
  // Flutter Web and native targets use the same API. Override this at build or
  // run time with --dart-define=API_BASE_URL=...
  static const baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );
}
