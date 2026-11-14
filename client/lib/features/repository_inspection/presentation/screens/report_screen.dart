import 'package:flutter/material.dart';

import '../../data/models/ai_explanation.dart';
import '../../data/models/project_report.dart';
import '../state/inspection_controller.dart';

class ReportScreen extends StatelessWidget {
  const ReportScreen({super.key, required this.controller});

  final InspectionController controller;

  @override
  Widget build(BuildContext context) {
    final report = controller.report!;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Technical report'),
        actions: [
          IconButton(
            tooltip: 'Inspect another repository',
            onPressed: () => controller.report = null,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: AnimatedBuilder(
        animation: controller,
        builder: (context, _) => SelectionArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 48),
            children: [
              _RepositoryHeader(report: report),
              const SizedBox(height: 18),
              _ReportSection(
                title: 'Overview',
                icon: Icons.dashboard_outlined,
                child: _Overview(report: report),
              ),
              _ReportSection(
                title: 'Evidence boundaries',
                icon: Icons.fact_check_outlined,
                child: _TrustContext(report: report),
              ),
              _ReportSection(
                title: 'Repository purpose',
                icon: Icons.description_outlined,
                child: _Purpose(report: report),
              ),
              _ReportSection(
                title: 'Source inspection',
                icon: Icons.code_outlined,
                child: _SourceInspection(report: report),
              ),
              _ReportSection(
                title: 'Technology stack',
                icon: Icons.layers_outlined,
                child: _TechnologyStack(report: report),
              ),
              _ReportSection(
                title: 'Codebase health',
                icon: Icons.health_and_safety_outlined,
                child: _Health(report: report),
              ),
              _ReportSection(
                title: 'Architecture assessment',
                icon: Icons.account_tree_outlined,
                child: _Architecture(report: report),
              ),
              _ReportSection(
                title: 'Security signals',
                icon: Icons.shield_outlined,
                child: _FindingList(
                  findings: report.findings
                      .where((finding) => finding.category == 'security')
                      .toList(),
                  empty: 'No conservative security signals detected.',
                ),
              ),
              _ReportSection(
                title: 'Configuration risks',
                icon: Icons.settings_outlined,
                child: _FindingList(
                  findings: report.findings
                      .where((finding) => finding.category == 'configuration')
                      .toList(),
                  empty: 'No configuration risks detected in inspected content.',
                ),
              ),
              _ReportSection(
                title: 'Testing & CI',
                icon: Icons.fact_check_outlined,
                child: _FindingList(
                  findings: report.findings
                      .where((finding) => finding.category == 'testing')
                      .toList(),
                  empty: 'No testing or CI findings were emitted.',
                ),
              ),
              _ReportSection(
                title: 'Release readiness',
                icon: Icons.rocket_launch_outlined,
                child: _FindingList(
                  findings: report.findings
                      .where((finding) =>
                          finding.category == 'release' ||
                          finding.category == 'repository_quality')
                      .toList(),
                  empty: 'No repository-quality readiness findings were emitted.',
                ),
              ),
              _ReportSection(
                title: 'API',
                icon: Icons.api_outlined,
                child: _SignalList(
                  signals: report.apiSignals,
                  empty: 'No API signals detected.',
                ),
              ),
              _ReportSection(
                title: 'Authentication',
                icon: Icons.lock_outline_rounded,
                child: _SignalList(
                  signals: report.authenticationSignals,
                  empty: 'No authentication signals detected.',
                ),
              ),
              _ReportSection(
                title: 'Data / databases',
                icon: Icons.storage_outlined,
                child: _SignalList(
                  signals: report.databaseSignals,
                  empty: 'No database signals detected.',
                ),
              ),
              _ReportSection(
                title: 'Project structure',
                icon: Icons.folder_open_outlined,
                child: _Structure(report: report),
              ),
              _ReportSection(
                title: 'Evidence',
                icon: Icons.fact_check_outlined,
                child: _SignalList(
                  signals: report.evidence,
                  empty: 'No deterministic signals detected.',
                ),
              ),
              if (report.limitations.hasLimitations)
                _Limitations(report: report),
              const SizedBox(height: 6),
              _AiAction(controller: controller),
              if (controller.aiResponse != null)
                _AiResult(response: controller.aiResponse!),
              if (controller.errorMessage != null &&
                  controller.status != InspectionStatus.error)
                _InlineError(message: controller.errorMessage!),
            ],
          ),
        ),
      ),
    );
  }
}

