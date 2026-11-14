import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:github_repo_inspector/features/repository_inspection/data/models/ai_explanation.dart';
import 'package:github_repo_inspector/features/repository_inspection/data/models/project_report.dart';
import 'package:github_repo_inspector/features/repository_inspection/data/repository_api.dart';
import 'package:github_repo_inspector/features/repository_inspection/presentation/screens/inspection_screen.dart';
import 'package:github_repo_inspector/features/repository_inspection/presentation/state/inspection_controller.dart';
import 'package:github_repo_inspector/main.dart';

class FakeRepositoryApi implements RepositoryApi {
  FakeRepositoryApi({this.shouldFail = false, this.aiAvailable = false});

  final bool shouldFail;
  final bool aiAvailable;
  int inspectCalls = 0;
  int explainCalls = 0;

  @override
  Future<ProjectReport> inspect(String repositoryUrl) async {
    inspectCalls++;
    await Future<void>.delayed(const Duration(milliseconds: 10));
    if (shouldFail) {
      throw const ApiException('Repository not found or not public.');
    }
    return fixtureReport;
  }

  @override
  Future<AiExplanationResponse> explain(ProjectReport report) async {
    explainCalls++;
    if (aiAvailable) {
      return const AiExplanationResponse(
        available: true,
        provider: 'fake',
        model: 'fake-model',
        explanation: AiExplanation(
          summary: 'Structured explanation',
          howItWorks: ['The report is explained from evidence.'],
          architectureExplanation: [],
          technologyExplanations: [],
          apiExplanation: null,
          authenticationExplanation: null,
          dataExplanation: null,
          learningRoadmap: [],
          interviewQuestions: [],
          uncertainties: [],
        ),
        reason: null,
      );
    }
    return const AiExplanationResponse(
      available: false,
      provider: 'fake',
      model: 'fake-model',
      explanation: null,
      reason: 'AI is unavailable in this test.',
    );
  }
}

void main() {
  testWidgets('validates URL before calling the API', (tester) async {
    final api = FakeRepositoryApi();
    await tester.pumpWidget(RepositoryInspectorApp(api: api));

    await tester.enterText(
      find.byType(TextField),
      'https://example.com/project',
    );
    await tester.tap(find.text('Inspect repository'));
    await tester.pump();

    expect(find.textContaining('Enter a public GitHub URL'), findsOneWidget);
    expect(api.inspectCalls, 0);
  });

  testWidgets('shows loading and renders a deterministic report', (
    tester,
  ) async {
    final api = FakeRepositoryApi();
    await tester.pumpWidget(RepositoryInspectorApp(api: api));
    await tester.enterText(
      find.byType(TextField),
      'https://github.com/owner/project',
    );
    await tester.tap(find.text('Inspect repository'));
    await tester.pump();
    expect(find.text('Inspecting repository...'), findsOneWidget);
    await tester.pumpAndSettle();

    expect(find.text('owner/project'), findsOneWidget);
    expect(find.text('Flutter application'), findsOneWidget);
    expect(find.text('0 stars'), findsOneWidget);
    await tester.tap(find.text('Stack'));
    await tester.pumpAndSettle();
    expect(find.text('Technology stack'), findsOneWidget);
    await tester.tap(find.text('Health'));
    await tester.pumpAndSettle();
    expect(find.text('Codebase health'), findsOneWidget);
    expect(find.text('Potential credential exposed'), findsAtLeastNWidgets(1));
    await tester.tap(find.text('Evidence').first);
    await tester.pumpAndSettle();
    expect(find.text('Evidence'), findsNWidgets(2));
    expect(api.inspectCalls, 1);
    expect(api.explainCalls, 0);
  });

  testWidgets('renders API errors without raw response bodies', (tester) async {
    final api = FakeRepositoryApi(shouldFail: true);
    await tester.pumpWidget(RepositoryInspectorApp(api: api));
    await tester.enterText(
      find.byType(TextField),
      'https://github.com/owner/project',
    );
    await tester.tap(find.text('Inspect repository'));
    await tester.pumpAndSettle();

    expect(find.text('Repository not found or not public.'), findsOneWidget);
    expect(find.textContaining('Exception'), findsNothing);
  });

  testWidgets('narrow report has no overflow and can return to start', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(400, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final api = FakeRepositoryApi();
    await tester.pumpWidget(RepositoryInspectorApp(api: api));
    expect(tester.takeException(), isNull, reason: 'landing screen');
    await tester.enterText(
      find.byType(TextField),
      'https://github.com/owner/project',
    );
    await tester.tap(find.text('Inspect repository'));
    await tester.pumpAndSettle();
    final layoutException = tester.takeException();
    expect(layoutException, isNull, reason: 'report screen: $layoutException');
    await tester.tap(find.byTooltip('Inspect another repository'));
    await tester.pumpAndSettle();
    expect(find.text('Inspect the codebase.'), findsOneWidget);
    expect(
      tester.widget<TextField>(find.byType(TextField)).controller!.text,
      isEmpty,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'AI is called only after explicit action and unavailable state renders',
    (tester) async {
      final api = FakeRepositoryApi();
      final controller = InspectionController(api);
      await tester.pumpWidget(
        MaterialApp(home: InspectionScreen(controller: controller)),
      );
      await tester.enterText(
        find.byType(TextField),
        'https://github.com/owner/project',
      );
      await tester.tap(find.text('Inspect repository'));
      await tester.pumpAndSettle();
      expect(api.explainCalls, 0);

      await tester.ensureVisible(find.text('AI insights'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('AI insights'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Explain this report with AI'));
      await tester.pumpAndSettle();
      expect(api.explainCalls, 1);
      expect(find.text('AI is unavailable in this test.'), findsOneWidget);
    },
  );

  testWidgets('renders a structured AI explanation after explicit action', (
    tester,
  ) async {
    final api = FakeRepositoryApi(aiAvailable: true);
    final controller = InspectionController(api);
    await tester.pumpWidget(
      MaterialApp(home: InspectionScreen(controller: controller)),
    );
    await tester.enterText(
      find.byType(TextField),
      'https://github.com/owner/project',
    );
    await tester.tap(find.text('Inspect repository'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('AI insights'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('AI insights'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Explain this report with AI'));
    await tester.pumpAndSettle();
    expect(find.text('Structured explanation'), findsOneWidget);
    expect(find.text('AI explanation'), findsOneWidget);
  });

  test('parses report metadata, technology, evidence, and limitations', () {
    final report = ProjectReport.fromJson(fixtureReportJson);
    expect(report.repository.fullName, 'owner/project');
    expect(report.technologies.frameworks.single.name, 'Flutter');
    expect(report.evidence.single.evidence, ['pubspec.yaml', 'lib/']);
    expect(report.limitations.hasLimitations, isTrue);
  });
}

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
