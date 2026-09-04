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


def test_purpose_consistency_reports_unverified_claims_without_calling_them_false() -> None:
    report = analyze_repository(snapshot(
        ["README.md", "main.py", ".gitignore"],
        {"README.md": "A Flutter mobile app with an API and PostgreSQL backend. This is a full-stack project.", "main.py": "print('hello')"},
    ))

    purpose_findings = [finding for finding in report.findings if finding.id.startswith("purpose_")]
    assert {finding.id for finding in purpose_findings} == {
        "purpose_flutter_not_observed",
        "purpose_api_not_observed",
        "purpose_backend_not_observed",
        "purpose_database_not_observed",
        "purpose_multicomponent_not_observed",
    }
    assert all(
        "not proof that the claim is false" in finding.summary
        for finding in purpose_findings
        if finding.id != "purpose_multicomponent_not_observed"
    )


def test_operational_configuration_signals_are_conservative_and_redacted() -> None:
    secret = "synthetic-password-value"
    report = analyze_repository(snapshot(
        ["README.md", "api/app.py"],
        {"README.md": "A FastAPI service.", "api/app.py": (
            f'API_KEY = "{secret}"\n'
            'DATABASE_URL = "postgresql://user:password@db/app"\n'
            'INTERNAL = "10.0.0.4"\n'
            'API_URL = "http://api.example.com"\n'
            'allow_origins = ["*"]\n'
            'debug = True\n'
        )},
    ))

    ids = {finding.id for finding in report.findings}
    assert {"potential_secret", "database_connection_string", "private_network_address"} <= ids
    assert {"insecure_http_endpoint", "wildcard_cors", "debug_configuration"} <= ids
    assert secret not in report.model_dump_json()


def test_localhost_http_is_not_reported_as_insecure_external_endpoint() -> None:
    report = analyze_repository(snapshot(
        ["README.md", "app.py"],
        {"README.md": "A service.", "app.py": 'LOCAL = "http://localhost:8000"'},
    ))

    assert "insecure_http_endpoint" not in {finding.id for finding in report.findings}


def test_incidental_http_text_is_not_reported_as_an_endpoint() -> None:
    report = analyze_repository(snapshot(
        ["README.md", "app.py"],
        {
            "README.md": "A service.",
            "app.py": "# See http://example.com/docs for protocol documentation",
        },
    ))

    assert "insecure_http_endpoint" not in {finding.id for finding in report.findings}


def test_readiness_and_architecture_observations_use_existing_report_findings() -> None:
    repository_snapshot = snapshot(
        ["README.md", "api/app.py", "api/requirements.txt", "client/package.json", "Dockerfile"],
        {
            "README.md": "A FastAPI backend and web client.",
            "api/app.py": 'from fastapi import FastAPI\napp = FastAPI()\n@app.get("/")\ndef root(): return {"ok": True}\nurl = os.getenv("DATABASE_URL")',
            "client/package.json": "{}",
            "Dockerfile": "FROM python:3.12",
        },
    )
    repository_snapshot.source_file_contents = {"api/app.py": repository_snapshot.file_contents["api/app.py"]}
    report = analyze_repository(repository_snapshot)

    ids = {finding.id for finding in report.findings}
    assert {"ci_not_detected", "environment_template_not_detected", "deployment_configuration_detected"} <= ids
    assert {"api_boundary_observed", "monorepo_structure_observed"} <= ids

    project_report = __import__("app.services.report_builder", fromlist=["build_project_report"]).build_project_report(report)
    assert any("CI configuration" in item for item in project_report.trust_context.potential_issues)
    assert project_report.trust_context.not_verified
    assert all("not detected" in item.lower() for item in project_report.trust_context.not_verified)
    assert "Code was not executed." == project_report.trust_context.runtime_status


def test_maintainability_thresholds_report_large_deep_and_excessive_work_markers() -> None:
    markers = "\n".join("# TODO: review" for _ in range(6))
    report = analyze_repository(snapshot(
        ["README.md", "src/a/b/c/d/e/f/module.py"],
        {"README.md": "A tool.", "src/a/b/c/d/e/f/module.py": markers},
        {"src/a/b/c/d/e/f/module.py": 100_001},
    ))

    ids = {finding.id for finding in report.findings}
    assert {"large_file", "deep_path", "todo_markers"} <= ids
    assert "review threshold" in next(f.summary for f in report.findings if f.id == "todo_markers")


def test_maintainability_negative_case_does_not_report_small_clean_source() -> None:
    report = analyze_repository(snapshot(
        ["README.md", "src/module.py"],
        {"README.md": "A tool.", "src/module.py": "def run():\n    return True\n"},
        {"src/module.py": 100_000},
    ))

    assert not {"large_file", "deep_path", "todo_markers"} & {finding.id for finding in report.findings}


def test_dependency_ecosystems_and_multiple_manifests_are_reported_without_vulnerability_claims() -> None:
    report = analyze_repository(snapshot(
        ["pyproject.toml", "poetry.lock", "client/package.json", "api/requirements.txt"],
    ))

    ids = {finding.id for finding in report.findings}
    assert "multiple_dependency_manifests" in ids
    assert "lockfile_missing" not in ids
    assert all("vulnerab" not in finding.summary.lower() for finding in report.findings)


def test_readme_usefulness_signals_and_finding_priority_are_deterministic() -> None:
    report = analyze_repository(snapshot(
        ["README.md", "api/app.py", "config.py"],
        {
            "README.md": "A FastAPI service.",
            "api/app.py": 'API_URL = "http://example.com"\n' + "\n".join("# TODO" for _ in range(6)),
            "config.py": 'API_KEY = "synthetic-secret-value"',
        },
    ))

    ids = {finding.id for finding in report.findings}
    assert {"setup_instructions_not_detected", "testing_instructions_not_detected", "deployment_instructions_not_detected"} <= ids
    categories = [finding.category for finding in report.findings]
    assert categories == sorted(categories, key=lambda category: {
        "security": 0, "configuration": 1, "architecture": 2, "maintainability": 3,
        "testing": 4, "documentation": 5, "release": 6, "dependencies": 7,
        "repository_quality": 8,
    }[category])
