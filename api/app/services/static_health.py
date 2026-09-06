import re
from collections import Counter
from pathlib import PurePosixPath

from app.schemas.analysis import (
    AnalysisReport,
    Finding,
    HealthSummary,
    RepositorySnapshot,
)


SECRET_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|apikey|secret|password|passwd|token|access[_-]?token)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]"
)
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
ENVIRONMENT_URL_PATTERN = re.compile(r"https?://(?:localhost|127\.0\.0\.1|dev\.|staging\.|internal\.)", re.I)
PRIVATE_NETWORK_PATTERN = re.compile(
    r"(?<!\d)(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(?!\d)"
)
INSECURE_URL_PATTERN = re.compile(
    r"\b(?:url|uri|endpoint|base[-_]?url|api[-_]?url|origin|host)\b\s*(?::|=)\s*[\"']?http://(?!localhost(?:[:/]|$)|127\.0\.0\.1(?:[:/]|$))[^\s'\"]+",
    re.I,
)
WILDCARD_CORS_PATTERN = re.compile(r"(?:allow_origins|origins)\s*=\s*\[[^\]]*[\"']\*[\"']", re.I)
DEBUG_PATTERN = re.compile(r"\b(?:debug|DEBUG)\s*=\s*(?:True|true|1)\b")
ENVIRONMENT_USAGE_PATTERN = re.compile(r"(?:os\.getenv|os\.environ|getenv\(|process\.env|String\.fromEnvironment)")
DATABASE_URL_PATTERN = re.compile(r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://", re.I)
TODO_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.I)

# These thresholds are intentionally simple review signals, not quality scores.
LARGE_SOURCE_FILE_BYTES = 100_000
DEEP_SOURCE_PATH_PARTS = 7
EXCESSIVE_WORK_MARKERS = 5
AUTH_BOUNDARY_PATTERN = re.compile(
    r"(?:@login_required|depends\s*\(\s*get_current_user|permission_classes|before_request|"
    r"app\.use\s*\([^\n]*auth|middleware[^\n]*auth|require_auth|protect\s*\()",
    re.I,
)
NON_SOURCE_PARTS = {"tests", "test", "docs", "doc", "vendor", "node_modules", "dist", "build", ".dart_tool", "generated"}
NON_SOURCE_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz", ".tar",
    ".key", ".pem", ".crt", ".cer", ".der", ".woff", ".woff2", ".ttf", ".otf",
}
SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".dart", ".java", ".kt", ".go", ".rs",
    ".rb", ".php", ".cs", ".swift", ".c", ".cpp", ".h", ".hpp", ".vue", ".html",
    ".css", ".scss", ".yaml", ".yml", ".toml", ".json", ".xml", ".ini",
}

FINDING_CATEGORY_ORDER = {
    "security": 0,
    "configuration": 1,
    "architecture": 2,
    "maintainability": 3,
    "testing": 4,
    "documentation": 5,
    "release": 6,
    "dependencies": 7,
    "repository_quality": 8,
}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}


def analyze_codebase_health(snapshot: RepositorySnapshot, analysis: AnalysisReport) -> tuple[list[Finding], HealthSummary]:
    findings: list[Finding] = []
    findings.extend(_secret_findings(snapshot))
    findings.extend(_documentation_findings(snapshot, analysis))
    findings.extend(_purpose_findings(snapshot, analysis))
    findings.extend(_configuration_findings(snapshot))
    findings.extend(_todo_findings(snapshot))
    findings.extend(_testing_findings(snapshot, analysis))
    findings.extend(_readiness_findings(snapshot, analysis))
    findings.extend(_structure_findings(snapshot, analysis))
    findings.extend(_architecture_findings(snapshot, analysis))
    findings.extend(_repository_quality_findings(snapshot, analysis))
    findings.extend(_dependency_findings(snapshot, analysis))
    findings = sorted(findings, key=_finding_sort_key)
    category_counts = dict(sorted(Counter(finding.category for finding in findings).items()))
    severity_counts = dict(sorted(Counter(finding.severity for finding in findings).items()))
    return findings, HealthSummary(
        total_findings=len(findings),
        category_counts=category_counts,
        severity_counts=severity_counts,
    )