class _RepositoryHeader extends StatelessWidget {
  const _RepositoryHeader({required this.report});

  final ProjectReport report;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            report.repository.fullName,
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          Text(
            report.repository.description ??
                'No repository description provided.',
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _Badge(
                label: report.overview.primaryClassification,
                highlighted: true,
              ),
              _Badge(label: '${report.repository.stars} stars'),
              _Badge(label: '${report.repository.forks} forks'),
              _Badge(label: 'branch: ${report.repository.defaultBranch}'),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            report.repository.htmlUrl,
            style: const TextStyle(
              fontFamily: 'monospace',
              color: Color(0xFFFFB454),
            ),
          ),
        ],
      ),
    ),
  );
}

class _Overview extends StatelessWidget {
  const _Overview({required this.report});

  final ProjectReport report;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        'Detected as ${report.overview.primaryClassification}.',
        style: Theme.of(context).textTheme.bodyLarge,
      ),
      if (report.overview.classifications.length > 1) ...[
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: report.overview.classifications
              .skip(1)
              .map((item) => _Badge(label: item))
              .toList(),
        ),
      ],
      const SizedBox(height: 12),
      _BulletList(items: report.overview.classificationBasis),
    ],
  );
}

class _Purpose extends StatelessWidget {
  const _Purpose({required this.report});

  final ProjectReport report;

  @override
  Widget build(BuildContext context) {
    final findings = report.findings
        .where((finding) =>
            finding.category == 'documentation' && finding.id.startsWith('purpose_'))
        .toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Detected as ${report.overview.primaryClassification}.'),
        const SizedBox(height: 8),
        _BulletList(items: report.overview.classificationBasis),
        if (findings.isNotEmpty) ...[
          const SizedBox(height: 12),
          Text('Purpose consistency', style: Theme.of(context).textTheme.titleSmall),
          _FindingList(findings: findings, empty: ''),
        ],
      ],
    );
  }
}

class _Health extends StatelessWidget {
  const _Health({required this.report});

  final ProjectReport report;

  @override
  Widget build(BuildContext context) {
    const categories = [
      'security',
      'documentation',
      'testing',
      'maintainability',
      'repository_quality',
      'configuration',
      'architecture',
      'dependencies',
      'release',
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('CODEBASE HEALTH', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 6),
        Text('${report.healthSummary.totalFindings} findings'),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: ['high', 'medium', 'low', 'info']
              .map(
                (severity) => _Badge(
                  label:
                      '$severity: ${report.healthSummary.severityCounts[severity] ?? 0}',
                ),
              )
              .toList(),
        ),
        const SizedBox(height: 12),
        Text(report.healthSummary.overall),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: categories
              .map(
                (category) => _Badge(
                  label:
                      '${_categoryLabel(category)}: ${report.healthSummary.categoryCounts[category] ?? 0}',
                ),
              )
              .toList(),
        ),
        const SizedBox(height: 12),
        if (report.findings.isEmpty)
          const Text(
            'No static findings were emitted for the inspected evidence.',
          )
        else
          Column(
            children: report.findings
                .map((finding) => _FindingTile(finding: finding))
                .toList(),
          ),
      ],
    );
  }
}

class _FindingTile extends StatelessWidget {
  const _FindingTile({required this.finding});

  final CodebaseFinding finding;

