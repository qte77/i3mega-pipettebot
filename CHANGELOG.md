# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- `pipettebot.gantry.open_marlin_port()` — opens a Marlin serial port at 250000 baud with a Linux `TCSETS2 + BOTHER` fallback for Python builds missing `termios.B250000`. Used by `tools/preflight.py` and `examples/showcase_v0_pipette_sim.py`.
- `tools/diagnose_axis.py` — safe per-axis motion diagnostic for headless-gantry use. `AXIS=X|Y|Z`. Reports endstop state via `M119`, then steps the chosen axis by 1 mm under operator confirmation. Never homes, restores `G90` on exit. First entry under `tools/` per the AGENTS.md "hardware experiments" convention.
- `tools/marlin_repl.py` — interactive G-code REPL with a built-in cheat-sheet (`?`). For one-shots like `M119` (endstops), `M999` (clear halt), `M114` (position), `M115` (firmware), `M503` (EEPROM dump).
- `tools/preflight.py --export` — emits `export I3MEGA_PORT=...` / `export PIPETTE_PORT=...` lines on stdout (probe chatter routed to stderr) so the discovered ports can be chained into the next command via shell `eval`. Example: `eval "$(uv run python tools/preflight.py --export)" && uv run python examples/showcase_v0_pipette_sim.py`.
- `docs/marlin-commands.md` — reference table of common Marlin G/M-codes for i3 Mega bring-up and debugging, plus i3 Mega coordinate orientation and project-specific gotchas (M412 not on 1.1.9, G28 Z risk after head removal, T0 abnormal recovery, 250000-baud Linux fallback).
- `docs/sbc-deployment.md` — Path 2 (SBC-on-printer) deployment guide (#21)
- `.claude/rules/{compound-learning,context-management,core-principles}.md` — repo-local agent governance rules (#20)
- `AGENT_LEARNINGS.md` first entry: sandbox bind-mount untracked-files pattern (#25)
- `AGENT_REQUESTS.md` "SBC deployment (Path 2)" section migrating the doc-body backlog (#25)

### Changed

- `examples/preflight.py` → `tools/preflight.py`. Reclassifies preflight as a hardware-diagnostic tool rather than a usage example, matching the AGENTS.md `tools/` convention. All references in README / docs / sibling tools updated.
- `examples/showcase_v0_pipette_sim.py` replaces `showcase_v0.py` as the canonical hardware demo — raw-serial read-until-`ok`, plunger simulated via gantry Z, G-code tee to disk (#23)
- `tools/preflight.py` rewritten — auto-discovers ports, 3 s boot wait, dPette stub-mode detection, configurable standby retry (#23)
- README example commands use `uv run` (#16)
- `docs/hardware.md` documents CH340 + CP2102N USB-bridge variants and `M115` tiebreaker; corrects stock baud to 250000 (#25)
- `.claude/rules/core-principles.md` refined for project use — AHA principle, Communication section, pre-task clarity check (#24)
- `.gitignore` excludes per-session agent state and sandbox-bind-mounted dotfiles (#19, #24)
- README, CONTRIBUTING.md, docs/calibration.md copy-paste blocks no longer break stock zsh (#25)

### Fixed

- Marlin USB probe (`tools/preflight.py`) and the v0 hardware showcase (`examples/showcase_v0_pipette_sim.py`) now open 250000 baud via Linux `TCSETS2 + BOTHER` ioctl on any Linux Python build that omits `termios.B250000`. Previously both crashed with `termios.error: (22, 'Invalid argument')`. The shared `pipettebot.gantry.open_marlin_port` helper is gated on `sys.platform == "linux"` and is harmless on builds that do expose the constant.
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
