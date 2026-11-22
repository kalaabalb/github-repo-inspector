import 'dart:math' as math;

import '../data/models/project_report.dart';

/// Turns raw report data into short, plain-English wording for the UI.
/// Pure Dart: no Flutter imports, so it is easy to unit-test.

enum Priority { fixNow, worthFixing, minor, goodToKnow }

Priority priorityOf(String severity) => switch (severity) {
  'high' => Priority.fixNow,
  'medium' => Priority.worthFixing,
  'low' => Priority.minor,
  _ => Priority.goodToKnow,
};

String priorityLabel(Priority priority) => switch (priority) {
  Priority.fixNow => 'Fix now',
  Priority.worthFixing => 'Worth fixing',
  Priority.minor => 'Minor',
  Priority.goodToKnow => 'Good to know',
};

/// Highest priority first.
int comparePriority(CodebaseFinding a, CodebaseFinding b) =>
    priorityOf(a.severity).index.compareTo(priorityOf(b.severity).index);

List<CodebaseFinding> issuesOf(ProjectReport report) =>
    report.findings.where((f) => priorityOf(f.severity) != Priority.goodToKnow).toList()
      ..sort(comparePriority);

List<CodebaseFinding> notesOf(ProjectReport report) =>
    report.findings.where((f) => priorityOf(f.severity) == Priority.goodToKnow).toList();

/// A 0-100 rough guide derived from finding severities. Not a guarantee.
/// Keep identical to `health_score` in api/app/services/markdown_export.py.
int healthScore(HealthSummary summary) {
  final high = summary.severityCounts['high'] ?? 0;
  final medium = summary.severityCounts['medium'] ?? 0;
  final low = summary.severityCounts['low'] ?? 0;
  return math.max(0, math.min(100, 100 - high * 18 - medium * 8 - low * 3));
}

String scoreVerdict(int score) {
  if (score >= 85) return 'Looks healthy';
  if (score >= 65) return 'A few things to fix';
  if (score >= 40) return 'Needs attention';
  return 'Needs work';
}

String _plural(int count, String singular, [String? plural]) =>
    count == 1 ? singular : (plural ?? '${singular}s');

/// One sentence explaining the score in terms of what to do.
String scoreSentence(HealthSummary summary) {
  final high = summary.severityCounts['high'] ?? 0;
  final medium = summary.severityCounts['medium'] ?? 0;
  final low = summary.severityCounts['low'] ?? 0;
  final total = high + medium + low;
  if (total == 0) {
    return 'No problems were found in the files we looked at.';
  }
  final parts = <String>[
    if (high > 0) '$high to fix now',
    if (medium > 0) '$medium worth fixing',
    if (low > 0) '$low minor',
  ];
  return '$total ${_plural(total, 'thing')} to look at: ${parts.join(', ')}.';
}

/// "a, b and c" (at most four names, then "+N more").
String joinNatural(List<String> items, {int max = 4}) {
  if (items.isEmpty) return '';
  final shown = items.take(max).toList();
  final extra = items.length - shown.length;
  if (extra > 0) shown.add('+$extra more');
  if (shown.length == 1) return shown.first;
  return '${shown.sublist(0, shown.length - 1).join(', ')} and ${shown.last}';
}

/// "a full-stack application", but keeps proper nouns such as "Flutter" intact.
String _withArticle(String phrase, Set<String> properNouns) {
  if (phrase.isEmpty) return phrase;
  final firstWord = phrase.split(RegExp(r'[\s/-]')).first.toLowerCase();
  final keepCase = properNouns.contains(firstWord);
  final text = keepCase ? phrase : phrase[0].toLowerCase() + phrase.substring(1);
  final article = 'aeiou'.contains(text[0].toLowerCase()) ? 'an' : 'a';
  return '$article $text';
}

/// "A full-stack application written in Dart and Python, using FastAPI and Flutter."
String describeProject(ProjectReport report) {
  final languages = report.technologies.languages.map((s) => s.name).toList();
  final frameworks = report.technologies.frameworks.map((s) => s.name).toList();
  final properNouns = {
    for (final name in [...languages, ...frameworks]) name.toLowerCase(),
  };
  final kind = _withArticle(report.overview.primaryClassification, properNouns);
  final buffer = StringBuffer(kind[0].toUpperCase() + kind.substring(1));
  if (languages.isNotEmpty) {
    buffer.write(' written in ${joinNatural(languages, max: 3)}');
  }
  if (frameworks.isNotEmpty) {
    buffer.write(languages.isNotEmpty ? ', using ' : ' using ');
    buffer.write(joinNatural(frameworks, max: 3));
  }
  buffer.write('.');
  return buffer.toString();
}

/// "Found: FastAPI routes" or "Not found".
String foundOrNot(List<DetectedSignal> signals) =>
    signals.isEmpty ? 'Not found' : joinNatural(signals.map((s) => s.name).toList());

String categoryName(String category) {
  final spaced = category.replaceAll('_', ' ');
  return spaced.isEmpty ? spaced : spaced[0].toUpperCase() + spaced.substring(1);
}

/// Ecosystem -> dependencies, runtime first, then dev, then optional.
Map<String, List<Dependency>> groupDependencies(List<Dependency> dependencies) {
  const kindOrder = {'runtime': 0, 'dev': 1, 'optional': 2};
  final groups = <String, List<Dependency>>{};
  for (final dependency in dependencies) {
    groups.putIfAbsent(dependency.ecosystem, () => <Dependency>[]).add(dependency);
  }
  for (final list in groups.values) {
    list.sort((a, b) {
      final byKind = (kindOrder[a.kind] ?? 3).compareTo(kindOrder[b.kind] ?? 3);
      return byKind != 0 ? byKind : a.name.compareTo(b.name);
    });
  }
  return groups;
}

String formatCount(int value) {
  if (value >= 1000000) return '${(value / 1000000).toStringAsFixed(1)}M';
  if (value >= 1000) return '${(value / 1000).toStringAsFixed(1)}k';
  return '$value';
}

/// "1 star", "2 stars", "1.2k stars".
String starsLabel(int stars) => '${formatCount(stars)} ${stars == 1 ? 'star' : 'stars'}';