  @override
  Widget build(BuildContext context) {
    final color = _severityColor(finding.severity);
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      childrenPadding: const EdgeInsets.only(bottom: 12),
      leading: Icon(_severityIcon(finding.severity), color: color),
      title: Text(finding.title),
      subtitle: Text(
        '${_findingStatus(finding)} • ${finding.severity} severity • ${finding.category} • ${finding.confidence} confidence',
      ),
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'What we found',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 4),
              Text(finding.summary),
              if (finding.whyItMatters.isNotEmpty) ...[
                const SizedBox(height: 10),
                Text(
                  'Why it matters',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                const SizedBox(height: 4),
                Text(finding.whyItMatters),
              ],
              const SizedBox(height: 10),
              Text('Evidence', style: Theme.of(context).textTheme.titleSmall),
              _PathList(items: finding.evidence),
              if (finding.affectedPaths.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  'Affected paths',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                _PathList(items: finding.affectedPaths),
              ],
              const SizedBox(height: 8),
              Text(
                'Recommended action',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 4),
              Text(
                finding.recommendedAction.isEmpty
                    ? finding.recommendation
                    : finding.recommendedAction,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _FindingList extends StatelessWidget {
  const _FindingList({required this.findings, required this.empty});

  final List<CodebaseFinding> findings;
  final String empty;

  @override
  Widget build(BuildContext context) => findings.isEmpty
      ? Text(empty)
      : Column(
          children: findings
              .map((finding) => _FindingTile(finding: finding))
              .toList(),
        );
}

class _SourceInspection extends StatelessWidget {
  const _SourceInspection({required this.report});

  final ProjectReport report;

  @override
  Widget build(BuildContext context) {
    final source = report.sourceInspection;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('SOURCE INSPECTION'),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            _Badge(label: '${source.filesInspected} files inspected'),
            _Badge(label: '${source.filesSkipped} files skipped'),
            _Badge(label: '${source.filesTruncated} files truncated'),
          ],
        ),
        if (source.notes.isNotEmpty) ...[
          const SizedBox(height: 10),
          _BulletList(items: source.notes),
        ],
        const SizedBox(height: 8),
        Text(
          'Source is treated as untrusted text. Repository code was not executed and raw source is not shown here.',
        ),
      ],
    );
  }
}

class _TrustContext extends StatelessWidget {
  const _TrustContext({required this.report});

  final ProjectReport report;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      _TrustGroup(
        title: 'Verified / detected',
        items: report.trustContext.verifiedDetected,
      ),
      _TrustGroup(
        title: 'Potential issues',
        items: report.trustContext.potentialIssues,
      ),
      _TrustGroup(
        title: 'Not verified',
        items: report.trustContext.notVerified,
      ),
      _TrustGroup(title: 'Limitations', items: report.trustContext.limitations),
      const SizedBox(height: 8),
      Text('Runtime status', style: Theme.of(context).textTheme.titleSmall),
      const SizedBox(height: 4),
      Text(report.trustContext.runtimeStatus),
    ],
  );
}

class _TrustGroup extends StatelessWidget {
  const _TrustGroup({required this.title, required this.items});

  final String title;
  final List<String> items;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: 4),
        _BulletList(items: items.isEmpty ? ['None reported.'] : items),
      ],
    ),
  );
}

String _categoryLabel(String category) => category.replaceAll('_', ' ');

String _findingStatus(CodebaseFinding finding) {
  if (finding.category == 'documentation' &&
      (finding.id.contains('unverified') || finding.id.contains('not_detected'))) {
    return 'Not verified';
  }
  return finding.severity == 'info' ? 'Verified / detected' : 'Potential';
}

Color _severityColor(String severity) => switch (severity) {
  'high' => const Color(0xFFFF8E7D),
  'medium' => const Color(0xFFFFC978),
  _ => const Color(0xFF9DB8C2),
};

IconData _severityIcon(String severity) => switch (severity) {
  'high' => Icons.warning_amber_rounded,
  'medium' => Icons.priority_high_rounded,
  _ => Icons.info_outline_rounded,
};

class _TechnologyStack extends StatelessWidget {
  const _TechnologyStack({required this.report});

  final ProjectReport report;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      _SignalGroup(title: 'Languages', signals: report.technologies.languages),
      _SignalGroup(
        title: 'Frameworks',
        signals: report.technologies.frameworks,
      ),
      _SignalGroup(
        title: 'Package managers',
        signals: report.technologies.packageManagers,
      ),
    ],
  );
}

class _Architecture extends StatelessWidget {
  const _Architecture({required this.report});

  final ProjectReport report;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        'Observed structure',
        style: Theme.of(context).textTheme.titleMedium,
      ),
      const SizedBox(height: 8),
      _PathList(items: report.architecture.observedStructure),
      const SizedBox(height: 14),
      Text(
        'Deterministic interpretation',
        style: Theme.of(context).textTheme.titleMedium,
      ),
      const SizedBox(height: 8),
      _BulletList(items: report.architecture.interpretations),
    ],
  );
}

