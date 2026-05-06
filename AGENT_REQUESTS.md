# Agent Requests / Backlog

Deferred-but-remembered work. Anything we explicitly chose **not** to do in
v0 ends up here so it doesn't get forgotten. Promote items to issues / PRs
when they're ready to start.

## Liquid handling

- [ ] 8-channel dPette support — same driver, expose `multichannel.COLUMN_PITCH_MM = 9.0`
- [ ] Tip pickup / eject — dpette `eject_tip()` is `NotImplementedError`; needs GPIO solenoid or M280 servo
- [ ] Multi-pipette parallel control (multiple physical dPettes on independent USB ports)
- [ ] Aspirate / dispense speed control surfaced through `PipetteBot` API
- [ ] Mixing, splitting, dilution helpers — delegate to dpette `WorkingMode` modes

## Deck and motion

- [ ] Deck geometry library — `deck.py` with `WellPlate96`, `TipRack`, named slots
- [ ] Origin probe / calibration routine — one-shot, persisted to JSON
- [ ] Soft-limit + crash-guard — `safety.py` with `MIN_TRAVEL_Z`, `DISPENSE_Z_OFFSET`
- [ ] Trajectory blending / look-ahead optimization

## Firmware (deferred from v0)

- [ ] **Stage 1**: Marlin `Configuration.h` patch — disable thermal runaway on E0, raise `Z_MAX_POS`, add `M280` for tip-eject servo
- [ ] **Stage 2a**: Pass-through M-code (`M820`) — single-USB-cable mode (UART tap, level-shifter required)
- [ ] **Stage 2b**: Embedded dPette state machine in Marlin — headless SD-card runs
- [ ] **Stage 2c**: Motion-planner-synchronous pipetting — sub-50 ms sync (probably never needed for liquid handling)

## Hardware

- [ ] Pipette mount STL + BOM — depends on physical i3-Mega X-carriage measurement
- [ ] Level-shifter PCB (5 V ↔ 3.3 V) — for Stage 2 UART tap

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

- [ ] Hardware photo set (mount + plate + tips + dPette)
- [ ] Demo video / GIF (live, replacing the `.github/assets/showcase.gif` placeholder)
- [ ] ADR: why PC-as-host instead of Stage 2 firmware integration
- [ ] Social-preview PNG (1280×640) — manually upload via repo Settings → Social preview

## Open assumptions to revisit

- v0 supports a **single dPette only**, hardcoded coordinates, no calibration
- `dpette` consumed as **git dep** pinned to commit SHA (not vendored)
- Repo is **public** on GitHub
- `.claude/settings.json` has **no hooks** in v0
