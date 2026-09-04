from app.schemas.analysis import AnalysisLimitations, RepositorySnapshot
from app.schemas.repository import RepositoryMetadata
from app.services.ai.prompts import build_explanation_prompt
from app.services.analyzer import analyze_repository


def snapshot(files: list[str], contents: dict[str, str] | None = None, sizes: dict[str, int] | None = None) -> RepositorySnapshot:
    return RepositorySnapshot(
        metadata=RepositoryMetadata(
            owner="owner",
            name="project",
            full_name="owner/project",
            description=None,
            html_url="https://github.com/owner/project",
            default_branch="main",
            language=None,
            stargazers_count=0,
            forks_count=0,
            open_issues_count=0,
            private=False,
        ),
        files=files,
        directories=[],
        file_contents=contents or {},
        file_sizes=sizes or {},
    )


def test_clean_flutter_repository_has_supported_documentation_and_test_evidence() -> None:
    report = analyze_repository(snapshot(
        ["README.md", ".gitignore", "pubspec.yaml", "pubspec.lock", "lib/main.dart", "test/widget_test.dart"],
        {
            "README.md": "# App\nA Flutter application.",
            "pubspec.yaml": "dependencies:\n  flutter:\n    sdk: flutter\n",
        },
    ))

    assert any(finding.id == "documentation_verified" for finding in report.findings)
    assert any(finding.id == "test_evidence" for finding in report.findings)
    assert report.health_summary.total_findings == len(report.findings)
    assert report.health_summary.severity_counts["info"] >= 1
    assert report.health_summary.overall == "Static inspection only"


def test_todo_markers_are_reported_without_calling_them_bugs() -> None:
    report = analyze_repository(snapshot(["README.md", "app.py"], {"app.py": "# TODO: split this module\n# FIXME: document this\n"}))

    finding = next(finding for finding in report.findings if finding.id == "todo_markers")
    assert finding.category == "maintainability"
    assert finding.severity == "low"
    assert "not automatically bugs" in finding.summary
    assert "technical debt" in finding.why_it_matters
    assert finding.recommended_action


def test_secret_values_are_redacted_from_findings_and_ai_input() -> None:
    secret = "super-secret-value-12345"
    report = analyze_repository(snapshot(
        ["config.py", "README.md"],
        {"config.py": f'API_KEY = "{secret}"\nPRIVATE = "-----BEGIN RSA PRIVATE KEY-----"'},
    ))

    findings_json = report.model_dump_json()
    assert secret not in findings_json
    project_report = __import__("app.services.report_builder", fromlist=["build_project_report"]).build_project_report(report)
    assert secret not in build_explanation_prompt(project_report)
    assert any(finding.category == "security" for finding in report.findings)


def test_documentation_mismatch_is_unverified_not_proof_of_falsehood() -> None:
    report = analyze_repository(snapshot(
        ["README.md", "main.py"],
        {"README.md": "This service uses PostgreSQL and JWT authentication."},
    ))

    ids = {finding.id for finding in report.findings}
    assert "documentation_unverified" in ids
    assert sum(finding.id == "documentation_unverified" for finding in report.findings) == 2
    assert all("does not prove" in finding.summary for finding in report.findings if finding.id == "documentation_unverified")


def test_testing_quality_and_repository_quality_findings_are_conservative() -> None:
    report = analyze_repository(snapshot(["main.py", "requirements.txt", ".env", "dist/app.js"]))

    ids = {finding.id for finding in report.findings}
    assert "missing_readme" in ids
    assert "missing_gitignore" in ids
    assert "tracked_environment_file" in ids
    assert "generated_artifacts" in ids
    assert "missing_test_evidence" not in ids


def test_health_summary_has_stable_counts_and_guidance() -> None:
    report = analyze_repository(snapshot(
        ["README.md", "requirements.txt", "app.py"],
        {"README.md": "# Project\n", "app.py": "TODO: add tests\n"},
    ))

    assert report.health_summary.total_findings == len(report.findings)
    assert report.health_summary.category_counts["maintainability"] == 1
    assert report.health_summary.severity_counts["low"] >= 1
    assert all(finding.why_it_matters for finding in report.findings)
    assert all(finding.recommended_action for finding in report.findings)


def test_limitation_information_is_preserved() -> None:
    limitations = AnalysisLimitations(
        tree_truncated=True,
        paths_truncated=True,
        content_truncated=True,
        notes=["Bounded inspection"],
    )
    report = analyze_repository(snapshot(["README.md"], {"README.md": "# Project"}))
    report.limitations = limitations
    project_report = __import__("app.services.report_builder", fromlist=["build_project_report"]).build_project_report(report)

    assert project_report.limitations == limitations
