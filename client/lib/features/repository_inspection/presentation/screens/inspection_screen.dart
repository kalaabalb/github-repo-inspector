import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/aurora_background.dart';
import '../../../../core/widgets/glass_card.dart';
import '../../data/repository_api.dart';
import '../../data/repository_url.dart';
import '../state/inspection_controller.dart';
import '../widgets/common.dart';
import '../widgets/scan_progress.dart';
import 'report_screen.dart';

class InspectionScreen extends StatefulWidget {
  const InspectionScreen({super.key, required this.controller});

  final InspectionController controller;

  @override
  State<InspectionScreen> createState() => _InspectionScreenState();
}

class _InspectionScreenState extends State<InspectionScreen> {
  late final TextEditingController _urlController;

  @override
  void initState() {
    super.initState();
    _urlController = TextEditingController();
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.controller,
      builder: (context, _) {
        final controller = widget.controller;
        if (controller.report != null &&
            controller.status != InspectionStatus.error) {
          return ReportScreen(controller: controller);
        }
        final loading = controller.status == InspectionStatus.loading;
        final narrow = MediaQuery.of(context).size.width < 640;
        return Scaffold(
          body: AuroraBackground(
            child: SafeArea(
              child: Center(
                child: SingleChildScrollView(
                  padding: EdgeInsets.symmetric(
                    horizontal: narrow ? 18 : 28,
                    vertical: narrow ? 22 : 40,
                  ),
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 780),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const _BrandBar(),
                        SizedBox(height: narrow ? 30 : 48),
                        _Hero(narrow: narrow),
                        SizedBox(height: narrow ? 24 : 32),
                        _InputCard(
                          controller: _urlController,
                          loading: loading,
                          onSubmit: _inspect,
                          onPaste: _paste,
                        ),
                        if (controller.status == InspectionStatus.error) ...[
                          const SizedBox(height: 16),
                          InlineMessage(
                            title: 'That did not work',
                            message:
                                controller.errorMessage ?? 'Something went wrong.',
                            icon: Icons.error_outline_rounded,
                            color: AppColors.danger,
                          ),
                        ],
                        if (loading) ...[
                          const SizedBox(height: 20),
                          ScanProgress(
                            target: controller.targetName ?? 'the repository',
                          ),
                        ] else ...[
                          const SizedBox(height: 22),
                          _Shortcuts(
                            onPick: _inspect,
                            onSample: controller.loadSample,
                          ),
                          const SizedBox(height: 28),
                          const _TrustNote(),
                        ],
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  Future<void> _paste() async {
    final data = await Clipboard.getData('text/plain');
    final text = data?.text?.trim();
    if (text == null || text.isEmpty) return;
    _urlController.text = text;
  }

  Future<void> _inspect([String? value]) async {
    if (value != null) _urlController.text = value;
    final parsed = RepositoryUrl.tryParse(_urlController.text);
    if (parsed == null) {
      widget.controller.showInputError(invalidUrlMessage);
      return;
    }
    FocusManager.instance.primaryFocus?.unfocus();
    await widget.controller.inspect(parsed.url);
  }
}

class _BrandBar extends StatelessWidget {
  const _BrandBar();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            gradient: AppColors.brandGradient,
            borderRadius: BorderRadius.circular(12),
            boxShadow: [
              BoxShadow(
                color: AppColors.primary.withValues(alpha: 0.5),
                blurRadius: 18,
              ),
            ],
          ),
          child: const Icon(
            Icons.travel_explore_rounded,
            color: Colors.white,
            size: 22,
          ),
        ),
        const SizedBox(width: 12),
        const Flexible(
          child: Text(
            'Repo Inspector',
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.3,
              color: AppColors.textPrimary,
            ),
          ),
        ),
      ],
    );
  }
}

class _Hero extends StatelessWidget {
  const _Hero({required this.narrow});

  final bool narrow;

  @override
  Widget build(BuildContext context) {
    final style = AppText.display.copyWith(fontSize: narrow ? 34 : 52);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Semantics(
          header: true,
          child: Text('Understand any codebase', style: style),
        ),
        ShaderMask(
          blendMode: BlendMode.srcIn,
          shaderCallback: (bounds) => AppColors.brandGradient.createShader(
            Rect.fromLTWH(0, 0, bounds.width, bounds.height),
          ),
          child: Text('in about a minute.', style: style.copyWith(color: Colors.white)),
        ),
        const SizedBox(height: 18),
        const Text(
          'Paste a GitHub link and get a plain-English report: what it is, what it is built with, and what to fix first.',
          style: AppText.lead,
        ),
      ],
    );
  }
}

