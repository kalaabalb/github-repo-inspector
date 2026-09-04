from app.schemas.analysis import AnalysisReport, DetectedSignal
from app.schemas.report import (
    ProjectReport,
    ReportApi,
    ReportArchitecture,
    ReportAuthentication,
    ReportData,
    ReportOverview,
    ReportProjectStructure,
    ReportRepository,
    SourceInspectionSummary,
    ReportTrustContext,
    ReportTechnologies,
)


def build_project_report(analysis: AnalysisReport) -> ProjectReport:
    classifications, basis = _classify_project(analysis)
    characteristics = analysis.project_characteristics
    structure = analysis.structure

    return ProjectReport(
        repository=ReportRepository(
            owner=analysis.repository.owner,
            name=analysis.repository.name,
            full_name=analysis.repository.full_name,
            description=analysis.repository.description,
            html_url=str(analysis.repository.html_url),
            default_branch=analysis.repository.default_branch,
            stars=analysis.repository.stargazers_count,
            forks=analysis.repository.forks_count,
            primary_language=_primary_language(analysis),
        ),
        overview=ReportOverview(
            classifications=classifications,
            primary_classification=classifications[0],
            classification_basis=basis,
        ),
        technologies=ReportTechnologies(
            languages=analysis.languages,
            frameworks=analysis.frameworks,
            package_managers=analysis.package_managers,
        ),
        architecture=_build_architecture(analysis),
        api=ReportApi(signals=analysis.api_signals),
        authentication=ReportAuthentication(signals=analysis.authentication),
        data=ReportData(databases=analysis.databases),
        project_structure=ReportProjectStructure(
            important_directories=structure.notable_paths,
            important_files=structure.top_level_files,
            configuration_files=characteristics.configuration_files,
            has_tests=characteristics.has_test_directory,
            has_docs="docs" in {path.lower() for path in structure.top_level_directories},
            has_ci=characteristics.has_ci_configuration,
            has_docker=characteristics.has_docker_configuration,
            has_environment_example=characteristics.has_environment_example,
        ),
        evidence=_all_signals(analysis),
        limitations=analysis.limitations,
        findings=analysis.findings,
        health_summary=analysis.health_summary,
        trust_context=ReportTrustContext(
            verified_detected=[
                "Repository metadata and bounded file-tree evidence were inspected.",
                "Technology and structure signals are based on deterministic matching.",
            ],
            potential_issues=[
                finding.title for finding in analysis.findings
                if finding.severity != "info"
            ],
            not_verified=[
                finding.title for finding in analysis.findings
                if finding.category == "documentation" and finding.severity != "info"
            ],
            limitations=analysis.limitations.notes,
            runtime_status="Code was not executed.",
        ),
        source_inspection=SourceInspectionSummary(
            files_inspected=len(analysis.source_files_inspected),
            files_skipped=len(analysis.source_files_skipped),
            files_truncated=len(analysis.source_files_truncated),
            content_truncated=analysis.source_content_truncated,
            notes=analysis.source_limitation_notes,
        ),
    )


def _classify_project(analysis: AnalysisReport) -> tuple[list[str], list[str]]:
    framework_names = {signal.name for signal in analysis.frameworks}
    language_names = {signal.name for signal in analysis.languages}
    api_names = {signal.name for signal in analysis.api_signals}
    directories = {path.split("/", 1)[0].lower() for path in analysis.structure.notable_paths}
    classifications: list[str] = []
    basis: list[str] = []

    has_frontend = bool(framework_names & {"Flutter", "React", "Next.js", "Vue", "Angular"}) or bool(
        directories & {"client", "frontend", "mobile"}
    )
    has_backend = bool(framework_names & {"FastAPI", "Django", "Flask", "Express", "Spring", ".NET"}) or bool(
        directories & {"api", "backend", "server"}
    ) or bool(api_names & {"FastAPI routes", "Express routes"})

    # Priority is intentional: full-stack, concrete framework types, then language families.
    if has_frontend and has_backend:
        classifications.append("Full-stack application")
        basis.append("frontend and backend evidence are both present")
    if "Flutter" in framework_names:
        classifications.append("Flutter application")
        basis.append("Flutter framework evidence is present")
    if "FastAPI" in framework_names:
        classifications.append("Backend/API")
        basis.append("FastAPI evidence is present")
    if "Express" in framework_names:
        classifications.append("Node.js application")
        basis.append("Express framework evidence is present")
    if framework_names & {"React", "Next.js", "Vue", "Angular"}:
        classifications.append("Frontend web application")
        basis.append("web frontend framework evidence is present")
    if "Python" in language_names and "Backend/API" not in classifications:
        classifications.append("Python application")
        basis.append("Python language evidence is present")
    if not classifications and language_names:
        classifications.append("General software repository")
        basis.append("source-language evidence is present")
    if not classifications:
        classifications.append("Unknown")
        basis.append("available evidence is insufficient for a more specific classification")
    return classifications, basis


def _primary_language(analysis: AnalysisReport) -> str | None:
    metadata_language = analysis.repository.language
    if metadata_language:
        return metadata_language
    return analysis.languages[0].name if analysis.languages else None


def _build_architecture(analysis: AnalysisReport) -> ReportArchitecture:
    observed = analysis.structure.notable_paths
    interpretations: list[str] = []
    roots = {path.split("/", 1)[0].lower() for path in observed}
    labels = {
        "client": "client application directory observed",
        "frontend": "frontend application directory observed",
        "mobile": "mobile application directory observed",
        "server": "server directory observed",
        "backend": "backend directory observed",
        "api": "API directory observed",
        "docs": "documentation directory observed",
        "tests": "test directory observed",
        "test": "test directory observed",
    }
    interpretations.extend(labels[root] for root in sorted(roots & labels.keys()))
    if not interpretations:
        interpretations.append("insufficient structural evidence for an architectural interpretation")
    return ReportArchitecture(observed_structure=observed, interpretations=interpretations)


def _all_signals(analysis: AnalysisReport) -> list[DetectedSignal]:
    return [
        *analysis.languages,
        *analysis.frameworks,
        *analysis.package_managers,
        *analysis.databases,
        *analysis.authentication,
        *analysis.api_signals,
    ]
