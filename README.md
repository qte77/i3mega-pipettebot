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

> **Status: v0 prototype.** A working aspirate-then-dispense demo over
> hardcoded coordinates. Deck calibration, 8-channel, tip handling, and
> firmware modifications are all on the [backlog](AGENT_REQUESTS.md).

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
make init          # uv sync --extra dev
make test          # mocked-serial tests, no hardware required
```

### Run the v0 demo (requires hardware)

Two separate guides cover the physical/electrical setup and the
well-origin calibration before you run the demo:

- [`docs/hardware.md`](docs/hardware.md) — cabling, port discovery (CH340 vs CP2102), Marlin firmware sanity check
- [`docs/calibration.md`](docs/calibration.md) — finding well A1 with `M114`, the 9 mm pitch check, where to set the constants

After hookup, sanity-check ports + firmware **before any motion**:

```bash
uv run examples/preflight.py     # reads M115 from Marlin and dPette EEPROM; no motion
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
Real pipette I/O is exercised via `examples/preflight.py` and ad-hoc
scripts; full integration through the same showcase awaits the
firmware path in [`AGENT_REQUESTS.md`](AGENT_REQUESTS.md).

Three modules: `gantry.py` (G-code wrapper), `bot.py` (composer),
`__init__.py` (re-exports). No deck library, no safety limits, no
calibration in v0 — the caller passes raw `(x, y, z)`.

## Development

```bash
make validate         # ruff format + lint, mypy strict, pytest mocked
make quick_validate   # lint + mypy only
make lint_fix         # auto-fix formatting and lint
make test             # pytest (hardware tests excluded)
```

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

- [docs/hardware.md](docs/hardware.md) — i3 Mega + dPette wiring, port discovery, firmware sanity check
- [docs/calibration.md](docs/calibration.md) — well-A1 origin procedure, 9 mm pitch check
- [AGENTS.md](AGENTS.md) — agent rules, decision framework, architecture
- [AGENT_LEARNINGS.md](AGENT_LEARNINGS.md) — gotchas as we discover them
- [AGENT_REQUESTS.md](AGENT_REQUESTS.md) — deferred features and questions
- [CONTRIBUTING.md](CONTRIBUTING.md) — dev workflow

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
