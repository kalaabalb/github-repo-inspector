# GitHub Repo Inspector - Flutter Client

The Flutter client for GitHub Repo Inspector, a developer-oriented repository
analysis tool. It inspects public GitHub repositories using bounded,
deterministic analysis and can request optional AI-assisted explanations from
the FastAPI backend.

## Features

- Public GitHub repository URL inspection
- Repository metadata and project classification
- Language, framework, and package manager detection
- API, authentication, and database signals
- Project structure analysis
- Bounded source inspection of selected text files
- Evidence-backed codebase health findings and guidance
- Limitation and truncation reporting
- Optional structured AI explanation
- Responsive technical report UI

## Architecture

```text
client/
├── lib/
│   ├── core/
│   │   ├── config/
│   │   └── theme/
│   ├── features/
│   │   └── repository_inspection/
│   │       ├── data/
│   │       │   ├── models/
│   │       │   └── repository_api.dart
│   │       ├── presentation/
│   │       │   ├── screens/
│   │       │   └── state/
│   │       └── ...
│   └── main.dart
└── test/
    └── widget_test.dart
```

Typed models parse deterministic reports and AI responses. `RepositoryApi`
defines the client contract, while `HttpRepositoryApi` sends HTTP requests to
the FastAPI backend and maps failures to safe user-facing errors.

`InspectionController` manages loading, report, error, and optional AI
explanation state. `InspectionScreen` handles URL input and the initial flow.
`ReportScreen` renders the technical report, evidence, health findings,
source-inspection status, and limitations. `AppTheme` defines the developer
tool visual language.

## Backend Connection

The client communicates with the FastAPI backend through:

- `POST /api/v1/repositories/inspect`
- `POST /api/v1/repositories/explain`

Flutter does not communicate directly with Gemini. Gemini credentials remain
on the backend, and the backend sends only a compact structured report for an
explicit explanation request.

## Configuration

The API base URL is configured with Dart's compile-time environment value:

```bash
flutter run --dart-define=API_BASE_URL=http://localhost:8000
```

If `API_BASE_URL` is omitted, the client uses `http://localhost:8000`.

## Running Locally

From the `client/` directory:

```bash
flutter pub get
flutter analyze
flutter test
flutter run --dart-define=API_BASE_URL=http://localhost:8000
```

To run the web client in a browser:

```bash
flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000
```

Start the FastAPI backend separately from the repository root as described in
the root [README](../README.md).

## Testing

The Flutter widget tests cover URL validation, loading states, deterministic
report rendering, API errors, evidence, limitations, AI unavailable and
successful states, and the requirement that AI is invoked only after an
explicit user action.

## Security Boundaries

- Flutter does not store Gemini credentials.
- Flutter does not call Gemini directly.
- Repository code is never executed by the client or backend.
- Raw repository source is not displayed as a report feature.
- The backend controls GitHub repository inspection and source limits.
- API and network errors are presented without internal stack traces.

## Limitations

- Inspection is bounded and only selected source/configuration files are read.
- Repository code is treated as untrusted text and is never executed.
- Runtime behavior and production correctness are not verified.
- Private repositories are not currently supported.
- GitHub API rate limits can affect live inspection.
- AI explanation is optional and requires backend Gemini configuration.

## Project Status

This is an actively developed developer tool in early MVP development. The
client and deterministic backend report flow are implemented; broader
repository analysis and future product features remain under development.
