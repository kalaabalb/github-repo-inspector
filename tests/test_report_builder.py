from app.schemas.analysis import (
    AnalysisLimitations,
    AnalysisReport,
    DetectedSignal,
    ProjectStructure,
    RepositoryCharacteristics,
)
from app.schemas.repository import RepositoryMetadata
from app.services.report_builder import build_project_report


def signal(name: str, category: str, *evidence: str) -> DetectedSignal:
    return DetectedSignal(name=name, category=category, evidence=list(evidence))  # type: ignore[arg-type]


def analysis_fixture(
    frameworks: list[DetectedSignal],
    languages: list[DetectedSignal],
    package_managers: list[DetectedSignal] | None = None,
    databases: list[DetectedSignal] | None = None,
    authentication: list[DetectedSignal] | None = None,
    api_signals: list[DetectedSignal] | None = None,
    directories: list[str] | None = None,
    limitations: AnalysisLimitations | None = None,
) -> AnalysisReport:
    directories = directories or []
    return AnalysisReport(
        repository=RepositoryMetadata(
            owner="owner",
            name="project",
            full_name="owner/project",
            description="Project description",
            html_url="https://github.com/owner/project",
            default_branch="main",
            language="Python",
            stargazers_count=12,
            forks_count=3,
            open_issues_count=1,
            private=False,
        ),
        languages=languages,
        frameworks=frameworks,
        package_managers=package_managers or [],
        databases=databases or [],
        authentication=authentication or [],
        api_signals=api_signals or [],
        structure=ProjectStructure(
            top_level_directories=directories,
            top_level_files=["README.md"],
            notable_paths=directories,
        ),
        project_characteristics=RepositoryCharacteristics(
            has_readme=True,
            has_license=True,
            has_ci_configuration=True,
            has_docker_configuration=False,
            has_test_directory=bool({"test", "tests"} & set(directories)),
            has_environment_example=True,
            file_count=10,
            directory_count=len(directories),
            configuration_files=["requirements.txt"],
        ),
        limitations=limitations or AnalysisLimitations(),
    )


def test_flutter_classification_and_evidence_are_preserved() -> None:
    flutter = signal("Flutter", "framework", "pubspec.yaml", "lib/")
    report = build_project_report(
        analysis_fixture(
            frameworks=[flutter],
            languages=[signal("Dart", "language", "lib/main.dart")],
            package_managers=[signal("Dart Pub", "package_manager", "pubspec.yaml")],
            directories=["lib", "test"],
        )
    )

    assert report.overview.primary_classification == "Flutter application"
    assert report.technologies.frameworks == [flutter]
    assert report.evidence[0] == signal("Dart", "language", "lib/main.dart")
    assert report.project_structure.has_tests is True


def test_python_fastapi_classification_preserves_api_evidence() -> None:
    fastapi = signal("FastAPI", "framework", "app/main.py")
    routes = signal("FastAPI routes", "api", "app/main.py")
    report = build_project_report(
        analysis_fixture(
            frameworks=[fastapi],
            languages=[signal("Python", "language", "app/main.py")],
            api_signals=[routes],
        )
    )

    assert report.overview.primary_classification == "Backend/API"
    assert report.api.signals == [routes]


def test_python_package_layout_is_not_classified_as_a_python_application() -> None:
    report = build_project_report(
        analysis_fixture(
            frameworks=[],
            languages=[signal("Python", "language", "src/requests/api.py")],
            package_managers=[signal("Python Packaging", "package_manager", "pyproject.toml")],
            directories=["src", "tests"],
        )
    )

    assert report.overview.primary_classification == "Python library/package"


def test_node_express_and_react_classifications() -> None:
    node_report = build_project_report(
        analysis_fixture(
            frameworks=[signal("Express", "framework", "package.json")],
            languages=[signal("JavaScript", "language", "src/App.jsx")],
        )
    )
    react_report = build_project_report(
        analysis_fixture(
            frameworks=[signal("React", "framework", "package.json")],
            languages=[signal("JavaScript", "language", "src/App.jsx")],
        )
    )

    assert node_report.overview.primary_classification == "Node.js application"
    assert react_report.overview.primary_classification == "Frontend web application"


def test_full_stack_metadata_authentication_data_and_limitations() -> None:
    limitations = AnalysisLimitations(
        tree_truncated=True,
        paths_truncated=True,
        notes=["Only a bounded tree was analyzed."],
    )
    report = build_project_report(
        analysis_fixture(
            frameworks=[
                signal("React", "framework", "client/package.json"),
                signal("FastAPI", "framework", "server/main.py"),
            ],
            languages=[
                signal("TypeScript", "language", "client/App.tsx"),
                signal("Python", "language", "server/main.py"),
            ],
            databases=[signal("PostgreSQL", "database", "server/main.py")],
            authentication=[signal("JWT", "authentication", "server/main.py")],
            api_signals=[signal("FastAPI routes", "api", "server/main.py")],
            directories=["client", "server", "docs", "tests"],
            limitations=limitations,
        )
    )

    assert report.overview.primary_classification == "Full-stack application"
    assert report.repository.full_name == "owner/project"
    assert report.repository.stars == 12
    assert report.data.databases[0].evidence == ["server/main.py"]
    assert report.authentication.signals[0].name == "JWT"
    assert report.api.signals[0].evidence == ["server/main.py"]
    assert report.limitations == limitations
    assert "docs" in report.project_structure.important_directories


def test_unknown_project_does_not_receive_exaggerated_classification() -> None:
    report = build_project_report(analysis_fixture(frameworks=[], languages=[]))

    assert report.overview.classifications == ["Unknown"]
    assert report.overview.primary_classification == "Unknown"
    assert report.architecture.interpretations == [
        "insufficient structural evidence for an architectural interpretation"
    ]