class _InputCard extends StatelessWidget {
  const _InputCard({
    required this.controller,
    required this.loading,
    required this.onSubmit,
    required this.onPaste,
  });

  final TextEditingController controller;
  final bool loading;
  final Future<void> Function([String? value]) onSubmit;
  final Future<void> Function() onPaste;

  @override
  Widget build(BuildContext context) {
    final field = TextField(
      controller: controller,
      enabled: !loading,
      keyboardType: TextInputType.url,
      textInputAction: TextInputAction.go,
      style: const TextStyle(fontSize: 16, color: AppColors.textPrimary),
      onSubmitted: (_) => onSubmit(),
      decoration: InputDecoration(
        hintText: 'github.com/owner/repository',
        prefixIcon: const Icon(Icons.link_rounded),
        suffixIcon: IconButton(
          tooltip: 'Paste from clipboard',
          icon: const Icon(Icons.content_paste_rounded, size: 20),
          onPressed: loading ? null : onPaste,
        ),
      ),
    );
    final button = _GradientButton(
      label: loading ? 'Inspecting repository...' : 'Inspect repository',
      icon: Icons.manage_search_rounded,
      loading: loading,
      onPressed: loading ? null : () => onSubmit(),
    );
    return GlassCard(
      padding: const EdgeInsets.all(18),
      radius: 22,
      borderColor: AppColors.primary.withValues(alpha: 0.45),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final wide = constraints.maxWidth >= 620;
          if (wide) {
            return Row(
              children: [
                Expanded(child: field),
                const SizedBox(width: 12),
                button,
              ],
            );
          }
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [field, const SizedBox(height: 12), button],
          );
        },
      ),
    );
  }
}

class _GradientButton extends StatelessWidget {
  const _GradientButton({
    required this.label,
    required this.icon,
    required this.onPressed,
    this.loading = false,
  });

  final String label;
  final IconData icon;
  final VoidCallback? onPressed;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: enabled ? AppColors.brandGradient : null,
        color: enabled ? null : AppColors.surfaceHigh,
        borderRadius: BorderRadius.circular(14),
        boxShadow: enabled
            ? [
                BoxShadow(
                  color: AppColors.primary.withValues(alpha: 0.4),
                  blurRadius: 22,
                  offset: const Offset(0, 8),
                ),
              ]
            : null,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: onPressed,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 18),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (loading)
                  const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                else
                  Icon(icon, color: Colors.white, size: 20),
                const SizedBox(width: 10),
                Flexible(
                  child: Text(
                    label,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize: 15,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Shortcuts extends StatelessWidget {
  const _Shortcuts({required this.onPick, required this.onSample});

  final Future<void> Function([String? value]) onPick;
  final Future<void> Function() onSample;

  static const _repos = ['flutter/flutter', 'tiangolo/fastapi'];

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 10,
      runSpacing: 10,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        ActionChip(
          avatar: const Icon(
            Icons.play_circle_outline_rounded,
            size: 18,
            color: AppColors.secondary,
          ),
          label: const Text('Try a sample report'),
          tooltip: 'Opens a bundled example. Works offline.',
          onPressed: onSample,
          backgroundColor: AppColors.surfaceHigh,
          side: BorderSide(color: AppColors.secondary.withValues(alpha: 0.5)),
          labelStyle: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
          ),
        ),
        const Text('or try', style: AppText.small),
        for (final repo in _repos)
          ActionChip(
            label: Text(repo),
            onPressed: () => onPick('https://github.com/$repo'),
            backgroundColor: AppColors.surface,
            side: const BorderSide(color: AppColors.border),
            labelStyle: const TextStyle(
              fontSize: 13,
              color: AppColors.textSecondary,
            ),
          ),
      ],
    );
  }
}

class _TrustNote extends StatelessWidget {
  const _TrustNote();

  @override
  Widget build(BuildContext context) {
    return const Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(Icons.lock_outline_rounded, size: 16, color: AppColors.textMuted),
        SizedBox(width: 8),
        Expanded(
          child: Text(
            'Read-only. The code is never run, and only public repositories can be inspected.',
            style: AppText.small,
          ),
        ),
      ],
    );
  }
}
