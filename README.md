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

Connect:

- `/dev/ttyUSB0` — i3 Mega (Marlin) @ 115200 8N1
- `/dev/ttyUSB1` — dPette (CP2102) @ 9600 8N1

```bash
python examples/showcase_v0.py
```

Expected behavior: home → move over well A1 → aspirate 100 µL → move
over well B1 (9 mm pitch) → dispense → home.

## Architecture (v0)

```text
examples/showcase_v0.py
        │
        ▼
PipetteBot
    ├── GcodeGantry  ──► /dev/ttyUSB0  (Marlin, G-code)
    └── DPetteDriver ──► /dev/ttyUSB1  (dpette-usb-driver)
```

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
pytest -m hardware
```

## Architecture decision: why PC-as-host (no firmware mods)

Marlin runs unmodified. Pipetting cycles are slow (seconds per move,
seconds per aspirate); USB-serial round-trip latency (~20–50 ms) is
inconsequential. Firmware integration (Stage 1 config patch, Stage 2
UART tap to dPette) is documented in [AGENT_REQUESTS.md](AGENT_REQUESTS.md)
but deliberately **not** part of v0.

## Documentation

- [AGENTS.md](AGENTS.md) — agent rules, decision framework, architecture
- [AGENT_LEARNINGS.md](AGENT_LEARNINGS.md) — gotchas as we discover them
- [AGENT_REQUESTS.md](AGENT_REQUESTS.md) — deferred features and questions
- [CONTRIBUTING.md](CONTRIBUTING.md) — dev workflow

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
