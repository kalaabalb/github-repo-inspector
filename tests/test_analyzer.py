import pytest

from app.schemas.analysis import RepositorySnapshot
from app.schemas.repository import RepositoryMetadata
from app.services.analyzer import analyze_repository


def repository_snapshot(
    files: list[str],
    directories: list[str],
    file_contents: dict[str, str] | None = None,
) -> RepositorySnapshot:
    return RepositorySnapshot(
        metadata=RepositoryMetadata(
            owner="example",
            name="fixture",
            full_name="example/fixture",
            description=None,
            html_url="https://github.com/example/fixture",
            default_branch="main",
            language=None,
            stargazers_count=0,
            forks_count=0,
            open_issues_count=0,
            private=False,
        ),
        files=files,
        directories=directories,
        file_contents=file_contents or {},
    )


@pytest.fixture
def project_fixtures() -> list[tuple[str, RepositorySnapshot, dict[str, list[str]]]]:
    return [
        (
            "flutter",
            repository_snapshot(
                ["pubspec.yaml", "lib/main.dart", "test/widget_test.dart", "README.md"],
                ["lib", "test"],
                {"pubspec.yaml": "dependencies:\n  flutter:\n    sdk: flutter\n"},
            ),
            {"languages": ["Dart"], "frameworks": ["Flutter"], "package_managers": ["Dart Pub"]},
        ),
        (
            "fastapi",
            repository_snapshot(
                ["requirements.txt", "app/main.py", "tests/test_api.py"],
                ["app", "tests"],
                {"app/main.py": "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/health')\ndef health(): pass\n"},
            ),
            {"languages": ["Python"], "frameworks": ["FastAPI"], "package_managers": ["pip"], "api_signals": ["FastAPI routes"]},
        ),
        (
            "node-express",
            repository_snapshot(
                ["package.json", "src/server.js"],
                ["src"],
                {
                    "package.json": '{"dependencies":{"express":"^5.0.0"}}',
                    "src/server.js": "const express = require('express'); app.get('/health', handler);",
                },
            ),
            {"languages": ["JavaScript"], "frameworks": ["Express"], "package_managers": ["npm"], "api_signals": ["Express routes"]},
        ),
        (
            "react",
            repository_snapshot(
                ["package.json", "src/App.jsx"],
                ["src"],
                {"package.json": '{"dependencies":{"react":"^19.0.0"}}'},
            ),
            {"languages": ["JavaScript"], "frameworks": ["React"], "package_managers": ["npm"]},
        ),
        (
            "full-stack",
            repository_snapshot(
                [
                    "client/package.json",
                    "client/src/App.tsx",
                    "server/requirements.txt",
                    "server/main.py",
                    ".env.example",
                    ".github/workflows/ci.yml",
                    "README.md",
                ],
                ["client", "client/src", "server", ".github", ".github/workflows"],
                {
                    "client/package.json": '{"dependencies":{"react":"latest","axios":"latest","jsonwebtoken":"latest"}}',
                    "server/main.py": "from fastapi import FastAPI\nimport asyncpg\n# OAuth and JWT authentication\n@app.get('/items')\ndef items(): pass\n",
                },
            ),
            {
                "languages": ["Python", "TypeScript"],
                "frameworks": ["FastAPI", "React"],
                "package_managers": ["npm", "pip"],
                "databases": ["PostgreSQL"],
                "authentication": ["JWT", "OAuth"],
                "api_signals": ["FastAPI routes", "HTTP client usage"],
            },
        ),
        (
            "unknown",
            repository_snapshot(["README.md", "notes.txt"], [], {}),
            {"languages": [], "frameworks": [], "package_managers": [], "databases": [], "authentication": [], "api_signals": []},
        ),
    ]


@pytest.mark.parametrize("fixture_name", ["flutter", "fastapi", "node-express", "react", "full-stack", "unknown"])
def test_project_fixture_signals_have_expected_evidence(
    project_fixtures: list[tuple[str, RepositorySnapshot, dict[str, list[str]]]],
    fixture_name: str,
) -> None:
    _, snapshot, expected = next(item for item in project_fixtures if item[0] == fixture_name)

    report = analyze_repository(snapshot)

    for category, names in expected.items():
        signals = getattr(report, category)
        assert [signal.name for signal in signals] == sorted(names)
        for signal in signals:
            assert signal.evidence


def test_full_stack_evidence_points_to_input_paths(project_fixtures: list[tuple[str, RepositorySnapshot, dict[str, list[str]]]]) -> None:
    _, snapshot, _ = next(item for item in project_fixtures if item[0] == "full-stack")

    report = analyze_repository(snapshot)

    signals = {signal.name: signal for signal in report.frameworks + report.databases + report.authentication}
    assert signals["React"].evidence == ["client/package.json"]
    assert signals["PostgreSQL"].evidence == ["server/main.py"]
    assert signals["JWT"].evidence == ["client/package.json", "server/main.py"]
    assert signals["OAuth"].evidence == ["server/main.py"]


