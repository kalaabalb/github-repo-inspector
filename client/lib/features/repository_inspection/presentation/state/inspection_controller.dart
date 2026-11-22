import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../../data/models/ai_explanation.dart';
import '../../data/models/project_report.dart';
import '../../data/repository_api.dart';
import '../../data/repository_url.dart';

enum InspectionStatus { idle, loading, loaded, error, explaining, explained }

typedef SampleLoader = Future<String> Function();

Future<String> _bundledSample() =>
    rootBundle.loadString('assets/sample_report.json');

class InspectionController extends ChangeNotifier {
  InspectionController(this.api, {SampleLoader? sampleLoader})
    : _sampleLoader = sampleLoader ?? _bundledSample;

  final SampleLoader _sampleLoader;

  final RepositoryApi api;
  InspectionStatus status = InspectionStatus.idle;
  ProjectReport? report;
  AiExplanationResponse? aiResponse;
  String? errorMessage;

  /// Name of what is being inspected, shown while loading.
  String? targetName;

  void reset() {
    status = InspectionStatus.idle;
    report = null;
    aiResponse = null;
    errorMessage = null;
    targetName = null;
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
    targetName = RepositoryUrl.tryParse(url)?.fullName ?? url;
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

  /// Opens the bundled sample report. Needs no network and no API.
  Future<void> loadSample() async {
    status = InspectionStatus.loading;
    report = null;
    aiResponse = null;
    errorMessage = null;
    targetName = 'the sample report';
    notifyListeners();
    try {
      final decoded = jsonDecode(await _sampleLoader());
      report = ProjectReport.fromJson(decoded as Map<String, dynamic>);
      status = InspectionStatus.loaded;
    } catch (_) {
      status = InspectionStatus.error;
      errorMessage = 'The sample report could not be loaded.';
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
