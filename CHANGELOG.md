# Changelog

All notable changes to this project will be documented in this file.

<!-- scriv-insert-here -->

## [Unreleased]

## [0.2.0] — 2026-09-17

Third tagged release. Adds an ADR for the firmware-modification escalation
path, Pi 3 B+ deploy infrastructure, motion-profile + deck-layout SVG
visualization with dark-mode theming shared across the CAD and viz
pipelines, a dPette+ 8-channel column-pitch constant, and a substantial
doc/governance sync — on top of the A30/Smartto bring-up and CAD/slicer
pipeline work accumulated below since 0.1.0.

### Changed

- `pipettebot.gantry.open_marlin_port` renamed to `open_gcode_port` (the helper is firmware-agnostic — a Linux baud helper, not a Marlin-protocol thing). The old name is preserved for one release cycle as a one-line alias that emits `DeprecationWarning` on call, so downstream scripts keep working while operators migrate. All in-tree callers (`pipettebot.devices.discover`, `tools/gantry_repl.py`, `tools/gantry_probe.py`, `tools/diagnose_axis.py`, `examples/home_G28_fast.py`) updated to the new name. Both names re-exported from `pipettebot.__init__`.
- **Single `PRINTER_PORT` env across the project.** `FirmwarePolicy.port_env_aliases` field removed; per-model `I3MEGA_PORT` / `SMARTTO_PORT` / generic `GANTRY_PORT` collapsed into one `PRINTER_PORT_ENV` constant in `pipettebot.devices`. Firmware family is identified by `discover()` after open, not by which env var the operator set. `tools/preflight.py --export` emits `export PRINTER_PORT=...` regardless of detected family; `tools/gantry_repl.py` and `tools/gantry_probe.py` read `PRINTER_PORT` only. Existing `_i3` example scripts updated to read `PRINTER_PORT` / `PRINTER_BAUD` in lockstep.
- **Existing showcase scripts renamed with `_i3` infix** (`home_G28_fast_i3`, `showcase_v0_i3_pipette_sim`, `showcase_v0_i3_full_dpette_cycles`, `showcase_v0_i3_full_pipettebot`, `showcase_v0_i3_full_pipettebot_rows`, `showcase_v0_i3_full_plate`, `showcase_v0_i3_tip_pickup_release`). They're hardcoded to i3-Mega deck coords (210×210 bed) and plain `G28`, which would crash Z on Smartto/A30 builds. Same directory now hosts A30 scripts alongside without naming ambiguity.
- **Motion profiles retuned to exact 3x ratio** — SLOW (accel_x/y/z 200/267/67, jerk 1.0/1.67/0.07, accel_default 200) → MID (600/800/200, 3/5/0.2, 600) → FAST (1800/2400/600, 9/15/0.6, 1800). Earlier values had non-uniform spacing (FAST was 1.67x MID on accel_x, 1.5x on accel_y); third/triple around the operator-validated MID anchor makes the per-profile difference obvious on the bench and predictable when tuning per-leg feedrates inside these caps. Accel rounded to integer mm/s² (M201/M204 want integers); jerk to two decimals. ADR 0003 example block + motion_profile.py docstring comparison table both updated to match.
- **`so101-biolab-automation` pinned to a commit SHA** instead of a floating `@main` ref (mirrors the existing `dpette` pin), and `[tool.uv] exclude-newer` bumped forward. Root-cause fix for `main`'s CI (`lint-and-test`) failing on every push for roughly two months: the floating ref bumped its `fastapi`/`numpy` floors past the resolver's cutoff, and this project's `uv.lock` is deliberately gitignored (library project), so every CI run re-resolved from scratch and hit the same failure.
- **`tools/slicer/validate.py`**: now detects PrusaSlicer's silent `"objects outside the print volume"` exit-0 case as a real failure, requires the output file to actually exist before declaring PASS, and forwards `tools/slicer/profiles/*.ini` keys as explicit CLI flags (PrusaSlicer 2.9.4's `--load` silently drops most profile keys).
- **`tools/slicer/profiles/pla_plus_02mm.ini`**: added `first_layer_temperature`, `first_layer_bed_temperature`, and a `start_gcode`/`end_gcode` pair that actually heats the bed before printing (previously the slicer emitted nozzle heat only, and PLA wouldn't stick).
- **`docs/3d-parts.md`**, **`AGENT_LEARNINGS.md`**: cross-referenced issue #75 (upper-clamp cap history) and corrected a stale "Open issues" table that still listed several already-closed issues.

### Added

- **`docs/research/aspirate-monitoring.md`** — append-only research log on aspirate verification (clog / dry-well / volume confirmation) technologies. First entry surveys Hamilton MAD / TADM as the industry reference; verdict for v0 is document-only (the dPette+ nozzle has no exposed sensor port and a bolt-on inline pressure sensor would require dPette+ internal characterization out of scope for v0). Linked from the Deferred section of `docs/roadmap.md` and from the Documentation index in `README.md`.
- **`docs/research/tip-disposal-belt-module.md`** — append-only research log on used-tip disposal mechanisms. First two entries cover the conveyor-belt 3D printer landscape (all commercial belt printers are tilted roll-off; no horizontal-loop product exists at any price; verified vendor list with first-party citations from `3dsourced.com`, `clevercreations.org`, and the `NAK3DDesigns/White-Knight` GitHub repo) and a commodity standalone belt module (~$37–72 BOM, deferred behind firmware-modification gating per AGENTS rule #4). v0 keeps the passive `dpette_tip_release` waste slot. Linked from the Deferred section of `docs/roadmap.md` and from the Documentation index in `README.md`.
- **`docs/research/alternative-pipettes.md`** — append-only research log evaluating candidate pipettes for the `_Pipette` Protocol. First three entries: DLAB dPette+ (supported reference) and 8-channel dPette (candidate, untested, multi cradle already in `parts.json`); Opentrons GEN2 (not viable — proprietary CAN protocol with no public documentation); ac-rad Digital Pipette (out of scope — syringe, not disposable-tip). Linked from the Documentation index in `README.md`.
- **`README.md` related-repositories entry**: added [`xg590/Learn_dPettePlus`](https://github.com/xg590/Learn_dPettePlus) as the intellectual-lineage source for the `dpette-usb-driver` reverse-engineering.
- **`[tool.pyright]` config block in `pyproject.toml`** (#158, by JosefVacha — fixes #156). Points Pyright at the project venv (`.venv`) and `src/` layout so editor / Pylance diagnostics align with `mypy --strict src/`'s view. No CI gate change; `make validate` still runs `mypy --strict src/`. Eliminates the "Import could not be resolved" noise for pytest / hypothesis / pipettebot.devices / serial that surfaced repeatedly during PR #157 work.
- **Signed-commits policy in CONTRIBUTING.md** (#159). Every commit on a PR branch must carry a verified GPG or SSH signature. Squash-merge preserves contributor author attribution on `main` (web-flow signs the squash commit), so the requirement is about source-commit chain-of-custody, not credit. Anticipated follow-up: enable "Require signed commits" in branch-protection settings to enforce mechanically.
- **`pipettebot.devices.safe_home(gantry, policy)` dispatcher** — policy-driven home: `full_g28` (Marlin) sends `G28`; `xy_then_polled_z` (Smartto/A30) runs `G28 X Y` + absolute-mode polled-Z descent + `G92 Z0`; `manual_only` (unknown) raises. Polled descent uses M119 polling between absolute `G1 Z<target>` steps (Smartto's `G91` G1 Z doesn't move; absolute does), `G92 Z<max_travel>` headroom bypasses soft endstops, per-step 0.8 s host sleep prevents Smartto's M400-race from queueing commands ahead of physical motion, and the failure path captures both M119 + M114 for triage. `home_xy=False` skips `G28 X Y` for post-cycle Z-only verification. Hardware-validated on Geeetech A30 + Smartto v1.xx.58.
- **`GcodeGantry.send(line)` and `.query(line)` public methods.** `send` returns just the terminating `ok` line; `query` returns every reply line (multi-line `M119`/`M114`/`M115`/`M503`). Both used by `safe_home`. `.flush_input()` for stale-buffer recovery after long burst sessions.
- **ADR 0004 — Single `PRINTER_PORT` env + policy-driven `safe_home`** documents the alias collapse, alternatives considered (two adapter classes vs. method-on-GcodeGantry vs. free function), and the manual-confirm Z-home approach that was withdrawn after hardware testing (A30's stepper-energized leadscrew can't be jogged by hand).
- **`examples/home_safe_a30.py`** — dedicated A30 home script. Counterpart to `home_G28_fast_i3.py`. Applies motion profile then calls `safe_home`; exits. Verified live: polled descent triggers at the inductive sensor's LED point.
- **`examples/showcase_v0_a30_liquid_handling.py`** — end-to-end A30 liquid-handling demo. Discovery → motion profile → pre-home Z lift (forces fresh descent every run) → `safe_home` → linger at Z=0 → N transfer cycles with split-feedrate dives (`XY_FEED`/`Z_FAST_FEED`/`LIQUID_DIVE_FEED`, `TOUCHDOWN_APPROACH_MM=10` — same pattern as `showcase_v0_i3_full_pipettebot_rows`) → post-cycle Z-only re-home → linger at Z=0 → park at (0, 0, 0). Defaults exercise both X and Y (SOURCE diagonal-from DEST). Gracefully runs gantry-only when `PIPETTE_PORT` is unset (`_LoggingPipette` stub satisfies the `_Pipette` protocol).
- **`tools/gantry_repl.py`** — interactive G-code REPL with per-firmware cheat-sheet dispatch. Auto-detects firmware via `pipettebot.devices.discover()`; `--device {marlin,smartto,unknown}` overrides the auto-detect. Reads `PRINTER_PORT`. Replaces `tools/marlin_repl.py` + `tools/smartto_repl.py`.
- **`tools/gantry_probe.py`** — read-only diagnostic + capability probe for any G-code firmware. Same auto-detect via `discover()`. Nine non-motion candidates (six original — `M503`/`M400`/`M203`/`M204`/`M205`/`M501` — plus `M220 S100` / `M211 S1` / `M85 S0` for feedrate scale, soft endstops, idle timeout). Per-family `QUIRKS` footer surfaces operator notes (e.g. Smartto's `M503` no-op, `G1 X Y` silent acceptance, `G28 Z` dive). Replaces `tools/smartto_probe.py`.
- **Test coverage** — `tests/tools/test_gantry_repl_cli.py` and `tests/tools/test_gantry_probe_cli.py` (12 in-process CLI tests). `tests/test_devices.py` extended with safe_home / polled-Z descent coverage (~10 new tests + Hypothesis property test on M115 parsing). Total suite: 121 passed, 6 skipped.
- **ADR 0005 — PC-as-host** (`docs/adr/0005-pc-as-host.md`). Formalizes the existing "no firmware modifications in v0" policy with the full Stage 0-2c escalation path and trigger conditions for each stage. Unblocks Stage 1+ firmware issues, which require an ADR to exist before merging per `AGENTS.md` rule 4.
- **Pi 3 B+ deploy infrastructure**: `tools/deploy/bootstrap.sh`, `tools/deploy/deploy.sh`, `tools/deploy/orchestrator.service`, `tools/deploy/99-pipettebot.rules` (udev), and a new `make check_deploy` target (shellcheck + bats + `systemd-analyze verify` + best-effort `udevadm`). Both scripts support `--dry-run`. Documents the CP2102N VID:PID collision between i3 Mega and dPette as a known limitation requiring per-unit `ATTRS{serial}` rules.
- **`_ArmController` Protocol** in `src/pipettebot/so101/orchestrator.py` — decouples type-checking from the optional `[orchestrator]` extra; the real `so101.arms` import now only happens at runtime inside `load_so101_controller()`.
- **Slicer tooling**: `make slice PART=<name>` (STL -> tracked `hardware/bgcode/<area>/<part>.bgcode` via named Input Shaper presets), `make setup_prusa_presets` (extracts MK4 IS presets from the system PrusaSlicer bundle into `~/.config/PrusaSlicer/`), `make dev_diagram` (wraps the diagramforge dev server).
- **`tools/cad/i3/carriage_dpette_mount_frictionfit.py`** — a self-contained, clearly-labeled (`parts.json` `"status": "testing"`) preservation of an abandoned carriage-mount design iteration (glue/friction-fit upper clamp, J-hook lower clamp) reached through real physical dry-fit testing on a since-diverged branch. Kept as reference/testing material, not a production candidate — see issue #75 for why it was abandoned.
- **`tools/cad/view.py`** — push a named part to the ocp-vscode browser viewer for design review. **`tools/slicer/upload_to_prusalink.py`** — PrusaLink HTTP upload with credentials read from `~/.cloud-credentials` (permission-checked, never committed). **`tools/slicer/print_carriage_assembly.py`** — batch-prints the friction-fit testing mount's 4 main pieces as one pre-arranged bed layout.
- **`COLUMN_PITCH_MM = 9.0`** constant in `src/pipettebot/bot.py` (re-exported from `pipettebot`) — the dPette+ 8-channel's SBS-matching row pitch, for callers computing column XY offsets by hand. Documents the physical constraint that all 8 channels share one piston bar (no independent per-channel volume).
- **Hypothesis property test** (`tests/test_gantry.py`) asserting `GcodeGantry.move_to()` emits well-formed `G1` lines (field order, 3-decimal precision, feedrate, single terminating newline) across the full float domain.
- **Pre-push validate guidance** in `CONTRIBUTING.md`: an optional three-line `.git/hooks/pre-push` snippet running `make validate`, plus a `--no-verify` emergency-skip note.
- `scriv` added to the `dev` extra — the `[tool.scriv]` config and `changelog.d/` fragment directory existed already but the CLI itself was never added as a dependency.
- **`tools/motion_profile_plot.py`** (closes #116) — renders three design-review SVGs to `hardware/svg/motion-profile/`: per-axis kinematics under the active `MotionProfile`'s M203/M201/M205 caps, a three-view path plot, and a deck-layout top view replacing the ASCII sketch in `docs/sketches/deck-layout-rows-script.md`. Deck geometry is read from `examples/showcase_v0_i3_full_pipettebot_rows.py` via reflection so the plot can't drift from what the gantry actually receives. New optional `viz` extra (`matplotlib`) and `viz` pytest marker; `make render_motion_profile MOTION_PROFILE=slow|mid|fast` (default `mid`).
- **`tools/cad/util/theme_svgs.py`** now content-sniffs matplotlib vs. build123d SVGs and applies the right dark-mode CSS for each dialect — matplotlib's inline `style=` attributes and unstyled vector-glyph text need different selectors than build123d's bare `stroke="rgb(...)"` output. Verified against a real `polyfetch --color-scheme dark` screenshot, not just code review.

### Fixed

- **`tests/tools/cad/test_parts_smoke.py`** referenced two CAD files (`labware/tip_rack_holder.py`, `labware/plate_holder.py`) removed months earlier when they were consolidated into `labware/deck_plate.py`'s combined assembly. Replaced with the part that's actually registered in `tools/cad/parts.json`.
- **`.gitignore`** was missing `hardware/step/` despite STEP export existing since the original deck-plate PR — generated STEP files were untracked-but-visible in every `git status` since.

### Removed

- `tools/marlin_repl.py` — superseded by `tools/gantry_repl.py`.
- `tools/smartto_repl.py` — superseded by `tools/gantry_repl.py`.
- `tools/smartto_probe.py` — superseded by `tools/gantry_probe.py`.
- `FirmwarePolicy.port_env_aliases` field — superseded by the single `PRINTER_PORT_ENV` constant.

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
