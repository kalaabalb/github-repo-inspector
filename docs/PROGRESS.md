# Progress

Handoff note for the current implementation. Product and architecture decisions are in
[DECISIONS.md](DECISIONS.md); client behavior and layout guidance are in [DESIGN.md](DESIGN.md).

## Implemented

- PR #1 merged: MIT license, CONTRIBUTING guide, CI, Dockerfile, examples, and roadmap.
- Bounded GitHub repository inspection with evidence, deterministic health findings, and
  protections for repository text treated as untrusted input.
- Offline analysis of local folders and ZIP files, dependency manifest parsing, CLI inspection,
  Markdown and JSON export, plus bundled sample report endpoints.
- Flutter client with Summary, Issues, Tech, and Details tabs; plain language; share/export
  actions; local sample mode; semantic labels; and narrow-screen layout.
- Locally bundled Roboto and CanvasKit resources and a service worker cache for offline web loads.
- CI workflow with API tests, CLI smoke check, Flutter analysis, Flutter tests, and a web build.
  Latest run `44993368702` passed both `api-tests` and `client-tests` after the implementation push.
- Real browser screenshots in `docs/images/`; the Summary image is included near the top of
  `README.md`.

## Verified locally

- API: `PYTHONPATH=api python -m pytest` — 117 passed.
- Client: `flutter analyze` — no issues; `flutter test` — 29 passed.
- Release web build: `flutter build web --release --no-web-resources-cdn` succeeded.
- CLI: local folder Markdown export and bundled sample JSON smoke checks succeeded.
- Browser: live inspection of `kalaabalb/github-repo-inspector` returned HTTP 200 and rendered
  its report; “Inspect another repository” returned to the start form.
- Browser offline check: service worker activated and cached the app shell; reload with network
  emulation offline still served the app, and the bundled sample report opened.
- Browser layout checked at 1280×800 and 400×800; no narrow-screen overflow observed.

## Remaining

- ZIP/folder picking in the Flutter UI and loading saved report files are future client work.
- A hosted public demo still needs an owner-provided hosting account/domain and GitHub token.
