---
title: "i3mega-pipettebot"
status: "PROTOTYPE"
updated: "2026-05-06"
owner: "lambda biolab"
---

[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![CI](https://github.com/Lambda-Biolab/i3mega-pipettebot/actions/workflows/ci.yml/badge.svg)](https://github.com/Lambda-Biolab/i3mega-pipettebot/actions/workflows/ci.yml)

Turn an **Anycubic i3 Mega** (Marlin / Trigorilla) into a 3-axis pipetting
robot driven by **DLAB dPette** electronic pipettes via the
[`dpette-usb-driver`](https://github.com/Lambda-Biolab/dpette-usb-driver).
The print head and PCB are physically removed from the carriage; the
chassis is repurposed as a 3-axis motion platform with the dPette
mounted on the bare carriage (see [`docs/3d-parts.md`](docs/3d-parts.md)).

> **Status: v0 prototype.** A working aspirate-then-dispense demo over
> hardcoded coordinates. Deck calibration, dPette mount real geometry,
> and firmware modifications are on the [backlog](AGENT_REQUESTS.md)
> and [open issues](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues).

## Why this matters

| Solution                              | Cost      | Tips        | API control |
|---------------------------------------|-----------|-------------|-------------|
| **i3 Mega + dPette + this repo**      | **~$300** | Disposable  | Python      |
| Science Jubilee + OT-2 pipette        | ~$900+    | Disposable  | Python      |
| Opentrons OT-2                        | ~$10,000+ | Disposable  | Python      |

## Quickstart

Requires [`uv`](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

```bash
git clone https://github.com/Lambda-Biolab/i3mega-pipettebot.git
cd i3mega-pipettebot
make init
make test
```

`make init` runs `uv sync --extra dev`; `make test` runs the mocked-serial
test suite (no hardware required).

### Run the v0 demo (requires hardware)

Two separate guides cover the physical/electrical setup and the
well-origin calibration before you run the demo:

- [`docs/hardware.md`](docs/hardware.md) — cabling, port discovery (CH340 vs CP2102), Marlin firmware sanity check
- [`docs/calibration.md`](docs/calibration.md) — finding well A1 with `M114`, the 9 mm pitch check, where to set the constants

After hookup, sanity-check ports + firmware **before any motion**:

```bash
uv run tools/preflight.py
```

This reads `M115` from Marlin and the EEPROM packet from the dPette;
no motion is sent. Preflight passes when **either** device is found —
the gantry and the pipette are exercised independently in v0.

To chain discovery directly into the next command, use `--export`:

```bash
eval "$(uv run python tools/preflight.py --export)" \
  && uv run python examples/showcase_v0_pipette_sim.py
```

Then the demo. v0 ships a single example that drives the gantry
through a back-well-to-front-well pipetting cycle and tees the G-code
stream to disk for replay/SD use; the pipette plunger action is
simulated with a 5 cm Z stroke at each well (no real dPette command
is sent — see `AGENT_REQUESTS.md` Stage 2a for the firmware path that
unlocks real M820 pipette pass-through):

```bash
uv run examples/showcase_v0_pipette_sim.py
```

### Hardware diagnostics (`tools/`)

For headless-gantry bring-up, debugging, and post-removal sanity checks:

| Tool                        | Purpose                                                  |
|-----------------------------|----------------------------------------------------------|
| `tools/preflight.py`        | Port discovery + Marlin/dPette firmware probe.           |
| `tools/diagnose_axis.py`    | Per-axis (`AXIS=X\|Y\|Z`) stepped motion under operator confirmation. Reports `M119` first, never homes. |
| `tools/marlin_repl.py`      | Interactive G-code REPL with built-in command cheat-sheet (`?`). For ad-hoc `M119`, `M999`, `M114`, `M503`, etc. |
| `tools/cad/`                | build123d CAD scripts for printable parts (tip rack, plate holder, dPette cradles, tip ejector). `make render_parts` generates STL+SVG; `make check_prints` slices via OrcaSlicer (or PrusaSlicer fallback). |

See [`docs/marlin-commands.md`](docs/marlin-commands.md) for the full
G/M-code reference and i3 Mega coordinate orientation.

Expected behavior: home → bed sweeps to back well → 5 cm Z plunger
stroke → bed sweeps to front well → another stroke → home.

## Architecture (v0)

```text
examples/showcase_v0_pipette_sim.py
        │
        ▼
raw serial @ 250000 baud  ──► /dev/cu.usbserial-*  (Marlin, G-code)
        │
        └─ tee G-code stream ──► OUTPUT_GCODE file (replay / SD)
```

In v0 the dPette is wired in via `pipettebot.PipetteBot` + a real
`dpette.DPetteDriver`, but the canonical example simulates the
plunger with the gantry Z axis so it runs against the printer alone.
The dPette is exercised in isolation via the `dpette` driver's own
test suite; full integration through the same showcase awaits the
firmware path in [`AGENT_REQUESTS.md`](AGENT_REQUESTS.md).

Three modules: `gantry.py` (G-code wrapper), `bot.py` (composer),
`__init__.py` (re-exports). No deck library, no safety limits, no
calibration in v0 — the caller passes raw `(x, y, z)`.

## Development

| Recipe | What it runs |
|---|---|
| `make validate` | ruff format + lint, mypy strict, pytest mocked |
| `make quick_validate` | lint + mypy only |
| `make lint_fix` | auto-fix formatting and lint |
| `make test` | pytest (hardware tests excluded) |
| `make setup_cad` | install build123d (`uv sync --extra cad`) |
| `make setup_slicer` | probe for OrcaSlicer (preferred) or PrusaSlicer (fallback) |
| `make render_all` | render all parts to `hardware/{stl,svg}/` and slice for printability check |

Hardware tests are gated by `@pytest.mark.hardware`:

```bash
uv run pytest -m hardware
```

## Architecture decision: why PC-as-host (no firmware mods)

Marlin runs unmodified. Pipetting cycles are slow (seconds per move,
seconds per aspirate); USB-serial round-trip latency (~20–50 ms) is
inconsequential. Firmware integration (Stage 1 config patch, Stage 2
UART tap to dPette) is documented in [AGENT_REQUESTS.md](AGENT_REQUESTS.md)
but deliberately **not** part of v0.

## Documentation

- [docs/hardware.md](docs/hardware.md) — i3 Mega + dPette wiring, port discovery, firmware sanity check, dPette+ specs
- [docs/calibration.md](docs/calibration.md) — well-A1 origin procedure, 9 mm pitch check
- [docs/marlin-commands.md](docs/marlin-commands.md) — Marlin G/M-code reference + i3 Mega coordinate orientation
- [docs/3d-parts.md](docs/3d-parts.md) — CAD pipeline design rationale, payload + Z envelope math, SBS labware reference
- [docs/sbc-deployment.md](docs/sbc-deployment.md) — Path 2 (SBC-on-printer) deployment
- [AGENTS.md](AGENTS.md) — agent rules, decision framework, architecture
- [AGENT_LEARNINGS.md](AGENT_LEARNINGS.md) — gotchas as we discover them
- [AGENT_REQUESTS.md](AGENT_REQUESTS.md) — deferred features and questions
- [CONTRIBUTING.md](CONTRIBUTING.md) — dev workflow

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
