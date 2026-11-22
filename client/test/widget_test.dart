import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:github_repo_inspector/features/repository_inspection/data/models/ai_explanation.dart';
import 'package:github_repo_inspector/features/repository_inspection/data/models/project_report.dart';
import 'package:github_repo_inspector/features/repository_inspection/data/repository_api.dart';
import 'package:github_repo_inspector/features/repository_inspection/presentation/screens/inspection_screen.dart';
import 'package:github_repo_inspector/features/repository_inspection/presentation/state/inspection_controller.dart';
import 'package:github_repo_inspector/main.dart';

import 'fixture.dart';

class FakeRepositoryApi implements RepositoryApi {
  FakeRepositoryApi({
    this.shouldFail = false,
    this.aiAvailable = false,
    ProjectReport? report,
  }) : report = report ?? fixtureReport;

  final bool shouldFail;
  final bool aiAvailable;
  final ProjectReport report;
  int inspectCalls = 0;
  int explainCalls = 0;
  String? lastUrl;

  @override
  Future<ProjectReport> inspect(String repositoryUrl) async {
    inspectCalls++;
    lastUrl = repositoryUrl;
    await Future<void>.delayed(const Duration(milliseconds: 10));
    if (shouldFail) {
      throw const ApiException('Repository not found or not public.');
    }
    return report;
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

/// The landing background animates forever, so pumpAndSettle would never
/// finish. Advance time manually instead.
Future<void> settle(WidgetTester tester) async {
  for (var i = 0; i < 12; i++) {
    await tester.pump(const Duration(milliseconds: 200));
  }
}

void useScreen(
  WidgetTester tester, {
  double width = 1200,
  double height = 1800,
}) {
  tester.view.physicalSize = Size(width, height);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
}

Future<void> inspectUrl(WidgetTester tester, String url) async {
  await tester.enterText(find.byType(TextField), url);
  await tester.tap(find.text('Inspect repository'));
  await tester.pump();
}

Future<void> openTab(WidgetTester tester, String label) async {
  await tester.ensureVisible(find.text(label));
  await tester.pump();
  await tester.tap(find.text(label));
  await settle(tester);
}

Future<void> loadReport(WidgetTester tester, FakeRepositoryApi api) async {
  await tester.pumpWidget(RepositoryInspectorApp(api: api));
  await inspectUrl(tester, 'https://github.com/owner/project');
  await settle(tester);
}

void main() {
  testWidgets('validates the URL before calling the API', (tester) async {
    useScreen(tester);
    final api = FakeRepositoryApi();
    await tester.pumpWidget(RepositoryInspectorApp(api: api));

    await inspectUrl(tester, 'https://example.com/project');

    expect(find.textContaining('Enter a public GitHub URL'), findsOneWidget);
    expect(api.inspectCalls, 0);
  });

  testWidgets('accepts tree links and normalises them', (tester) async {
    useScreen(tester);
    final api = FakeRepositoryApi();
    await tester.pumpWidget(RepositoryInspectorApp(api: api));

    await inspectUrl(tester, 'github.com/owner/project/tree/main');
    await settle(tester);

    expect(api.lastUrl, 'https://github.com/owner/project');
  });

  testWidgets('shows progress, then a plain-language summary', (tester) async {
    useScreen(tester);
    final api = FakeRepositoryApi();
    await tester.pumpWidget(RepositoryInspectorApp(api: api));
    await inspectUrl(tester, 'https://github.com/owner/project');

    expect(find.text('Inspecting repository...'), findsOneWidget);
    expect(find.text('Finding the repository'), findsOneWidget);
    await settle(tester);

    expect(find.text('owner/project'), findsOneWidget);
    expect(
      find.text('A Flutter application written in Dart, using Flutter.'),
      findsOneWidget,
    );
    expect(find.text('A few things to fix'), findsOneWidget);
    expect(find.text('1 thing to look at: 1 to fix now.'), findsOneWidget);
    expect(find.text('Fix these first'), findsOneWidget);
    expect(find.text('Potential credential exposed'), findsOneWidget);
    expect(find.text('What looks good'), findsOneWidget);
    expect(api.explainCalls, 0);
  });

  testWidgets('issues tab filters by priority and expands details', (
    tester,
  ) async {
    useScreen(tester);
    final api = FakeRepositoryApi(report: richReport);
    await loadReport(tester, api);

    await openTab(tester, 'Issues');
    expect(find.text('Potential credential exposed'), findsOneWidget);
    expect(find.text('No CI workflow found'), findsOneWidget);
    expect(find.text('Good to know'), findsOneWidget);

    await tester.tap(find.text('Fix now  1'));
    await settle(tester);
    expect(find.text('Potential credential exposed'), findsOneWidget);
    expect(find.text('No CI workflow found'), findsNothing);

    await tester.tap(find.text('Potential credential exposed'));
    await settle(tester);
    expect(find.text('WHY IT MATTERS'), findsOneWidget);
    expect(
      find.text('Credentials in source can expose access.'),
      findsOneWidget,
    );
  });

  testWidgets('tech tab explains the stack and dependencies', (tester) async {
    useScreen(tester);
    final api = FakeRepositoryApi(report: richReport);
    await loadReport(tester, api);

    await openTab(tester, 'Tech');
    expect(find.text('Built with'), findsOneWidget);
    expect(find.text('What it includes'), findsOneWidget);
    expect(find.text('FastAPI routes'), findsOneWidget);
    expect(find.text('2 packages declared'), findsOneWidget);
    expect(find.text('pub'), findsOneWidget);
  });

  testWidgets('details tab keeps the technical material', (tester) async {
    useScreen(tester);
    final api = FakeRepositoryApi();
    await loadReport(tester, api);

    await openTab(tester, 'Details');
    expect(find.text('How this report was made'), findsOneWidget);
    expect(find.text('What we could not check'), findsOneWidget);
    expect(find.text('Files we read'), findsOneWidget);
    expect(find.text('Project layout'), findsOneWidget);
    expect(find.text('Everything we detected'), findsOneWidget);
    expect(find.text('Code was not executed.'), findsNothing);
    await tester.tap(find.text('How this report was made'));
    await settle(tester);
    expect(find.text('Code was not executed.'), findsOneWidget);
  });

  testWidgets('share menu copies a summary, Markdown and JSON', (tester) async {
    useScreen(tester);
    final copied = <String>[];
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      (call) async {
        if (call.method == 'Clipboard.setData') {
          copied.add((call.arguments as Map)['text'] as String);
        }
        return null;
      },
    );
    addTearDown(
      () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        null,
      ),
    );
    final api = FakeRepositoryApi();
    await loadReport(tester, api);

    for (final item in [
      'Copy short summary',
      'Copy as Markdown',
      'Copy as JSON',
    ]) {
      await tester.tap(find.byTooltip('Share or copy this report'));
      await settle(tester);
      await tester.tap(find.text(item));
      await settle(tester);
    }

    expect(copied, hasLength(3));
    expect(copied[0], contains('owner/project'));
    expect(copied[0], contains('82/100'));
    expect(copied[1], contains('# Repository report: owner/project'));
    expect(
      (jsonDecode(copied[2])
          as Map<String, dynamic>)['repository']['full_name'],
      'owner/project',
    );
    expect(find.text('Copied the report as JSON'), findsOneWidget);
  });

