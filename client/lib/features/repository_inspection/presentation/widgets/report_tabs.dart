import 'package:flutter/material.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/glass_card.dart';
import '../../data/models/ai_explanation.dart';
import '../../data/models/project_report.dart';
import '../plain_language.dart';
import '../state/inspection_controller.dart';
import 'common.dart';
import 'report_tiles.dart';

const int issuesTabIndex = 1;

// ===========================================================================
// Summary
// ===========================================================================

class SummaryTab extends StatelessWidget {
  const SummaryTab({super.key, required this.report, required this.controller});

  final ProjectReport report;
  final InspectionController controller;

  @override
  Widget build(BuildContext context) {
    final issues = issuesOf(report);
    final notes = notesOf(report);
    final structure = report.projectStructure;
    final topIssues = issues.take(3).toList();
    final issuesTitle = topIssues.isEmpty
        ? 'Nothing to fix'
        : switch (priorityOf(topIssues.first.severity)) {
            Priority.fixNow => 'Fix these first',
            Priority.worthFixing => 'Worth fixing',
            Priority.minor => 'Things worth a look',
            Priority.goodToKnow => 'Good to know',
          };

    return TabPage(
      children: [
        _ProjectHeader(report: report),
        _ScoreCard(report: report),
        SectionCard(
          title: issuesTitle,
          icon: Icons.flag_outlined,
          accent: topIssues.isEmpty ? AppColors.success : AppColors.warning,
          trailing: issues.length > topIssues.length
              ? TextButton(
                  onPressed: () => DefaultTabController.of(
                    context,
                  ).animateTo(issuesTabIndex),
                  child: Text('See all ${issues.length}'),
                )
              : null,
          child: topIssues.isEmpty
              ? const EmptyState(
                  icon: Icons.check_circle_rounded,
                  title: 'Nothing to fix',
                  message: 'No problems were found in the files we looked at.',
                )
              : Column(
                  children: [
                    for (final item in topIssues) IssueTile(finding: item),
                  ],
                ),
        ),
        SectionCard(
          title: 'What looks good',
          icon: Icons.thumb_up_alt_outlined,
          accent: AppColors.success,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  CheckChip(label: 'Tests', present: structure.hasTests),
                  CheckChip(label: 'Docs', present: structure.hasDocs),
                  CheckChip(label: 'CI', present: structure.hasCi),
                  CheckChip(label: 'Docker', present: structure.hasDocker),
                  CheckChip(
                    label: 'Example settings file',
                    present: structure.hasEnvironmentExample,
                  ),
                ],
              ),
              if (notes.isNotEmpty) ...[
                const SizedBox(height: 16),
                BulletList(
                  items: [for (final note in notes.take(4)) note.title],
                  color: AppColors.success,
                ),
                if (notes.length > 4)
                  Text(
                    '+${notes.length - 4} more under Issues > Good to know',
                    style: AppText.small,
                  ),
              ],
            ],
          ),
        ),
        AiPanel(controller: controller),
        if (report.limitations.hasLimitations)
          const InlineMessage(
            title: 'Only part of this repository was read',
            message:
                'It was too large to read in full, so some files were skipped. The Details tab lists what was and was not checked.',
            icon: Icons.info_outline_rounded,
            color: AppColors.warning,
          ),
      ],
    );
  }
}

class _ProjectHeader extends StatelessWidget {
  const _ProjectHeader({required this.report});

  final ProjectReport report;

