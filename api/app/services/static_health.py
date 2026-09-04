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
TODO_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.I)


def analyze_codebase_health(snapshot: RepositorySnapshot, analysis: AnalysisReport) -> tuple[list[Finding], HealthSummary]:
    findings: list[Finding] = []
    findings.extend(_secret_findings(snapshot))
    findings.extend(_documentation_findings(snapshot, analysis))
    findings.extend(_todo_findings(snapshot))
    findings.extend(_testing_findings(snapshot, analysis))
    findings.extend(_structure_findings(snapshot, analysis))
    findings.extend(_repository_quality_findings(snapshot, analysis))
    findings.extend(_dependency_findings(snapshot))
    findings = sorted(findings, key=lambda finding: (finding.category, finding.id))
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
                "hardcoded_configuration", "configuration", "low", "Environment-specific URL may need review",
                "An environment-specific URL was found in inspected content. This is not automatically a secret.",
                [path], "medium", "Confirm that this endpoint belongs in versioned configuration and is safe for the target environment.",
            ))
    return findings


def _documentation_findings(snapshot: RepositorySnapshot, analysis: AnalysisReport) -> list[Finding]:
    readme_path = next((path for path in snapshot.file_contents if PurePosixPath(path).name.lower().startswith("readme")), None)
    if readme_path is None:
        return []
    readme = snapshot.file_contents[readme_path].lower()
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
                "TODO, FIXME, HACK, or XXX markers indicate review items; they are not automatically bugs.",
                [path], "high", "Review unresolved work markers before presenting the repository as production-ready.",
            ))
    return findings


def _testing_findings(snapshot: RepositorySnapshot, analysis: AnalysisReport) -> list[Finding]:
    test_paths = [path for path in snapshot.files if any(part.lower() in {"test", "tests", "__tests__"} for part in path.split("/"))]
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


def _structure_findings(snapshot: RepositorySnapshot, analysis: AnalysisReport) -> list[Finding]:
    findings = []
    deep_paths = [path for path in snapshot.files if len(path.split("/")) >= 7]
    if deep_paths:
        findings.append(_finding(
            "deep_path", "architecture", "low", "Some repository paths are unusually deep",
            "Deep paths can make navigation and ownership harder to understand; this is a structural observation, not a design verdict.",
            deep_paths[:10], "medium", "Review whether deeply nested modules can be grouped by clear responsibility.",
        ))
    large_files = [path for path, size in snapshot.file_sizes.items() if size > 100_000]
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


def _dependency_findings(snapshot: RepositorySnapshot) -> list[Finding]:
    manifests = [path for path in snapshot.files if PurePosixPath(path).name.lower() in {"package.json", "pubspec.yaml", "requirements.txt", "pyproject.toml", "pom.xml", "build.gradle", "build.gradle.kts", "cargo.toml", "go.mod", "composer.json"}]
    lockfiles = [path for path in snapshot.files if PurePosixPath(path).name.lower() in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "pubspec.lock", "poetry.lock", "cargo.lock", "go.sum", "composer.lock"}]
    if manifests and not lockfiles:
        return [_finding(
            "lockfile_missing", "dependencies", "low", "Dependency manifest found without a lockfile",
            "A dependency manifest is present, but no recognizable lockfile was found in the bounded tree.", manifests, "medium", "Consider committing the lockfile when reproducible dependency resolution is appropriate.",
        )]
    return []


def _finding(
    finding_id: str,
    category: str,
    severity: str,
    title: str,
    summary: str,
    evidence: list[str],
    confidence: str,
    recommendation: str,
) -> Finding:
    why_it_matters, recommended_action = _guidance(finding_id, recommendation)
    return Finding(
        id=finding_id,
        category=category,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        title=title,
        summary=summary,
        evidence=sorted(set(evidence)),
        affected_paths=sorted(set(evidence)),
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


def _all_inspected_contents(snapshot: RepositorySnapshot) -> dict[str, str]:
    contents = dict(snapshot.file_contents)
    contents.update(snapshot.source_file_contents)
    return contents
