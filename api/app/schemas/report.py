from pydantic import BaseModel, Field

from app.schemas.analysis import AnalysisLimitations, DetectedSignal, Finding, HealthSummary


class ReportRepository(BaseModel):
    owner: str
    name: str
    full_name: str
    description: str | None = None
    html_url: str
    default_branch: str
    stars: int
    forks: int
    primary_language: str | None = None


class ReportOverview(BaseModel):
    classifications: list[str]
    primary_classification: str
    classification_basis: list[str] = Field(default_factory=list)


class ReportTechnologies(BaseModel):
    languages: list[DetectedSignal]
    frameworks: list[DetectedSignal]
    package_managers: list[DetectedSignal]


class ReportArchitecture(BaseModel):
    observed_structure: list[str]
    interpretations: list[str]


class ReportApi(BaseModel):
    signals: list[DetectedSignal]


class ReportAuthentication(BaseModel):
    signals: list[DetectedSignal]


class ReportData(BaseModel):
    databases: list[DetectedSignal]


class ReportProjectStructure(BaseModel):
    important_directories: list[str]
    important_files: list[str]
    configuration_files: list[str]
    has_tests: bool
    has_docs: bool
    has_ci: bool
    has_docker: bool
    has_environment_example: bool


class ReportTrustContext(BaseModel):
    verified_detected: list[str] = Field(default_factory=list)
    potential_issues: list[str] = Field(default_factory=list)
    not_verified: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    runtime_status: str = "Code was not executed."


class SourceInspectionSummary(BaseModel):
    files_inspected: int = 0
    files_skipped: int = 0
    files_truncated: int = 0
    content_truncated: bool = False
    notes: list[str] = Field(default_factory=list)


class ProjectReport(BaseModel):
    repository: ReportRepository
    overview: ReportOverview
    technologies: ReportTechnologies
    architecture: ReportArchitecture
    api: ReportApi
    authentication: ReportAuthentication
    data: ReportData
    project_structure: ReportProjectStructure
    evidence: list[DetectedSignal]
    limitations: AnalysisLimitations
    findings: list[Finding] = Field(default_factory=list)
    health_summary: HealthSummary = Field(default_factory=HealthSummary)
    trust_context: ReportTrustContext = Field(default_factory=ReportTrustContext)
    source_inspection: SourceInspectionSummary = Field(default_factory=SourceInspectionSummary)