  @override
  Widget build(BuildContext context) {
    final repo = report.repository;
    final initial = repo.name.isEmpty ? '?' : repo.name[0].toUpperCase();
    final description = repo.description;
    return GlassCard(
      padding: const EdgeInsets.all(22),
      borderColor: AppColors.primary.withValues(alpha: 0.45),
      gradient: LinearGradient(
        colors: [
          AppColors.primary.withValues(alpha: 0.28),
          AppColors.surface.withValues(alpha: 0.95),
          AppColors.secondary.withValues(alpha: 0.12),
        ],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 48,
                height: 48,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  gradient: AppColors.brandGradient,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Text(
                  initial,
                  style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                  ),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Semantics(
                  header: true,
                  child: Text(repo.fullName, style: AppText.h2),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(describeProject(report), style: AppText.lead),
          if (description != null && description.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(description, style: AppText.body),
          ],
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (repo.primaryLanguage != null)
                Pill(
                  label: repo.primaryLanguage!,
                  color: AppColors.secondary,
                  icon: Icons.code_rounded,
                ),
              if (repo.isLocal)
                const Pill(
                  label: 'Local analysis',
                  color: AppColors.accent,
                  icon: Icons.folder_open_outlined,
                )
              else if (repo.stars > 0)
                Pill(
                  label: starsLabel(repo.stars),
                  color: AppColors.warning,
                  icon: Icons.star_rounded,
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ScoreCard extends StatelessWidget {
  const _ScoreCard({required this.report});

  final ProjectReport report;

  @override
  Widget build(BuildContext context) {
    final score = healthScore(report.healthSummary);
    final tint = scoreColor(score);
    return GlassCard(
      child: LayoutBuilder(
        builder: (context, constraints) {
          final narrow = constraints.maxWidth < 520;
          final ring = HealthRing(score: score, color: tint);
          final words = Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                scoreVerdict(score),
                style: AppText.h2.copyWith(color: tint),
              ),
              const SizedBox(height: 6),
              Text(scoreSentence(report.healthSummary), style: AppText.body),
              const SizedBox(height: 12),
              const Text(
                'A rough guide from automatic, read-only checks. It is not a guarantee.',
                style: AppText.small,
              ),
            ],
          );
          if (narrow) {
            return Column(
              children: [
                ring,
                const SizedBox(height: 18),
                SizedBox(width: double.infinity, child: words),
              ],
            );
          }
          return Row(
            children: [
              ring,
              const SizedBox(width: 28),
              Expanded(child: words),
            ],
          );
        },
      ),
    );
  }
}

// ===========================================================================
// Issues
// ===========================================================================

class IssuesTab extends StatefulWidget {
  const IssuesTab({super.key, required this.report});

  final ProjectReport report;

  @override
  State<IssuesTab> createState() => _IssuesTabState();
}

class _IssuesTabState extends State<IssuesTab> {
  Priority? _filter;

  @override
  Widget build(BuildContext context) {
    final issues = issuesOf(widget.report);
    final notes = notesOf(widget.report);
    int countFor(Priority priority) =>
        issues.where((f) => priorityOf(f.severity) == priority).length;
    final visible = _filter == null
        ? issues
        : issues.where((f) => priorityOf(f.severity) == _filter).toList();

    final filters = <Priority?>[
      null,
      for (final priority in [
        Priority.fixNow,
        Priority.worthFixing,
        Priority.minor,
      ])
        if (countFor(priority) > 0) priority,
    ];

    return TabPage(
      children: [
        if (issues.isEmpty)
          const SectionCard(
            title: 'Issues',
            icon: Icons.check_circle_outline_rounded,
            accent: AppColors.success,
            child: EmptyState(
              icon: Icons.check_circle_rounded,
              title: 'No problems found',
              message: 'No problems were found in the files we looked at.',
            ),
          )
        else ...[
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final priority in filters)
                ChoiceChip(
                  showCheckmark: false,
                  selected: _filter == priority,
                  onSelected: (_) => setState(() => _filter = priority),
                  label: Text(
                    priority == null
                        ? 'All  ${issues.length}'
                        : '${priorityLabel(priority)}  ${countFor(priority)}',
                  ),
                  backgroundColor: AppColors.surface,
                  selectedColor:
                      (priority == null
                              ? AppColors.primary
                              : priorityColor(priority))
                          .withValues(alpha: 0.25),
                  side: BorderSide(
                    color: _filter == priority
                        ? (priority == null
                              ? AppColors.primary
                              : priorityColor(priority))
                        : AppColors.border,
                  ),
                  labelStyle: TextStyle(
                    fontWeight: FontWeight.w600,
                    color: _filter == priority
                        ? AppColors.textPrimary
                        : AppColors.textSecondary,
                  ),
                ),
            ],
          ),
          for (final priority in [
            Priority.fixNow,
            Priority.worthFixing,
            Priority.minor,
          ])
            if (visible.any((f) => priorityOf(f.severity) == priority))
              SectionCard(
                title: priorityLabel(priority),
                icon: priorityIcon(priority),
                accent: priorityColor(priority),
                child: Column(
                  children: [
                    for (final finding in visible)
                      if (priorityOf(finding.severity) == priority)
                        IssueTile(finding: finding),
                  ],
                ),
              ),
        ],
        if (notes.isNotEmpty)
          DetailSection(
            title: 'Good to know',
            subtitle:
                '${notes.length} ${notes.length == 1 ? 'note' : 'notes'}, nothing to fix',
            icon: Icons.lightbulb_outline_rounded,
            child: Column(
              children: [for (final note in notes) IssueTile(finding: note)],
            ),
          ),
      ],
    );
  }
}

