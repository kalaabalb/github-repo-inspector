import re
from collections.abc import Iterable
from pathlib import PurePosixPath

from app.schemas.analysis import (
    AnalysisReport,
    DetectedSignal,
    ProjectStructure,
    RepositoryCharacteristics,
    RepositorySnapshot,
)
from app.services.static_health import analyze_codebase_health


LANGUAGE_EXTENSIONS = {
    ".dart": "Dart",
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".swift": "Swift",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".cs": "C#",
    ".rb": "Ruby",
}

PACKAGE_MANAGER_FILES = {
    "pubspec.yaml": "Dart Pub",
    "package.json": "npm",
    "requirements.txt": "pip",
    "pyproject.toml": "Python Packaging",
    "pom.xml": "Maven",
    "build.gradle": "Gradle",
    "build.gradle.kts": "Gradle",
    "cargo.toml": "Cargo",
    "go.mod": "Go Modules",
    "composer.json": "Composer",
}

NOTABLE_DIRECTORIES = {
    "client",
    "server",
    "api",
    "backend",
    "frontend",
    "mobile",
    "docs",
    "tests",
    "test",
    "lib",
    "src",
}


def analyze_repository(snapshot: RepositorySnapshot) -> AnalysisReport:
    files = sorted({_normalize_path(path) for path in snapshot.files})
    directories = sorted({_normalize_path(path) for path in snapshot.directories})
    contents = {
        _normalize_path(path): text for path, text in snapshot.file_contents.items()
    }
    contents.update(
        {
            _normalize_path(path): text
            for path, text in snapshot.source_file_contents.items()
        }
    )
    detection_contents = {
        path: text
        for path, text in contents.items()
        if not PurePosixPath(path).name.lower().startswith("readme")
    }
    all_directories = sorted(set(directories) | _parent_directories(files))

    report = AnalysisReport(
        repository=snapshot.metadata,
        languages=_detect_languages(files),
        frameworks=_detect_frameworks(files, detection_contents),
        package_managers=_detect_package_managers(files),
        databases=_detect_databases(files, detection_contents),
        authentication=_detect_authentication(detection_contents),
        api_signals=_detect_api_signals(files, detection_contents),
        structure=_build_structure(files, all_directories),
        project_characteristics=_build_characteristics(files, all_directories),
        limitations=snapshot.limitations,
        findings=[],
        source_files_inspected=snapshot.source_files_inspected,
        source_files_skipped=snapshot.source_files_skipped,
        source_files_truncated=snapshot.source_files_truncated,
        source_content_truncated=snapshot.source_content_truncated,
        source_limitation_notes=snapshot.source_limitation_notes,
    )
    findings, health_summary = analyze_codebase_health(snapshot, report)
    report.findings = findings
    report.health_summary = health_summary
    return report


def _detect_languages(files: list[str]) -> list[DetectedSignal]:
    signals = []
    for extension, language in LANGUAGE_EXTENSIONS.items():
        evidence = [path for path in files if PurePosixPath(path).suffix == extension]
        if evidence:
            signals.append(_signal(language, "language", evidence))
    return sorted(signals, key=lambda signal: signal.name)


def _detect_frameworks(
    files: list[str], contents: dict[str, str]
) -> list[DetectedSignal]:
    signals: list[DetectedSignal] = []
    package_json = _content_path(files, contents, "package.json")
    python_manifests = _matching_manifest_paths(
        files,
        contents,
        {"requirements.txt", "pyproject.toml"},
    )

    if "pubspec.yaml" in files and _contains_any(
        contents.get("pubspec.yaml", ""), ["flutter:", "sdk: flutter"]
    ):
        signals.append(_signal("Flutter", "framework", _existing_evidence(files, "pubspec.yaml", "lib/")))
    fastapi_evidence = _matching_paths(contents, ["from fastapi", "import fastapi"])
    fastapi_evidence.extend(
        path for path, text in python_manifests.items()
        if _dependency_name_present(text, "fastapi")
    )
    if fastapi_evidence:
        signals.append(_signal("FastAPI", "framework", fastapi_evidence))
    if _content_contains(contents, ["django"]):
        signals.append(_signal("Django", "framework", _matching_paths(contents, ["django"])))
    flask_evidence = _matching_paths(contents, ["from flask", "import flask"])
    flask_evidence.extend(
        path for path, text in python_manifests.items()
        if _dependency_name_present(text, "flask")
    )
    if flask_evidence:
        signals.append(_signal("Flask", "framework", flask_evidence))
    if package_json is not None and _json_dependency_present(package_json[1], "express"):
        signals.append(_signal("Express", "framework", [package_json[0]]))
    if package_json is not None and _json_dependency_present(package_json[1], "react"):
        signals.append(_signal("React", "framework", [package_json[0]]))
    if package_json is not None and _json_dependency_present(package_json[1], "next"):
        signals.append(_signal("Next.js", "framework", [package_json[0]]))
    if package_json is not None and _json_dependency_present(package_json[1], "vue"):
        signals.append(_signal("Vue", "framework", [package_json[0]]))
    if package_json is not None and _json_dependency_present(package_json[1], "@angular/core"):
        signals.append(_signal("Angular", "framework", [package_json[0]]))
    if _content_contains(contents, ["springframework", "spring-boot"]):
        signals.append(_signal("Spring", "framework", _matching_paths(contents, ["spring"])))
    if _content_contains(contents, ["microsoft.aspnetcore", "asp.net"]):
        signals.append(_signal(".NET", "framework", _matching_paths(contents, ["asp.net", "aspnetcore"])))
    return sorted(signals, key=lambda signal: signal.name)


