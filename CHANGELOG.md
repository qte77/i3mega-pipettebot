# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- `tools/setup_pi.sh` — Pi-as-host provisioning helper (Path 2). Idempotent bootstrap: system deps → uv (ARMv6 → system-pip fallback) → repo clone → mocked test gate → port discovery → `config.local/pipettebot.env` with `/dev/serial/by-id/...` paths (#65).
- `docs/adr/0001-repo-structure-alignment.md` — first ADR. i3mega-pipettebot and so101-biolab-automation converge on `src/<pkg>/` + `tools/{cad,slicer}/` + `config/` (singular) + marketplace-only Claude skills & rules. Cross-repo migration: [so101#4](https://github.com/Lambda-Biolab/so101-biolab-automation/issues/4). Doc hierarchy extended with `docs/adr/NNNN-*.md` (#53, #54).
- `tools/cad/barrel_bore.py::make_clamp_bore` — reusable round-bore primitive (3 call sites: mount main, cap, single cradle). Top-level under `tools/cad/` to dodge the `dpette` package collision. Closes #41 (#49).
- `tools/cad/i3/carriage_dpette_mount.py::build_carriage_dpette_mount_main_lbracket` — scheme b mount variant. L-bracket reinforcement on carriage V-plate top (2× M4, 28 mm pitch). ~279 g total under the 300 g AI3M cap (#48).
- `tests/tools/cad/test_barrel_bore.py`, `test_tip_ejection_bar.py`, and 6 scheme-b cases in `test_carriage_dpette_mount.py` (#48, #49, #52).
- 3D parts pipeline under `tools/cad/` — build123d manifest-driven `render.py` + `parts.json` for tip rack, plate holder, dPette cradles, tip ejector, ejection post (ported from so101). New `cad` extras and `setup_cad`/`setup_slicer`/`setup_diagramforge`/`render_parts`/`check_prints`/`render_all` make targets.
- `tools/cad/i3/carriage_dpette_mount.py` real parametric geometry — two-piece split-clamp (main + cap) for the 8-channel dPette+ on the bare carriage. 4× M4 to the 21 × 13 mm pattern; 2× M3 cap on the Ø27 upper barrel. ~19 g PLA, ~28 g headroom under the 300 g cap. Hypothesis tests for payload budget, Z envelope, X-symmetry.
- `tools/cad/measurements.py` — single source of truth for measured hardware dimensions (carriage screw pattern, dPette+ envelope, Z envelope, material densities, AI3M payload cap).
- `tools/slicer/validate.py` — OrcaSlicer-first printability validator with PrusaSlicer fallback; shared `.ini` profiles in `tools/slicer/profiles/{pla_plus,tpu_95a}_02mm.ini` (Prusa-class, ported from so101).
- `.claude/settings.json` — adopt `qte77-claude-code-plugins` marketplace and 8 plugins (context7, code-review, code-simplifier, cc-meta, python-dev, docs-governance, commit-helper, codebase-tools).
- `.claude/rules/{testing,cad-script-conventions,slicer-profile-source-of-truth,i3-carriage-payload-budget,cad-printability-gate}.md` — path-scoped rules for the new pipeline.
- `pipettebot.gantry.open_marlin_port()` — opens a Marlin port at 250000 baud with a Linux `TCSETS2 + BOTHER` fallback for Python builds missing `termios.B250000` (#30).
- `tools/diagnose_axis.py` — safe per-axis motion diagnostic (`AXIS=X|Y|Z`). Reports `M119` first; never homes; restores `G90` on exit (#35).
- `tools/marlin_repl.py` — interactive G-code REPL with built-in cheat-sheet (`?`) for `M119`, `M999`, `M114`, `M115`, `M503` (#35).
- `tools/preflight.py --export` — emits `export I3MEGA_PORT=...` / `export PIPETTE_PORT=...` on stdout (chatter to stderr) for shell `eval` chaining (#36).
- `docs/marlin-commands.md` — Marlin G/M-code reference for i3 Mega bring-up + coordinate orientation + project-specific gotchas (#33).
- `docs/sbc-deployment.md` — Path 2 (Single-Board Computer on-printer) deployment guide (#21).
- `.claude/rules/{compound-learning,context-management,core-principles}.md` — repo-local agent governance rules (#20).
- `AGENT_LEARNINGS.md` first entry: sandbox bind-mount untracked-files pattern (#25).

### Changed

- `docs/sbc-deployment.md` — Pi setup section now invokes `tools/setup_pi.sh` via `curl | bash` instead of a 5-step manual recipe. Four stale `AGENT_REQUESTS.md` links repointed to live issues (#6, #11) and label conventions. **Single-Board Computer (SBC)** spelled out on first use. armhf vs arm64 image guidance clarified for Pi 1 B+ (#65).
- `.gitignore` — replaced stale `config/` ignore (left over from a Claude skill's scratch state, #19) with `config.local/` for host-local runtime config, unblocking ADR 0001's tracked `config/` slot (#65).
- `AGENT_REQUESTS.md` repurposed from per-area backlog to agent-to-human / agent-to-agent communication channel. Open items migrated to dedicated issues #59 and #60 (#56, #57, #58, #61).
- `Makefile` — every uv-using target prefers `.venv/bin/<tool>` over `uv run`, falling back to `uv run` only when `.venv` is absent. Sidesteps `uv run` writing `~/.cache/uv/` on read-only hosts (#50).
- `tools/cad/i3/carriage_dpette_mount.py` — 10 local copies of measured constants replaced with imports from `tools/cad/measurements.py`. Two tautological tests dropped (#51).
- `tools/cad/dpette/dpette_cradle.py` and `tools/cad/i3/carriage_dpette_mount.py` — bore subtraction switched from inline `Cylinder(...)` to `make_clamp_bore(...)` (#49).
- `tools/cad/measurements.py` docstring — imports-only convention across CAD scripts (#51).
- `pyproject.toml` — Python pin tightened to `>=3.11,<3.13` (cadquery-ocp → VTK lacks cp313 wheels). Ruff `mccabe.max-complexity` lowered to 8. `tools/cad/**` and `tools/slicer/**` excluded from mypy strict.
- Slicer profiles renamed `pla_plus_02mm.ini` / `tpu_95a_02mm.ini` (was `i3mega_{pla,petg}_02mm.ini`). Stripped i3 Mega prints nothing; fabrication moves to Prusa-class machines. `validate.py --profile` choices: `pla` | `tpu`.
- `.claude/rules/motion-safety.md` and `pipette-delegation.md` — added YAML `paths:` frontmatter so they only load in `src/`/`examples/`/`tests/` contexts.
- `examples/preflight.py` → `tools/preflight.py` (hardware diagnostic, not usage example). Makefile lints `tools/` too (#36).
- `examples/showcase_v0_pipette_sim.py` replaces `showcase_v0.py` as the canonical hardware demo — raw-serial read-until-`ok`, plunger simulated via gantry Z, G-code tee to disk (#23).
- `tools/preflight.py` — auto-discovers ports, 3 s boot wait, dPette stub-mode detection, configurable standby retry (#23). Passes when either i3 Mega or dPette is found, was: required both (#37).
- README example commands use `uv run` (#16).
- `docs/hardware.md` documents CH340 + CP2102N USB-bridge variants and `M115` tiebreaker; corrects stock baud to 250000 (#25).
- `.claude/rules/core-principles.md` refined for project use — AHA principle, Communication section, pre-task clarity check (#24).
- `.gitignore` excludes per-session agent state and sandbox-bind-mounted dotfiles (#19, #24).
- README, CONTRIBUTING.md, docs/calibration.md copy-paste blocks no longer break stock zsh (#25).

### Fixed

- `tools/cad/dpette/tip_ejection_bar.py` primitive stacking — build123d's `Cylinder`/`Cone` are centred-at-origin, not z-bottom. Now stacks correctly: base [-2, 2], post [2, 62], cone [62, 68]. Slicer warnings reduced from 5 sub-causes to 2 (#52).
- `tools/cad/render.py` and `tools/cad/util/export.py` SVG export — switched from `ExportSVG.add_shape` (2D exporter that flattens 3D to a misleading XY squash) to `Compound.project_to_viewport(...)` for proper hidden-line projection.
- `tools/cad/i3/carriage_dpette_mount.py` post connectivity — replaced central post (intersected both clamp bores → "Floating object part") with two posts at X=±18, Y=+14, each 6 × 12 mm anchored to plate + lower-clamp back-wall material.
- `tools/slicer/validate.py` `OVERHANG_KEYWORDS` — tightened from generic terms to literal slicer warning phrases. Old keywords matched routine slicer chatter ("support overhang threshold = 45°"); `plate_holder` and `tip_rack_holder` now PASS cleanly.
- `tools/cad/labware/plate_holder.py` — chained `+` returns a `ShapeList` on newer build123d; smoke test wraps into `Compound`.
- Marlin USB probe and v0 showcase open 250000 baud via Linux `TCSETS2 + BOTHER` ioctl on Python builds missing `termios.B250000`. Shared helper in `pipettebot.gantry.open_marlin_port` (#30).
- Default Marlin baud was 115200; now 250000 to match Anycubic stock + MARLIN-AI3M (#23, closes #17).
- Port discovery handles CP2102N on newer Anycubic batches (#23, #25, closes #18).
- Quickstart copy-paste no longer breaks on stock zsh with `interactive_comments` off (#25, closes #15).

### Removed

- `.github/social-preview.png` — repo now uses GitHub's default open-graph card.
- `examples/showcase_v0.py` — superseded by `examples/showcase_v0_pipette_sim.py` (#23).

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
