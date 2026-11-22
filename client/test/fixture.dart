import 'package:github_repo_inspector/features/repository_inspection/data/models/project_report.dart';

const fixtureReportJson = <String, dynamic>{
  'repository': {
    'owner': 'owner',
    'name': 'project',
    'full_name': 'owner/project',
    'description': 'A Flutter project',
    'html_url': 'https://github.com/owner/project',
    'default_branch': 'main',
    'stars': 0,
    'forks': 0,
    'primary_language': 'Dart',
  },
  'overview': {
    'classifications': ['Flutter application'],
    'primary_classification': 'Flutter application',
    'classification_basis': ['Flutter evidence is present'],
  },
  'technologies': {
    'languages': [
      {
        'name': 'Dart',
        'category': 'language',
        'evidence': ['lib/main.dart'],
      },
    ],
    'frameworks': [
      {
        'name': 'Flutter',
        'category': 'framework',
        'evidence': ['pubspec.yaml', 'lib/'],
      },
    ],
    'package_managers': [
      {
        'name': 'Dart Pub',
        'category': 'package_manager',
        'evidence': ['pubspec.yaml'],
      },
    ],
  },
  'architecture': {
    'observed_structure': ['lib', 'test'],
    'interpretations': ['test directory observed'],
  },
  'api': {'signals': []},
  'authentication': {'signals': []},
  'data': {'databases': []},
  'project_structure': {
    'important_directories': ['lib', 'test'],
    'important_files': ['README.md'],
    'configuration_files': ['pubspec.yaml'],
    'has_tests': true,
    'has_docs': false,
    'has_ci': false,
    'has_docker': false,
    'has_environment_example': false,
  },
  'evidence': [
    {
      'name': 'Flutter',
      'category': 'framework',
      'evidence': ['pubspec.yaml', 'lib/'],
    },
  ],
  'limitations': {
    'tree_truncated': true,
    'paths_truncated': false,
    'content_truncated': false,
    'notes': ['Bounded fixture'],
  },
  'findings': [
    {
      'id': 'credential-like-assignment',
      'category': 'security',
      'severity': 'high',
      'title': 'Potential credential exposed',
      'summary': 'The value is intentionally redacted.',
      'evidence': ['config.py'],
      'affected_paths': ['config.py'],
      'confidence': 'medium',
      'recommendation': 'Use environment-based secret storage.',
      'why_it_matters': 'Credentials in source can expose access.',
      'recommended_action': 'Use environment-based secret storage.',
    },
  ],
  'health_summary': {
    'total_findings': 1,
    'category_counts': {'security': 1},
    'severity_counts': {'high': 1},
    'overall': 'Static inspection only',
  },
  'trust_context': {
    'verified_detected': ['Bounded tree evidence was inspected.'],
    'potential_issues': ['Potential credential exposed'],
    'not_verified': [],
    'limitations': [],
    'runtime_status': 'Code was not executed.',
  },
  'source_inspection': {
    'files_inspected': 2,
    'files_skipped': 1,
    'files_truncated': 0,
    'content_truncated': false,
    'notes': ['Bounded source inspection'],
  },
};

final fixtureReport = ProjectReport.fromJson(fixtureReportJson);

/// A richer report: dependencies, a good-to-know note, more issues, an API signal.
final Map<String, dynamic> richReportJson = {
  ...fixtureReportJson,
  'api': {
    'signals': [
      {'name': 'FastAPI routes', 'category': 'api', 'evidence': ['api/app/main.py']},
    ],
  },
  'findings': [
    ...(fixtureReportJson['findings'] as List<dynamic>),
    {
      'id': 'no-ci',
      'category': 'repository_quality',
      'severity': 'medium',
      'title': 'No CI workflow found',
      'summary': 'No continuous integration configuration was found.',
      'evidence': ['.github/'],
      'affected_paths': <String>[],
      'confidence': 'medium',
      'recommendation': 'Add a CI workflow.',
      'why_it_matters': 'CI catches broken changes early.',
      'recommended_action': 'Add a CI workflow.',
    },
    {
      'id': 'tests-present',
      'category': 'testing',
      'severity': 'info',
      'title': 'Automated tests were found',
      'summary': 'A test directory exists.',
      'evidence': ['test/'],
      'affected_paths': <String>[],
      'confidence': 'high',
      'recommendation': '',
      'why_it_matters': '',
      'recommended_action': '',
    },
  ],
  'health_summary': {
    'total_findings': 3,
    'category_counts': {'security': 1, 'repository_quality': 1, 'testing': 1},
    'severity_counts': {'high': 1, 'medium': 1, 'info': 1},
    'overall': 'Static inspection only',
  },
  'dependencies': [
    {'name': 'http', 'version': '^1.3.0', 'ecosystem': 'pub', 'kind': 'runtime', 'source': 'pubspec.yaml'},
    {'name': 'flutter_test', 'version': 'sdk: flutter', 'ecosystem': 'pub', 'kind': 'dev', 'source': 'pubspec.yaml'},
  ],
};

final richReport = ProjectReport.fromJson(richReportJson);
