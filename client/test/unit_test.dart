import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

import 'package:github_repo_inspector/features/repository_inspection/data/models/project_report.dart';
import 'package:github_repo_inspector/features/repository_inspection/data/repository_url.dart';
import 'package:github_repo_inspector/features/repository_inspection/presentation/plain_language.dart';
import 'package:github_repo_inspector/features/repository_inspection/presentation/report_export.dart';

import 'fixture.dart';

void main() {
  group('RepositoryUrl.tryParse', () {
    const expected = 'https://github.com/owner/project';

    test('accepts the common ways people paste a repository', () {
      for (final input in const [
        'https://github.com/owner/project',
        'https://github.com/owner/project/',
        'https://github.com/owner/project.git',
        'https://github.com/owner/project/tree/main',
        'https://github.com/owner/project/blob/main/README.md',
        'https://www.github.com/owner/project',
        'http://github.com/owner/project',
        'github.com/owner/project',
        'owner/project',
        '  https://github.com/owner/project  ',
      ]) {
        expect(RepositoryUrl.tryParse(input)?.url, expected, reason: input);
      }
    });

    test('rejects anything that is not a GitHub repository', () {
      for (final input in const [
        '',
        'https://example.com/owner/project',
        'https://github.com/owner',
        'https://github.com',
        'github.com/owner',
        'not a url',
        'https://gitlab.com/owner/project',
      ]) {
        expect(RepositoryUrl.tryParse(input), isNull, reason: input);
      }
    });
  });

  group('plain language', () {
    test('score drops with severity and stays within 0-100', () {
      expect(healthScore(fixtureReport.healthSummary), 82);
      expect(healthScore(richReport.healthSummary), 74);
      final worst = ProjectReport.fromJson({
        ...fixtureReportJson,
        'health_summary': {
          'total_findings': 20,
          'category_counts': {'security': 20},
          'severity_counts': {'high': 20},
          'overall': 'bad',
        },
      });
      expect(healthScore(worst.healthSummary), 0);
    });

    test('verdicts and sentences are readable', () {
      expect(scoreVerdict(95), 'Looks healthy');
      expect(scoreVerdict(70), 'A few things to fix');
      expect(scoreVerdict(50), 'Needs attention');
      expect(scoreVerdict(10), 'Needs work');
      expect(scoreSentence(richReport.healthSummary), '2 things to look at: 1 to fix now, 1 worth fixing.');
      final clean = ProjectReport.fromJson({
        ...fixtureReportJson,
        'health_summary': {
          'total_findings': 0,
          'category_counts': <String, dynamic>{},
          'severity_counts': <String, dynamic>{},
          'overall': 'ok',
        },
      });
      expect(scoreSentence(clean.healthSummary), 'No problems were found in the files we looked at.');
    });

    test('joinNatural and describeProject', () {
      expect(joinNatural(['a']), 'a');
      expect(joinNatural(['a', 'b']), 'a and b');
      expect(joinNatural(['a', 'b', 'c']), 'a, b and c');
      expect(joinNatural(['a', 'b', 'c', 'd', 'e']), 'a, b, c, d and +1 more');
      expect(describeProject(fixtureReport), 'A Flutter application written in Dart, using Flutter.');
    });

    test('issues and notes are separated and ordered', () {
      expect(issuesOf(richReport).map((f) => f.title), ['Potential credential exposed', 'No CI workflow found']);
      expect(notesOf(richReport).map((f) => f.title), ['Automated tests were found']);
      expect(priorityLabel(priorityOf('high')), 'Fix now');
      expect(priorityLabel(priorityOf('info')), 'Good to know');
    });

    test('stars are pluralised and compacted', () {
      expect(starsLabel(1), '1 star');
      expect(starsLabel(2), '2 stars');
      expect(starsLabel(1200), '1.2k stars');
    });

    test('dependencies group by ecosystem, runtime first', () {
      final groups = groupDependencies(richReport.dependencies);
      expect(groups.keys, ['pub']);
      expect(groups['pub']!.map((d) => d.name), ['http', 'flutter_test']);
    });
  });

  group('export', () {
    test('summary is short and shareable', () {
      final text = reportToSummary(richReport);
      expect(text, contains('owner/project'));
      expect(text, contains('74/100'));
      expect(text, contains('[Fix now] Potential credential exposed'));
      expect(text.split('\n').length, lessThan(12));
    });

    test('markdown has the expected sections', () {
      final text = reportToMarkdown(richReport);
      for (final heading in ['# Repository report: owner/project', '## Summary', '## Issues', '## Good to know', '## Built with', '## Dependencies', '## What we could not check']) {
        expect(text, contains(heading));
      }
      expect(text, contains('| http | ^1.3.0 | pub | runtime |'));
      expect(reportToMarkdown(richReport), text);
    });

    test('JSON round-trips through the model', () {
      final decoded = jsonDecode(reportToJson(richReport)) as Map<String, dynamic>;
      final again = ProjectReport.fromJson(decoded);
      expect(again.repository.fullName, 'owner/project');
      expect(again.dependencies, hasLength(2));
      expect(again.findings, hasLength(3));
    });
  });

  group('bundled sample', () {
    test('parses and is the report of a local analysis', () {
      final text = File('assets/sample_report.json').readAsStringSync();
      final report = ProjectReport.fromJson(jsonDecode(text) as Map<String, dynamic>);
      expect(report.repository.isLocal, isTrue);
      expect(report.technologies.languages, isNotEmpty);
      expect(describeProject(report), isNotEmpty);
    });
  });
}