// ===========================================================================
// Tech
// ===========================================================================

class TechTab extends StatelessWidget {
  const TechTab({super.key, required this.report});

  final ProjectReport report;

  @override
  Widget build(BuildContext context) {
    final tech = report.technologies;
    final groups = groupDependencies(report.dependencies);
    final ecosystems = groups.keys.toList()..sort();
    return TabPage(
      children: [
        SectionCard(
          title: 'Built with',
          icon: Icons.layers_outlined,
          accent: AppColors.primary,
          subtitle: 'Hover or long-press a label to see where it was found',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('LANGUAGES', style: AppText.label),
              const SizedBox(height: 8),
              SignalChips(signals: tech.languages, color: AppColors.secondary),
              const SizedBox(height: 18),
              const Text('FRAMEWORKS', style: AppText.label),
              const SizedBox(height: 8),
              SignalChips(signals: tech.frameworks, color: AppColors.primary),
              const SizedBox(height: 18),
              const Text('TOOLS', style: AppText.label),
              const SizedBox(height: 8),
              SignalChips(
                signals: tech.packageManagers,
                color: AppColors.accent,
              ),
            ],
          ),
        ),
        SectionCard(
          title: 'What it includes',
          icon: Icons.widgets_outlined,
          accent: AppColors.secondary,
          child: Column(
            children: [
              _CapabilityRow(
                icon: Icons.api_outlined,
                title: 'An API',
                signals: report.apiSignals,
              ),
              _CapabilityRow(
                icon: Icons.lock_outline_rounded,
                title: 'Login and users',
                signals: report.authenticationSignals,
              ),
              _CapabilityRow(
                icon: Icons.storage_outlined,
                title: 'A database',
                signals: report.databaseSignals,
              ),
            ],
          ),
        ),
        SectionCard(
          title: 'Dependencies',
          icon: Icons.inventory_2_outlined,
          accent: AppColors.accent,
          subtitle: report.dependencies.isEmpty
              ? null
              : '${report.dependencies.length} packages declared',
          child: report.dependencies.isEmpty
              ? const Text(
                  'No dependency files were found, or none could be read.',
                  style: AppText.body,
                )
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (final ecosystem in ecosystems)
                      DependencyGroup(
                        ecosystem: ecosystem,
                        dependencies: groups[ecosystem]!,
                      ),
                    const Text(
                      'Read from the project files. Nothing was installed and no vulnerability database was checked.',
                      style: AppText.small,
                    ),
                  ],
                ),
        ),
      ],
    );
  }
}

class _CapabilityRow extends StatelessWidget {
  const _CapabilityRow({
    required this.icon,
    required this.title,
    required this.signals,
  });

