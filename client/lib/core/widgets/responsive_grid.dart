import 'package:flutter/material.dart';

/// Lays children out in equal-width columns that adapt to the available width.
class ResponsiveGrid extends StatelessWidget {
  const ResponsiveGrid({
    super.key,
    required this.children,
    this.wideColumns = 4,
    this.narrowColumns = 2,
    this.breakpoint = 640,
    this.spacing = 12,
  });

  final List<Widget> children;
  final int wideColumns;
  final int narrowColumns;
  final double breakpoint;
  final double spacing;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = constraints.maxWidth >= breakpoint
            ? wideColumns
            : narrowColumns;
        final width = ((constraints.maxWidth - spacing * (columns - 1)) /
                columns)
            .floorToDouble();
        return Wrap(
          spacing: spacing,
          runSpacing: spacing,
          children: [
            for (final child in children) SizedBox(width: width, child: child),
          ],
        );
      },
    );
  }
}