  testWidgets('inspect another repository returns to the start screen', (
    tester,
  ) async {
    useScreen(tester);
    final api = FakeRepositoryApi();
    await loadReport(tester, api);
    expect(find.text('Fix these first'), findsOneWidget);

    await tester.tap(find.byTooltip('Inspect another repository'));
    await settle(tester);

    expect(find.text('Fix these first'), findsNothing);
    expect(find.text('Inspect repository'), findsOneWidget);
  });

  testWidgets('shows API errors without raw response bodies', (tester) async {
    useScreen(tester);
    final api = FakeRepositoryApi(shouldFail: true);
    await loadReport(tester, api);

    expect(find.text('Repository not found or not public.'), findsOneWidget);
    expect(find.textContaining('Exception'), findsNothing);
  });

  testWidgets('the sample report opens without any API call', (tester) async {
    useScreen(tester);
    final api = FakeRepositoryApi();
    final controller = InspectionController(
      api,
      sampleLoader: () async => jsonEncode(fixtureReportJson),
    );
    await tester.pumpWidget(
      MaterialApp(home: InspectionScreen(controller: controller)),
    );

    await tester.tap(find.text('Try a sample report'));
    await settle(tester);

    expect(find.text('owner/project'), findsOneWidget);
    expect(api.inspectCalls, 0);
  });

  testWidgets('a broken sample shows a clear message', (tester) async {
    useScreen(tester);
    final controller = InspectionController(
      FakeRepositoryApi(),
      sampleLoader: () async => throw StateError('missing asset'),
    );
    await tester.pumpWidget(
      MaterialApp(home: InspectionScreen(controller: controller)),
    );

    await tester.tap(find.text('Try a sample report'));
    await settle(tester);

    expect(find.text('The sample report could not be loaded.'), findsOneWidget);
  });

  testWidgets('AI is only called after an explicit action', (tester) async {
    useScreen(tester);
    final api = FakeRepositoryApi();
    await loadReport(tester, api);
    expect(api.explainCalls, 0);

    await tester.ensureVisible(find.text('Explain this report with AI'));
    await tester.tap(find.text('Explain this report with AI'));
    await settle(tester);

    expect(api.explainCalls, 1);
    expect(find.text('AI is unavailable in this test.'), findsOneWidget);
  });

  testWidgets('renders a structured AI explanation', (tester) async {
    useScreen(tester);
    final api = FakeRepositoryApi(aiAvailable: true);
    await loadReport(tester, api);

    await tester.ensureVisible(find.text('Explain this report with AI'));
    await tester.tap(find.text('Explain this report with AI'));
    await settle(tester);

    expect(find.text('Structured explanation'), findsOneWidget);
    expect(find.text('AI explanation'), findsOneWidget);
  });

  testWidgets('every tab fits a 400px wide screen', (tester) async {
    useScreen(tester, width: 400, height: 900);
    final api = FakeRepositoryApi(report: richReport);
    await loadReport(tester, api);
    expect(tester.takeException(), isNull);

    for (final tab in ['Issues', 'Tech', 'Details', 'Summary']) {
      await openTab(tester, tab);
      expect(tester.takeException(), isNull, reason: 'overflow on $tab');
    }
  });

  testWidgets('the landing screen fits a 400px wide screen', (tester) async {
    useScreen(tester, width: 400, height: 800);
    await tester.pumpWidget(RepositoryInspectorApp(api: FakeRepositoryApi()));
    await settle(tester);
    expect(tester.takeException(), isNull);
  });

  testWidgets('screen readers get the score and tab names', (tester) async {
    useScreen(tester);
    final handle = tester.ensureSemantics();
    final api = FakeRepositoryApi();
    await loadReport(tester, api);

    expect(find.bySemanticsLabel('Health score 82 out of 100'), findsOneWidget);
    expect(find.bySemanticsLabel('Tests: found'), findsOneWidget);
    expect(find.bySemanticsLabel('Docs: not found'), findsOneWidget);
    expect(find.byTooltip('Inspect another repository'), findsOneWidget);
    expect(find.byTooltip('Share or copy this report'), findsOneWidget);
    handle.dispose();
  });
}
