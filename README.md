# GitHub Repository Inspector

An AI-powered developer tool that will turn a public GitHub repository into an understandable technical report.

[![CI](https://github.com/kalaabalb/github-repo-inspector/actions/workflows/ci.yml/badge.svg)](https://github.com/kalaabalb/github-repo-inspector/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)

![GitHub Repository Inspector report summary](docs/images/summary.png)

## Status

Early but working. Implemented: GitHub ingestion, **offline analysis of local folders and ZIP files**, bounded source inspection, deterministic findings, dependency parsing, a command line tool, Markdown/JSON export and optional AI explanations. Not implemented: deep semantic analysis, vulnerability scanning and private repositories (see [Limitations](#limitations)).

## Current Functionality

The backend accepts a public GitHub repository URL, retrieves repository metadata and bounded tree, configuration, and selected source information, and produces an evidence-backed deterministic analysis report. A separate `/api/v1/repositories/explain` endpoint can optionally send an already-generated compact report to Gemini for structured explanations; inspection itself never consumes AI tokens. Private repositories are not supported, and AI explanations are unavailable until a `GEMINI_API_KEY` is configured.

AI configuration is optional. Set `GEMINI_API_KEY` and, optionally, `GEMINI_MODEL` from the placeholders in `api/.env.example`; never commit real credentials. The AI layer receives structured report data only, not repository source code, and treats repository-derived text as untrusted data.

## Works offline

Everything that does not need GitHub works without internet:

```bash
cd api
python -m app.cli inspect ../my-project                 # a local folder -> Markdown on stdout
python -m app.cli inspect ./project.zip -o report.md    # a ZIP archive -> Markdown file
python -m app.cli inspect ../my-project -f json -o r.json
python -m app.cli render r.json                         # saved JSON report -> Markdown
python -m app.cli sample                                # the bundled sample report
python -m app.cli inspect --github owner/repo           # needs internet (set GITHUB_TOKEN for rate limits)
```

The same analysis is available over HTTP: `POST /api/v1/repositories/inspect-archive` takes a ZIP as the raw request body, and `GET /api/v1/sample-report` returns the bundled sample. Local analysis uses the same analyzer and size limits as GitHub analysis. Folders and ZIPs are only read, never extracted to disk, executed or installed; path traversal, symlinks, encrypted entries, oversized archives and archives with too many entries are rejected or skipped. Reports from local analysis are labelled `source: "local"` and have no stars, forks or branch. If GitHub cannot be reached, the CLI says so and points at the offline commands.

## Dependencies

Declared dependencies are parsed from `requirements*.txt`, `pyproject.toml` (PEP 621, Poetry, dependency groups), `package.json`, `pubspec.yaml`, `Cargo.toml`, `go.mod` and `composer.json`, and are reported with ecosystem, version constraint and where they were declared. This is static text parsing: nothing is installed or resolved, and no vulnerability database is queried. `pom.xml` and Gradle dependencies are not parsed yet.

## Limitations

- Analysis is static and bounded by file count, file size and total bytes; anything skipped is listed in the report.
- Detection is rule-based (imports, manifests, markers). It can miss technologies and can occasionally flag something that is not really used. Findings carry evidence so you can check them.
- The health score is a heuristic from finding severities, not a measure of quality or security.
- No vulnerability scanning, license checking, dependency resolution, code execution or type checking.
- Only public GitHub repositories are supported (not GitLab or Bitbucket).
- AI explanations are optional, depend on a third party, can be wrong, and only see the structured report, never raw source.

## Static Codebase Health

Deterministic inspection reports evidence-backed signals for suspicious configuration, documentation mismatches, TODO/FIXME markers, testing evidence, repository quality, and simple architecture or maintainability concerns. Analysis is static: repository code is never executed, runtime correctness is not guaranteed, and external dependency vulnerability scanning is not included. Findings include evidence and preserve bounded-inspection limitations.

## Bounded Source Inspection

The inspector selectively reads a small, configurable number of text-based source and configuration files to improve route, authentication, configuration, and architecture evidence. Inspection is bounded by file count, per-file size, total source bytes, and source-directory count; skipped and truncated files are reported.

Repository content is treated as untrusted text. Repository code is never executed, dependencies are never installed, and the repository is never cloned. Raw source is not sent to AI or displayed in the report. Runtime correctness is not verified.

## Planned Stack

- Flutter and Dart client
- Python and FastAPI API
- PostgreSQL for persistence
- GitHub API for public repository access
- AI provider integration

## Repository Structure

```text
client/  Flutter application
api/     FastAPI application and Python dependencies
docs/    Project documentation
tests/   Backend tests
infra/   Infrastructure configuration added later
scripts/ Development scripts added later
```

## Run the API

```bash
python -m venv api/.venv
source api/.venv/bin/activate
pip install -r api/requirements.txt
uvicorn app.main:app --app-dir api --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health`.

To start the API in Docker with one command from the repository root:

```bash
docker build -t github-repo-inspector-api . && \
  docker run --rm -p 8000:8000 github-repo-inspector-api
```

Run the backend test with:

```bash
PYTHONPATH=api pytest
```

## Run the Flutter Client

```bash
cd client
flutter pub get
flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000
```

The client uses the same Flutter codebase for Web, Android, iOS, and desktop.
`API_BASE_URL` is a compile-time configuration value; it contains no secret.
Use the local API URL during development and provide the deployed HTTPS API URL
for a release build, for example:

```bash
flutter build web --release \
  --dart-define=API_BASE_URL=https://api.example.com
```

Browser requests require the FastAPI `CORS_ALLOWED_ORIGINS` setting to contain
the exact Flutter Web origin. The backend has explicit local development
origins by default; configure the deployed Web origin in production and do not
use a wildcard origin.

## API examples

Start the API locally using the instructions above, then inspect a public
repository:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/repositories/inspect \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://github.com/kalaabalb/trail_sg"}'
```

The response is a `ProjectReport` JSON object. For example, the API returns
these fields (the values below are an excerpt from the generated report shown
in [the sample output](docs/sample-report.json)):

```json
{
  "repository": {
    "full_name": "kalaabalb/trail_sg",
    "html_url": "https://github.com/kalaabalb/trail_sg"
  },
  "overview": {
    "classifications": ["Library/package"],
    "primary_classification": "Library/package"
  },
  "health_summary": {
    "total_findings": 4,
    "overall": "Static inspection only"
  },
  "trust_context": {
    "runtime_status": "Code was not executed."
  }
}
```

The metadata endpoint is available for a single repository:

```bash
curl http://127.0.0.1:8000/api/v1/repositories/fastapi/fastapi
```

The optional explanation endpoint accepts a report produced by `/inspect` and
returns either a structured explanation or an `available: false` response
when Gemini is not configured. Inspection itself does not require an AI key.

## Sample generated report

[`docs/sample-report.json`](docs/sample-report.json) is the real output of
`python -m app.cli inspect ..` run offline on a local checkout of this repository
(`source: "local"`). It is also served by `GET /api/v1/sample-report` and is regenerated
with `scripts/generate_sample.sh`; it is never edited by hand. Findings change as the
code changes, so it is an example of the report shape, not a promise of current results.

## Roadmap

- [x] Offline folder/ZIP analysis, command line tool, dependency parsing, Markdown export (API side).
- [ ] Flutter client: sample/demo mode, open and save reports, Markdown export, copy as JSON.
- [ ] Expand deterministic checks while keeping findings evidence-backed.
- [ ] Add resilient GitHub API handling and clearer rate-limit recovery.
- [ ] Improve accessibility and loading/error states across the client.
- [ ] Document deployment configuration for the API and Flutter Web client.

Contributions and focused feature requests are welcome. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) and the open issues for ways to help.
