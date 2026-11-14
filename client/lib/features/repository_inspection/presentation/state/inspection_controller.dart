import 'package:flutter/foundation.dart';

import '../../data/models/ai_explanation.dart';
import '../../data/models/project_report.dart';
import '../../data/repository_api.dart';

enum InspectionStatus { idle, loading, loaded, error, explaining, explained }

class InspectionController extends ChangeNotifier {
  InspectionController(this.api);

  final RepositoryApi api;
  InspectionStatus status = InspectionStatus.idle;
  ProjectReport? report;
  AiExplanationResponse? aiResponse;
  String? errorMessage;

  void reset() {
    status = InspectionStatus.idle;
    report = null;
    aiResponse = null;
    errorMessage = null;
    notifyListeners();
  }

  void showInputError(String message) {
    status = InspectionStatus.error;
    errorMessage = message;
    notifyListeners();
  }

  Future<void> inspect(String url) async {
    status = InspectionStatus.loading;
    report = null;
    aiResponse = null;
    errorMessage = null;
    notifyListeners();
    try {
      report = await api.inspect(url);
      status = InspectionStatus.loaded;
    } on ApiException catch (error) {
      status = InspectionStatus.error;
      errorMessage = error.message;
    } catch (_) {
      status = InspectionStatus.error;
      errorMessage = 'Inspection failed. Please try again.';
    }
    notifyListeners();
  }

  Future<void> explain() async {
    final currentReport = report;
    if (currentReport == null) return;
    status = InspectionStatus.explaining;
    errorMessage = null;
    notifyListeners();
    try {
      aiResponse = await api.explain(currentReport);
      status = InspectionStatus.explained;
    } on ApiException catch (error) {
      status = InspectionStatus.loaded;
      errorMessage = error.message;
    } catch (_) {
      status = InspectionStatus.loaded;
      errorMessage =
          'AI explanation failed. The deterministic report is still available.';
    }
    notifyListeners();
  }
}
