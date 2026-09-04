import 'package:flutter/material.dart';

import 'core/config/api_config.dart';
import 'core/theme/app_theme.dart';
import 'features/repository_inspection/data/repository_api.dart';
import 'features/repository_inspection/presentation/screens/inspection_screen.dart';
import 'features/repository_inspection/presentation/state/inspection_controller.dart';

void main() {
  runApp(
    RepositoryInspectorApp(api: HttpRepositoryApi(baseUrl: ApiConfig.baseUrl)),
  );
}

class RepositoryInspectorApp extends StatelessWidget {
  const RepositoryInspectorApp({super.key, required this.api});

  final RepositoryApi api;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GitHub Repository Inspector',
      theme: AppTheme.dark(),
      home: InspectionScreen(controller: InspectionController(api)),
    );
  }
}