def _detect_package_managers(files: list[str]) -> list[DetectedSignal]:
    signals = []
    for filename, manager in PACKAGE_MANAGER_FILES.items():
        evidence = [path for path in files if PurePosixPath(path).name.lower() == filename]
        if evidence:
            signals.append(_signal(manager, "package_manager", evidence))
    return sorted(signals, key=lambda signal: signal.name)


def _detect_databases(
    files: list[str], contents: dict[str, str]
) -> list[DetectedSignal]:
    signals = []
    database_markers = {
        "MongoDB": ["mongodb", "pymongo", "mongoose"],
        "PostgreSQL": ["postgresql", "postgres", "psycopg", "asyncpg"],
        "MySQL": ["mysql", "pymysql"],
        "SQLite": ["sqlite", "sqlite3"],
        "Firebase": ["firebase", "google-services.json"],
        "Redis": ["redis", "ioredis"],
    }
    for name, markers in database_markers.items():
        evidence = _matching_paths(contents, markers)
        if name == "Firebase":
            evidence.extend(path for path in files if PurePosixPath(path).name == "google-services.json")
        if evidence:
            signals.append(_signal(name, "database", sorted(set(evidence))))
    return sorted(signals, key=lambda signal: signal.name)


def _detect_authentication(contents: dict[str, str]) -> list[DetectedSignal]:
    markers = {
        "JWT": ["jwt", "jsonwebtoken", "pyjwt", "authorization: bearer"],
        "OAuth": ["oauth", "openid"],
        "Session authentication": ["sessionmiddleware", "express-session", "session authentication", "session(", "session["],
        "Firebase Authentication": ["firebase/auth", "firebase authentication", "firebaseauth"],
        "Authorization middleware": ["authorization", "login_required", "get_current_user", "is_authenticated"],
    }
    signals = []
    for name, terms in markers.items():
        evidence = _matching_paths(contents, terms)
        if evidence:
            signals.append(_signal(name, "authentication", evidence))
    return sorted(signals, key=lambda signal: signal.name)


def _detect_api_signals(
    files: list[str], contents: dict[str, str]
) -> list[DetectedSignal]:
    signals = []
    patterns = {
        "FastAPI routes": [
            r"@(app|router)\.(get|post|put|patch|delete)\(",
            r"\bAPIRouter\s*\(",
        ],
        "Express routes": [],
        "GraphQL": [r"graphql", r"apollo"],
        "OpenAPI/Swagger": [r"openapi", r"swagger"],
        "HTTP client usage": [r"\brequests\.", r"\bhttpx\.", r"axios", r"dio\.", r"fetch\s*\("],
    }
    for name, regexes in patterns.items():
        if name == "Express routes":
            evidence = [
                path
                for path, text in contents.items()
                if re.search(r"\b(app|router)\.(get|post|put|patch|delete)\s*\(", text)
                and _contains_any(text, ["express", "express.router", "require('router'", 'require(\"router"'])
            ]
        else:
            evidence = _matching_paths(contents, regexes, regex=True)
        if name == "OpenAPI/Swagger":
            evidence.extend(
                path for path in files if PurePosixPath(path).name.lower() in {"openapi.yaml", "openapi.yml", "swagger.yaml", "swagger.yml"}
            )
        if evidence:
            signals.append(_signal(name, "api", sorted(set(evidence))))
    return sorted(signals, key=lambda signal: signal.name)


