import 'package:flutter/material.dart';

import '../state/inspection_controller.dart';
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
        return Scaffold(
          body: SafeArea(
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 48,
                ),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 760),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _BrandMark(),
                      const SizedBox(height: 34),
                      Text(
                        'Inspect the codebase.',
                        style: Theme.of(context).textTheme.headlineLarge,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        'Turn a public GitHub repository into a factual, evidence-backed technical report.',
                        style: Theme.of(context).textTheme.bodyLarge,
                      ),
                      const SizedBox(height: 34),
                      Text(
                        'PUBLIC REPOSITORY URL',
                        style: Theme.of(
                          context,
                        ).textTheme.labelSmall?.copyWith(letterSpacing: 1.4),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _urlController,
                        enabled: controller.status != InspectionStatus.loading,
                        keyboardType: TextInputType.url,
                        textInputAction: TextInputAction.go,
                        onSubmitted: (_) => _inspect(),
                        decoration: const InputDecoration(
                          hintText: 'https://github.com/owner/repository',
                          prefixIcon: Icon(Icons.link_rounded),
                        ),
                      ),
                      const SizedBox(height: 14),
                      SizedBox(
                        height: 50,
                        width: double.infinity,
                        child: FilledButton.icon(
                          onPressed:
                              controller.status == InspectionStatus.loading
                              ? null
                              : _inspect,
                          icon: controller.status == InspectionStatus.loading
                              ? const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Icon(Icons.manage_search_rounded),
                          label: Text(
                            controller.status == InspectionStatus.loading
                                ? 'Inspecting repository...'
                                : 'Inspect repository',
                          ),
                        ),
                      ),
                      const SizedBox(height: 22),
                      if (controller.status == InspectionStatus.loading)
                        const _ProgressNote(),
                      if (controller.status == InspectionStatus.error)
                        _ErrorNote(
                          message:
                              controller.errorMessage ?? 'Inspection failed.',
                        ),
                      if (controller.status == InspectionStatus.idle)
                        const _ScopeNote(),
                    ],
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  Future<void> _inspect() async {
    final value = _urlController.text.trim();
    final uri = Uri.tryParse(value);
    final parts =
        uri?.pathSegments.where((part) => part.isNotEmpty).toList() ?? [];
    if (uri == null ||
        uri.scheme != 'https' ||
        uri.host.toLowerCase() != 'github.com' ||
        parts.length != 2) {
      widget.controller.showInputError(
        'Enter a public GitHub URL like https://github.com/owner/repository.',
      );
      return;
    }
    await widget.controller.inspect(value);
  }
}

class _BrandMark extends StatelessWidget {
  @override
  Widget build(BuildContext context) => Row(
    children: [
      Container(
        width: 38,
        height: 38,
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.primary,
          borderRadius: BorderRadius.circular(9),
        ),
        child: const Icon(Icons.account_tree_rounded, color: Colors.black),
      ),
      const SizedBox(width: 12),
      Text(
        'GITHUB REPO INSPECTOR',
        style: Theme.of(
          context,
        ).textTheme.labelLarge?.copyWith(letterSpacing: 1.2),
      ),
    ],
  );
}

class _ProgressNote extends StatelessWidget {
  const _ProgressNote();

  @override
  Widget build(BuildContext context) => const _StatusPanel(
    icon: Icons.sync_rounded,
    title: 'Resolving repository structure',
    message:
        'Reading the bounded tree, then detecting technologies and evidence.',
  );
}

class _ScopeNote extends StatelessWidget {
  const _ScopeNote();

  @override
  Widget build(BuildContext context) => const _StatusPanel(
    icon: Icons.fact_check_outlined,
    title: 'Deterministic first',
    message:
        'The initial inspection uses repository evidence. AI explanation is optional after a report exists.',
  );
}

class _ErrorNote extends StatelessWidget {
  const _ErrorNote({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) => _StatusPanel(
    icon: Icons.error_outline_rounded,
    title: 'Inspection could not complete',
    message: message,
    error: true,
  );
}

class _StatusPanel extends StatelessWidget {
  const _StatusPanel({
    required this.icon,
    required this.title,
    required this.message,
    this.error = false,
  });

  final IconData icon;
  final String title;
  final String message;
  final bool error;

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: error ? const Color(0xFF321F1E) : const Color(0xFF171D21),
      borderRadius: BorderRadius.circular(10),
      border: Border.all(
        color: error ? const Color(0xFF9E5147) : const Color(0xFF2A3439),
      ),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          icon,
          color: error
              ? const Color(0xFFFF8E7D)
              : Theme.of(context).colorScheme.primary,
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 4),
              Text(message),
            ],
          ),
        ),
      ],
    ),
  );
}