def _secret_findings(snapshot: RepositorySnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for path, content in _all_inspected_contents(snapshot).items():
        if _is_documentation_path(path):
            continue
        if _is_test_certificate_fixture(path):
            continue
        if PRIVATE_KEY_PATTERN.search(content):
            findings.append(_finding(
                "potential_secret", "security", "high", "Potential private key exposed",
                "A private-key marker was found in inspected content; the key material is not included in this report.",
                [path], "high", "Remove the key material, rotate the credential, and use a secret manager.",
            ))
        elif SECRET_PATTERN.search(content):
            findings.append(_finding(
                "potential_secret", "security", "high", "Potential credential exposed",
                "A credential-like assignment was found in inspected content; the value is intentionally redacted.",
                [path], "medium", "Remove the value from repository history and use environment-based secret storage.",
            ))
        if ENVIRONMENT_URL_PATTERN.search(content):
            findings.append(_finding(
                "hardcoded_configuration", "configuration", "low", "Development endpoint detected",
                "A localhost, development, staging, or internal endpoint was found in inspected content. This is configuration context, not automatically a security problem or secret.",
                [path], "medium", "Confirm that this endpoint belongs in versioned configuration and is safe for the target environment.",
            ))
        if PRIVATE_NETWORK_PATTERN.search(content):
            findings.append(_finding(
                "private_network_address", "configuration", "low", "Private network address may need review",
                "A private-network address was found in inspected operational content. This may be intentional development or deployment configuration.",
                [f"{path}: private-network address detected"], "medium", "Confirm that the address is appropriate for the target environment and move environment-specific values into configuration when practical.",
                affected_paths=[path],
            ))
        if INSECURE_URL_PATTERN.search(content):
            findings.append(_finding(
                "insecure_http_endpoint", "security", "low", "HTTP endpoint may need review",
                "An HTTP endpoint was found in inspected operational content. The analyzer cannot determine whether it is protected by a trusted network.",
                [f"{path}: HTTP endpoint detected"], "medium", "Prefer HTTPS for production traffic and confirm whether this endpoint is development-only.",
                affected_paths=[path],
            ))
        if DATABASE_URL_PATTERN.search(content):
            findings.append(_finding(
                "database_connection_string", "security", "medium", "Database connection string detected",
                "A database connection-string pattern was found; any credential material is intentionally excluded from this report.",
                [f"{path}: database connection-string pattern detected"], "medium", "Keep connection strings and credentials outside source control and use environment-based configuration.",
                affected_paths=[path],
            ))
    return findings


def _purpose_findings(snapshot: RepositorySnapshot, analysis: AnalysisReport) -> list[Finding]:
    readme_path = next((path for path in snapshot.file_contents if PurePosixPath(path).name.lower().startswith("readme")), None)
    if readme_path is None:
        return []
    purpose = " ".join(
        part for part in [snapshot.file_contents.get(readme_path, ""), snapshot.metadata.description or ""] if part
    ).lower()
    findings: list[Finding] = []
    frameworks = {signal.name for signal in analysis.frameworks}
    languages = {signal.name for signal in analysis.languages}
    roots = {path.split("/", 1)[0].lower() for path in analysis.structure.notable_paths}
    backend_evidence = frameworks & {"FastAPI", "Django", "Flask", "Express", "Spring", ".NET"}
    has_backend = bool(backend_evidence or analysis.api_signals or roots & {"api", "backend", "server"})
    claims = [
        ("flutter", "mobile", "Flutter", bool("Flutter" in frameworks or "Dart" in languages), "purpose_flutter_not_observed"),
        ("api", "backend", "API/backend", has_backend, "purpose_api_not_observed"),
        ("backend", "backend", "API/backend", has_backend, "purpose_backend_not_observed"),
        ("postgresql", "database", "PostgreSQL", "PostgreSQL" in {signal.name for signal in analysis.databases}, "purpose_database_not_observed"),
        ("mongodb", "database", "MongoDB", "MongoDB" in {signal.name for signal in analysis.databases}, "purpose_database_not_observed"),
        ("authentication", "authentication", "authentication", bool(analysis.authentication), "purpose_authentication_not_observed"),
        ("docker", "Docker", "Docker", analysis.project_characteristics.has_docker_configuration, "purpose_docker_not_observed"),
    ]
    seen_ids: set[str] = set()
    for term, label, name, supported, finding_id in claims:
        if term not in purpose or supported or finding_id in seen_ids:
            continue
        seen_ids.add(finding_id)
        findings.append(_finding(
            finding_id, "documentation", "low", f"Purpose claim not verified: {name}",
            f"The README or repository description mentions {label}, but matching evidence was not found in the bounded inspection. This is a potential inconsistency, not proof that the claim is false.",
            [readme_path], "medium", "Review the stated purpose against the current implementation and add or update supporting documentation.",
        ))
    if ("full-stack" in purpose or "frontend and backend" in purpose or "frontend/backend" in purpose) and not (
        roots & {"client", "frontend", "mobile"} and roots & {"api", "backend", "server"}
    ):
        findings.append(_finding(
            "purpose_multicomponent_not_observed", "documentation", "low", "Multiple-component purpose not verified",
            "The documentation describes multiple application components, but the bounded structure does not show both a client/frontend and backend area.",
            [readme_path], "medium", "Verify the documented component boundaries against the current repository structure.",
        ))
    return findings


def _configuration_findings(snapshot: RepositorySnapshot) -> list[Finding]:
    findings: list[Finding] = []
    for path, content in _all_inspected_contents(snapshot).items():
        if _is_documentation_path(path):
            continue
        if WILDCARD_CORS_PATTERN.search(content):
            findings.append(_finding(
                "wildcard_cors", "security", "low", "Wildcard CORS configuration detected",
                "A wildcard CORS origin was found in inspected operational content. The analyzer cannot determine the deployment context.",
                [f"{path}: wildcard CORS origin detected"], "medium", "Restrict allowed origins to the clients and environments that require access.",
                affected_paths=[path],
            ))
        if DEBUG_PATTERN.search(content):
            findings.append(_finding(
                "debug_configuration", "configuration", "low", "Debug configuration enabled",
                "A debug setting appears enabled in inspected operational content; this may be appropriate for development but should be reviewed for deployment.",
                [f"{path}: debug setting detected"], "medium", "Keep debug settings environment-specific and disabled where production configuration requires it.",
                affected_paths=[path],
            ))
    return findings


def _documentation_findings(snapshot: RepositorySnapshot, analysis: AnalysisReport) -> list[Finding]:
    readme_path = next((path for path in snapshot.file_contents if PurePosixPath(path).name.lower().startswith("readme")), None)
    if readme_path is None:
        return []
    documentation = {
        path: content.lower()
        for path, content in _all_inspected_contents(snapshot).items()
        if _is_documentation_path(path)
    }
    readme = documentation[readme_path]
    detected = {signal.name.lower() for signal in analysis.frameworks + analysis.languages + analysis.databases + analysis.authentication}
    findings = []
    claims = {
        "flutter": "Flutter",
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
        "express": "Express",
        "react": "React",
        "next.js": "Next.js",
        "postgresql": "PostgreSQL",
        "mongodb": "MongoDB",
        "jwt": "JWT",
        "oauth": "OAuth",
    }
    for term, name in claims.items():
        if term not in readme:
            continue
        if name.lower() in detected:
            findings.append(_finding(
                "documentation_verified", "documentation", "info", f"README claim supported: {name}",
                f"The README mentions {name}, and matching deterministic evidence was detected.",
                [readme_path], "high", "Keep the documentation aligned with the detected repository evidence.",
            ))
        else:
            findings.append(_finding(
                "documentation_unverified", "documentation", "low", f"README claim could not be verified: {name}",
                f"The README mentions {name}, but matching evidence was not found in the bounded inspection. This does not prove the claim is false.",
                [readme_path], "medium", "Review the claim or provide the relevant configuration/dependency evidence.",
            ))
    checks = [
        ("setup_instructions_not_detected", ("install", "setup", "getting started", "requirements", "dependencies"), "setup/install instructions"),
        ("testing_instructions_not_detected", ("pytest", "flutter test", "npm test", "test suite", "testing"), "testing instructions"),
        ("deployment_instructions_not_detected", ("deploy", "deployment", "production", "docker"), "deployment instructions"),
        ("architecture_documentation_not_detected", ("architecture", "folder structure", "project structure", "api"), "architecture information"),
    ]
    for finding_id, terms, label in checks:
        if finding_id == "deployment_instructions_not_detected" and _is_library_repository(analysis):
            continue
        evidence_paths = [
            path for path, content in documentation.items()
            if any(term in content for term in terms)
        ]
        if not evidence_paths:
            findings.append(_finding(
                finding_id, "documentation", "low", f"{label.capitalize()} not detected",
                f"The README does not contain recognizable {label}. This does not prove the information is unavailable elsewhere.",
                [readme_path], "medium", f"Add concise {label} for developers who need to run or extend the project.",
            ))
    return findings


def _todo_findings(snapshot: RepositorySnapshot) -> list[Finding]:
    findings = []
    for path, content in _all_inspected_contents(snapshot).items():
        if PurePosixPath(path).name.lower().startswith("readme") or PurePosixPath(path).suffix.lower() in {".md", ".rst"}:
            continue
        matches = TODO_PATTERN.findall(content)
        if matches:
            count = len(matches)
            findings.append(_finding(
                "todo_markers", "maintainability", "low", f"{count} unresolved-work marker{'s' if count != 1 else ''} detected",
                f"TODO, FIXME, HACK, or XXX markers indicate review items; they are not automatically bugs. {'The count exceeds the review threshold of ' + str(EXCESSIVE_WORK_MARKERS) + '.' if count > EXCESSIVE_WORK_MARKERS else ''}",
                [path], "high", "Review unresolved work markers before presenting the repository as production-ready.",
            ))
    return findings


def _testing_findings(snapshot: RepositorySnapshot, analysis: AnalysisReport) -> list[Finding]:
    test_paths = [
        path for path in snapshot.files
        if any(part.lower() in {"test", "tests", "__tests__"} for part in path.split("/"))
        and _is_test_evidence_path(path)
    ]
    if test_paths or analysis.project_characteristics.has_test_directory:
        return [_finding(
            "test_evidence", "testing", "info", "Automated test evidence detected",
            "Test directories or test files are present in the inspected repository.",
            sorted(set(test_paths)) or ["test directory"], "high", "Keep the test suite maintained as the codebase changes.",
        )]
    if analysis.project_characteristics.file_count > 10 and not snapshot.limitations.paths_truncated:
        return [_finding(
            "missing_test_evidence", "testing", "low", "No obvious test suite detected",
            "The inspected repository has multiple files but no recognizable test directory or test file.",
            ["inspected repository tree"], "medium", "Consider adding automated tests appropriate to the detected project type.",
        )]
    return []


def _readiness_findings(snapshot: RepositorySnapshot, analysis: AnalysisReport) -> list[Finding]:
    characteristics = analysis.project_characteristics
    frameworks = {signal.name for signal in analysis.frameworks}
    app_like = bool(
        frameworks
        or analysis.api_signals
        or {path.split("/", 1)[0].lower() for path in analysis.structure.notable_paths}
        & {"client", "frontend", "mobile", "api", "backend", "server"}
    )
    findings: list[Finding] = []
    if app_like and not characteristics.has_ci_configuration:
        findings.append(_finding(
            "ci_not_detected", "testing", "low", "CI configuration not detected",
            "No recognizable CI configuration was found in the bounded repository tree. This does not prove that CI is absent elsewhere.",
            ["inspected repository tree"], "medium", "Consider adding automated checks for tests and static analysis if this project is maintained as an application.",
        ))
    if not characteristics.has_environment_example and any(
        ENVIRONMENT_USAGE_PATTERN.search(content)
        for path, content in _all_inspected_contents(snapshot).items()
        if not _is_documentation_path(path)
    ):
        findings.append(_finding(
            "environment_template_not_detected", "configuration", "low", "Environment usage found without a template",
            "Environment-variable usage was detected, but no recognizable environment example or template was found in the bounded tree.",
            ["inspected repository tree"], "medium", "Document required environment variables with a safe example that contains no credentials.",
        ))
    deployment_paths = [
        path for path in snapshot.files
        if PurePosixPath(path).name.lower() in {"dockerfile", "docker-compose.yml", "docker-compose.yaml", "procfile"}
        or PurePosixPath(path).name.lower() in {"deploy.sh", "deploy.yml", "deploy.yaml"}
    ]
    if characteristics.has_docker_configuration or deployment_paths:
        findings.append(_finding(
            "deployment_configuration_detected", "release", "info", "Deployment configuration detected",
            "The bounded repository tree contains recognizable deployment or container configuration.",
            deployment_paths or [path for path in snapshot.files if PurePosixPath(path).name.lower() == "dockerfile"], "high", "Keep deployment instructions and environment requirements documented.",
        ))
    return findings


def _structure_findings(snapshot: RepositorySnapshot, analysis: AnalysisReport) -> list[Finding]:
    findings = []
    deep_paths = [
        path for path in snapshot.files
        if len(path.split("/")) >= DEEP_SOURCE_PATH_PARTS
        and _is_maintainability_source_path(path)
    ]
    if deep_paths:
        findings.append(_finding(
            "deep_path", "architecture", "low", "Some repository paths are unusually deep",
            "Deep paths can make navigation and ownership harder to understand; this is a structural observation, not a design verdict.",
            deep_paths[:10], "medium", "Review whether deeply nested modules can be grouped by clear responsibility.",
        ))
    large_files = [
        path for path, size in snapshot.file_sizes.items()
        if size > LARGE_SOURCE_FILE_BYTES and _is_maintainability_source_path(path)
    ]
    if large_files:
        findings.append(_finding(
            "large_file", "maintainability", "low", "Large files may deserve review",
            "The tree metadata reports files larger than 100 KB. No source code was executed or interpreted.",
            large_files[:10], "high", "Consider whether large files can be split by responsibility.",
        ))
    roots = {path.split("/", 1)[0].lower() for path in analysis.structure.notable_paths}
    if {"client", "frontend", "mobile"} & roots and {"api", "backend", "server"} & roots:
        findings.append(_finding(
            "client_backend_separation", "architecture", "info", "Client and backend areas are separated",
            "Top-level structure contains recognizable client/frontend/mobile and backend/API/server areas.",
            sorted(roots & {"client", "frontend", "mobile", "api", "backend", "server"}), "high", "Document the boundary and communication contract between these areas.",
        ))
    if {"api", "backend", "server"} & roots and not {"client", "frontend", "mobile"} & roots:
        findings.append(_finding(
            "backend_only_repository", "architecture", "info", "Backend-only structure observed",
            "The bounded top-level structure contains backend/API areas without a recognizable client/frontend area. This is a structural classification, not a runtime conclusion.",
            sorted(roots & {"api", "backend", "server"}), "medium", "Document the service boundary and any external clients that are maintained elsewhere.",
        ))
    if {"client", "frontend", "mobile"} & roots and not {"api", "backend", "server"} & roots:
        findings.append(_finding(
            "frontend_only_repository", "architecture", "info", "Frontend-only structure observed",
            "The bounded top-level structure contains client/frontend/mobile areas without a recognizable backend area. This is a structural classification, not a runtime conclusion.",
            sorted(roots & {"client", "frontend", "mobile"}), "medium", "Document the external services or APIs this client depends on.",
        ))
    return findings


def _architecture_findings(snapshot: RepositorySnapshot, analysis: AnalysisReport) -> list[Finding]:
    findings: list[Finding] = []
    boundary_signals = [
        signal for signal in analysis.api_signals
        if signal.name in {"FastAPI routes", "Express routes", "GraphQL", "OpenAPI/Swagger"}
    ]
    if boundary_signals:
        paths = [path for signal in boundary_signals for path in signal.evidence]
        findings.append(_finding(
            "api_boundary_observed", "architecture", "info", "API boundary evidence detected",
            "Observable route, API, or protocol signals suggest an API boundary; this is not a complete API inventory.",
            [f"{path}: API signal detected" for path in sorted(set(paths))], "high", "Document the exposed boundary and its request/response contract.",
            affected_paths=paths,
        ))
    elif any(signal.name == "HTTP client usage" for signal in analysis.api_signals):
        paths = [
            path for signal in analysis.api_signals
            if signal.name == "HTTP client usage"
            for path in signal.evidence
        ]
        findings.append(_finding(
            "http_client_usage_observed", "architecture", "info", "HTTP client usage detected",
            "The repository contains HTTP client usage, but no service API boundary was inferred from that signal alone.",
            [f"{path}: HTTP client usage detected" for path in sorted(set(paths))], "high", "Review the client integration separately from server route or API-boundary analysis.",
            affected_paths=paths,
        ))
    if analysis.databases:
        paths = [path for signal in analysis.databases for path in signal.evidence]
        findings.append(_finding(
            "database_integration_observed", "architecture", "info", "Database integration evidence detected",
            "Configuration or source evidence suggests database integration; runtime connectivity was not verified.",
            [f"{path}: database signal detected" for path in sorted(set(paths))], "medium", "Document the data boundary and required connection configuration.",
            affected_paths=paths,
        ))
    if analysis.authentication and _has_application_auth_boundary(snapshot, analysis):
        paths = [path for signal in analysis.authentication for path in signal.evidence]
        findings.append(_finding(
            "authentication_boundary_observed", "architecture", "info", "Authentication boundary evidence detected",
            "Authentication-related implementation signals were detected; security and runtime behavior were not verified.",
            [f"{path}: authentication signal detected" for path in sorted(set(paths))], "medium", "Document where authentication is applied and how protected boundaries are defined.",
            affected_paths=paths,
        ))
    elif analysis.authentication:
        paths = [path for signal in analysis.authentication for path in signal.evidence]
        findings.append(_finding(
            "authentication_library_support_observed", "architecture", "info", "Authentication functionality detected",
            "Authentication-related functionality was detected in bounded source or configuration, but route protection or application middleware evidence was not found. This may represent client or library support.",
            [f"{path}: authentication functionality detected" for path in sorted(set(paths))], "high", "Review the relevant callers before interpreting this functionality as an application authentication boundary.",
            affected_paths=paths,
        ))
    manifest_paths = [
        path for path in snapshot.files
        if PurePosixPath(path).name.lower() in {"package.json", "pubspec.yaml", "pyproject.toml", "requirements.txt", "go.mod", "cargo.toml"}
        and not _is_documentation_only_path(path)
    ]
    if len(manifest_paths) > 1 and len({PurePosixPath(path).parent for path in manifest_paths}) > 1:
        findings.append(_finding(
            "monorepo_structure_observed", "architecture", "info", "Multiple package areas observed",
            "More than one dependency manifest appears in separate repository areas, suggesting a multi-package structure.",
            manifest_paths, "high", "Document package ownership and how the package areas are built or released.",
        ))
    return findings


def _repository_quality_findings(snapshot: RepositorySnapshot, analysis: AnalysisReport) -> list[Finding]:
    files = {PurePosixPath(path).name.lower(): path for path in snapshot.files}
    findings = []
    if not analysis.project_characteristics.has_readme:
        findings.append(_finding(
            "missing_readme", "repository_quality", "low", "README not detected",
            "No README file was found in the bounded repository tree.", ["inspected repository tree"], "high", "Add a concise README covering purpose, setup, and current limitations.",
        ))
    if not any(name.startswith("license") for name in files):
        findings.append(_finding(
            "missing_license", "repository_quality", "info", "License not detected",
            "No recognizable license file was found in the bounded repository tree.", ["inspected repository tree"], "high", "Add a license if the project is intended for public reuse.",
        ))
    if ".gitignore" not in files:
        findings.append(_finding(
            "missing_gitignore", "repository_quality", "low", ".gitignore not detected",
            "No .gitignore file was found in the bounded repository tree.", ["inspected repository tree"], "high", "Add ignores for local tooling, build output, and environment files.",
        ))
    for path in snapshot.files:
        if PurePosixPath(path).name.lower() in {".env", ".env.local", ".env.production"}:
            findings.append(_finding(
                "tracked_environment_file", "security", "medium", "Environment file appears in repository tree",
                "A non-example environment file is visible in the inspected tree; values were not fetched or displayed.", [path], "high", "Remove environment files from version control and keep only safe examples.",
            ))
    generated = [path for path in snapshot.files if any(part.lower() in {"node_modules", ".dart_tool", "__pycache__", "dist", "build"} for part in path.split("/"))]
    if generated:
        findings.append(_finding(
            "generated_artifacts", "repository_quality", "info", "Generated or build artifacts detected",
            "Common generated/build directories are present. Their legitimacy depends on the project workflow.", generated[:10], "high", "Confirm generated artifacts are intentional and ignored when appropriate.",
        ))
    return findings


def _dependency_findings(snapshot: RepositorySnapshot, analysis: AnalysisReport) -> list[Finding]:
    manifests = [
        path for path in snapshot.files
        if PurePosixPath(path).name.lower() in {
            "package.json", "pubspec.yaml", "requirements.txt", "pyproject.toml", "pom.xml",
            "build.gradle", "build.gradle.kts", "cargo.toml", "go.mod", "composer.json",
            "setup.py", "setup.cfg",
        }
        and not _is_documentation_only_path(path)
    ]
    lockfiles = [path for path in snapshot.files if PurePosixPath(path).name.lower() in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "pubspec.lock", "poetry.lock", "cargo.lock", "go.sum", "composer.lock"}]
    findings: list[Finding] = []
    if manifests and not lockfiles and not _is_library_repository(analysis):
        findings.append(_finding(
            "lockfile_missing", "dependencies", "low", "Dependency manifest found without a lockfile",
            "A dependency manifest is present, but no recognizable lockfile was found in the bounded tree.", manifests, "medium", "Consider committing the lockfile when reproducible dependency resolution is appropriate.",
        ))
    if len(manifests) > 1:
        ecosystems = {PurePosixPath(path).name.lower() for path in manifests}
        findings.append(_finding(
            "multiple_dependency_manifests", "dependencies", "info", "Multiple dependency manifests detected",
            "More than one dependency-management manifest is present. This may be intentional for a multi-language or multi-package repository.",
            manifests, "high", f"Document the ownership and build boundary for: {', '.join(sorted(ecosystems))}.",
        ))
    return findings


