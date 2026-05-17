# ADR 0001: Align `i3mega-pipettebot` and `so101-biolab-automation` layouts

- **Status:** Accepted
- **Date:** 2026-05-11
- **Scope:** Both [qte77/i3mega-pipettebot](https://github.com/qte77/i3mega-pipettebot) and [Lambda-Biolab/so101-biolab-automation](https://github.com/Lambda-Biolab/so101-biolab-automation)

## Context

Both repos cover overlapping lab-automation concerns (Marlin-based motion + pipette control + a CAD/slicer pipeline) but diverge on directory layout, which makes shared tooling and cross-repo refactors slow and error-prone.

Verified state on `main` at the time of this ADR:

| concern | `so101-biolab-automation` | `i3mega-pipettebot` |
|---|---|---|
| Python package root | `app/so101/`, `app/dashboard/` | `src/pipettebot/` |
| CAD scripts | `app/hardware/cad/` | `tools/cad/` |
| Slicer wrapper | `app/hardware/slicer/` | `tools/slicer/` |
| Runtime configs | `configs/` (plural) | none |
| Hardware outputs | `hardware/` (top-level) | `hardware/` (top-level) |
| Claude skills | vendored at `.claude/skills/` | marketplace-only |
| Claude rules | vendored at `.claude/rules/` | vendored at `.claude/rules/` |
| Slicer profile naming | `pla_plus_02mm.ini`, `tpu_95a_02mm.ini` | matches (PR #47) |

The slicer-profile naming converged on its own; everything else diverges.

## Decision

Both repos converge on the same hybrid layout:

- `src/<pkg>/` — Python package root (PEP 517 src layout; `[tool.hatch.build.targets.wheel].packages = ["src/<pkg>"]`)
- `tools/cad/`, `tools/slicer/` — CAD scripts and slicer wrapper, separated from runtime code
- `config/` (**singular**) — runtime YAML/TOML configuration; not in `pyproject.toml`
- `hardware/` — gitignored generated output (STL/SVG/G-code); unchanged from current state
- Claude **skills and rules** load from the user-level marketplace plugin (`qte77-claude-code-plugins`); no vendored `.claude/skills/` or `.claude/rules/` in either repo

## Consequences

### Pros

- **Idiomatic Python packaging.** `src/` layout is the PEP 517 default and matches hatchling, uv, modern poetry, and PEP 621.
- **One mental model across repos.** Contributors switching between i3mega and so101 stop hitting "wait, where does CAD live here?".
- **Single source of truth for Claude assets.** Skills + rules ship via one marketplace plugin; no drift between two vendored copies.
- **`tools/` is honest.** Build-time tooling (CAD scripts, slicer wrappers, diagnostics) is not application code; separating it makes packaging cleaner and prevents accidental shipping of CAD deps to runtime consumers.

### Cons

- **Larger migration in so101** — most of the work lives there: renaming `app/` → `src/`, moving `app/hardware/` → `tools/`, renaming `configs/` → `config/`, de-vendoring `.claude/skills/` and `.claude/rules/`.
- **Breaking import paths.** Any downstream consumer that imports `so101.…` from `app/so101/` will need to update. The package distribution name doesn't change, only the source layout.
- **Marketplace plugin must catch up.** De-vendoring rules means the marketplace plugin needs to ship the same rule set both repos relied on locally. This is preferable to two drift-prone copies, but requires a one-time consolidation.

### Neutral

- **CI/CD config updates** in both repos (paths in workflows, lint targets, packaging steps). Limited blast radius; mechanical changes.
- **AGENTS.md updates** in both repos to reflect the new layout and the marketplace-only-rules rule.

## Migration plan

Sequenced PRs per repo. Never one mega-rename commit. Each step lands before the next.

### `i3mega-pipettebot` (smaller surface)

1. Add `config/` directory and a placeholder (e.g., `config/.gitkeep` or first real runtime config) when a runtime config is actually needed. **Not a speculative move.**
2. Consolidate the rules in `.claude/rules/` into the marketplace plugin `qte77-claude-code-plugins`. Remove `.claude/rules/` from this repo.
3. Update [`AGENTS.md`](../../AGENTS.md): drop the line "Repo-local rules live in `.claude/rules/` and apply to every session in this directory." Replace with a marketplace-loaded note. Update path-scoped rule references accordingly.

### `so101-biolab-automation` (larger surface)

1. **Rename** `configs/` → `config/`. Update every reference (loader code, docs, CI).
2. **Move CAD + slicer:** `app/hardware/cad/` → `tools/cad/`, `app/hardware/slicer/` → `tools/slicer/`. Update import sites and any path-scoped rules.
3. **Move Python packages:** `app/<pkg>/` → `src/<pkg>/`. Update `pyproject.toml` (`[tool.hatch.build.targets.wheel].packages`), then `app/` becomes empty and gets removed.
4. **De-vendor skills + rules:** consolidate `.claude/skills/` and `.claude/rules/` into the marketplace plugin. Remove both directories from this repo. Keep `.claude/settings.json`.
5. Update `AGENTS.md` mirror in so101 to match.

Each numbered step is one PR. Steps 1–3 in so101 can interleave with i3mega's step 1, but should not block on it.

## Out of scope

- Renaming the **Python distribution names** (`so101`, `pipettebot`). This ADR only addresses source-tree layout.
- Renaming `hardware/` to anything else. Both repos already match.
- The marketplace plugin's internal structure. That's an implementation detail of `qte77-claude-code-plugins`, not of either lab repo.

## References

- This ADR — [docs/adr/0001-repo-structure-alignment.md](./0001-repo-structure-alignment.md)
- Decision context captured in handoff session for [`i3mega-pipettebot`](https://github.com/qte77/i3mega-pipettebot), 2026-05-11
- Cross-repo tracking issue in so101: [Lambda-Biolab/so101-biolab-automation#4](https://github.com/Lambda-Biolab/so101-biolab-automation/issues/4)
- AGENTS.md doc hierarchy convention: this is the first ADR; future architecture decisions go in `docs/adr/NNNN-<slug>.md`
