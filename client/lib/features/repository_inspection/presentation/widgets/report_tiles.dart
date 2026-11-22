import 'package:flutter/material.dart';

import '../../../../core/theme/app_theme.dart';
import '../../data/models/project_report.dart';
import '../plain_language.dart';
import 'common.dart';

/// Removes the default expansion divider lines so tiles sit cleanly in cards.
Widget _plainExpansion(BuildContext context, Widget child) => Theme(
  data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
  child: child,
);

class _TileFrame extends StatelessWidget {
  const _TileFrame({required this.child, this.borderColor});

  final Widget child;
  final Color? borderColor;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Container(
      decoration: BoxDecoration(
        color: AppColors.background.withValues(alpha: 0.55),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: borderColor ?? AppColors.border),
      ),
      child: child,
    ),
  );
}

class _DetailBlock extends StatelessWidget {
  const _DetailBlock({required this.label, required this.child});

  final String label;
  final Widget child;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 14),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label.toUpperCase(), style: AppText.label),
        const SizedBox(height: 6),
        child,
      ],
    ),
  );
}

/// One finding: plain title and priority up front, details when expanded.
class IssueTile extends StatelessWidget {
  const IssueTile({super.key, required this.finding});

  final CodebaseFinding finding;

  @override
  Widget build(BuildContext context) {
    final priority = priorityOf(finding.severity);
    final color = priorityColor(priority);
    final action = finding.recommendedAction.isEmpty
        ? finding.recommendation
        : finding.recommendedAction;
    final paths = finding.affectedPaths.isNotEmpty
        ? finding.affectedPaths
        : finding.evidence;
    final urgent = priority == Priority.fixNow || priority == Priority.worthFixing;
    return _TileFrame(
      borderColor: urgent ? color.withValues(alpha: 0.4) : null,
      child: _plainExpansion(
        context,
        ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
          childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 8),
          expandedAlignment: Alignment.centerLeft,
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          shape: const Border(),
          collapsedShape: const Border(),
          backgroundColor: Colors.transparent,
          collapsedBackgroundColor: Colors.transparent,
          iconColor: AppColors.textSecondary,
          collapsedIconColor: AppColors.textMuted,
          leading: Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.16),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(priorityIcon(priority), size: 19, color: color),
          ),
          title: Text(finding.title, style: AppText.title),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Wrap(
              spacing: 8,
              runSpacing: 4,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Pill(label: priorityLabel(priority), color: color, filled: true),
                Text(categoryName(finding.category), style: AppText.small),
              ],
            ),
          ),
          children: [
            _DetailBlock(
              label: 'What we found',
              child: Text(finding.summary, style: AppText.body),
            ),
            if (finding.whyItMatters.isNotEmpty)
              _DetailBlock(
                label: 'Why it matters',
                child: Text(finding.whyItMatters, style: AppText.body),
              ),
            if (action.isNotEmpty)
              _DetailBlock(
                label: 'What to do',
                child: Text(action, style: AppText.bodyStrong),
              ),
            _DetailBlock(
              label: 'Where we found it',
              child: PathList(items: paths),
            ),
          ],
        ),
      ),
    );
  }
}

/// A detected signal with its evidence files (used in the Details tab).
class SignalTile extends StatelessWidget {
  const SignalTile({super.key, required this.signal});

  final DetectedSignal signal;

  @override
  Widget build(BuildContext context) {
    return _TileFrame(
      child: _plainExpansion(
        context,
        ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
          childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
          expandedAlignment: Alignment.centerLeft,
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          shape: const Border(),
          collapsedShape: const Border(),
          backgroundColor: Colors.transparent,
          collapsedBackgroundColor: Colors.transparent,
          iconColor: AppColors.textSecondary,
          collapsedIconColor: AppColors.textMuted,
          title: Text(signal.name, style: AppText.title),
          subtitle: Text(categoryName(signal.category), style: AppText.small),
          children: [PathList(items: signal.evidence)],
        ),
      ),
    );
  }
}

/// Technology chips; hovering (or long-pressing) shows where it was found.
class SignalChips extends StatelessWidget {
  const SignalChips({
    super.key,
    required this.signals,
    required this.color,
    this.empty = 'None found.',
  });

  final List<DetectedSignal> signals;
  final Color color;
  final String empty;

  @override
  Widget build(BuildContext context) {
    if (signals.isEmpty) return Text(empty, style: AppText.small);
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final signal in signals)
          Tooltip(
            message: signal.evidence.isEmpty
                ? signal.name
                : 'Found in: ${signal.evidence.take(3).join(', ')}',
            child: Pill(label: signal.name, color: color, filled: true),
          ),
      ],
    );
  }
}

/// One ecosystem's declared dependencies, expandable.
class DependencyGroup extends StatelessWidget {
  const DependencyGroup({
    super.key,
    required this.ecosystem,
    required this.dependencies,
  });

  final String ecosystem;
  final List<Dependency> dependencies;

  @override
  Widget build(BuildContext context) {
    return _TileFrame(
      child: _plainExpansion(
        context,
        ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
          childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
          expandedAlignment: Alignment.centerLeft,
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          shape: const Border(),
          collapsedShape: const Border(),
          backgroundColor: Colors.transparent,
          collapsedBackgroundColor: Colors.transparent,
          iconColor: AppColors.textSecondary,
          collapsedIconColor: AppColors.textMuted,
          title: Text(ecosystem, style: AppText.title),
          subtitle: Text(
            '${dependencies.length} ${dependencies.length == 1 ? 'package' : 'packages'}',
            style: AppText.small,
          ),
          children: [
            for (final dependency in dependencies)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        dependency.name,
                        overflow: TextOverflow.ellipsis,
                        style: AppText.bodyStrong,
                      ),
                    ),
                    if (dependency.version != null)
                      Flexible(
                        child: Text(
                          dependency.version!,
                          overflow: TextOverflow.ellipsis,
                          style: monoStyle(color: AppColors.textMuted),
                        ),
                      ),
                    if (dependency.kind != 'runtime') ...[
                      const SizedBox(width: 8),
                      Pill(label: dependency.kind),
                    ],
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
