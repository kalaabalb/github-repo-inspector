# Design

## Who it is for
A developer (or a curious non-developer) who just wants to know: **what is this project, is it in
good shape, and what should I look at first?** The first screen must answer that in about five
seconds. Everything technical is still there, one click deeper.

## Principles (from research on dashboard and report UX)
1. **One primary question per screen, answered first.** A score and a plain-English sentence lead.
2. **Progressive disclosure in three layers.** Summary -> contributing factors -> raw evidence.
   Summary is always visible; evidence lives under "Details" and inside expandable rows.
3. **Plain labels.** "Fix now / Worth fixing / Minor / Good to know" instead of
   "high / medium / low / info". "Built with" instead of "Technology signals".
4. **Problems and good news are separate.** Informational findings are shown as "Good to know",
   never mixed into a list of issues.
5. **Remove noise.** No confidence/category pill soup on every row, no duplicate sections,
   no counts that nobody acts on.
6. **Honest.** The score is labelled a rough guide. Limits and unverified claims are shown
   (briefly on Summary, fully in Details). Nothing is faked.
7. **Make it shareable.** One-tap Copy summary / Copy as Markdown / Copy as JSON.

## Structure
Landing: headline, one input, example repositories, "Try a sample report" (works offline,
bundled asset), a one-line trust note.

Report, four tabs:
- **Summary**: project in one sentence, score ring + verdict, "Fix these first" (top 3),
  "What looks good", a one-glance checklist (tests, docs, CI, Docker, env example), optional
  AI explanation, and a short note if only part of the repo could be read.
- **Issues**: grouped by priority with filter chips. Each row: plain title and one line; expand
  for why it matters, what to do, and which files. "Good to know" is collapsed at the bottom.
- **Tech**: Built with (languages, frameworks, tools), What it includes (API, login, database,
  in plain words), and Dependencies grouped by ecosystem.
- **Details**: how the report was made, what could not be checked, files read, project layout,
  everything detected. Collapsed sections; for the curious or the skeptical.

## Visual language
Dark surface, violet-to-cyan accent, generous spacing, rounded cards, a calm animated
background on the landing page only (disabled when the OS asks for reduced motion). Colour is
never the only signal: priority also has an icon and a word.

## Accessibility
Icon buttons have tooltips; the score ring and issue rows have semantic labels; text keeps
contrast against the dark surface; layouts are tested at 400px width; motion respects the
reduced-motion setting.
