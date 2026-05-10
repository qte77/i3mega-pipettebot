# ADR 0002: Extract the CAD tool-chain into a shared `qte77/cadkit` package

- **Status:** Accepted
- **Date:** 2026-05-11
- **Scope:** Three repos — new [qte77/cadkit](https://github.com/qte77/cadkit) (the extracted package), [Lambda-Biolab/i3mega-pipettebot](https://github.com/Lambda-Biolab/i3mega-pipettebot), [Lambda-Biolab/so101-biolab-automation](https://github.com/Lambda-Biolab/so101-biolab-automation)

## Context

Both lab-automation repos run the same CAD tool-chain — build123d for parametric solids, [DiagramForge](https://github.com/qte77/DiagramForge) for dark-mode SVG theming, OrcaSlicer (PrusaSlicer fallback) for printability validation. The code that wires this tool-chain together is duplicated in each repo today:

| current location (per repo) | what it does |
|---|---|
| `tools/cad/render.py` | manifest-driven build123d → STL/SVG dispatcher |
| `tools/cad/util/export.py`, `stl_to_svg.py` | STL + iso-projected SVG export (with the `project_to_viewport` fix from PR #39) |
| `tools/cad/util/theme_svgs.py` | DiagramForge dark-mode CSS injection |
| `tools/slicer/validate.py` | OrcaSlicer-first / PrusaSlicer-fallback validator + WARN/FAIL parsing |
| `tools/slicer/profiles/*.ini` | shared Prusa MK3S+-class profiles (`pla_plus_02mm`, `tpu_95a_02mm`) |
| `tools/cad/barrel_bore.py` (i3 only today) | reusable round-bore-with-clearance primitive |

Drift between the two repos is the active pain point. PR #47 in i3mega already had to re-derive the SVG export fix that should have come from a single source; the slicer profiles were independently named in each repo until PR #47 aligned them. As ADR 0001's marketplace-plugin decision documented for `.claude/` assets, "avoid drift between two vendored copies of the same thing" is the right principle here too — applied now to the CAD tool-chain instead of Claude assets.

## Decision

Extract the tool-chain into a new package hosted at **[qte77/cadkit](https://github.com/qte77/cadkit)**. Both i3mega-pipettebot and so101-biolab-automation consume it as a **git-pinned dependency** (matching how [dpette-usb-driver](https://github.com/Lambda-Biolab/dpette-usb-driver) is consumed today), pinned to a tag SHA in each repo's `pyproject.toml`.

**Why qte77, not Lambda-Biolab:** the package is general-purpose CAD/slicer/SVG plumbing — it isn't lab-automation-specific. Hosting it under qte77 keeps the org boundary clean (Lambda-Biolab repos are the *lab applications*, qte77 owns the *generic tooling* they consume).

### Module shape in `cadkit`

```text
cadkit/
├── render.py            # was tools/cad/render.py — manifest dispatcher, no I/O surprises
├── export.py            # was tools/cad/util/export.py + stl_to_svg.py — STL + iso SVG via project_to_viewport
├── svg/
│   └── theme.py         # was tools/cad/util/theme_svgs.py — DiagramForge CSS
├── slicer/
│   ├── validate.py      # was tools/slicer/validate.py — OrcaSlicer/PrusaSlicer wrapper
│   └── profiles/        # was tools/slicer/profiles/ — shared .ini bundles
└── geom/
    └── barrel_bore.py   # was tools/cad/barrel_bore.py — make_clamp_bore primitive
```

Plus a console-script entry point `cadkit-render` (and `cadkit-slicer-validate`) so callers don't `python -m cadkit.render`.

### What stays repo-local in i3mega and so101

- `tools/cad/parts.json` — each repo's manifest of its own parts
- `tools/cad/<area>/*.py` — per-part build scripts (i3 carriage mount, so101 cradles, dPette tip ejector, etc.)
- `tools/cad/measurements.py` — repo-specific measured constants
- `Makefile` — local `make render_parts` / `make check_prints` recipes invoking the cadkit console scripts

Per-part scripts switch from `from build123d import Box, Cylinder` + local imports to `from cadkit.geom import make_clamp_bore` for shared primitives. They keep their direct `build123d` imports — `cadkit` doesn't try to wrap or re-export build123d itself.

## Consequences

### Pros

- **Single source of truth for tool-chain wiring.** Bug fixes (like PR #47's SVG export fix) land once, not twice.
- **Room for third / nth consumer.** A future lab repo can adopt `cadkit` without re-deriving the build123d + slicer integration.
- **Cleaner repo focus.** i3mega's `tools/cad/` becomes "i3's parts and measurements" — the orchestrator is a dependency, not local code.
- **`.ini` profile reuse is structural, not coincidental.** PR #47 aligned the profile *names*; this ADR aligns the *source* — both repos pull profiles from the same `cadkit.slicer.profiles/` bundle.

### Cons

- **Three repos to track instead of two.** Every cross-cutting change is now a tag-bump on `cadkit` plus parallel PRs on i3mega and so101 to roll the pinned SHA forward.
- **First-extraction risk.** Anything subtly i3-specific that lands in `cadkit` becomes a footgun for so101. Mitigation: i3 adopts first (smaller blast radius), so101 follows second to surface the gaps.
- **API stability is now a real concern.** Today, changing `tools/cad/render.py` is a one-repo refactor. Post-extraction, it's an API change that affects both consumers. `cadkit` needs a versioning + deprecation discipline that the in-repo tools didn't.

### Neutral

- **`pyproject.toml`** in each consuming repo gains one line:
  `cadkit @ git+https://github.com/qte77/cadkit@<tag-sha>`.
- **CI on i3 and so101** needs to fetch `cadkit` from GitHub during dependency install — same constraint as the existing `dpette-usb-driver` git dep, no new infra needed.
- **AGENTS.md** in i3 and so101 gets a one-line update noting where the CAD tool-chain now lives.

## Migration plan

Sequenced PRs across three repos. Each step lands and stabilises before the next.

### Phase 1 — Scaffold `qte77/cadkit`

1. Create the repo. Initial commit: extracted modules from **i3mega** (which has the more recent + tested versions, notably the `project_to_viewport` SVG fix and the `make_clamp_bore` primitive). Mirror the repo skeleton from i3mega (src/ + tests/ + Makefile patterns + AGENTS.md, marketplace-only Claude assets per ADR 0001's direction).
2. Add tests covering: render dispatcher loads a sample manifest; SVG export produces non-empty visible+hidden line groups; slicer validate handles missing slicer cleanly; `make_clamp_bore` returns a Cylinder with the right radius.
3. Tag `v0.0.1`. The tag SHA is what consumers pin to.

### Phase 2 — i3mega adopts `cadkit` v0.0.1

1. Add `cadkit @ git+https://github.com/qte77/cadkit@<v0.0.1-sha>` to `pyproject.toml` `[tool.uv.sources]` or equivalent.
2. Delete extracted files from i3mega (`tools/cad/render.py`, `tools/cad/util/*.py`, `tools/cad/barrel_bore.py`, `tools/slicer/validate.py`, `tools/slicer/profiles/*.ini`).
3. Update per-part build scripts to `from cadkit.geom import make_clamp_bore`. Keep direct `from build123d import …` (cadkit doesn't wrap build123d).
4. Update `Makefile`: `render_parts:` calls `cadkit-render --manifest tools/cad/parts.json`; `check_prints:` calls `cadkit-slicer-validate …`.
5. Update `AGENTS.md` "CAD pipeline" section pointing at `cadkit` as the tool-chain home.

### Phase 3 — so101 adopts `cadkit` v0.0.1

Same shape as Phase 2, parallel PR. Surfaces any API gaps that i3's adoption didn't catch.

### Phase 4 — Iterate

When either repo needs an unshared bit (a new geom primitive, a slicer feature, a different SVG view angle), it goes into `cadkit` first, tag-bump, both repos pin to the new tag in lock-step.

## Out of scope

- **PyPI publishing.** `cadkit` stays a git-pinned dependency for the foreseeable future, matching `dpette-usb-driver`. PyPI is a future promotion when the API stabilises and downstream consumers outside qte77's GitHub need it.
- **build123d wrapping.** `cadkit` does not try to abstract or re-export build123d. Per-part scripts continue to `import build123d` directly. The package wraps *integration* (manifest dispatch, export pipelines, slicer invocation), not the CAD DSL itself.
- **Renaming i3mega or so101 distribution names.** Same scope-bound as ADR 0001 — this ADR only adds a new package; existing distributions stay named as-is.
- **Consolidating `.claude/` assets into `cadkit`.** That belongs in ADR 0001's marketplace-plugin track, not here.

## References

- [ADR 0001 — repo-structure alignment](./0001-repo-structure-alignment.md) — sets the precedent for "avoid drift between vendored copies"; this ADR applies the same principle to the CAD tool-chain
- [dpette-usb-driver](https://github.com/Lambda-Biolab/dpette-usb-driver) — the model for git-pinned consumption (commit SHA in `pyproject.toml`)
- Cross-repo tracking issues will be opened once `qte77/cadkit` is scaffolded: one in [Lambda-Biolab/i3mega-pipettebot](https://github.com/Lambda-Biolab/i3mega-pipettebot) for the i3 migration, one in [Lambda-Biolab/so101-biolab-automation](https://github.com/Lambda-Biolab/so101-biolab-automation) for the so101 migration. The new `qte77/cadkit` repo holds its own first-issue for the initial scaffold.