def _finding_sort_key(finding: Finding) -> tuple[int, int, int, str]:
    return (
        FINDING_CATEGORY_ORDER.get(finding.category, len(FINDING_CATEGORY_ORDER)),
        SEVERITY_ORDER.get(finding.severity, len(SEVERITY_ORDER)),
        CONFIDENCE_ORDER.get(finding.confidence, len(CONFIDENCE_ORDER)),
        finding.id,
    )


def _is_library_repository(analysis: AnalysisReport) -> bool:
    directories = {path.split("/", 1)[0].lower() for path in analysis.structure.notable_paths}
    package_managers = {signal.name for signal in analysis.package_managers}
    framework_names = {signal.name for signal in analysis.frameworks}
    has_app_boundary = bool(
        framework_names & {"FastAPI", "Django", "Flask", "Express", "Spring", ".NET", "Flutter", "React", "Next.js", "Vue", "Angular"}
        or directories & {"client", "frontend", "mobile", "api", "backend", "server"}
        or {signal.name for signal in analysis.api_signals} & {"FastAPI routes", "Express routes", "GraphQL", "OpenAPI/Swagger"}
    )
    return bool(directories & {"src", "lib"}) and bool(
        package_managers & {"Python Packaging", "pip", "npm", "Dart Pub", "Cargo", "Go Modules"}
    ) and not has_app_boundary