def _build_structure(files: list[str], directories: list[str]) -> ProjectStructure:
    top_level_files = sorted(path for path in files if "/" not in path)
    top_level_directories = sorted(
        path.split("/", 1)[0] for path in directories if path and "/" not in path
    )
    notable_paths = sorted(
        path
        for path in set(directories)
        if "/" not in path
        or PurePosixPath(path).name.lower() in NOTABLE_DIRECTORIES
    )
    return ProjectStructure(
        top_level_directories=top_level_directories,
        top_level_files=top_level_files,
        notable_paths=notable_paths,
    )


def _build_characteristics(
    files: list[str], directories: list[str]
) -> RepositoryCharacteristics:
    lower_files = {path.lower(): path for path in files}
    return RepositoryCharacteristics(
        has_readme=any(PurePosixPath(path).name.lower().startswith("readme") for path in files),
        has_license=any(PurePosixPath(path).name.lower().startswith("license") for path in files),
        has_ci_configuration=any(path.startswith(".github/workflows/") for path in files)
        or any(PurePosixPath(path).name.lower() in {".travis.yml", "circle.yml", "azure-pipelines.yml"} for path in files),
        has_docker_configuration=any(PurePosixPath(path).name.lower() in {"dockerfile", "docker-compose.yml", "docker-compose.yaml"} for path in files),
        has_test_directory=any(
            part.lower() in {"test", "tests", "__tests__"}
            for path in directories
            for part in path.split("/")
        ),
        has_environment_example=any(
            PurePosixPath(path).name.lower() in {".env.example", ".env.sample"}
            for path in files
        ),
        file_count=len(files),
        directory_count=len(directories),
        configuration_files=sorted(
            original
            for lower, original in lower_files.items()
            if lower.endswith((".yaml", ".yml", ".json", ".toml", ".xml", ".ini"))
            or PurePosixPath(lower).name in {"dockerfile", "makefile"}
        ),
    )


def _signal(name: str, category: str, evidence: Iterable[str]) -> DetectedSignal:
    return DetectedSignal(name=name, category=category, evidence=sorted(set(evidence)))  # type: ignore[arg-type]


def _normalize_path(path: str) -> str:
    return path.strip("/").replace("\\", "/")


def _parent_directories(files: list[str]) -> set[str]:
    parents = set()
    for path in files:
        parts = path.split("/")
        parents.update("/".join(parts[:index]) for index in range(1, len(parts)))
    return parents


def _content_path(
    files: list[str], contents: dict[str, str], filename: str
) -> tuple[str, str] | None:
    for path in files:
        if PurePosixPath(path).name.lower() == filename.lower() and path in contents:
            return path, contents[path]
    return None


def _content_contains(contents: dict[str, str], terms: list[str]) -> bool:
    return any(_contains_any(text, terms) for text in contents.values())


def _contains_any(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _matching_paths(
    contents: dict[str, str], terms: list[str], regex: bool = False
) -> list[str]:
    matches = []
    for path, text in contents.items():
        if regex:
            if any(re.search(term, text, re.IGNORECASE) for term in terms):
                matches.append(path)
        elif _contains_any(text, terms):
            matches.append(path)
    return sorted(matches)


def _existing_evidence(files: list[str], *paths: str) -> list[str]:
    evidence = []
    for path in paths:
        if path.endswith("/"):
            if any(file_path.startswith(path) for file_path in files):
                evidence.append(path)
        elif path in files:
            evidence.append(path)
    return evidence


def _json_dependency_present(package_json: str, dependency: str) -> bool:
    # Dependency names are checked as JSON keys without adding a JSON parser
    # because the detector only needs conservative key evidence.
    return re.search(rf'["\']{re.escape(dependency)}["\']\s*:', package_json) is not None


def _matching_manifest_paths(
    files: list[str], contents: dict[str, str], names: set[str]
) -> dict[str, str]:
    return {
        path: contents[path]
        for path in files
        if PurePosixPath(path).name.lower() in names and path in contents
    }


def _dependency_name_present(manifest: str, dependency: str) -> bool:
    return re.search(rf"(?im)^\s*{re.escape(dependency)}(?:\s*\[[^\]]+\])?\s*(?:[<>=!~]|$)", manifest) is not None or re.search(
        rf"[\"']{re.escape(dependency)}[\"']\s*:", manifest
    ) is not None