class _Structure extends StatelessWidget {
  const _Structure({required this.report});

  final ProjectReport report;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      _FactRow(label: 'Tests', value: report.projectStructure.hasTests),
      _FactRow(label: 'Documentation', value: report.projectStructure.hasDocs),
      _FactRow(label: 'CI', value: report.projectStructure.hasCi),
      _FactRow(label: 'Docker', value: report.projectStructure.hasDocker),
      _FactRow(
        label: 'Environment example',
        value: report.projectStructure.hasEnvironmentExample,
      ),
      const SizedBox(height: 12),
      Text(
        'Important directories',
        style: Theme.of(context).textTheme.titleMedium,
      ),
      _PathList(items: report.projectStructure.importantDirectories),
      const SizedBox(height: 10),
      Text(
        'Configuration files',
        style: Theme.of(context).textTheme.titleMedium,
      ),
      _PathList(items: report.projectStructure.configurationFiles),
    ],
  );
}

class _SignalList extends StatelessWidget {
  const _SignalList({required this.signals, required this.empty});

  final List<DetectedSignal> signals;
  final String empty;

  @override
  Widget build(BuildContext context) => signals.isEmpty
      ? Text(empty)
      : Column(
          children: signals
              .map((signal) => _EvidenceTile(signal: signal))
              .toList(),
        );
}

class _SignalGroup extends StatelessWidget {
  const _SignalGroup({required this.title, required this.signals});

  final String title;
  final List<DetectedSignal> signals;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 14),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        if (signals.isEmpty)
          const Text('None detected.')
        else
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: signals
                .map((signal) => _Badge(label: signal.name))
                .toList(),
          ),
      ],
    ),
  );
}

class _EvidenceTile extends StatelessWidget {
  const _EvidenceTile({required this.signal});

  final DetectedSignal signal;

  @override
  Widget build(BuildContext context) => ExpansionTile(
    tilePadding: EdgeInsets.zero,
    childrenPadding: const EdgeInsets.only(bottom: 10),
    title: LayoutBuilder(
      builder: (context, constraints) {
        final badge = _Badge(label: signal.category);
        if (constraints.maxWidth < 240) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(signal.name, softWrap: true),
              const SizedBox(height: 4),
              badge,
            ],
          );
        }
        return Row(
          children: [
            Expanded(child: Text(signal.name, softWrap: true)),
            const SizedBox(width: 8),
            badge,
          ],
        );
      },
    ),
    subtitle: const Text('View evidence'),
    children: [
      Align(
        alignment: Alignment.centerLeft,
        child: _PathList(items: signal.evidence),
      ),
    ],
  );
}

class _Limitations extends StatelessWidget {
  const _Limitations({required this.report});

  final ProjectReport report;

  @override
  Widget build(BuildContext context) => Card(
    color: const Color(0xFF30271B),
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.info_outline_rounded,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(width: 8),
              Text(
                'Analysis limitations',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ],
          ),
          const SizedBox(height: 10),
          _BulletList(
            items: report.limitations.notes.isEmpty
                ? ['The repository was only partially analyzed.']
                : report.limitations.notes,
          ),
        ],
      ),
    ),
  );
}

class _AiAction extends StatelessWidget {
  const _AiAction({required this.controller});

  final InspectionController controller;

  @override
  Widget build(BuildContext context) {
    final working = controller.status == InspectionStatus.explaining;
    return OutlinedButton.icon(
      onPressed: working ? null : controller.explain,
      icon: working
          ? const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : const Icon(Icons.auto_awesome_outlined),
      label: Text(
        working ? 'Explaining report...' : 'Explain this report with AI',
      ),
    );
  }
}

class _AiResult extends StatelessWidget {
  const _AiResult({required this.response});

  final AiExplanationResponse response;