def _finding(
    finding_id: str,
    category: str,
    severity: str,
    title: str,
    summary: str,
    evidence: list[str],
    confidence: str,
    recommendation: str,
    affected_paths: list[str] | None = None,
) -> Finding:
    why_it_matters, recommended_action = _guidance(finding_id, recommendation)
    return Finding(
        id=finding_id,
        category=category,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        title=title,
        summary=summary,
        evidence=sorted(set(evidence)),
        affected_paths=sorted(set(affected_paths or evidence)),
        confidence=confidence,  # type: ignore[arg-type]
        recommendation=recommendation,
        why_it_matters=why_it_matters,
        recommended_action=recommended_action,
    )


_GUIDANCE: dict[str, tuple[str, str]] = {
    "potential_secret": (
        "Private key material in a repository can allow unauthorized access if it is usable.",
        "Remove the key material, rotate the credential, and use a secret manager.",
    ),
    "credential-like-assignment": (
        "Credential-like values in source can expose access and make safe configuration management harder.",
        "Remove the value from repository history and use environment-based secret storage.",
    ),
    "hardcoded_configuration": (
        "Environment-specific configuration embedded in source can make deployment and configuration management harder.",
        "Move environment-specific values into an appropriate configuration mechanism and keep secrets outside source control.",
    ),
    "private_network_address": (
        "Private addresses can couple a repository to one development or deployment network.",
        "Confirm the address is environment-appropriate and move it into configuration when practical.",
    ),
    "insecure_http_endpoint": (
        "Unencrypted HTTP can expose traffic when it crosses an untrusted network.",
        "Prefer HTTPS for production traffic and confirm whether this endpoint is development-only.",
    ),
    "database_connection_string": (
        "Connection strings can include credentials or reveal infrastructure details.",
        "Keep connection strings outside source control and use environment-based configuration.",
    ),
    "wildcard_cors": (
        "Wildcard CORS can allow unexpected web origins to call a browser-accessible API.",
        "Restrict allowed origins to the clients and environments that require access.",
    ),
    "debug_configuration": (
        "Debug settings can expose diagnostic behavior or unsafe defaults in a deployed service.",
        "Keep debug settings environment-specific and disabled where production configuration requires it.",
    ),
    "environment_template_not_detected": (
        "Undocumented environment variables make setup less reproducible and can encourage unsafe secret handling.",
        "Document required variables with a safe example that contains no credentials.",
    ),
    "ci_not_detected": (
        "Without visible CI checks, regressions may not be caught consistently before changes are merged.",
        "Consider adding automated tests and static analysis to a CI workflow.",
    ),
    "deployment_configuration_detected": (
        "Deployment configuration helps explain how the project is intended to run outside development.",
        "Keep deployment instructions and environment requirements documented.",
    ),
    "api_boundary_observed": (
        "An explicit API boundary helps reviewers understand how clients and services communicate.",
        "Document the exposed boundary and its request/response contract.",
    ),
    "http_client_usage_observed": (
        "HTTP client usage identifies an outbound integration, not necessarily a server API boundary.",
        "Document the external service contract separately from server route analysis.",
    ),
    "database_integration_observed": (
        "A database boundary identifies where persistence and operational configuration enter the system.",
        "Document the data boundary and required connection configuration.",
    ),
    "authentication_boundary_observed": (
        "An authentication boundary identifies where access-control behavior must be reviewed carefully.",
        "Document where authentication is applied and how protected boundaries are defined.",
    ),
    "authentication_library_support_observed": (
        "Authentication functionality in a client or library is not the same as an application access-control boundary.",
        "Review the callers and route protection before treating this as application authentication.",
    ),
    "backend_only_repository": (
        "A backend-only structure helps identify the service boundary, but does not describe runtime consumers.",
        "Document external clients or dependent systems when they are maintained outside this repository.",
    ),
    "frontend_only_repository": (
        "A frontend-only structure identifies a client boundary, but does not describe the external services it calls.",
        "Document the external APIs or services required by this client.",
    ),
    "monorepo_structure_observed": (
        "Multiple package areas can increase build and ownership complexity.",
        "Document package ownership and how the package areas are built or released.",
    ),
    "purpose_flutter_not_observed": (
        "A purpose claim without matching bounded evidence can mislead readers about the repository contents.",
        "Review the stated purpose against the current implementation and supporting files.",
    ),
    "purpose_api_not_observed": (
        "An unverified API claim can make the repository architecture harder to understand.",
        "Review the API claim against detected routes, frameworks, and structure.",
    ),
    "purpose_backend_not_observed": (
        "An unverified backend claim can make the repository architecture harder to understand.",
        "Review the backend claim against detected frameworks, routes, and structure.",
    ),
    "purpose_database_not_observed": (
        "An unverified database claim can create incorrect expectations about persistence.",
        "Review the database claim against detected dependencies and configuration.",
    ),
    "purpose_multicomponent_not_observed": (
        "A multi-component claim without matching boundaries can confuse contributors about project layout.",
        "Verify the documented component boundaries against the repository structure.",
    ),
    "purpose_authentication_not_observed": (
        "An unverified authentication claim can create incorrect expectations about access control.",
        "Review the authentication claim against detected implementation and configuration evidence.",
    ),
    "purpose_docker_not_observed": (
        "An unverified Docker claim can make setup and deployment expectations unclear.",
        "Review the Docker claim against the bounded repository tree and deployment configuration.",
    ),
    "backend_only_repository": (
        "A backend-only structure helps identify the service boundary, but does not describe runtime consumers.",
        "Document external clients or dependent systems when they are maintained outside this repository.",
    ),
    "frontend_only_repository": (
        "A frontend-only structure identifies a client boundary, but does not describe the external services it calls.",
        "Document the external APIs or services required by this client.",
    ),
    "setup_instructions_not_detected": (
        "Missing setup guidance makes local reproduction harder for developers and reviewers.",
        "Add concise installation and setup steps to the README.",
    ),
    "testing_instructions_not_detected": (
        "Missing testing guidance makes it harder to verify changes consistently.",
        "Document the commands used to run the repository's tests.",
    ),
    "deployment_instructions_not_detected": (
        "Missing deployment guidance leaves the intended release path unclear.",
        "Document deployment prerequisites and the supported release process.",
    ),
    "architecture_documentation_not_detected": (
        "Missing architecture guidance makes boundaries and responsibilities harder to discover.",
        "Add a short architecture or project-structure explanation to the README.",
    ),
    "multiple_dependency_manifests": (
        "Multiple manifests can be intentional, but undocumented boundaries make dependency maintenance harder.",
        "Document which package or ecosystem owns each manifest and how they are built.",
    ),
    "documentation_verified": (
        "Matching evidence gives users a concrete basis for the documented technology claim.",
        "Keep the documentation aligned with the detected repository evidence.",
    ),
    "documentation_unverified": (
        "Incorrect documentation can mislead users, contributors, and recruiters, but missing evidence does not prove the claim false.",
        "Verify the README claim against the current implementation or provide the relevant dependency/configuration evidence.",
    ),
    "todo_markers": (
        "Unresolved markers can indicate unfinished work or technical debt.",
        "Review the markers and resolve or document them before presenting the repository as production-ready.",
    ),
    "test_evidence": (
        "Automated test evidence helps reviewers understand where regressions may be checked.",
        "Keep the test suite maintained as the codebase changes.",
    ),
    "missing_test_evidence": (
        "Limited automated testing makes regressions harder to detect.",
        "Add tests around important business logic and API behavior.",
    ),
    "deep_path": (
        "Very deep paths can make navigation and ownership harder to understand.",
        "Review whether deeply nested modules can be grouped by clear responsibility.",
    ),
    "large_file": (
        "Very large files can make maintenance and review harder.",
        "Consider separating unrelated responsibilities into smaller modules.",
    ),
    "client_backend_separation": (
        "A visible client/backend boundary can help contributors locate responsibilities and integration points.",
        "Document the boundary and communication contract between these areas.",
    ),
    "missing_readme": (
        "Without a README, users and contributors have less context for purpose and setup.",
        "Add a concise README covering purpose, setup, and current limitations.",
    ),
    "missing_license": (
        "Without a license, reuse and contribution permissions may be unclear.",
        "Add a license if the project is intended for public reuse.",
    ),
    "missing_gitignore": (
        "Missing ignores can allow local tooling, build output, or environment files into version control.",
        "Add ignores for local tooling, build output, and environment files.",
    ),
    "tracked_environment_file": (
        "Tracked environment files can expose deployment-specific configuration or secrets.",
        "Remove environment files from version control and keep only safe examples.",
    ),
    "generated_artifacts": (
        "Generated artifacts can add noise and may become stale when committed unintentionally.",
        "Confirm generated artifacts are intentional and ignored when appropriate.",
    ),
    "lockfile_missing": (
        "Without a lockfile, dependency resolution may vary between environments.",
        "Consider committing the lockfile when reproducible dependency resolution is appropriate.",
    ),
}


