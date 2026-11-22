import 'dart:async';

import 'package:flutter/material.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/glass_card.dart';

class _Phase {
  const _Phase(this.icon, this.title, this.detail);

  final IconData icon;
  final String title;
  final String detail;
}

/// Shows the stages of an inspection while the single API request runs.
///
/// The stages advance on a timer to keep the wait readable; the report appears
/// as soon as the analysis actually completes.
class ScanProgress extends StatefulWidget {
  const ScanProgress({super.key, required this.target});

  final String target;

  @override
  State<ScanProgress> createState() => _ScanProgressState();
}

class _ScanProgressState extends State<ScanProgress> {
  static const _phases = <_Phase>[
    _Phase(Icons.hub_outlined, 'Finding the repository', 'Checking it exists and is public'),
    _Phase(Icons.folder_open_outlined, 'Reading the files', 'Looking at the folder layout and key files'),
    _Phase(Icons.layers_outlined, 'Spotting the tech stack', 'Languages, frameworks and packages'),
    _Phase(Icons.health_and_safety_outlined, 'Checking for problems', 'Security, tests, docs and structure'),
    _Phase(Icons.edit_note_rounded, 'Writing your report', 'Nearly there'),
  ];

  int _active = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(milliseconds: 2200), (_) {
      if (!mounted) return;
      if (_active < _phases.length - 1) {
        setState(() => _active++);
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      borderColor: AppColors.secondary.withValues(alpha: 0.35),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('LOOKING AT', style: AppText.label),
          const SizedBox(height: 6),
          Text(widget.target, style: AppText.h2),
          const SizedBox(height: 4),
          const Text(
            'Read-only. Nothing is installed or run.',
            style: AppText.small,
          ),
          const SizedBox(height: 18),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              minHeight: 4,
              backgroundColor: AppColors.border.withValues(alpha: 0.6),
              valueColor: const AlwaysStoppedAnimation<Color>(
                AppColors.secondary,
              ),
            ),
          ),
          const SizedBox(height: 18),
          for (var i = 0; i < _phases.length; i++)
            _PhaseRow(phase: _phases[i], done: i < _active, active: i == _active),
        ],
      ),
    );
  }
}

class _PhaseRow extends StatelessWidget {
  const _PhaseRow({
    required this.phase,
    required this.done,
    required this.active,
  });

  final _Phase phase;
  final bool done;
  final bool active;

  @override
  Widget build(BuildContext context) {
    final Widget marker;
    if (done) {
      marker = const Icon(
        Icons.check_circle_rounded,
        size: 20,
        color: AppColors.success,
      );
    } else if (active) {
      marker = const SizedBox(
        width: 18,
        height: 18,
        child: CircularProgressIndicator(
          strokeWidth: 2.2,
          color: AppColors.secondary,
        ),
      );
    } else {
      marker = const Icon(
        Icons.circle_outlined,
        size: 20,
        color: AppColors.textMuted,
      );
    }
    return AnimatedOpacity(
      duration: const Duration(milliseconds: 300),
      opacity: done || active ? 1 : 0.55,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 7),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(width: 24, height: 22, child: Center(child: marker)),
            const SizedBox(width: 12),
            Icon(phase.icon, size: 18, color: AppColors.textSecondary),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(phase.title, style: AppText.bodyStrong),
                  if (active) Text(phase.detail, style: AppText.small),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
