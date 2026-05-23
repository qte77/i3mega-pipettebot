# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed

- `pipettebot.gantry.open_marlin_port` renamed to `open_gcode_port` (the helper is firmware-agnostic — a Linux baud helper, not a Marlin-protocol thing). The old name is preserved for one release cycle as a one-line alias that emits `DeprecationWarning` on call, so downstream scripts keep working while operators migrate. All in-tree callers (`pipettebot.devices.discover`, `tools/gantry_repl.py`, `tools/gantry_probe.py`, `tools/diagnose_axis.py`, `examples/home_G28_fast.py`) updated to the new name. Both names re-exported from `pipettebot.__init__`.

### Added

- `tools/gantry_repl.py` — interactive G-code REPL with per-firmware cheat-sheet dispatch. Auto-detects firmware via `pipettebot.devices.discover()`; `--device {marlin,smartto,unknown}` overrides the auto-detect. Reads `GANTRY_PORT` (or `SMARTTO_PORT` / `I3MEGA_PORT` for operator continuity). Replaces `tools/marlin_repl.py` + `tools/smartto_repl.py`.
- `tools/gantry_probe.py` — read-only diagnostic + capability probe for any G-code firmware. Same auto-detect via `discover()`. Nine non-motion candidates (six original — `M503`/`M400`/`M203`/`M204`/`M205`/`M501` — plus `M220 S100` / `M211 S1` / `M85 S0` for feedrate scale, soft endstops, idle timeout). Per-family `QUIRKS` footer surfaces operator notes (e.g. Smartto's `M503` no-op, `G1 X Y` silent acceptance, `G28 Z` dive). Replaces `tools/smartto_probe.py`.
- `tests/tools/test_gantry_repl_cli.py` and `tests/tools/test_gantry_probe_cli.py` — 12 in-process CLI tests covering port-missing exit codes, cheat-sheet dispatch by family, `--device` override skipping `discover()`, banned-motion-command refusal, `PROBE_CANDIDATES` count + content, and `QUIRKS` content per family.

### Removed

- `tools/marlin_repl.py` — superseded by `tools/gantry_repl.py`.
- `tools/smartto_repl.py` — superseded by `tools/gantry_repl.py`.
- `tools/smartto_probe.py` — superseded by `tools/gantry_probe.py`.

## [0.1.0] — 2026-05-23

Second tagged release. Adds Geeetech A30 / Smartto firmware bring-up,
experiment + motion profile modules, the 3D-parts CAD/slicer pipeline,
six end-to-end showcase scripts, and a substantial doc + governance
buildout.

### Added

- **Geeetech A30 / Smartto bring-up** — `tools/smartto_probe.py` (read-only diagnostic + capability probe, 6 non-motion candidates classified SUPPORTED/UNSUPPORTED/PARTIAL/SILENT) and `tools/smartto_repl.py` (interactive REPL at 115200 baud). Live capability probe confirmed `M400`/`M203`/`M204`/`M205`/`M501` supported on Smartto v1.37.58 — Marlin-compatible motion surface. Operational caveat: `G28 Z` dives on this build (probe-pin variant); v0 routes around via `G28 X Y` + manual `G92 Z0`.
- **Experiment-profile loader** — `pipettebot.experiment_profile.load_experiment_profile` (TOML) + `PIPETTE_PROFILE` env on every dpette showcase. Sample profiles in `examples/experiment_profiles/`. Phase 1 of #79 (#82).
- **Motion-profile module** — `pipettebot.motion_profile` bundles SLOW/MID/FAST profiles; selectable via `MOTION_PROFILE`; emits `M203/M201/M204/M205` bootstrap. Design rationale in [ADR 0003](docs/adr/0003-motion-profile-bundled-constants.md).
- **Shared CLI env-var resolution** — `pipettebot.cli_profile` (`build_volumes()`, `resolve_profile()`) consumed by every showcase. 16 unit tests.
- **Showcase scripts** — `home_G28_fast`, `showcase_v0_pipette_sim`, `showcase_v0_tip_pickup_release`, `showcase_v0_full_plate`, `showcase_v0_full_pipettebot`, `showcase_v0_full_pipettebot_rows`, `showcase_v0_full_dpette_cycles`.
- **Hardware bring-up tools** — `tools/preflight.py` (auto-discovers ports, `--export` for shell `eval`, dPette retry on standby), `tools/marlin_repl.py` (G-code REPL with cheat-sheet), `tools/diagnose_axis.py` (per-axis safe motion), `tools/setup_pi.sh` (Pi provisioning, #65).
- **3D parts pipeline** — `tools/cad/` (build123d manifest-driven `render.py` + `parts.json`: dPette cradles, tip ejector, carriage mount, deck plate, measurements module, reusable `make_clamp_bore` primitive) and `tools/slicer/validate.py` (OrcaSlicer-first printability gate with PrusaSlicer fallback).
- **`pipettebot.gantry.open_marlin_port()`** — opens at 250000 baud with Linux `TCSETS2 + BOTHER` fallback for Python builds missing `termios.B250000` (#30).
- **Docs** — `UserStory.md` (personas + workflows), `deck-layout.md` (220 × 220 mm deck-frame spec), `marlin-commands.md` (G/M-code reference), `sbc-deployment.md` (Pi-on-printer path). Two research logs: `cad-alternatives.md` (AI-CAD evaluation: GenCAD/EvoCAD/evo-cad — all SKIP/TRACK, none adopted) and `gantry-firmware-alternatives.md` (Geeetech A30 + Smartto). Three ADRs (0001 repo structure, 0002 cadkit extraction, 0003 motion-profile constants).
- **CI** — `.github/workflows/codeql.yml` (Python security-and-quality) and `.github/dependabot.yml` (weekly Actions + pip).
- **Agent governance** — `.claude/rules/{compound-learning,context-management,core-principles,testing,cad-script-conventions,slicer-profile-source-of-truth,i3-carriage-payload-budget,cad-printability-gate}.md`. `AGENT_LEARNINGS.md` first entry. Adoption of `qte77-claude-code-plugins` marketplace (8 plugins).

### Changed

- **Repo identity** migrated `Lambda-Biolab` → `qte77` across README, SECURITY, CONTRIBUTING, pyproject, NOTICE, ADRs, docs. `dpette-usb-driver` and `so101-biolab-automation` URLs preserved.
- **Naming symmetry** for profile modules: `pipettebot.profiles` → `pipettebot.experiment_profile` (parallel with new `motion_profile`); `examples/profiles/` → `examples/experiment_profiles/`; `load_profile()` → `load_experiment_profile()`.
- **Showcase scripts deduplicated** through `pipettebot.cli_profile.build_volumes()` — shared `PIPETTE_PROFILE` / `PIPETTE_VOLUME_UL` precedence, identical banner shape.
- **Per-dive Z slowdowns + touchdown split** in `showcase_v0_full_pipettebot_rows.py` — `TOUCHDOWN_APPROACH_MM=10.0` fast-then-slow approach reduces per-dive wall-clock by ~80% while preserving bed-contact protection.
- **Showcase geometry tightened** — `TRAVEL_Z` 125 → 95 mm (~6 s/cycle saved); `SBS_COL_PITCH` −10 → −9 mm (correct SBS standard, cumulative pitch error eliminated); asymmetric tip-pickup Z constants (#82, #83).
- **`RELEASE_BAR_Y`** re-measured to 220 (was 190 — hook is on the chassis frame, not the bed).
- **README** reworked with badge row, comparison table (Science Jubilee, OT-2 at $15,950), Quickstart hardening; YAML frontmatter dropped; demo GIF centred.
- **Makefile** reorganized: `help` is default; recipes grouped by `# MARK:` section; per-tool `.venv/bin/<tool>`-first dispatch with `uv run` fallback; recipe renames (`init` → `setup_dev`; new `setup_uv` / `setup_prod` / `setup_all`); `setup_diagramforge` SHA-pinned; `setup_*` recipes pass `--inexact` to `uv sync`.
- **Python pin** tightened to `>=3.11,<3.13` (cadquery-ocp → VTK lacks cp313 wheels). Ruff `mccabe.max-complexity` lowered to 8. `tools/cad/**` + `tools/slicer/**` excluded from mypy strict.
- **Slicer profiles** renamed `pla_plus_02mm.ini` / `tpu_95a_02mm.ini` — fabrication moves to Prusa-class machines (stripped i3 prints nothing).
- **`tools/preflight.py`** auto-discovers ports with stub-mode detection + standby retry; passes when *either* i3 Mega or dPette is found (was: required both) (#23, #37).
- **Marlin USB baud** corrected to 250000 (was 115200 — Anycubic stock + MARLIN-AI3M).
- **`AGENT_REQUESTS.md`** repurposed from per-area backlog into agent-to-human / agent-to-agent communication channel; open items migrated to GitHub issues.
- **`examples/preflight.py`** → `tools/preflight.py` (hardware diagnostic, not usage example).
- **`examples/showcase_v0_pipette_sim.py`** replaces `showcase_v0.py` as the canonical hardware demo (raw-serial read-until-`ok`, plunger simulated via gantry Z, G-code tee to disk).
- **`docs/hardware.md`** documents CH340 + CP2102N USB-bridge variants and `M115` tiebreaker.
- **`.claude/rules/motion-safety.md`** + `pipette-delegation.md` gain YAML `paths:` frontmatter so they only load in `src/`/`examples/`/`tests/` contexts.
- **`docs/sbc-deployment.md`** Pi setup invokes `tools/setup_pi.sh` via `curl | bash` (was 5-step manual recipe) (#65).
- README, CONTRIBUTING.md, docs/calibration.md copy-paste blocks no longer break stock zsh (`interactive_comments` off) (#25).

### Fixed

- CAD primitive stacking (build123d `Cylinder`/`Cone` are centred-at-origin), SVG export hidden-line projection, post connectivity in carriage mount.
- Slicer overhang keyword false-positives — tightened from generic terms to literal slicer warning phrases.
- USB port discovery for CP2102N on newer Anycubic batches (#23, #25, closes #18).
- Marlin USB at 250000 baud on Python builds missing `termios.B250000` (Linux `TCSETS2 + BOTHER` ioctl) (#30).
- Default Marlin baud was 115200; now 250000 to match Anycubic stock + MARLIN-AI3M (closes #17).
- Quickstart copy-paste no longer breaks on stock zsh (closes #15).

### Removed

- `examples/showcase_v0.py` — superseded by `examples/showcase_v0_pipette_sim.py` (#23).
- `.github/social-preview.png` — repo now uses GitHub's default open-graph card.

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
