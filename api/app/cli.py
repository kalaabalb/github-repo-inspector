"""Command line interface. Everything except ``--github`` works offline.

    python -m app.cli inspect ./my-project            # folder
    python -m app.cli inspect ./project.zip           # ZIP archive
    python -m app.cli inspect ./my-project -f json -o report.json
    python -m app.cli render report.json              # JSON report -> Markdown
    python -m app.cli sample                          # bundled sample report
    python -m app.cli inspect --github owner/repo     # needs internet (+ optional GITHUB_TOKEN)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.schemas.report import ProjectReport
from app.services.local_source import LocalSourceError, snapshot_from_directory, snapshot_from_zip
from app.services.markdown_export import render_markdown
from app.services.repositories import (
    InvalidRepositoryUrlError,
    RepositoryAnalysisError,
    build_report_from_snapshot,
    validate_repository_identifiers,
)


def _emit(report: ProjectReport, fmt: str, output: str | None) -> None:
    text = render_markdown(report) if fmt == "markdown" else report.model_dump_json(indent=2) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8")
        print(f"Wrote {output}", file=sys.stderr)
    else:
        sys.stdout.write(text)


def _inspect_github(spec: str) -> ProjectReport:
    from app.integrations.github import GitHubClient  # imported lazily: needs network only here
    from app.services.repositories import RepositoryService

    cleaned = spec.strip().removeprefix("https://github.com/").strip("/")
    parts = cleaned.split("/")
    if len(parts) < 2:
        raise InvalidRepositoryUrlError
    reference = validate_repository_identifiers(parts[0], parts[1])
    return asyncio.run(RepositoryService(GitHubClient()).inspect(reference))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repo-inspector", description="Evidence-backed repository reports.")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect", help="Inspect a local folder, a ZIP file or (online) a GitHub repository.")
    inspect.add_argument("path", nargs="?", help="Folder or .zip file.")
    inspect.add_argument("--github", metavar="OWNER/REPO", help="Fetch from GitHub instead (needs internet).")
    inspect.add_argument("-f", "--format", choices=["markdown", "json"], default="markdown")
    inspect.add_argument("-o", "--output", help="Write to a file instead of stdout.")

    render = sub.add_parser("render", help="Render a saved JSON report as Markdown (offline).")
    render.add_argument("report", help="Path to a JSON report.")
    render.add_argument("-o", "--output")

    sample = sub.add_parser("sample", help="Print the bundled sample report.")
    sample.add_argument("-f", "--format", choices=["markdown", "json"], default="markdown")
    sample.add_argument("-o", "--output")

    args = parser.parse_args(argv)
    try:
        if args.command == "render":
            report = ProjectReport.model_validate(json.loads(Path(args.report).read_text(encoding="utf-8")))
            _emit(report, "markdown", args.output)
        elif args.command == "sample":
            from app.api.sample import load_sample_report

            _emit(load_sample_report(), args.format, args.output)
        else:
            if args.github:
                report = _inspect_github(args.github)
            elif args.path:
                target = Path(args.path).expanduser()
                if target.is_dir():
                    snapshot = snapshot_from_directory(target)
                elif target.is_file() and target.suffix.lower() == ".zip":
                    snapshot = snapshot_from_zip(target.read_bytes(), name=target.name)
                else:
                    raise LocalSourceError(f"Not a folder or .zip file: {args.path}")
                report = build_report_from_snapshot(snapshot)
            else:
                parser.error("Give a folder/ZIP path or --github OWNER/REPO.")
            _emit(report, args.format, args.output)
    except LocalSourceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except InvalidRepositoryUrlError:
        print("error: use OWNER/REPO or a github.com URL.", file=sys.stderr)
        return 2
    except RepositoryAnalysisError:
        print("error: the analysis failed.", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - GitHub/network errors get a friendly message
        name = type(exc).__name__
        if name.startswith("GitHub"):
            hints = {
                "GitHubNetworkError": "cannot reach GitHub. You appear to be offline; folders and ZIPs still work without internet.",
                "GitHubRateLimitError": "GitHub rate limit reached. Set GITHUB_TOKEN to raise it.",
                "GitHubRepositoryNotFoundError": "repository not found or not public.",
            }
            print(f"error: {hints.get(name, 'GitHub returned an unexpected response.')}", file=sys.stderr)
            return 3
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
