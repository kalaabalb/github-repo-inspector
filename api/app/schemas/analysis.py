from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.repository import RepositoryMetadata


SignalCategory = Literal[
    "language",
    "framework",
    "package_manager",
    "database",
    "authentication",
    "api",
]

FindingCategory = Literal[
    "security",
    "configuration",
    "documentation",
    "architecture",
    "testing",
    "dependencies",
    "maintainability",
    "repository_quality",
]
FindingSeverity = Literal["info", "low", "medium", "high"]
FindingConfidence = Literal["low", "medium", "high"]


class Finding(BaseModel):
    id: str
    category: FindingCategory
    severity: FindingSeverity
    title: str
    summary: str
    evidence: list[str] = Field(min_length=1)
    affected_paths: list[str] = Field(default_factory=list)
    confidence: FindingConfidence
    recommendation: str
    why_it_matters: str = ""
    recommended_action: str = ""


class HealthSummary(BaseModel):
    total_findings: int = 0
    category_counts: dict[str, int] = Field(default_factory=dict)
    severity_counts: dict[str, int] = Field(default_factory=dict)
    overall: str = "Static inspection only"


class AnalysisLimitations(BaseModel):
    tree_truncated: bool = False
    paths_truncated: bool = False
    content_truncated: bool = False
    notes: list[str] = Field(default_factory=list)


class RepositorySnapshot(BaseModel):
    metadata: RepositoryMetadata
    files: list[str] = Field(default_factory=list)
    directories: list[str] = Field(default_factory=list)
    file_contents: dict[str, str] = Field(default_factory=dict)
    source_file_contents: dict[str, str] = Field(default_factory=dict)
    source_files_inspected: list[str] = Field(default_factory=list)
    source_files_skipped: list[str] = Field(default_factory=list)
    source_files_truncated: list[str] = Field(default_factory=list)
    source_content_truncated: bool = False
    source_limitation_notes: list[str] = Field(default_factory=list)
    file_sizes: dict[str, int] = Field(default_factory=dict)
    limitations: "AnalysisLimitations" = Field(default_factory=lambda: AnalysisLimitations())


class DetectedSignal(BaseModel):
    name: str
    category: SignalCategory
    evidence: list[str] = Field(min_length=1)


class ProjectStructure(BaseModel):
    top_level_directories: list[str]
    top_level_files: list[str]
    notable_paths: list[str]


class RepositoryCharacteristics(BaseModel):
    has_readme: bool
    has_license: bool
    has_ci_configuration: bool
    has_docker_configuration: bool
    has_test_directory: bool
    has_environment_example: bool
    file_count: int
    directory_count: int
    configuration_files: list[str]


class AnalysisReport(BaseModel):
    repository: RepositoryMetadata
    languages: list[DetectedSignal]
    frameworks: list[DetectedSignal]
    package_managers: list[DetectedSignal]
    databases: list[DetectedSignal]
    authentication: list[DetectedSignal]
    api_signals: list[DetectedSignal]
    structure: ProjectStructure
    project_characteristics: RepositoryCharacteristics
    limitations: AnalysisLimitations
    findings: list[Finding] = Field(default_factory=list)
    health_summary: HealthSummary = Field(default_factory=HealthSummary)
    source_files_inspected: list[str] = Field(default_factory=list)
    source_files_skipped: list[str] = Field(default_factory=list)
    source_files_truncated: list[str] = Field(default_factory=list)
    source_content_truncated: bool = False
    source_limitation_notes: list[str] = Field(default_factory=list)
