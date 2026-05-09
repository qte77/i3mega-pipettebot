"""Hardware-motion simulation of the v0 pipetting cycle — gantry-only, no dPette.

Drives the i3 Mega through 2 cycles of:

1. Board sweeps to the **back** well (Y=180 mm).
2. Head descends to Z=5 mm.
3. Head strokes 5 cm UP and back DOWN — simulates the dPette plunger
   action using the Z axis since no real pipette is wired in.
4. Head lifts to travel Z (40 mm).
5. Board sweeps to the **front** well (Y=20 mm).
6. Same descend / stroke / lift.

This is the canonical v0 hardware demo. It runs real motion against
the printer but does **not** require the dPette to be plugged in —
useful for proving the gantry, axis range, and cabling work end-to-end
before introducing the pipette.

Talks raw serial (instead of `pipettebot.GcodeGantry`) and reads
until `ok` so commands are properly sequenced — sidesteps the
`GcodeGantry._send` "one-line readline" bug (issue #26).

Required environment variable:

    I3MEGA_PORT   Marlin USB-serial path. Run `examples/preflight.py`
                  first to discover it.

Optional:

    I3MEGA_BAUD     Default 250000 (Anycubic stock + MARLIN-AI3M).
    OUTPUT_GCODE    Path to also tee the G-code stream to disk.
                    Default: `showcase_v0_pipette_sim.gcode` in the cwd.
                    Set to empty (`OUTPUT_GCODE=`) to disable.

The G-code file mirrors what's sent to Marlin, with `[host]` log lines
captured as `;` comments. It can be replayed from SD or fed to another
host without re-running this script. Note: this file does **not**
contain pipette commands (no `M820` etc. exist in stock Marlin); the
plunger strokes are pure gantry Z motion that you'll see in the file
as additional `G1 Z...` lines.

**Safety**: the printer homes and descends to Z=5 mm at (X=105, Y=180)
and (X=105, Y=20). Bed must be clear of objects at those XY locations
or the gantry will collide. v0 has no software soft-limit enforcement
(see `.claude/rules/motion-safety.md`).

**Side effect**: this script raises Marlin's Z max feedrate (`M203 Z20`)
and Z acceleration (`M201 Z200`) for snappier strokes. These changes
last until power-cycle unless saved with `M500`. Originals on this
hardware were `Z6` / `Z60` per AI3M defaults.
"""

from __future__ import annotations

import os
import sys
import time
from typing import TYPE_CHECKING

from pipettebot.gantry import open_marlin_port

if TYPE_CHECKING:
    from typing import TextIO

    import serial  # type: ignore[import-untyped]

DEFAULT_BAUD = 250000
DEFAULT_GCODE_OUT = "showcase_v0_pipette_sim.gcode"

# Geometry (i3 Mega bed: 210 x 210 mm)
CENTER_X = 105.0
BACK_WELL_Y = 180.0
FRONT_WELL_Y = 20.0
WELL_Z = 5.0
TRAVEL_Z = 40.0
STROKE_PEAK_Z = WELL_Z + 50.0  # 5 cm above well — simulated plunger up
NUM_CYCLES = 2

# Feedrates (under M203 X500 Y500 / Z20 caps after the M203 bump below)
XY_FEED = 6000  # 100 mm/s
Z_FEED = 1200  # 20 mm/s — needs M203 Z20 sent first


def gsend(
    link: serial.Serial,
    cmd: str,
    *,
    gcode_out: TextIO | None = None,
    max_secs: float = 180.0,
) -> None:
    """Send `cmd` to Marlin and (optionally) tee it into `gcode_out`.

    Tolerates intermediate `echo:busy: processing` lines (long G28 / M400)
    and the SD-init chatter Marlin emits when the card is unreadable.
    Raises on hard protocol/motion errors.
    """
    print(f"  >>> {cmd}")
    if gcode_out is not None:
        gcode_out.write(cmd + "\n")
    link.write((cmd + "\n").encode("ascii"))
    deadline = time.time() + max_secs
    while time.time() < deadline:
        raw = link.readline()
        if not raw:
            continue
        s = raw.decode("ascii", errors="replace").rstrip()
        if not s:
            continue
        if s == "ok" or s.startswith("ok "):
            return
        if "volume.init" in s or "SD init" in s:
            continue  # benign — card unreadable, motion unaffected
        if s.startswith(("Resend:", "!! ", "Error:Printer halted", "Error:Thermal")):
            raise RuntimeError(f"Marlin error: {s} (after `{cmd}`)")
    raise TimeoutError(f"no `ok` after {max_secs}s for `{cmd}`")


