class DetectedSignal {
  const DetectedSignal({
    required this.name,
    required this.category,
    required this.evidence,
  });

  final String name;
  final String category;
  final List<String> evidence;

  factory DetectedSignal.fromJson(Map<String, dynamic> json) {
    return DetectedSignal(
      name: json['name'] as String,
      category: json['category'] as String,
      evidence: _strings(json['evidence']),
    );
  }
}

class CodebaseFinding {
  const CodebaseFinding({
    required this.id,
    required this.category,
    required this.severity,
    required this.title,
    required this.summary,
    required this.evidence,
    required this.affectedPaths,
    required this.confidence,
    required this.recommendation,
    required this.whyItMatters,
    required this.recommendedAction,
  });

  final String id;
  final String category;
  final String severity;
  final String title;
  final String summary;
  final List<String> evidence;
  final List<String> affectedPaths;
  final String confidence;
  final String recommendation;
  final String whyItMatters;
  final String recommendedAction;

  factory CodebaseFinding.fromJson(Map<String, dynamic> json) =>
      CodebaseFinding(
        id: json['id'] as String,
        category: json['category'] as String,
        severity: json['severity'] as String,
        title: json['title'] as String,
        summary: json['summary'] as String,
        evidence: _strings(json['evidence']),
        affectedPaths: _strings(json['affected_paths']),
        confidence: json['confidence'] as String,
        recommendation: json['recommendation'] as String? ?? '',
        whyItMatters: json['why_it_matters'] as String? ?? '',
        recommendedAction:
            json['recommended_action'] as String? ??
            json['recommendation'] as String? ??
            '',
      );
}

class HealthSummary {
  const HealthSummary({
    required this.totalFindings,
    required this.categoryCounts,
    required this.severityCounts,
    required this.overall,
  });

  final int totalFindings;
  final Map<String, int> categoryCounts;
  final Map<String, int> severityCounts;
  final String overall;

  factory HealthSummary.fromJson(Map<String, dynamic> json) => HealthSummary(
    totalFindings: json['total_findings'] as int? ?? 0,
    categoryCounts: (json['category_counts'] as Map<String, dynamic>? ?? {})
        .map((key, value) => MapEntry(key, value as int)),
    severityCounts: (json['severity_counts'] as Map<String, dynamic>? ?? {})
        .map((key, value) => MapEntry(key, value as int)),
    overall: json['overall'] as String? ?? 'Static inspection only',
  );
}

class ReportTrustContext {
  const ReportTrustContext({
    required this.verifiedDetected,
    required this.potentialIssues,
    required this.notVerified,
    required this.limitations,
    required this.runtimeStatus,
  });

  final List<String> verifiedDetected;
  final List<String> potentialIssues;
  final List<String> notVerified;
  final List<String> limitations;
  final String runtimeStatus;

  factory ReportTrustContext.fromJson(Map<String, dynamic> json) =>
      ReportTrustContext(
        verifiedDetected: _strings(json['verified_detected']),
        potentialIssues: _strings(json['potential_issues']),
        notVerified: _strings(json['not_verified']),
        limitations: _strings(json['limitations']),
        runtimeStatus:
            json['runtime_status'] as String? ?? 'Code was not executed.',
      );
}

class SourceInspectionSummary {
  const SourceInspectionSummary({
    required this.filesInspected,
    required this.filesSkipped,
    required this.filesTruncated,
    required this.contentTruncated,
    required this.notes,
  });

  final int filesInspected;
  final int filesSkipped;
  final int filesTruncated;
  final bool contentTruncated;
  final List<String> notes;

  factory SourceInspectionSummary.fromJson(Map<String, dynamic> json) =>
      SourceInspectionSummary(
        filesInspected: json['files_inspected'] as int? ?? 0,
        filesSkipped: json['files_skipped'] as int? ?? 0,
        filesTruncated: json['files_truncated'] as int? ?? 0,
        contentTruncated: json['content_truncated'] as bool? ?? false,
        notes: _strings(json['notes']),
      );
}

class RepositorySummary {
  const RepositorySummary({
    required this.owner,
    required this.name,
    required this.fullName,
    required this.description,
    required this.htmlUrl,
    required this.defaultBranch,
    required this.stars,
    required this.forks,
    required this.primaryLanguage,
  });

  final String owner;
  final String name;
  final String fullName;
  final String? description;
  final String htmlUrl;
  final String defaultBranch;
  final int stars;
  final int forks;
  final String? primaryLanguage;

  factory RepositorySummary.fromJson(Map<String, dynamic> json) {
    return RepositorySummary(
      owner: json['owner'] as String,
      name: json['name'] as String,
      fullName: json['full_name'] as String,
      description: json['description'] as String?,
      htmlUrl: json['html_url'] as String,
      defaultBranch: json['default_branch'] as String,
      stars: json['stars'] as int,
      forks: json['forks'] as int,
      primaryLanguage: json['primary_language'] as String?,
    );
  }
}

