# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- `docs/adr/0001-repo-structure-alignment.md` — first ADR. Decides both i3mega-pipettebot and so101-biolab-automation converge on `src/<pkg>/` (PEP 517 src layout) + `tools/{cad,slicer}/` + `config/` (singular) + marketplace-only Claude skills **and** rules. Cross-repo migration tracked at [Lambda-Biolab/so101-biolab-automation#4](https://github.com/Lambda-Biolab/so101-biolab-automation/issues/4). AGENTS.md doc hierarchy extended with `docs/adr/NNNN-*.md` for future architecture decisions (#53, #54).
- `tools/cad/barrel_bore.py::make_clamp_bore(d, h, diametral_clearance_mm)` — reusable round-bore primitive for clamping cylindrical pipette barrels. Three call sites (mount main, mount cap, single cradle) standardise on the diametral-clearance convention; closes #41 by replacing inline `Cylinder(r, h)` patterns that had drifted on clearance semantics. Lives at top of `tools/cad/` (not under `tools/cad/dpette/`) to dodge the namespace collision with the installed `dpette-usb-driver` package (#49).
- `tools/cad/i3/carriage_dpette_mount.py::build_carriage_dpette_mount_main_lbracket` — scheme b mount variant. Adds an L-bracket reinforcement engaging the carriage V-plate top with 2× M4 (28 mm pitch, 27.5 mm Z) — resists pitch torque under XY acceleration. ~23 g PLA main + ~3 g cap + 250 g pipette + 3 g tips = ~279 g, under the 300 g AI3M payload cap. Cap is shared with scheme a (#48).
- `tests/tools/cad/test_barrel_bore.py`, `tests/tools/cad/test_tip_ejection_bar.py`, and 6 scheme-b cases in `tests/tools/cad/i3/test_carriage_dpette_mount.py` (#48, #49, #52).
- 3D parts pipeline under `tools/cad/` — build123d (manifest-driven `render.py` + `parts.json`) generates STLs/SVGs for tip rack, plate holder, dPette cradles, tip ejector, ejection post; ported from `so101-biolab-automation`. New extras group `cad`, new make targets `setup_cad`, `setup_slicer`, `setup_diagramforge`, `render_parts`, `check_prints`, `render_all`.
- `tools/cad/i3/carriage_dpette_mount.py` real parametric geometry (replaces earlier stub) — two-piece split-clamp design (main + cap) for the dPette+ 8-channel on the bare i3 Mega carriage. Bolts via 4× M4 to the carriage's existing 21 × 13 mm hole pattern; cap captures the Ø27 round upper barrel via 2× M3. Mass ~19 g PLA, leaves ~28 g headroom under the 300 g AI3M carriage payload cap. Hypothesis-style tests assert payload budget, Z envelope, and X-symmetry.
- `tools/cad/measurements.py` — single source of truth for every measured hardware dimension (carriage screw pattern, dPette+ envelope, printer Z envelope, material densities, AI3M payload cap).
- `tools/slicer/validate.py` — OrcaSlicer-first printability validator with PrusaSlicer fallback; shared `.ini` profiles in `tools/slicer/profiles/{pla_plus,tpu_95a}_02mm.ini` (Prusa-class, ported from so101 — fabrication happens off-printer).
- `.claude/settings.json` — adopt `qte77-claude-code-plugins` marketplace and 8 plugins (context7, code-review, code-simplifier, cc-meta, python-dev, docs-governance, commit-helper, codebase-tools); deny/ask blocks push dedicated tools over bash.
- `.claude/rules/{testing,cad-script-conventions,slicer-profile-source-of-truth,i3-carriage-payload-budget,cad-printability-gate}.md` — path-scoped rules for the new pipeline.
- `pipettebot.gantry.open_marlin_port()` — opens a Marlin serial port at 250000 baud with a Linux `TCSETS2 + BOTHER` fallback for Python builds missing `termios.B250000`. Used by `tools/preflight.py` and `examples/showcase_v0_pipette_sim.py` (#30)
- `tools/diagnose_axis.py` — safe per-axis motion diagnostic for headless-gantry use. `AXIS=X|Y|Z`. Reports endstop state via `M119`, then steps the chosen axis by 1 mm under operator confirmation. Never homes, restores `G90` on exit. First entry under `tools/` per the AGENTS.md "hardware experiments" convention (#35)
- `tools/marlin_repl.py` — interactive G-code REPL with a built-in cheat-sheet (`?`). For one-shots like `M119` (endstops), `M999` (clear halt), `M114` (position), `M115` (firmware), `M503` (EEPROM dump) (#35)
- `tools/preflight.py --export` — emits `export I3MEGA_PORT=...` / `export PIPETTE_PORT=...` lines on stdout (probe chatter routed to stderr) so the discovered ports can be chained into the next command via shell `eval`. Example: `eval "$(uv run python tools/preflight.py --export)" && uv run python examples/showcase_v0_pipette_sim.py` (#36)
- `docs/marlin-commands.md` — reference table of common Marlin G/M-codes for i3 Mega bring-up and debugging, plus i3 Mega coordinate orientation and project-specific gotchas (M412 not on 1.1.9, G28 Z risk after head removal, T0 abnormal recovery, 250000-baud Linux fallback) (#33)
- `docs/sbc-deployment.md` — Path 2 (SBC-on-printer) deployment guide (#21)
- `.claude/rules/{compound-learning,context-management,core-principles}.md` — repo-local agent governance rules (#20)
- `AGENT_LEARNINGS.md` first entry: sandbox bind-mount untracked-files pattern (#25)
- `AGENT_REQUESTS.md` "SBC deployment (Path 2)" section migrating the doc-body backlog (#25)

### Changed

- `AGENT_REQUESTS.md` repurposed from per-area backlog to agent-to-human / agent-to-agent communication channel. Plain task lists and closed-item history removed; preamble explains the file's intent (messages, not work items). Open agent-to-human items from this session migrated to dedicated issues #59 (V-plate Y fit-test) and #60 (tip_ejection_bar XY decision) (#56, #57, #58, #61).
- `Makefile` — every uv-using target (`lint`, `lint_fix`, `test`, `validate`, `quick_validate`, `render_parts`, `check_prints`) now prefers `.venv/bin/<tool>` over `uv run`, falling back to `uv run` only when `.venv` is absent. Sidesteps `uv run` writing `~/.cache/uv/` on read-only hosts (sandbox builds, sealed Pi images). `check_complexity` keeps `uv run complexipy` — niche, not in `make validate` (#50).
- `tools/cad/i3/carriage_dpette_mount.py` measured constants — 10 local copies (carriage screw pattern, dPette+ clamp sizes, PLA density) replaced with explicit imports from `tools/cad/measurements.py`. Mount-specific design knobs (top-plate geometry, post placement, etc.) stay local. Drift between source-of-truth and local copies is now structurally impossible. Two tautological "constants match" tests dropped (#51).
- `tools/cad/dpette/dpette_cradle.py` and `tools/cad/i3/carriage_dpette_mount.py` — bore subtraction switched from inline `Cylinder((d + clearance) / 2, h)` to `make_clamp_bore(...)` (#49).
- `tools/cad/measurements.py` docstring — convention is now imports-only across CAD scripts (#51).
- `pyproject.toml` Python pin tightened to `>=3.11,<3.13` (build123d → cadquery-ocp → VTK has no cp313 wheels). Ruff `mccabe.max-complexity` lowered to 8 (was 10) for stricter complexity gating across `src/`, `tools/`, `tests/`, `examples/`. `tools/cad/**` and `tools/slicer/**` excluded from mypy strict.
- Slicer profile naming + targets — `tools/slicer/profiles/i3mega_{pla,petg}_02mm.ini` removed; replaced with `pla_plus_02mm.ini` and `tpu_95a_02mm.ini` (Prusa MK3S+-class, ported from so101). The stripped i3 Mega chassis no longer prints anything; mount fabrication happens elsewhere on a Prusa-class machine. `validate.py` `--profile` choices: `pla` | `tpu` (was `pla` | `petg`).
- `.claude/rules/motion-safety.md` and `.claude/rules/pipette-delegation.md` — added YAML `paths:` frontmatter so they only load in `src/`/`examples/`/`tests/` contexts.
- `examples/preflight.py` → `tools/preflight.py`. Reclassifies preflight as a hardware-diagnostic tool rather than a usage example, matching the AGENTS.md `tools/` convention. All references in README / docs / sibling tools updated. Makefile lints `tools/` too (#36)
- `examples/showcase_v0_pipette_sim.py` replaces `showcase_v0.py` as the canonical hardware demo — raw-serial read-until-`ok`, plunger simulated via gantry Z, G-code tee to disk (#23)
- `tools/preflight.py` rewritten — auto-discovers ports, 3 s boot wait, dPette stub-mode detection, configurable standby retry (#23)
- `tools/preflight.py` passes when either i3 Mega **or** dPette is found (was: required both). Reflects v0 usage where the gantry and pipette are exercised independently. `--export` mode emits only the lines for devices that were actually found. Existing `I3MEGA_PORT` / `PIPETTE_PORT` env overrides unchanged (#37)
- README example commands use `uv run` (#16)
- `docs/hardware.md` documents CH340 + CP2102N USB-bridge variants and `M115` tiebreaker; corrects stock baud to 250000 (#25)
- `.claude/rules/core-principles.md` refined for project use — AHA principle, Communication section, pre-task clarity check (#24)
- `.gitignore` excludes per-session agent state and sandbox-bind-mounted dotfiles (#19, #24)
- README, CONTRIBUTING.md, docs/calibration.md copy-paste blocks no longer break stock zsh (#25)

### Fixed

- `tools/cad/dpette/tip_ejection_bar.py` primitive stacking — build123d's `Cylinder` and `Cone` default to fully-centred-at-origin, not z-bottom-at-origin. Original code positioned the post centre at z = T/2 (= 2 mm), making the post span z ∈ [-28, 32] (bottom half buried below the base) and floated the cone at z ∈ [59, 65] with a 27 mm air gap to the post top. Now stacks correctly: base [-2, 2], post [2, 62], cone [62, 68]. Slicer warnings reduced from 5 sub-causes to 2 (residual = post centred over Ø25 waste hole, requires bridging — design issue, separate from this fix) (#52).
- `tools/cad/render.py` and `tools/cad/util/export.py` SVG export — switched from `Rot(35.264, 0, -45) * shape` + `ExportSVG.add_shape` (a 2D-shape exporter that flattens 3D solids to a misleading XY squash, with a "non-planar shape" warning) to `Compound.project_to_viewport(viewport_origin, viewport_up, look_at)` for proper hidden-line projection. Visible edges render solid black, hidden edges dotted gray. SVGs now match the STL geometry and are right-side-up.
- `tools/cad/i3/carriage_dpette_mount.py` post connectivity — single central post at (X=0, Y=0) intersected both clamp bores (top plate D-cavity and lower clamp horseshoe), leaving the lower clamp floating in the slicer's eyes. Replaced with two posts at X=±18, Y=+14 (behind the bores), each 6 × 12 mm cross-section, anchored to real plate + lower-clamp back-wall material. Slicer no longer reports "Floating object part".
- `tools/slicer/validate.py` `OVERHANG_KEYWORDS` — tightened from generic terms (`overhang`, `bridge`, `unsupported`) to literal slicer warning phrases (`floating object part`, `floating bridge anchors`, `loose extrusions`, `long bridging extrusions`, `empty layer`, `could not slice`). The old keywords matched routine slicer chatter (config-string descriptions like "support overhang threshold = 45°") and surfaced false-positive WARN on every part. Now `plate_holder` and `tip_rack_holder` PASS cleanly.
- `tools/cad/labware/plate_holder.py::build_plate_holder` returns a `ShapeList` from chained `+` operations on newer build123d versions; smoke test now wraps into `Compound` mirroring `render.py`'s existing `_to_compound` wrapper.
- Marlin USB probe (`tools/preflight.py`) and the v0 hardware showcase (`examples/showcase_v0_pipette_sim.py`) now open 250000 baud via Linux `TCSETS2 + BOTHER` ioctl on any Linux Python build that omits `termios.B250000`. Previously both crashed with `termios.error: (22, 'Invalid argument')`. The shared `pipettebot.gantry.open_marlin_port` helper is gated on `sys.platform == "linux"` and is harmless on builds that do expose the constant (#30)
- Default Marlin baud was 115200 in gantry/preflight/docs; now 250000 to match Anycubic stock + MARLIN-AI3M (#23, closes #17)
- Port discovery handles CP2102N on newer Anycubic batches; docs reflect both bridge variants (#23, #25, closes #18)
- Quickstart copy-paste no longer breaks on stock zsh with `interactive_comments` off (#25, closes #15)

### Removed

- `.github/social-preview.png` — repo now uses GitHub's default open-graph card. The asset is unused and the asset-slot doc was updated accordingly.
- `examples/showcase_v0.py` — superseded by `examples/showcase_v0_pipette_sim.py` (#23)

## [0.0.1] — 2026-05-07

First tagged release. Working v0 prototype with software-only validation
and a hardware onboarding path.

### Added

- v0 pipettebot package: `GcodeGantry`, `PipetteBot`
- `examples/showcase_v0.py` — happy-path aspirate/dispense demo
- `examples/preflight.py` — non-actuating port + firmware sanity check
- `docs/hardware.md` — i3 Mega + dPette wiring, port discovery
- `docs/calibration.md` — well-A1 origin procedure, 9 mm pitch check
- `.github/social-preview.png` — repo social preview matching Lambda Biolab style
- Mocked-serial test suite (9 tests, both Python 3.11 and 3.12)
- CI workflow (uv-based; ruff format/lint, mypy strict, pytest mocked)
- Apache-2.0 license + NOTICE crediting Anycubic i3 Mega, Marlin, dpette-usb-driver
- AGENTS.md / CLAUDE.md / GEMINI.md doc hierarchy mirroring Agents-eval
- AGENT_REQUESTS.md backlog with deferred liquid-handling, deck, firmware, hardware items
- `.claude/rules/motion-safety.md` and `.claude/rules/pipette-delegation.md`
- Makefile recipes via `uv run`; pre-commit removed in favor of Makefile + CI

### Pinned

- `dpette` dependency pinned to commit SHA for reproducibility
