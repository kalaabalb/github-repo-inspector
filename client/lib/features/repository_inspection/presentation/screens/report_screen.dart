import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../core/theme/app_theme.dart';
import '../plain_language.dart';
import '../report_export.dart';
import '../state/inspection_controller.dart';
import '../widgets/report_tabs.dart';

enum _ShareAction { summary, markdown, json }

class ReportScreen extends StatelessWidget {
  const ReportScreen({super.key, required this.controller});

  final InspectionController controller;

  @override
  Widget build(BuildContext context) {
    final report = controller.report!;
    final issueCount = issuesOf(report).length;

    Future<void> share(_ShareAction action) async {
      final (text, label) = switch (action) {
        _ShareAction.summary => (reportToSummary(report), 'summary'),
        _ShareAction.markdown => (
          reportToMarkdown(report),
          'report as Markdown',
        ),
        _ShareAction.json => (reportToJson(report), 'report as JSON'),
      };
      await Clipboard.setData(ClipboardData(text: text));
      if (!context.mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Copied the $label')));
    }

    return DefaultTabController(
      length: 4,
      child: Scaffold(
        appBar: AppBar(
          titleSpacing: 16,
          title: Row(
            children: [
              Container(
                width: 30,
                height: 30,
                decoration: BoxDecoration(
                  gradient: AppColors.brandGradient,
                  borderRadius: BorderRadius.circular(9),
                ),
                child: const Icon(
                  Icons.travel_explore_rounded,
                  size: 18,
                  color: Colors.white,
                ),
              ),
              const SizedBox(width: 12),
              const Flexible(
                child: Text(
                  'Repo Inspector',
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
                ),
              ),
            ],
          ),
          actions: [
            PopupMenuButton<_ShareAction>(
              tooltip: 'Share or copy this report',
              icon: const Icon(Icons.ios_share_rounded),
              color: AppColors.surfaceHigh,
              onSelected: share,
              itemBuilder: (context) => const [
                PopupMenuItem(
                  value: _ShareAction.summary,
                  child: Text('Copy short summary'),
                ),
                PopupMenuItem(
                  value: _ShareAction.markdown,
                  child: Text('Copy as Markdown'),
                ),
                PopupMenuItem(
                  value: _ShareAction.json,
                  child: Text('Copy as JSON'),
                ),
              ],
            ),
            IconButton(
              tooltip: 'Inspect another repository',
              icon: const Icon(Icons.refresh_rounded),
              onPressed: controller.reset,
            ),
            const SizedBox(width: 8),
          ],
          bottom: TabBar(
            isScrollable: false,
            tabAlignment: TabAlignment.fill,
            labelPadding: const EdgeInsets.symmetric(horizontal: 4),
            dividerColor: AppColors.border,
            indicatorColor: AppColors.secondary,
            indicatorWeight: 3,
            labelColor: AppColors.textPrimary,
            unselectedLabelColor: AppColors.textMuted,
            labelStyle: const TextStyle(fontWeight: FontWeight.w700),
            tabs: [
              _tabLabel('Summary'),
              _tabLabel('Issues', badge: issueCount),
              _tabLabel('Tech'),
              _tabLabel('Details'),
            ],
          ),
        ),
        body: SelectionArea(
          child: AnimatedBuilder(
            animation: controller,
            builder: (context, _) => TabBarView(
              children: [
                SummaryTab(report: report, controller: controller),
                IssuesTab(report: report),
                TechTab(report: report),
                DetailsTab(report: report),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

Tab _tabLabel(String label, {int badge = 0}) {
  return Tab(
    height: 46,
    child: FittedBox(
      fit: BoxFit.scaleDown,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label),
          if (badge > 0) ...[
            const SizedBox(width: 4),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
              decoration: BoxDecoration(
                color: AppColors.warning.withValues(alpha: 0.22),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                '$badge',
                style: const TextStyle(
                  fontSize: 11.5,
                  fontWeight: FontWeight.w800,
                  color: AppColors.warning,
                ),
              ),
            ),
          ],
        ],
      ),
    ),
  );
}
