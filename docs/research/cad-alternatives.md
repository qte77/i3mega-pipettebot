# CAD alternatives — research log

Append-only log of CAD tooling and labware-model alternatives evaluated against
the current build123d-based pipeline at `tools/cad/`. Verdicts may be revisited
if upstream state changes (license added, code released, engine ported).

Applies to both `i3mega-pipettebot` (this repo) and the sibling
`so101-biolab-automation` — both converge on `config/ + src/ + tools/cad/` and
share Apache-2.0 licensing constraints. Per-repo verdicts are called out only
when they diverge.

## Evaluation criteria

Hard requirements (any failure is a blocker):

- Parametric `build_*()` functions with no I/O (per
  `.claude/rules/cad-script-conventions.md`)
- STL + STEP + SVG export — STEP is required for FreeCAD inspection
- License compatible with Apache-2.0 — MIT/BSD/Apache OK; GPL/AGPL/unlicensed
  is a blocker
- Headless CI invocation — no GUI dependency, no mandatory per-run API keys
- BREP-quality geometry (not CSG/mesh-only) so volume-based mass estimation
  works for the i3 carriage payload budget
  (`.claude/rules/i3-carriage-payload-budget.md`)

Soft preferences:

- AI-assisted authoring fit
- Live viewer / design-feedback loop (see #69)
- build123d-compatible API, or trivial port

## Entries

### 2026-05-20 — AI-assisted CAD generators

Three targets evaluated together because they share a theme (LLM/ML-driven
parametric CAD generation):

#### GenCAD — github.com/ferdous-alam/GenCAD

The original target name "GenCED" did not resolve; GenCAD is the closest match
and matches the project description.

- **What:** image → parametric CAD via transformer + diffusion. Standalone
  PyTorch application (`train_gencad.py`, `inference_gencad.py`), not a
  library.
- **License:** none declared. All-rights-reserved by default. **BLOCKER.**
- **Engine:** pythonocc-core (OCCT), not build123d. Output is an internal
  representation, not importable geometry that plugs into a `build_*()`
  function.
- **Maintenance:** last push 2025-07-14; ~2.9k stars; 31 open issues. Active
  but research-grade.
- **Verdict:** **SKIP.** No license, not a library, GPU-bound and not
  headless-CI friendly, wrong engine.

#### EvoCAD (paper) — arxiv.org/abs/2510.11631

- **Paper:** "EvoCAD: Evolutionary CAD Code Generation with Vision Language
  Models" — Preintner, Yuan, König, Bäck, Raponi, van Stein. IEEE ICTAI 2025.
- **What:** VLM (GPT-4V/4o) + evolutionary loop generates CadQuery scripts
  from text prompts. Selection / crossover / mutation over a population of
  scripts, VLM-scored fitness over rendered views. Introduces an
  Euler-characteristic topology metric.
- **Code:** no public release referenced in the abstract; the
  `toprei/evo-cad` repo (next entry) is the implementation companion.
- **Verdict:** **TRACK.** No code to integrate beyond the companion repo;
  GPT-4o-per-iteration cost makes it impractical to self-host as published.
  Revisit if authors release a permissively-licensed reproducer.

#### evo-cad — github.com/toprei/evo-cad

- **What:** CadQuery-based implementation companion to the EvoCAD paper.
  VLM evolutionary loop as described in the paper.
- **License:** none declared. **BLOCKER.**
- **Engine:** CadQuery, not build123d. Same OCCT backend; APIs incompatible.
- **Maintenance:** 2 stars, 1 fork, last commit 2025-06-23. Paper-dump repo,
  not actively maintained.
- **Verdict:** **SKIP.** No license, wrong engine, paper artifact rather than
  reusable tooling.

#### Shippable pattern (no dependency required)

The one reusable idea across all three is **VLM-as-fitness over rendered
views to iterate parametric scripts**. The current `tools/cad/render.py`
already emits STL + STEP + SVG per part — feeding the SVG (or an iso PNG)
into a VLM scoring loop is ~200 lines of glue around the existing manifest,
with no upstream code adopted. Tracked in #139.

## Future entries

Subsequent research adds a dated H3 entry above this section. Keep verdict
labels in plain ASCII (ADOPT / SUPPLEMENT / TRACK / SKIP) so they grep
cleanly.
