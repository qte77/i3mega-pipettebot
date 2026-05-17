---
title: "User personas, workflows, and scope"
status: "DRAFT"
updated: "2026-05-17"
---

User personas and the workflows they need to succeed. This file informs
scope decisions and acceptance criteria; it does not replace [open
issues](https://github.com/qte77/i3mega-pipettebot/issues) (the source
of truth for specific actionable work).

## Personas

### 1. Resource-constrained researcher

**Profile.** PhD student, postdoc, or PI in a wet lab with a tight
budget. Repetitive pipetting (gradient prep, plate fills, dilutions,
master-mix distribution) eats hours but doesn't justify an Opentrons
OT-2 ($15,950+) or a Hamilton/Beckman robot ($30k+). Comfortable with
Python; not with custom firmware.

**Has.** An Anycubic i3 Mega (or willing to buy one used for ~$200),
basic lab supplies (96-well plates, disposable tips, reservoirs), a
DLAB dPette electronic pipette.

**Wants.**

- Reproducible aspirate/dispense across a 96-well plate.
- Programmable per-cycle volume (calibration curves, gradients).
- Disposable tips — no carryover between samples.
- A Python control surface; the protocol is just a script.

**Acceptance criteria.**

- `make setup_dev` runs to green on Linux/macOS without root.
- `uv run tools/preflight.py` discovers both i3 Mega and dPette ports.
- `examples/showcase_v0_full_pipettebot.py` runs end-to-end on hardware.
- A TOML profile in `examples/profiles/` drives cycle count + per-cycle
  volumes; `PIPETTE_PROFILE=<file>` is the only env var that needs to
  change to vary a run.

### 2. Maker / educator

**Profile.** Workshop instructor, biohacker, undergraduate course
running a "DIY lab automation" module. Wants a reproducible build that
can be replicated cheaply by every student.

**Has.** Time, a 3D printer (the i3 Mega itself or a second printer),
willingness to print custom mounts.

**Wants.**

- Step-by-step build guide from hardware to first plate fill.
- Printable parts that work on a **stock** i3 Mega (no firmware
  changes, no carriage rewiring beyond removing the hot end).
- Sane safety story: no risk of bricking the printer or driving the
  nozzle into the bed.

**Acceptance criteria.**

- [`docs/hardware.md`](hardware.md) covers cabling, port discovery
  (CH340 vs CP2102), and the Marlin firmware probe.
- [`docs/calibration.md`](calibration.md) walks through the well-A1
  origin procedure and the 9 mm pitch check.
- [`docs/3d-parts.md`](3d-parts.md) documents the CAD pipeline, payload
  budget (`< 300 g`), and slicer printability gate.
- `tools/cad/` parts pass `make check_prints` without overhang/bridge
  warnings.
- The v0 path uses stock Marlin only.

### 3. Open-source contributor

**Profile.** Developer wanting to extend the project — new pipette
models, deck calibration, firmware integration, alternate gantries.
Cares about clean architecture, test coverage, and well-defined
extension points.

**Has.** Git, Python ≥3.11, a working dev environment.

**Wants.**

- Clear separation: gantry layer (G-code) vs pipette layer (6-byte
  serial) vs orchestrator (`PipetteBot`).
- Mocked-serial test fixtures so CI doesn't need hardware.
- Defined places to add modules: the four-module library convention
  (`gantry`, `bot`, `profiles`, `__init__`) plus `examples/` for
  hardware demos and `tools/` for diagnostics.
- Decision-record discipline for architectural changes.

**Acceptance criteria.**

- `make validate` (ruff format/check, mypy strict, pytest mocked) is
  green on every PR.
- [`AGENTS.md`](../AGENTS.md) documents agent rules and the decision
  framework.
- [`docs/adr/`](adr/) captures architectural decisions; new ADRs
  follow `NNNN-<slug>.md`.
- New ops on `src/pipettebot/bot.py::PipetteBot` ship with matching
  cases in `tests/test_bot.py` using `FakeSerial` / `FakePipette`.
- [`AGENT_REQUESTS.md`](../AGENT_REQUESTS.md) is for short-term
  agent-to-human hand-offs only; actionable work lives in GitHub issues.

## Workflows

The end-to-end paths the project must support:

| Workflow | Driver | Doc |
|---|---|---|
| Bring-up — connect both devices, mocked tests pass | [README Quickstart](../README.md#quickstart) | — |
| Hardware probe — Marlin + dPette firmware detected | `tools/preflight.py` | [docs/hardware.md](hardware.md) |
| Well-A1 calibration — measure deck zero, set constants | `tools/marlin_repl.py` | [docs/calibration.md](calibration.md) |
| First plate fill | `examples/showcase_v0_full_pipettebot.py` | [docs/deck-layout.md](deck-layout.md) |
| Custom protocol — TOML profile, vary cycles + volumes | `PIPETTE_PROFILE=…` | [examples/profiles/](../examples/profiles/) |
| Print a custom part | `make render_all` | [docs/3d-parts.md](3d-parts.md) |
| Deploy on a Single-Board Computer | `tools/setup_pi.sh` | [docs/sbc-deployment.md](sbc-deployment.md) |

## Out of scope (v0)

- **Deck calibration library** — the caller passes raw `(x, y, z)`.
- **Software soft-limit enforcement** — coordinates are untrusted; the
  i3 Mega will happily drive the nozzle into the bed if asked.
- **Firmware modifications** — stock Marlin only. Stage 1+ firmware
  work is tracked in [open issues](https://github.com/qte77/i3mega-pipettebot/issues)
  and must not be merged to `main` without an ADR.
- **Multi-deck / multi-plate workflows** — single deck per session.
- **GUI** — Python API only.

These bounds protect v0's "ships in a weekend" property. Removing any
of them is an architectural decision and needs an ADR.
