class AiExplanation {
  const AiExplanation({
    required this.summary,
    required this.howItWorks,
    required this.architectureExplanation,
    required this.technologyExplanations,
    required this.apiExplanation,
    required this.authenticationExplanation,
    required this.dataExplanation,
    required this.learningRoadmap,
    required this.interviewQuestions,
    required this.uncertainties,
  });

  final String summary;
  final List<String> howItWorks;
  final List<String> architectureExplanation;
  final List<String> technologyExplanations;
  final String? apiExplanation;
  final String? authenticationExplanation;
  final String? dataExplanation;
  final List<String> learningRoadmap;
  final List<String> interviewQuestions;
  final List<String> uncertainties;

  factory AiExplanation.fromJson(Map<String, dynamic> json) => AiExplanation(
    summary: json['summary'] as String? ?? '',
    howItWorks: _aiStrings(json['how_it_works']),
    architectureExplanation: _aiStrings(json['architecture_explanation']),
    technologyExplanations: _aiStrings(json['technology_explanations']),
    apiExplanation: json['api_explanation'] as String?,
    authenticationExplanation: json['authentication_explanation'] as String?,
    dataExplanation: json['data_explanation'] as String?,
    learningRoadmap: _aiStrings(json['learning_roadmap']),
    interviewQuestions: _aiStrings(json['interview_questions']),
    uncertainties: _aiStrings(json['uncertainties']),
  );
}

class AiExplanationResponse {
  const AiExplanationResponse({
    required this.available,
    required this.provider,
    required this.model,
    required this.explanation,
    required this.reason,
  });

  final bool available;
  final String provider;
  final String? model;
  final AiExplanation? explanation;
  final String? reason;

  factory AiExplanationResponse.fromJson(Map<String, dynamic> json) =>
      AiExplanationResponse(
        available: json['available'] as bool,
        provider: json['provider'] as String,
        model: json['model'] as String?,
        explanation: json['explanation'] == null
            ? null
            : AiExplanation.fromJson(
                json['explanation'] as Map<String, dynamic>,
              ),
        reason: json['reason'] as String?,
      );
}

List<String> _aiStrings(dynamic value) =>
    (value as List<dynamic>? ?? []).cast<String>();