def _guidance(finding_id: str, fallback_action: str) -> tuple[str, str]:
    guidance = _GUIDANCE.get(finding_id)
    if guidance is not None:
        return guidance
    return "This static observation should be reviewed in the context of the repository.", fallback_action


def _has_application_auth_boundary(snapshot: RepositorySnapshot, analysis: AnalysisReport) -> bool:
    if not analysis.api_signals:
        return False
    return any(
        AUTH_BOUNDARY_PATTERN.search(content)
        for path, content in _all_inspected_contents(snapshot).items()
        if not _is_documentation_path(path)
    )


def _is_documentation_only_path(path: str) -> bool:
    return any(part.lower() in {"docs", "doc", "documentation"} for part in PurePosixPath(path).parts[:-1])


def _is_test_certificate_fixture(path: str) -> bool:
    parts = {part.lower() for part in PurePosixPath(path).parts}
    suffix = PurePosixPath(path).suffix.lower()
    return bool(parts & {"test", "tests"}) and suffix in {".key", ".pem", ".crt", ".cer", ".der"}


def _is_test_evidence_path(path: str) -> bool:
    pure_path = PurePosixPath(path)
    return not _is_test_certificate_fixture(path) and pure_path.suffix.lower() not in NON_SOURCE_SUFFIXES


def _is_maintainability_source_path(path: str) -> bool:
    pure_path = PurePosixPath(path)
    parts = {part.lower() for part in pure_path.parts[:-1]}
    if parts & NON_SOURCE_PARTS or pure_path.suffix.lower() in NON_SOURCE_SUFFIXES:
        return False
    return pure_path.suffix.lower() in SOURCE_SUFFIXES


def _is_documentation_path(path: str) -> bool:
    return PurePosixPath(path).name.lower().startswith("readme") or PurePosixPath(path).suffix.lower() in {".md", ".rst"}


def _all_inspected_contents(snapshot: RepositorySnapshot) -> dict[str, str]:
    contents = dict(snapshot.file_contents)
    contents.update(snapshot.source_file_contents)
    return contents
