"""Render a ProjectReport as a readable, deterministic Markdown document."""

from __future__ import annotations

from collections import defaultdict

from app.schemas.report import ProjectReport

SEVERITY_ORDER = ["high", "medium", "low", "info"]


def health_score(severity_counts: dict[str, int]) -> int:
    """0-100 heuristic. Keep identical to ``healthScore`` in the Flutter client."""
    raw = 100 - 18 * severity_counts.get("high", 0) - 8 * severity_counts.get("medium", 0) - 3 * severity_counts.get("low", 0)
    return max(0, min(100, raw))


def _cell(value: str | None) -> str:
    return (value or "-").replace("|", "\\|").replace("\n", " ")


def _bullets(items: list[str], empty: str = "_None._") -> list[str]:
    return [f"- {item}" for item in items] or [empty]


def _label(value: str) -> str:
    return value.replace("_", " ").capitalize()


def render_markdown(report: ProjectReport) -> str:
    repo = report.repository
    summary = report.health_summary
    score = health_score(summary.severity_counts)
    lines: list[str] = [f"# Repository report: {repo.full_name}", ""]

    if repo.description:
        lines += [f"> {repo.description}", ""]
    if repo.source == "local":
        lines += ["_Source: local analysis (folder or ZIP). GitHub metadata is not available._", ""]
    else:
        lines += [f"<{repo.html_url}>", ""]

    lines += ["## Summary", "", "| | |", "| --- | --- |"]
    lines.append(f"| Classification | {_cell(report.overview.primary_classification)} |")
    if repo.primary_language:
        lines.append(f"| Primary language | {_cell(repo.primary_language)} |")
    if repo.source != "local":
        lines.append(f"| Stars / forks | {repo.stars} / {repo.forks} |")
        lines.append(f"| Default branch | {_cell(repo.default_branch)} |")
    lines.append(f"| Static health score | {score}/100 (heuristic) |")
    lines.append(f"| Findings | {summary.total_findings} |")
    lines += ["", f"_{summary.overall}_", ""]
    lines += ["_The health score is a heuristic built from static finding severities. It is a prioritisation aid, not a guarantee of quality._", ""]

    lines += ["## What this repository is", ""]
    lines += _bullets(report.overview.classification_basis)
    lines.append("")

    lines += ["## Findings", ""]
    if not report.findings:
        lines += ["No static findings were emitted for the inspected evidence.", ""]
    grouped: dict[str, list] = defaultdict(list)
    for finding in report.findings:
        grouped[finding.severity].append(finding)
    for severity in SEVERITY_ORDER:
        for finding in grouped.get(severity, []):
            lines += [f"### [{severity.upper()}] {finding.title}", ""]
            lines += [f"*{_label(finding.category)} · {finding.confidence} confidence*", "", finding.summary, ""]
            if finding.why_it_matters:
                lines += [f"**Why it matters:** {finding.why_it_matters}", ""]
            action = finding.recommended_action or finding.recommendation
            if action:
                lines += [f"**Recommended action:** {action}", ""]
            lines += ["Evidence:", ""] + [f"- `{item}`" for item in finding.evidence]
            if finding.affected_paths:
                lines += ["", "Affected paths:", ""] + [f"- `{item}`" for item in finding.affected_paths]
            lines.append("")

    tech = report.technologies
    lines += ["## Technology stack", ""]
    for title, signals in (("Languages", tech.languages), ("Frameworks", tech.frameworks), ("Package managers", tech.package_managers)):
        lines.append(f"**{title}:** " + (", ".join(s.name for s in signals) or "none detected"))
    for title, signals in (("API", report.api.signals), ("Authentication", report.authentication.signals), ("Databases", report.data.databases)):
        lines.append(f"**{title}:** " + (", ".join(s.name for s in signals) or "none detected"))
    lines.append("")

    if report.dependencies:
        lines += ["## Dependencies", "", "| Name | Version | Ecosystem | Kind | Declared in |", "| --- | --- | --- | --- | --- |"]
        for dep in sorted(report.dependencies, key=lambda d: (d.ecosystem, d.kind, d.name)):
            lines.append(f"| {_cell(dep.name)} | {_cell(dep.version)} | {dep.ecosystem} | {dep.kind} | `{dep.source}` |")
        lines += ["", "_Declared dependencies only. Nothing was installed or resolved, and no vulnerability database was queried._", ""]

    lines += ["## Architecture", "", "Observed structure:", ""]
    lines += [f"- `{item}`" for item in report.architecture.observed_structure] or ["_None._"]
    lines += ["", "Interpretation:", ""] + _bullets(report.architecture.interpretations) + [""]

    structure = report.project_structure
    lines += ["## Project essentials", ""]
    for label, value in (
        ("Tests", structure.has_tests),
        ("Documentation", structure.has_docs),
        ("CI", structure.has_ci),
        ("Docker", structure.has_docker),
        ("Environment example", structure.has_environment_example),
    ):
        lines.append(f"- [{'x' if value else ' '}] {label}")
    lines.append("")

    trust = report.trust_context
    lines += ["## Evidence boundaries", ""]
    for title, items in (
        ("Verified / detected", trust.verified_detected),
        ("Potential issues", trust.potential_issues),
        ("Not verified", trust.not_verified),
        ("Limitations", trust.limitations),
    ):
        lines += [f"**{title}**", ""] + _bullets(items, "_None reported._") + [""]
    lines += [f"**Runtime status:** {trust.runtime_status}", ""]

    source = report.source_inspection
    lines += [
        "## Source inspection",
        "",
        f"Files inspected: {source.files_inspected} · skipped: {source.files_skipped} · truncated: {source.files_truncated}",
        "",
    ]
    if report.limitations.notes:
        lines += ["## Limitations", ""] + _bullets(report.limitations.notes) + [""]

    lines += ["---", "_Generated by Repo Inspector (static analysis; repository code was never executed)._", ""]
    return "\n".join(lines)