  final IconData icon;
  final String title;
  final List<DetectedSignal> signals;

  @override
  Widget build(BuildContext context) {
    final found = signals.isNotEmpty;
    final color = found ? AppColors.success : AppColors.textMuted;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Icon(icon, size: 20, color: color),
          const SizedBox(width: 14),
          Expanded(child: Text(title, style: AppText.bodyStrong)),
          const SizedBox(width: 12),
          Flexible(
            child: Text(
              foundOrNot(signals),
              textAlign: TextAlign.end,
              style: AppText.body.copyWith(color: color),
            ),
          ),
        ],
      ),
    );
  }
}

// ===========================================================================
// Details
// ===========================================================================

class DetailsTab extends StatelessWidget {
  const DetailsTab({super.key, required this.report});

  final ProjectReport report;

  @override
  Widget build(BuildContext context) {
    final trust = report.trustContext;
    final structure = report.projectStructure;
    final source = report.sourceInspection;
    final unchecked = [...trust.notVerified, ...trust.limitations];
    return TabPage(
      children: [
        DetailSection(
          title: 'How this report was made',
          icon: Icons.fact_check_outlined,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'We read a limited set of the project\'s files and matched them against known patterns. Everything here is based on files we actually saw.',
                style: AppText.body,
              ),
              const SizedBox(height: 12),
              BulletList(items: trust.verifiedDetected),
              const SizedBox(height: 4),
              Text(trust.runtimeStatus, style: AppText.bodyStrong),
            ],
          ),
        ),
        DetailSection(
          title: 'What we could not check',
          icon: Icons.help_outline_rounded,
          child: unchecked.isEmpty
              ? const Text('Nothing was reported.', style: AppText.body)
              : BulletList(items: unchecked, color: AppColors.warning),
        ),
        DetailSection(
          title: 'Files we read',
          subtitle:
              '${source.filesInspected} read, ${source.filesSkipped} skipped, ${source.filesTruncated} too large',
          icon: Icons.description_outlined,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Large repositories are only sampled so reports stay fast. Skipped files are not part of the findings.',
                style: AppText.body,
              ),
              if (source.notes.isNotEmpty) ...[
                const SizedBox(height: 12),
                BulletList(items: source.notes, color: AppColors.textMuted),
              ],
              if (report.limitations.notes.isNotEmpty) ...[
                const SizedBox(height: 4),
                BulletList(
                  items: report.limitations.notes,
                  color: AppColors.textMuted,
                ),
              ],
            ],
          ),
        ),
        DetailSection(
          title: 'Project layout',
          icon: Icons.account_tree_outlined,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('MAIN FOLDERS', style: AppText.label),
              const SizedBox(height: 8),
              PathList(items: structure.importantDirectories),
              const SizedBox(height: 16),
              const Text('KEY FILES', style: AppText.label),
              const SizedBox(height: 8),
              PathList(items: structure.importantFiles),
              const SizedBox(height: 16),
              const Text('SETTINGS FILES', style: AppText.label),
              const SizedBox(height: 8),
              PathList(items: structure.configurationFiles),
              if (report.architecture.interpretations.isNotEmpty) ...[
                const SizedBox(height: 16),
                const Text('NOTES ON THE STRUCTURE', style: AppText.label),
                const SizedBox(height: 8),
                BulletList(items: report.architecture.interpretations),
              ],
            ],
          ),
        ),
        DetailSection(
          title: 'Everything we detected',
          subtitle:
              '${report.evidence.length} signals, each with the files behind it',
          icon: Icons.manage_search_rounded,
          child: report.evidence.isEmpty
              ? const Text('Nothing was detected.', style: AppText.body)
              : Column(
                  children: [
                    for (final signal in report.evidence)
                      SignalTile(signal: signal),
                  ],
                ),
        ),
      ],
    );
  }
}