  @override
  Widget build(BuildContext context) {
    if (!response.available || response.explanation == null) {
      return _InlineError(
        message: response.reason ?? 'AI explanation is unavailable.',
      );
    }
    final explanation = response.explanation!;
    return Column(
      children: [
        _ReportSection(
          title: 'AI explanation',
          icon: Icons.auto_awesome_outlined,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (explanation.summary.isNotEmpty)
                Text(
                  explanation.summary,
                  style: Theme.of(context).textTheme.bodyLarge,
                ),
              _AiList(title: 'How it works', items: explanation.howItWorks),
              _AiList(
                title: 'Architecture explanation',
                items: explanation.architectureExplanation,
              ),
              _AiList(
                title: 'Technology explanations',
                items: explanation.technologyExplanations,
              ),
              _AiText(
                title: 'API explanation',
                value: explanation.apiExplanation,
              ),
              _AiText(
                title: 'Authentication explanation',
                value: explanation.authenticationExplanation,
              ),
              _AiText(
                title: 'Data explanation',
                value: explanation.dataExplanation,
              ),
              _AiList(
                title: 'Learning roadmap',
                items: explanation.learningRoadmap,
              ),
              _AiList(
                title: 'Interview questions',
                items: explanation.interviewQuestions,
              ),
              _AiList(title: 'Uncertainties', items: explanation.uncertainties),
            ],
          ),
        ),
      ],
    );
  }
}

class _AiList extends StatelessWidget {
  const _AiList({required this.title, required this.items});
  final String title;
  final List<String> items;
  @override
  Widget build(BuildContext context) => items.isEmpty
      ? const SizedBox.shrink()
      : Padding(
          padding: const EdgeInsets.only(top: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 6),
              _BulletList(items: items),
            ],
          ),
        );
}

class _AiText extends StatelessWidget {
  const _AiText({required this.title, required this.value});
  final String title;
  final String? value;
  @override
  Widget build(BuildContext context) => value == null || value!.isEmpty
      ? const SizedBox.shrink()
      : Padding(
          padding: const EdgeInsets.only(top: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 6),
              Text(value!),
            ],
          ),
        );
}

class _ReportSection extends StatelessWidget {
  const _ReportSection({
    required this.title,
    required this.icon,
    required this.child,
  });
  final String title;
  final IconData icon;
  final Widget child;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(
                    icon,
                    size: 19,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                  const SizedBox(width: 9),
                  Text(title, style: Theme.of(context).textTheme.titleMedium),
                ],
              ),
              const SizedBox(height: 16),
              child,
            ],
          ),
        ),
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge({required this.label, this.highlighted = false});
  final String label;
  final bool highlighted;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
    decoration: BoxDecoration(
      color: highlighted
          ? Theme.of(context).colorScheme.primaryContainer
          : const Color(0xFF222B30),
      borderRadius: BorderRadius.circular(6),
    ),
    child: Text(
      label,
      style: TextStyle(
        fontSize: 12,
        color: highlighted
            ? Theme.of(context).colorScheme.onPrimaryContainer
            : const Color(0xFFD2DADD),
      ),
    ),
  );
}

class _PathList extends StatelessWidget {
  const _PathList({required this.items});
  final List<String> items;
  @override
  Widget build(BuildContext context) => items.isEmpty
      ? const Text('None observed.')
      : Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: items
              .map(
                (item) => Padding(
                  padding: const EdgeInsets.only(bottom: 5),
                  child: Text(
                    item,
                    softWrap: true,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      color: Color(0xFFFFC978),
                    ),
                  ),
                ),
              )
              .toList(),
        );
}

class _BulletList extends StatelessWidget {
  const _BulletList({required this.items});
  final List<String> items;
  @override
  Widget build(BuildContext context) => items.isEmpty
      ? const SizedBox.shrink()
      : Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: items
              .map(
                (item) => Padding(
                  padding: const EdgeInsets.only(bottom: 5),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('•  '),
                      Expanded(child: Text(item)),
                    ],
                  ),
                ),
              )
              .toList(),
        );
}

class _FactRow extends StatelessWidget {
  const _FactRow({required this.label, required this.value});
  final String label;
  final bool value;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 5),
    child: Row(
      children: [
        Icon(
          value ? Icons.check_circle_outline : Icons.remove_circle_outline,
          size: 17,
          color: value ? const Color(0xFF8BD3A8) : const Color(0xFF77848A),
        ),
        const SizedBox(width: 8),
        Text('$label: ${value ? 'present' : 'not detected'}'),
      ],
    ),
  );
}

class _InlineError extends StatelessWidget {
  const _InlineError({required this.message});
  final String message;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 14),
    child: Text(message, style: const TextStyle(color: Color(0xFFFF8E7D))),
  );
}
