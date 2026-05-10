# Agent Requests / Backlog

Deferred-but-remembered work. Items below are tracked as **GitHub issues**
once they're ready to action; this file holds the strategic *why* and
points at the issue numbers. Edit-and-commit lifecycle.

> Each unchecked item becomes a GitHub issue under the `v0.1.0` milestone
> after the v0.0.1 tag. Once an issue exists, append `(#N)` to the entry.

## Liquid handling

- [ ] 8-channel dPette support — same driver, expose `multichannel.COLUMN_PITCH_MM = 9.0`
- [ ] Tip pickup / eject — dpette `eject_tip()` is `NotImplementedError`; needs GPIO solenoid or M280 servo (depends on Stage 1 firmware patch)
- [ ] Multi-pipette parallel control (multiple physical dPettes on independent USB ports)
- [ ] Aspirate / dispense speed control surfaced through `PipetteBot` API
- [ ] Mixing, splitting, dilution helpers — delegate to dpette `WorkingMode` modes

## Deck and motion

- [ ] Deck geometry library — `deck.py` with `WellPlate96`, `TipRack`, named slots; replaces hardcoded `BACK_WELL_Y`/`FRONT_WELL_Y` in `examples/showcase_v0_pipette_sim.py` (#10) — **blocked on a real use case**: no caller iterates over wells today, so the API would be Opentrons-mimicry without a concrete protocol. Unblock when someone writes a multi-well protocol the constants can't express.
- [ ] Origin probe / calibration routine — one-shot, persisted to JSON; today users edit constants per [`docs/calibration.md`](docs/calibration.md)
- [ ] Soft-limit + crash-guard — `safety.py` with `MIN_TRAVEL_Z`, `DISPENSE_Z_OFFSET`
- [ ] Trajectory blending / look-ahead optimization

## Firmware (deferred from v0)

- [ ] **Stage 1**: Marlin `Configuration.h` patch — disable thermal runaway on E0, raise `Z_MAX_POS`, add `M280` for tip-eject servo
- [ ] **Stage 2a**: Pass-through M-code (`M820`) — single-USB-cable mode (UART tap, level-shifter required)
- [ ] **Stage 2b**: Embedded dPette state machine in Marlin — headless SD-card runs
- [ ] **Stage 2c**: Motion-planner-synchronous pipetting — sub-50 ms sync (probably never needed for liquid handling)

## Hardware

- [ ] Pipette mount STL + BOM — tracked as #40 (carriage measurement), #41 (barrel-bore module), #42 (payload tests), #43 (vendor scan)
- [ ] Level-shifter PCB (5 V ↔ 3.3 V) — for Stage 2 UART tap

## 3D parts pipeline (`tools/cad/`)

Open work moved to GitHub issues for visibility — see also
[`docs/3d-parts.md`](docs/3d-parts.md):

- [#40](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/40) — Measure AI3M carriage screw pattern (blocks real mount geometry)
- [#41](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/41) — Extract barrel-bore primitives into reusable module
- [#42](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/42) — Hypothesis tests for mount payload budget
- [#43](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/43) — Vendor real dPette barrel scan from so101
- [#44](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/44) — Confirm OrcaSlicer install method
- [#45](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/45) — ADR: Arduino host architecture (PC-host → MCU-host)

## SBC deployment (Path 2)

Concrete follow-ups so [`docs/sbc-deployment.md`](docs/sbc-deployment.md)
can graduate from DRAFT:

- [ ] First physical Pi-on-Mega build, photographed, BOM line items confirmed
- [ ] 3D-printed mount STL committed under `hardware/sbc-mount.stl`
- [ ] Power-piggyback test: 24 V → 5 V buck regulator off the i3 Mega PSU; confirm clean enumeration of both USB-UART chips
- [ ] CI matrix entry: `make test` on `linux/arm64` (Pi Zero 2 W is `aarch64`) so we catch arm-only regressions before deploy
- [ ] Deferred-features audit — what fails on Pi Zero (RAM-limited) vs Pi 4 (comfortable)

## Tooling / quality

- [ ] Hypothesis property-based tests (mirror qpcr-machine-hacking)
- [ ] Coverage tooling
- [ ] `bump-my-version` + CHANGELOG automation
- [ ] mkdocs site
- [ ] CodeFactor, CodeQL, Dependabot badges

## Skills / automation deferred

- [ ] `embedded-dev:implementing-firmware` for Stage 1+
- [ ] `docs-generator:generating-tech-spec` for ADR on UART-tap decision
- [ ] `cc-meta:orchestrating-parallel-workers` for STL + firmware + multichannel parallel build
- [ ] SessionStart hook to load motion-safety rules automatically

## Documentation

- [x] Hardware setup guide — see [`docs/hardware.md`](docs/hardware.md)
- [x] Calibration procedure — see [`docs/calibration.md`](docs/calibration.md)
- [x] Preflight script — `tools/preflight.py`
- [ ] Hardware photo set (mount + plate + tips + dPette) for `.github/assets/hero.png`
- [ ] Demo video / GIF (live) replacing the `.github/assets/showcase.gif` placeholder
- [ ] ADR: why PC-as-host instead of Stage 2 firmware integration

## Completed in v0.0.1

- [x] v0 module scaffold (`gantry.py`, `bot.py`, `__init__.py`)
- [x] Mocked-serial test suite (9 tests)
- [x] CI on Python 3.11 + 3.12 (uv + ruff + mypy + pytest)
- [x] Apache-2.0 license + NOTICE
- [x] AGENTS.md doc hierarchy mirroring Agents-eval
- [x] dpette dependency pinned to commit SHA

## Open assumptions to revisit

- v0 supports a **single dPette only**, hardcoded coordinates, no calibration library
- `dpette` consumed as **git dep** pinned to commit SHA (not vendored)
- Repo is **public** on GitHub
- `.claude/settings.json` has **no hooks** in v0