def test_misleading_filenames_do_not_create_unsupported_claims() -> None:
    snapshot = repository_snapshot(
        ["auth.py", "database.py", "api.txt", "README.md"],
        [],
    )

    report = analyze_repository(snapshot)

    assert report.languages[0].name == "Python"
    assert report.frameworks == []
    assert report.databases == []
    assert report.authentication == []
    assert report.api_signals == []


def test_python_manifest_can_support_framework_detection_without_source_fetching() -> None:
    snapshot = repository_snapshot(
        ["pyproject.toml", "README.md"],
        [],
        {"pyproject.toml": '[project.dependencies]\nfastapi = ">=0.100"\n'},
    )

    report = analyze_repository(snapshot)

    assert [signal.name for signal in report.frameworks] == ["FastAPI"]
    assert report.frameworks[0].evidence == ["pyproject.toml"]


def test_source_routes_and_authentication_are_reported_as_signals() -> None:
    snapshot = repository_snapshot(
        ["app/main.py", "server.js", "auth.py"],
        ["app"],
        {},
    )
    snapshot.source_file_contents = {
        "app/main.py": "from fastapi import APIRouter\nrouter = APIRouter()\n@router.get('/items')\n",
        "server.js": "const express = require('express'); app.post('/login', handler);",
        "auth.py": "token = jwt.decode(value)\n@login_required\ndef profile(): pass\n",
    }

    report = analyze_repository(snapshot)

    assert "FastAPI routes" in [signal.name for signal in report.api_signals]
    assert "Express routes" in [signal.name for signal in report.api_signals]
    assert "JWT" in [signal.name for signal in report.authentication]
    assert "Authorization middleware" in [signal.name for signal in report.authentication]
    assert report.api_signals[0].evidence


def test_source_secret_is_redacted_and_preserves_path_evidence() -> None:
    snapshot = repository_snapshot(["lib/config.dart"], [], {})
    snapshot.source_file_contents = {
        "lib/config.dart": 'const apiKey = "synthetic-secret-value-12345";'
    }

    report = analyze_repository(snapshot)

    serialized = report.model_dump_json()
    assert "synthetic-secret-value-12345" not in serialized
    finding = next(finding for finding in report.findings if finding.id == "potential_secret")
    assert finding.affected_paths == ["lib/config.dart"]
    assert "lib/config.dart" in finding.evidence[0]


def _frameworks(report) -> list[str]:
    return [signal.name for signal in report.frameworks]


def test_flutter_is_detected_in_a_monorepo_subdirectory() -> None:
    report = analyze_repository(
        repository_snapshot(
            ["client/pubspec.yaml", "client/lib/main.dart", "api/app/main.py"],
            ["client", "client/lib", "api"],
            {"client/pubspec.yaml": "dependencies:\n  flutter:\n    sdk: flutter\n"},
        )
    )

    flutter = next(s for s in report.frameworks if s.name == "Flutter")
    assert flutter.evidence == ["client/lib/", "client/pubspec.yaml"]


def test_framework_names_in_plain_strings_are_not_detected() -> None:
    keyword_list = (
        'FRAMEWORKS = ["django", "flask", "springframework", "spring-boot", "asp.net"]\n'
        "# Supports Django, Flask, Spring and ASP.NET projects.\n"
    )
    report = analyze_repository(
        repository_snapshot(
            ["api/detector.py"],
            ["api"],
            {"api/detector.py": keyword_list},
        )
    )

    assert _frameworks(report) == []


def test_real_django_spring_and_dotnet_usage_is_still_detected() -> None:
    report = analyze_repository(
        repository_snapshot(
            ["web/views.py", "svc/App.java", "net/Program.cs"],
            ["web", "svc", "net"],
            {
                "web/views.py": "from django.http import HttpResponse\n",
                "svc/App.java": "import org.springframework.boot.SpringApplication;\n",
                "net/Program.cs": "using Microsoft.AspNetCore.Builder;\n",
            },
        )
    )

    assert {"Django", "Spring", ".NET"} <= set(_frameworks(report))


def test_languages_with_several_extensions_are_reported_once() -> None:
    report = analyze_repository(
        repository_snapshot(
            ["app/Main.kt", "build.gradle.kts"],
            ["app"],
        )
    )

    names = [signal.name for signal in report.languages]
    assert names.count("Kotlin") == 1
    kotlin = next(s for s in report.languages if s.name == "Kotlin")
    assert kotlin.evidence == ["app/Main.kt", "build.gradle.kts"]


def test_keyword_lists_in_source_do_not_count_as_database_or_auth_evidence() -> None:
    marker_file = (
        'DATABASES = {"Redis": ["redis", "ioredis", "aioredis"]}\n'
        'AUTH = ["jwt", "oauth", "openid"]\n'
    )
    report = analyze_repository(
        repository_snapshot(["api/markers.py"], ["api"], {"api/markers.py": marker_file})
    )

    assert report.databases == []
    assert report.authentication == []


def test_real_database_usage_in_source_is_still_detected() -> None:
    report = analyze_repository(
        repository_snapshot(
            ["db.py"],
            [],
            {"db.py": "import psycopg\nconn = psycopg.connect(DSN)\n"},
        )
    )

    assert [signal.name for signal in report.databases] == ["PostgreSQL"]