def visit_well(
    link: serial.Serial,
    x: float,
    y: float,
    label: str,
    *,
    gcode_out: TextIO | None = None,
) -> None:
    """Travel above well at safe Z, descend, plunger stroke, lift."""
    print(f"[host] === {label} at (X={x}, Y={y}) ===")
    if gcode_out is not None:
        gcode_out.write(f"\n; ===== {label} at (X={x}, Y={y}) =====\n")
    gsend(link, f"G1 X{x:.3f} Y{y:.3f} Z{TRAVEL_Z:.3f} F{XY_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 X{x:.3f} Y{y:.3f} Z{WELL_Z:.3f} F{XY_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    if gcode_out is not None:
        gcode_out.write(f"; plunger stroke 5 cm up/down at {Z_FEED // 60} mm/s\n")
    gsend(link, f"G1 Z{STROKE_PEAK_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, f"G1 Z{WELL_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{TRAVEL_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)


def _gcode_header() -> str:
    return (
        "; showcase_v0_pipette_sim.gcode\n"
        "; generated by examples/showcase_v0_pipette_sim.py\n"
        "; tested against Anycubic i3 Mega + MARLIN-AI3M v1.4.6\n"
        "; pipette plunger is simulated via gantry Z motion (no M820)\n"
    )


def _run(link: serial.Serial, gcode_out: TextIO | None) -> None:
    """The full motion sequence — single entry point for both hardware and tee paths."""
    if gcode_out is not None:
        gcode_out.write(_gcode_header())
        gcode_out.write("; raise Z max feedrate + accel for snappy strokes\n")
    gsend(link, "M203 Z20", gcode_out=gcode_out)
    gsend(link, "M201 Z200", gcode_out=gcode_out)

    if gcode_out is not None:
        gcode_out.write("\n; ===== initial home =====\n")
    gsend(link, "G28", gcode_out=gcode_out, max_secs=120)
    gsend(link, "M400", gcode_out=gcode_out)

    for n in range(1, NUM_CYCLES + 1):
        print(f"\n[host] ====== CYCLE {n}/{NUM_CYCLES} ======")
        if gcode_out is not None:
            gcode_out.write(f"\n; ====== CYCLE {n}/{NUM_CYCLES} ======\n")
        visit_well(
            link,
            CENTER_X,
            BACK_WELL_Y,
            f"ASPIRATE @ BACK well [cycle {n}]",
            gcode_out=gcode_out,
        )
        visit_well(
            link,
            CENTER_X,
            FRONT_WELL_Y,
            f"DISPENSE @ FRONT well [cycle {n}]",
            gcode_out=gcode_out,
        )

    if gcode_out is not None:
        gcode_out.write("\n; ===== final home =====\n")
    gsend(link, "G28", gcode_out=gcode_out, max_secs=120)
    gsend(link, "M400", gcode_out=gcode_out)


def main() -> int:
    port = os.environ.get("I3MEGA_PORT")
    if not port:
        sys.stderr.write(
            "ERROR: set I3MEGA_PORT to your printer's serial port.\n"
            "       Run `uv run examples/preflight.py` to discover it.\n"
        )
        return 1
    baud = int(os.environ.get("I3MEGA_BAUD", str(DEFAULT_BAUD)))
    gcode_path = os.environ.get("OUTPUT_GCODE", DEFAULT_GCODE_OUT)

    link = open_marlin_port(port, baudrate=baud, timeout=2.0)
    if link is None:
        sys.stderr.write(
            f"ERROR: could not open {port} @ {baud} baud.\n"
            "       Run `uv run examples/preflight.py` to verify the port.\n"
        )
        return 1
    with link:
        print(f"[host] open {port} @ {baud}; waiting 3s for Marlin boot")
        time.sleep(3)
        link.reset_input_buffer()
        if gcode_path:
            print(f"[host] tee G-code stream to {gcode_path}")
            with open(gcode_path, "w") as gf:
                _run(link, gf)
        else:
            _run(link, None)
        print("[host] done — gantry at home, board at home position")
    return 0


if __name__ == "__main__":
    sys.exit(main())
