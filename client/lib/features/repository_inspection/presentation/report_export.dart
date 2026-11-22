import 'dart:convert';

import '../data/models/project_report.dart';
import 'plain_language.dart';

/// Text exports of a report, used by the Share menu. Pure Dart.

String reportToJson(ProjectReport report) =>
    const JsonEncoder.withIndent('  ').convert(report.toJson());

/// A short, paste-anywhere summary (chat, issue, README).
String reportToSummary(ProjectReport report) {
  final score = healthScore(report.healthSummary);
  final issues = issuesOf(report);
  final lines = <String>[
    report.repository.fullName,
    describeProject(report),
    'Health: $score/100 (${scoreVerdict(score)}). ${scoreSentence(report.healthSummary)}',
  ];
  if (issues.isNotEmpty) {
    lines.add('');
    lines.add('Look at first:');
    for (final issue in issues.take(3)) {
      lines.add('- [${priorityLabel(priorityOf(issue.severity))}] ${issue.title}');
    }
  }
  lines.add('');
  lines.add('Rough guide from automatic, read-only checks. Code was never run.');
  return lines.join('\n');
}

String _cell(String? value) =>
    (value == null || value.isEmpty ? '-' : value).replaceAll('|', r'\|').replaceAll('\n', ' ');

List<String> _bullets(List<String> items, {String empty = '_None._'}) =>
    items.isEmpty ? [empty] : items.map((item) => '- $item').toList();

/// A readable Markdown document. Mirrors api/app/services/markdown_export.py.
String reportToMarkdown(ProjectReport report) {
  final repo = report.repository;
  final score = healthScore(report.healthSummary);
  final lines = <String>['# Repository report: ${repo.fullName}', ''];
  if (repo.description != null && repo.description!.isNotEmpty) {
    lines.addAll(['> ${repo.description}', '']);
  }
  if (repo.isLocal) {
    lines.addAll(['_Source: local analysis (folder or ZIP). GitHub details are not available._', '']);
  } else {
    lines.addAll(['<${repo.htmlUrl}>', '']);
  }

  lines.addAll([
    '## Summary',
    '',
    describeProject(report),
    '',
    '| | |',
    '| --- | --- |',
    '| Health | $score/100 - ${scoreVerdict(score)} |',
    '| Findings | ${report.healthSummary.totalFindings} |',
  ]);
  if (!repo.isLocal) {
    lines.add('| Stars / forks | ${repo.stars} / ${repo.forks} |');
  }
  lines.addAll([
    '',
    '_The score is a rough guide from automatic checks, not a guarantee of quality._',
    '',
    '## Issues',
    '',
  ]);
  final issues = issuesOf(report);
  if (issues.isEmpty) lines.addAll(['No problems were found in the files we looked at.', '']);
  for (final issue in issues) {
    lines.addAll(['### [${priorityLabel(priorityOf(issue.severity))}] ${issue.title}', '']);
    lines.addAll([issue.summary, '']);
    if (issue.whyItMatters.isNotEmpty) {
      lines.addAll(['**Why it matters:** ${issue.whyItMatters}', '']);
    }
    final action = issue.recommendedAction.isNotEmpty ? issue.recommendedAction : issue.recommendation;
    if (action.isNotEmpty) lines.addAll(['**What to do:** $action', '']);
    lines.addAll(['Where:', '']);
    lines.addAll(issue.evidence.map((item) => '- `$item`'));
    lines.add('');
  }

  final notes = notesOf(report);
  if (notes.isNotEmpty) {
    lines.addAll(['## Good to know', '']);
    lines.addAll(notes.map((note) => '- ${note.title}'));
    lines.add('');
  }

  final tech = report.technologies;
  lines.addAll(['## Built with', '']);
  lines.add('**Languages:** ${_names(tech.languages)}');
  lines.add('**Frameworks:** ${_names(tech.frameworks)}');
  lines.add('**Tools:** ${_names(tech.packageManagers)}');
  lines.add('**API:** ${foundOrNot(report.apiSignals)}');
  lines.add('**Login / users:** ${foundOrNot(report.authenticationSignals)}');
  lines.add('**Database:** ${foundOrNot(report.databaseSignals)}');
  lines.add('');

  if (report.dependencies.isNotEmpty) {
    lines.addAll([
      '## Dependencies',
      '',
      '| Name | Version | Ecosystem | Kind | Declared in |',
      '| --- | --- | --- | --- | --- |',
    ]);
    final groups = groupDependencies(report.dependencies);
    for (final ecosystem in groups.keys.toList()..sort()) {
      for (final d in groups[ecosystem]!) {
        lines.add('| ${_cell(d.name)} | ${_cell(d.version)} | ${d.ecosystem} | ${d.kind} | `${d.source}` |');
      }
    }
    lines.addAll(['', '_Declared only. Nothing was installed and no vulnerability database was checked._', '']);
  }

  final structure = report.projectStructure;
  lines.addAll(['## Project essentials', '']);
  lines.add('- [${structure.hasTests ? 'x' : ' '}] Tests');
  lines.add('- [${structure.hasDocs ? 'x' : ' '}] Documentation');
  lines.add('- [${structure.hasCi ? 'x' : ' '}] CI');
  lines.add('- [${structure.hasDocker ? 'x' : ' '}] Docker');
  lines.add('- [${structure.hasEnvironmentExample ? 'x' : ' '}] Environment example');
  lines.add('');

  final trust = report.trustContext;
  lines.addAll(['## What we could not check', '']);
  lines.addAll(_bullets([...trust.notVerified, ...trust.limitations], empty: '_Nothing reported._'));
  lines.addAll(['', '**Runtime:** ${trust.runtimeStatus}', '']);
  if (report.limitations.notes.isNotEmpty) {
    lines.addAll(['## Limits of this report', '']);
    lines.addAll(_bullets(report.limitations.notes));
    lines.add('');
  }
  lines.addAll(['---', '_Generated by Repo Inspector (read-only; code was never run)._', '']);
  return lines.join('\n');
}

String _names(List<DetectedSignal> signals) =>
    signals.isEmpty ? 'none detected' : signals.map((s) => s.name).join(', ');