class ReportOverview {
  const ReportOverview({
    required this.classifications,
    required this.primaryClassification,
    required this.classificationBasis,
  });

  final List<String> classifications;
  final String primaryClassification;
  final List<String> classificationBasis;

  factory ReportOverview.fromJson(Map<String, dynamic> json) {
    return ReportOverview(
      classifications: _strings(json['classifications']),
      primaryClassification: json['primary_classification'] as String,
      classificationBasis: _strings(json['classification_basis']),
    );
  }
}

class ReportTechnologies {
  const ReportTechnologies({
    required this.languages,
    required this.frameworks,
    required this.packageManagers,
  });

  final List<DetectedSignal> languages;
  final List<DetectedSignal> frameworks;
  final List<DetectedSignal> packageManagers;

  factory ReportTechnologies.fromJson(Map<String, dynamic> json) {
    return ReportTechnologies(
      languages: _signals(json['languages']),
      frameworks: _signals(json['frameworks']),
      packageManagers: _signals(json['package_managers']),
    );
  }
}

class ReportArchitecture {
  const ReportArchitecture({
    required this.observedStructure,
    required this.interpretations,
  });

  final List<String> observedStructure;
  final List<String> interpretations;

  factory ReportArchitecture.fromJson(Map<String, dynamic> json) {
    return ReportArchitecture(
      observedStructure: _strings(json['observed_structure']),
      interpretations: _strings(json['interpretations']),
    );
  }
}

class ReportProjectStructure {
  const ReportProjectStructure({
    required this.importantDirectories,
    required this.importantFiles,
    required this.configurationFiles,
    required this.hasTests,
    required this.hasDocs,
    required this.hasCi,
    required this.hasDocker,
    required this.hasEnvironmentExample,
  });

  final List<String> importantDirectories;
  final List<String> importantFiles;
  final List<String> configurationFiles;
  final bool hasTests;
  final bool hasDocs;
  final bool hasCi;
  final bool hasDocker;
  final bool hasEnvironmentExample;

  factory ReportProjectStructure.fromJson(Map<String, dynamic> json) {
    return ReportProjectStructure(
      importantDirectories: _strings(json['important_directories']),
      importantFiles: _strings(json['important_files']),
      configurationFiles: _strings(json['configuration_files']),
      hasTests: json['has_tests'] as bool,
      hasDocs: json['has_docs'] as bool,
      hasCi: json['has_ci'] as bool,
      hasDocker: json['has_docker'] as bool,
      hasEnvironmentExample: json['has_environment_example'] as bool,
    );
  }
}

class ReportLimitations {
  const ReportLimitations({
    required this.treeTruncated,
    required this.pathsTruncated,
    required this.contentTruncated,
    required this.notes,
  });

  final bool treeTruncated;
  final bool pathsTruncated;
  final bool contentTruncated;
  final List<String> notes;

  bool get hasLimitations =>
      treeTruncated || pathsTruncated || contentTruncated || notes.isNotEmpty;

  factory ReportLimitations.fromJson(Map<String, dynamic> json) {
    return ReportLimitations(
      treeTruncated: json['tree_truncated'] as bool,
      pathsTruncated: json['paths_truncated'] as bool,
      contentTruncated: json['content_truncated'] as bool,
      notes: _strings(json['notes']),
    );
  }
}

class ProjectReport {
  const ProjectReport({
    required this.repository,
    required this.overview,
    required this.technologies,
    required this.architecture,
    required this.apiSignals,
    required this.authenticationSignals,
    required this.databaseSignals,
    required this.projectStructure,
    required this.evidence,
    required this.limitations,
    required this.findings,
    required this.healthSummary,
    required this.trustContext,
    required this.sourceInspection,
  });

  final RepositorySummary repository;
  final ReportOverview overview;
  final ReportTechnologies technologies;
  final ReportArchitecture architecture;
  final List<DetectedSignal> apiSignals;
  final List<DetectedSignal> authenticationSignals;
  final List<DetectedSignal> databaseSignals;
  final ReportProjectStructure projectStructure;
  final List<DetectedSignal> evidence;
  final ReportLimitations limitations;
  final List<CodebaseFinding> findings;
  final HealthSummary healthSummary;
  final ReportTrustContext trustContext;
  final SourceInspectionSummary sourceInspection;

