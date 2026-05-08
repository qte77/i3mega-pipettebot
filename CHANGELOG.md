# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- `docs/sbc-deployment.md` — Path 2 (SBC-on-printer) deployment guide (#21)
- `.claude/rules/{compound-learning,context-management,core-principles}.md` — repo-local agent governance rules (#20)
- `AGENT_LEARNINGS.md` first entry: sandbox bind-mount untracked-files pattern (#25)
- `AGENT_REQUESTS.md` "SBC deployment (Path 2)" section migrating the doc-body backlog (#25)

### Changed

- `examples/showcase_v0_pipette_sim.py` replaces `showcase_v0.py` as the canonical hardware demo — raw-serial read-until-`ok`, plunger simulated via gantry Z, G-code tee to disk (#23)
- `examples/preflight.py` rewritten — auto-discovers ports, 3 s boot wait, dPette stub-mode detection, configurable standby retry (#23)
- `examples/preflight.py` passes when either i3 Mega **or** dPette is found (was: required both). Reflects v0 usage where the gantry and pipette are exercised independently. Existing `I3MEGA_PORT` / `PIPETTE_PORT` env overrides unchanged.
- README example commands use `uv run` (#16)
- `docs/hardware.md` documents CH340 + CP2102N USB-bridge variants and `M115` tiebreaker; corrects stock baud to 250000 (#25)
- `.claude/rules/core-principles.md` refined for project use — AHA principle, Communication section, pre-task clarity check (#24)
- `.gitignore` excludes per-session agent state and sandbox-bind-mounted dotfiles (#19, #24)
- README, CONTRIBUTING.md, docs/calibration.md copy-paste blocks no longer break stock zsh (#25)

### Fixed

- `examples/preflight.py` Marlin probe now opens 250000 baud via Linux `TCSETS2 + BOTHER` ioctl when Python's `termios` lacks `B250000` (Fedora + 3.13). Previously crashed with `termios.error: (22, 'Invalid argument')`.
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
