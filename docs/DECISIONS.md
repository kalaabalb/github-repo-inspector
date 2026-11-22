# Decisions

Product and architecture decisions, newest last. Each entry says what was decided and why,
so a new contributor (or a new chat) can continue without re-deriving them.

## D1. Offline-first; GitHub is one input among several
Every analysis is `snapshot -> analyzer -> report`. GitHub, a local folder and a ZIP file are
three ways to build a snapshot. Everything except fetching from GitHub works with no internet.
When GitHub is unreachable the tools say so and point at the offline commands.
*Why:* trust (nothing leaves your machine), speed to first result, and demos that cannot break.

## D2. A CLI is a first-class interface
`python -m app.cli inspect <folder|zip>` prints a Markdown report. Developers share terminal
output and CI logs; a one-line command is the fastest "try it in a minute".

## D3. Local analysis reuses the GitHub limits and analyzer
Same file, byte and directory bounds, same findings. Reports are tagged `source: "local"` and
stars/forks/branch are hidden rather than shown as zero.
*Why:* one behavior to document and test; no "local mode is different" surprises.

## D4. ZIPs are read in memory only
No extraction to disk. Reject path traversal, absolute paths, drive letters, symlinks,
encrypted entries; cap archive bytes (25 MB) and entry count (20,000); read at most the
per-file limit from any member. *Why:* an upload endpoint must be safe against zip bombs and
traversal by construction.

## D5. Dependencies are parsed statically, not resolved
Manifests only (PyPI, npm, pub, crates.io, Go, Packagist). No installs, no network, no
vulnerability lookups. Malformed manifests yield nothing instead of an error. Maven/Gradle are
not parsed yet and the README says so.

## D6. Findings that differ only by file are merged
Same id, title and severity become one finding listing every file. *Why:* one issue should not
appear (and be scored) several times.

## D7. Detection must not match its own keyword lists
Source lines made only of quoted keyword lists are ignored as evidence; framework detection
needs real imports or manifest dependencies. *Why:* the inspector reported Django, Flask, JWT
and MongoDB on its own repository because its detector listed those words.

## D8. Reports are cached by the existing in-process `InspectionCache`
It also de-duplicates concurrent identical requests. No second cache was added.
*Why:* one mechanism to reason about; big GitHub rate-limit savings with no infrastructure.

## D9. The health score is a heuristic and is labelled as one
`100 - 18*high - 8*medium - 3*low`, clamped to 0-100. The same formula lives in the API
(`markdown_export.health_score`) and the client (`healthScore`). Tests pin both to the same values.

## D10. The bundled sample is generated from this repository
`docs/sample-report.json` (identical to `api/app/data/sample_report.json`, enforced by a test)
is the real output of `python -m app.cli inspect ..` on a local checkout, tagged `local`.
It is regenerated with `scripts/generate_sample.sh`, never edited by hand. No screenshots
are committed until they are taken from the running app.

## D11. No new Flutter dependencies for core features
The client uses only the Flutter SDK so that it builds offline and has nothing to audit.
(File picking for ZIP and report import is the one exception; it needs a package or browser API.)

## D12. Honesty over polish
The README keeps an explicit Limitations section. Features are marked done only when tested.

## D13. Plain language first, technical detail on request
The report leads with a short human summary, a score and the few things worth acting on.
Evidence, limits and file lists exist (trust matters) but sit behind a "Details" section.
Informational findings are shown as "good signs", not mixed in with problems.
See `docs/DESIGN.md`.

## D14. Unverified claims are notes, not problems; one claim is reported once
"The README mentions X but we found no evidence" cannot prove anything is wrong, and the
analyzer says so itself. Those findings are `info` ("Good to know"), not `low`. When both a
specific README claim and the generic purpose check fire for the same technology, only the
README claim is kept. *Why:* the sample report listed PostgreSQL twice and counted both
against the score, which made a healthy project look worse and the report noisier.

## D15. Four tabs, plain labels
Summary, Issues, Tech, Details (see DESIGN.md). Severity words become Fix now / Worth fixing /
Minor / Good to know. The AI explanation lives inside Summary instead of its own tab.
Technical material (evidence, limits, file counts, layout) is under Details, collapsed.

## D16. The client has an offline sample mode
`client/assets/sample_report.json` (same bytes as `docs/sample-report.json`, enforced by a
test) opens from "Try a sample report" with no network and no API. Connection errors say that
the sample still works.

## D17. Sharing is copy-to-clipboard first
Copy short summary / Markdown / JSON need no packages and work on every platform. Saving a
file and picking a ZIP need a package or browser API and are left to the platform step.
