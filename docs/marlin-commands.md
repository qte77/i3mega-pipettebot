---
title: "Marlin command reference"
status: "DRAFT"
updated: "2026-05-09"
owner: "lambda biolab"
---

Quick reference for the G/M-codes you actually reach for when bringing up
or debugging an i3 Mega running MARLIN-AI3M v1.4.6 (Marlin 1.1.9 base).
Not exhaustive — see the [Marlin G-code index](https://marlinfw.org/meta/gcode/)
for the full set. The same table is built into
[`tools/marlin_repl.py`](../tools/marlin_repl.py) under the `?` /
`help` command.

## Coordinate orientation (i3 Mega, front view)

| Axis  | Min direction              | Max direction              |
|-------|----------------------------|----------------------------|
| X     | LEFT frame                 | RIGHT frame                |
| Y     | FRONT (bed toward operator)| BACK                       |
| Z     | BED                        | TOP                        |

So `G0 X-1` moves the head **left**; `G0 Y-1` moves the bed **toward you**;
`G0 Z-1` moves the head **down toward the bed**. `G28 X` drives left until
`x_min` triggers — which is exactly the path that hammered when the
carriage tab couldn't reach the switch.

## How to send these

Any of:

- Interactive REPL: `I3MEGA_PORT=/dev/ttyUSB0 uv run python tools/marlin_repl.py`
- Stepped axis motion: `AXIS=X I3MEGA_PORT=/dev/ttyUSB0 uv run python tools/diagnose_axis.py`
- Port discovery + chaining: `eval "$(uv run python tools/preflight.py --export)" && ...`
- A serial terminal that handles 250000 baud (e.g. `tio -b 250000 /dev/ttyUSB0`).

`pyserial` direct opens at 250000 fail on Linux Python builds without
`termios.B250000` — the `pipettebot.gantry.open_marlin_port` helper used by
the tools/ scripts works around that. See [AGENT_LEARNINGS.md](../AGENT_LEARNINGS.md).

## Identification and state

| Command  | Effect                                                              |
|----------|---------------------------------------------------------------------|
| `M115`   | Firmware name + capabilities. Returns `MACHINE_TYPE`, `FIRMWARE_NAME`, `UUID`. Also serves as the preflight tiebreaker. |
| `M114`   | Current XYZE position as Marlin sees it. Useful mid-debug; differs from physical position when steppers slipped or homing failed. |
| `M119`   | Endstop status: `x_min`, `y_min`, `z_min`, `z2_min`. Each reports `open` or `TRIGGERED`. Press a switch by hand and re-send to confirm wiring. |
| `M503`   | Dump EEPROM-backed settings (steps/mm, feedrates, accel, Z offset, …). Grep its output for `M412` to confirm whether the runtime runout-toggle is wired in your build. |

## Halt and recovery

| Command  | Effect                                                              |
|----------|---------------------------------------------------------------------|
| `M999`   | Clear `Error:Printer halted` flag after a `kill()` (e.g. T0 abnormal). The underlying cause re-fires next sample tick — fix the cause first. |
| `M112`   | Emergency stop. Marlin halts and refuses commands until power-cycle. Avoid unless you mean it. |

## Motion

| Command          | Effect                                                       |
|------------------|--------------------------------------------------------------|
| `G90`            | Absolute positioning (default). Coordinates are room-fixed.  |
| `G91`            | Relative positioning. Coordinates are deltas from current.   |
| `G0 X10 F600`    | Move to/by X=10 at 600 mm/min. `G90` vs `G91` decides the meaning. |
| `G1 ... F...`    | Same motion as `G0`. `G1` is for "extruding" moves but moves identically. |
| `M400`           | Block until all queued moves finish. Required between `G0/G1` and any pipette aspirate/dispense. |
| `G92 X0 Y0 Z0`   | Set the current position as origin. No physical motion.      |

## Homing

| Command   | Effect                                                       |
|-----------|--------------------------------------------------------------|
| `G28`     | Home all axes (X → Y → Z). On stock AI3M, Z homing uses the head-mounted inductive probe. |
| `G28 X`   | Home X only. Drives toward the X-min frame microswitch.      |
| `G28 Y`   | Home Y only. Drives toward the Y-min frame microswitch.      |
| `G28 Z`   | Home Z only. **Do not run on a headless gantry** — without the inductive probe, `z_min` never triggers and the gantry drives into the bed. |

## Steppers and power

| Command       | Effect                                                       |
|---------------|--------------------------------------------------------------|
| `M17`         | Energize all steppers. Holds position electrically.          |
| `M18` / `M84` | De-energize all steppers. Frees the gantry for hand-movement. |
| `M84 S30`     | Auto-disable steppers after 30 s idle.                       |

## Sensor and safety overrides

| Command       | Effect                                                       |
|---------------|--------------------------------------------------------------|
| `M302 P1`     | Allow cold extrusion. Bypasses the "below MIN_TEMP" extruder lockout. Irrelevant for headless-gantry use. |
| `M211 S0`     | Disable software endstops. The gantry can move past `*_MAX_POS` / `*_MIN_POS`. Use only for explicit out-of-range tests. |
| `M412 S0`     | Disable filament runout sensor at runtime. **Marlin 2.0+ only — your AI3M v1.4.6 (1.1.9) returns `Unknown command`.** Use the LCD `Configuration → Filament Sensor → Off` toggle instead, or jumper the sensor's signal-to-GND. |

## EEPROM

| Command  | Effect                                                              |
|----------|---------------------------------------------------------------------|
| `M500`   | Save current RAM settings to EEPROM (persists across power-cycle).  |
| `M501`   | Reload EEPROM settings into RAM (undoes unsaved RAM edits).         |
| `M502`   | Reset RAM settings to firmware defaults. Does **not** touch EEPROM until you also send `M500`. |

## Project-specific gotchas

- **`z2_min`** appears in `M119` output even on stock AI3M (single Z motor). It's a Marlin compile-time artifact and reads the same as `z_min` on this hardware — ignore unless you've added a second Z probe.
- **`G28` after head removal** will succeed for X and Y but hang or crash on Z, since the probe is gone with the head. Use `G28 X Y` until you've decided on a Z-endstop strategy (file an [AGENT_REQUESTS.md](../AGENT_REQUESTS.md) item for the firmware track).
- **T0 abnormal at boot** is independent of any of these commands — it triggers in Marlin's safety loop before the USB queue is drained. Hardware fix (100 kΩ across the T0 connector) or firmware patch (`TEMP_SENSOR_0 0`) is the only path.
- **Custom baud (250000)** is the AI3M default. macOS and most Windows Python builds open it directly via `pyserial`; some Linux builds need the `TCSETS2 + BOTHER` ioctl fallback handled by `pipettebot.gantry.open_marlin_port`.