// ===========================================================================
// AI explanation (optional, inside Summary)
// ===========================================================================

class AiPanel extends StatelessWidget {
  const AiPanel({super.key, required this.controller});

  final InspectionController controller;

  @override
  Widget build(BuildContext context) {
    final working = controller.status == InspectionStatus.explaining;
    final response = controller.aiResponse;
    final error = controller.errorMessage;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        GlassCard(
          borderColor: AppColors.secondary.withValues(alpha: 0.4),
          gradient: LinearGradient(
            colors: [
              AppColors.secondary.withValues(alpha: 0.14),
              AppColors.primary.withValues(alpha: 0.14),
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                children: [
                  Icon(Icons.auto_awesome_outlined, color: AppColors.secondary),
                  SizedBox(width: 10),
                  Expanded(
                    child: Text('Want it in plain English?', style: AppText.h3),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              const Text(
                'Optional. An AI explains how this project works, using only this report. It never sees the source code.',
                style: AppText.body,
              ),
              const SizedBox(height: 14),
              FilledButton.icon(
                onPressed: working ? null : controller.explain,
                style: FilledButton.styleFrom(
                  minimumSize: const Size(0, 48),
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
                icon: working
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.auto_awesome_outlined),
                label: Text(
                  working ? 'Explaining...' : 'Explain this report with AI',
                ),
              ),
            ],
          ),
        ),
        if (error != null && controller.status != InspectionStatus.error) ...[
          const SizedBox(height: 12),
          InlineMessage(
            message: error,
            icon: Icons.error_outline_rounded,
            color: AppColors.danger,
          ),
        ],
        if (response != null) ...[
          const SizedBox(height: 12),
          AiResult(response: response),
        ],
      ],
    );
  }
}

class AiResult extends StatelessWidget {
  const AiResult({super.key, required this.response});

  final AiExplanationResponse response;

  @override
  Widget build(BuildContext context) {
    final explanation = response.explanation;
    if (!response.available || explanation == null) {
      return InlineMessage(
        message: response.reason ?? 'The AI explanation is not available.',
        icon: Icons.cloud_off_rounded,
        color: AppColors.warning,
      );
    }
    return SectionCard(
      title: 'AI explanation',
      icon: Icons.auto_awesome_outlined,
      accent: AppColors.secondary,
      subtitle: response.model == null
          ? 'Generated by ${response.provider}'
          : 'Generated by ${response.provider} (${response.model})',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (explanation.summary.isNotEmpty)
            Text(explanation.summary, style: AppText.lead),
          _AiList(title: 'How it works', items: explanation.howItWorks),
          _AiList(
            title: 'How it is organised',
            items: explanation.architectureExplanation,
          ),
          _AiList(
            title: 'Technologies',
            items: explanation.technologyExplanations,
          ),
          _AiText(title: 'API', value: explanation.apiExplanation),
          _AiText(title: 'Login', value: explanation.authenticationExplanation),
          _AiText(title: 'Data', value: explanation.dataExplanation),
          _AiList(
            title: 'Learning roadmap',
            items: explanation.learningRoadmap,
          ),
          _AiList(
            title: 'Interview questions',
            items: explanation.interviewQuestions,
          ),
          _AiList(title: 'Not sure about', items: explanation.uncertainties),
        ],
      ),
    );
  }
}

class _AiList extends StatelessWidget {
  const _AiList({required this.title, required this.items});

  final String title;
  final List<String> items;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title.toUpperCase(), style: AppText.label),
          const SizedBox(height: 10),
          BulletList(items: items),
        ],
      ),
    );
  }
}

class _AiText extends StatelessWidget {
  const _AiText({required this.title, required this.value});

  final String title;
  final String? value;

  @override
  Widget build(BuildContext context) {
    final text = value;
    if (text == null || text.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title.toUpperCase(), style: AppText.label),
          const SizedBox(height: 10),
          Text(text, style: AppText.body),
        ],
      ),
    );
  }
}