  factory ProjectReport.fromJson(Map<String, dynamic> json) {
    final api = json['api'] as Map<String, dynamic>;
    final authentication = json['authentication'] as Map<String, dynamic>;
    final data = json['data'] as Map<String, dynamic>;
    return ProjectReport(
      repository: RepositorySummary.fromJson(
        json['repository'] as Map<String, dynamic>,
      ),
      overview: ReportOverview.fromJson(
        json['overview'] as Map<String, dynamic>,
      ),
      technologies: ReportTechnologies.fromJson(
        json['technologies'] as Map<String, dynamic>,
      ),
      architecture: ReportArchitecture.fromJson(
        json['architecture'] as Map<String, dynamic>,
      ),
      apiSignals: _signals(api['signals']),
      authenticationSignals: _signals(authentication['signals']),
      databaseSignals: _signals(data['databases']),
      projectStructure: ReportProjectStructure.fromJson(
        json['project_structure'] as Map<String, dynamic>,
      ),
      evidence: _signals(json['evidence']),
      limitations: ReportLimitations.fromJson(
        json['limitations'] as Map<String, dynamic>,
      ),
      findings: (json['findings'] as List<dynamic>? ?? [])
          .map((item) => CodebaseFinding.fromJson(item as Map<String, dynamic>))
          .toList(),
      healthSummary: HealthSummary.fromJson(
        json['health_summary'] as Map<String, dynamic>? ?? const {},
      ),
      trustContext: ReportTrustContext.fromJson(
        json['trust_context'] as Map<String, dynamic>? ?? const {},
      ),
      sourceInspection: SourceInspectionSummary.fromJson(
        json['source_inspection'] as Map<String, dynamic>? ?? const {},
      ),
    );
  }

  Map<String, dynamic> toJson() => {
    'repository': {
      'owner': repository.owner,
      'name': repository.name,
      'full_name': repository.fullName,
      'description': repository.description,
      'html_url': repository.htmlUrl,
      'default_branch': repository.defaultBranch,
      'stars': repository.stars,
      'forks': repository.forks,
      'primary_language': repository.primaryLanguage,
    },
    'overview': {
      'classifications': overview.classifications,
      'primary_classification': overview.primaryClassification,
      'classification_basis': overview.classificationBasis,
    },
    'technologies': {
      'languages': _signalJson(technologies.languages),
      'frameworks': _signalJson(technologies.frameworks),
      'package_managers': _signalJson(technologies.packageManagers),
    },
    'architecture': {
      'observed_structure': architecture.observedStructure,
      'interpretations': architecture.interpretations,
    },
    'api': {'signals': _signalJson(apiSignals)},
    'authentication': {'signals': _signalJson(authenticationSignals)},
    'data': {'databases': _signalJson(databaseSignals)},
    'project_structure': {
      'important_directories': projectStructure.importantDirectories,
      'important_files': projectStructure.importantFiles,
      'configuration_files': projectStructure.configurationFiles,
      'has_tests': projectStructure.hasTests,
      'has_docs': projectStructure.hasDocs,
      'has_ci': projectStructure.hasCi,
      'has_docker': projectStructure.hasDocker,
      'has_environment_example': projectStructure.hasEnvironmentExample,
    },
    'evidence': _signalJson(evidence),
    'limitations': {
      'tree_truncated': limitations.treeTruncated,
      'paths_truncated': limitations.pathsTruncated,
      'content_truncated': limitations.contentTruncated,
      'notes': limitations.notes,
    },
    'findings': findings
        .map(
          (finding) => {
            'id': finding.id,
            'category': finding.category,
            'severity': finding.severity,
            'title': finding.title,
            'summary': finding.summary,
            'evidence': finding.evidence,
            'affected_paths': finding.affectedPaths,
            'confidence': finding.confidence,
            'recommendation': finding.recommendation,
            'why_it_matters': finding.whyItMatters,
            'recommended_action': finding.recommendedAction,
          },
        )
        .toList(),
    'health_summary': {
      'total_findings': healthSummary.totalFindings,
      'category_counts': healthSummary.categoryCounts,
      'severity_counts': healthSummary.severityCounts,
      'overall': healthSummary.overall,
    },
    'trust_context': {
      'verified_detected': trustContext.verifiedDetected,
      'potential_issues': trustContext.potentialIssues,
      'not_verified': trustContext.notVerified,
      'limitations': trustContext.limitations,
      'runtime_status': trustContext.runtimeStatus,
    },
    'source_inspection': {
      'files_inspected': sourceInspection.filesInspected,
      'files_skipped': sourceInspection.filesSkipped,
      'files_truncated': sourceInspection.filesTruncated,
      'content_truncated': sourceInspection.contentTruncated,
      'notes': sourceInspection.notes,
    },
  };
}

List<String> _strings(dynamic value) =>
    (value as List<dynamic>? ?? []).cast<String>();

List<DetectedSignal> _signals(dynamic value) => (value as List<dynamic>? ?? [])
    .map((item) => DetectedSignal.fromJson(item as Map<String, dynamic>))
    .toList();

List<Map<String, dynamic>> _signalJson(List<DetectedSignal> signals) => signals
    .map(
      (signal) => {
        'name': signal.name,
        'category': signal.category,
        'evidence': signal.evidence,
      },
    )
    .toList();
