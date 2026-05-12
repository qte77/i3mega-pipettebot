"""Full plate fill — i3 Mega gantry + REAL dPette aspirate/dispense.

================================================================================
PRECONDITION — READ BEFORE RUNNING:
================================================================================

  TIPS MUST BE REMOVED from the dPette before this script starts.

  Phase 1 issues `G28 X Y Z` (explicit axes — plain `G28` on the
  AI3M Marlin variant has been observed to skip Z), which homes Z to
  its calibrated zero. Per docs/calibration.md, Z=0 = tip-end-on-deck
  WITH tips loaded — so running with tips still mounted drives the tip
  into the deck. Destructive.

  The dPette must also be:
    - Awake (press its button if standby has dropped the USB chip).
    - On `PIPETTE_PORT` (CP2102 USB-UART, default 9600 baud).
    - Loaded — by phase 3 onward — with the same 49.5 mm disposable
      tips as the tip box. Phase 2 picks them up before any aspirate.

================================================================================

Same gantry tour as `showcase_v0_full_plate.py`, with two changes:

  - phase 3 calls `pipette.aspirate()` / `pipette.dispense()` instead
    of simulating the plunger with a bare Z dive. The pipette fires at
    the bottom of each dive AFTER `M400` flushes the planner (per
    `.claude/rules/motion-safety.md` — tip stationary before pipetting).
  - bootstrap opens a second serial port for the dPette and runs the
    PI-mode handshake (B0 WOL → motor homes), then sets PI volume ONCE
    via B2. Each cycle reuses that volume; no per-cycle B2 packet.

Phases::

    1. bootstrap     — M203/M201 bump, M211 S0, G28 X Y Z, lift to TRAVEL_Z.
    2. tip pickup    — 6-step sequence: pre-Z, XY, engage, lift, XY to
                       reservoir, descend to TRAVEL_Z.
    3. column tour   — for col in 1..NUM_COLUMNS (back→front):
                         travel to reservoir, dive, B3 SUCK, lift
                         travel to SBS col N, dive, B3 BLOW, lift
    4. park          — Z-first to home corner at PARK_Z (no G28).

`_visit_xy_dive` is the single transit helper used by both `visit_reservoir`
and `visit_column` — same Z-first XY-dive pattern, just a different
target (XY, dive Z) and a different `on_dive` callback (aspirate vs
dispense).

Timing (approximate; replaced by real prints after first run):

  - dPette B3 SUCK / BLOW: ~0.4–0.8 s each. Driver's KEY_TIMEOUT_S =
    10 s is the hard ceiling.
  - Gantry per cycle: ~11 s (4× Z descend/lift at 20 mm/s + short XY at
    200 mm/s). Gantry dominates over dPette by ~15×.
  - Full NUM_COLUMNS=11 tour: ~2-3 min wall-clock.

Cycle budget: NUM_COLUMNS × 2 ops = 22 < dPette MAX_CONTIGUOUS_CYCLES=50.

Required environment variables:

    I3MEGA_PORT          Marlin USB-serial path.
    PIPETTE_PORT         dPette USB-serial path. Run `tools/preflight.py`
                         to discover both.

Optional:

    I3MEGA_BAUD          Default 250000 (Anycubic stock + MARLIN-AI3M).
    PIPETTE_BAUD         Default 9600 (DLAB dPette CP2102 stock).
    PIPETTE_VOLUME_UL    Per-channel volume in microlitres. Default 50.0.
    OUTPUT_GCODE         Path to tee Marlin commands to disk. Default
                         `showcase_v0_full_pipettebot.gcode` in cwd.
                         Set to empty (`OUTPUT_GCODE=`) to disable.

The tee'd G-code file contains ONLY Marlin commands. dPette ops are
not G-code — they're logged inline as `;` comments around each dive's
M400 so an SD-replay can sequence pipette firing against the original
gantry timing.

**Safety**: same gantry rules as `showcase_v0_full_plate.py` plus:
WELL_Z == RESERVOIR_Z by design — each SBS well starts empty, so the
dispense Z need not be above any liquid line (first-and-only fill per
well). The B3 BLOW piston return creates suction; submerged dispense
would draw extra liquid, but with empty target wells this is moot.

**Side effect**: raises Marlin's Z max feedrate (M203 Z20) and Z accel
(M201 Z200), disables soft endstops (M211 S0). All last until power
cycle unless saved with M500.
"""

from __future__ import annotations

import os
import sys
import time
from typing import TYPE_CHECKING

from dpette import DPetteDriver, SerialConfig

from pipettebot.gantry import open_marlin_port

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TextIO

    import serial  # type: ignore[import-untyped]

DEFAULT_BAUD = 250000
DEFAULT_PIPETTE_BAUD = 9600
DEFAULT_GCODE_OUT = "showcase_v0_full_pipettebot.gcode"
DEFAULT_VOLUME_UL = 50.0

# --- Deck geometry ------------------------------------------------------
# Canonical source: docs/deck-layout.md "Slot extents" + "Motion constants".
# Any change here must be reflected there (and vice versa).

# Y convention: positive 0–250 mm, Y=0 BACK, Y=250 FRONT. No Y offset.
DECK_OFFSET_X = 25.0  # +X = right (commanded X = deck X + 25)
DECK_OFFSET_Y = 0.0  # Y axis positive (Y=0 back, Y=250 front)

# SBS plate (per user spec): X=50, cycle 1 Y=180, step -10 mm per cycle.
SBS_REF_X = 25.0 + DECK_OFFSET_X  # 50.0 Marlin
SBS_COL1_Y = 180.0 + DECK_OFFSET_Y  # 180.0 Marlin (cycle 1)
SBS_COL_PITCH = -10.0  # -10 mm per cycle

# Reservoir (per user spec): X=155, Y=115.
RESERVOIR_REF_X = 130.0 + DECK_OFFSET_X  # 155.0 Marlin
RESERVOIR_REF_Y = 115.0 + DECK_OFFSET_Y  # 115.0 Marlin

# Tip box (per user spec): X=155, Y=220.
TIP_PICKUP_X = 130.0 + DECK_OFFSET_X  # 155.0 Marlin
TIP_PICKUP_Y = 220.0 + DECK_OFFSET_Y  # 220.0 Marlin

# --- Motion altitudes (deck-plate frame) --------------------------------
# Z-first transit: all XY motion at TRAVEL_Z (above every slot).
# WELL_Z == RESERVOIR_Z — each SBS well starts empty so the dispense
# need not be above any liquid line (preserves WELL_Z >= RESERVOIR_Z
# invariant at the boundary).
TRAVEL_Z = 125.0  # transit altitude — all XY motion happens here
WELL_Z = 75.0  # dive Z into SBS well
RESERVOIR_Z = 75.0  # dive Z into reservoir

# Tip-pickup phase Z sequence (per user spec).
TIP_PICKUP_PRE_Z = 90.0  # Z before XY travel to tip box
TIP_PICKUP_Z = 70.0  # tip engagement Z (body bottom on tip tops)
TIP_PICKUP_LIFT_Z = 140.0  # post-engagement lift; clears tip box + tips

# End-of-tour park altitude: 1.5 × disposable tip length.
PARK_TIP_LENGTH_MM = 49.5
PARK_TIP_CLEARANCE_FACTOR = 1.5
PARK_Z = PARK_TIP_LENGTH_MM * PARK_TIP_CLEARANCE_FACTOR  # 74.25 mm

# --- Feedrates (under M203 X500 Y500 / Z20 caps after the bump below) ---
XY_FEED = 12000  # 200 mm/s — well under the X500/Y500 mm/s cap
Z_FEED = 1200  # 20 mm/s — at the M203 Z20 cap (leadscrew mechanical limit)

NUM_COLUMNS = 11


def gsend(
    link: serial.Serial,
    cmd: str,
    *,
    gcode_out: TextIO | None = None,
    max_secs: float = 180.0,
) -> None:
    """Send `cmd` to Marlin and (optionally) tee it into `gcode_out`.

    Tolerates `echo:busy: processing` chatter on long G28/M400 and the
    SD-init noise Marlin emits when the card is unreadable. Raises on
    hard protocol/motion errors.
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
            continue
        if s.startswith(("Resend:", "!! ", "Error:Printer halted", "Error:Thermal")):
            raise RuntimeError(f"Marlin error: {s} (after `{cmd}`)")
    raise TimeoutError(f"no `ok` after {max_secs}s for `{cmd}`")


def _visit_xy_dive(
    link: serial.Serial,
    x: float,
    y: float,
    dive_z: float,
    label: str,
    *,
    on_dive: Callable[[], object] | None = None,
    gcode_out: TextIO | None = None,
) -> float:
    """Z-first visit: lift → XY at TRAVEL_Z → dive → on_dive → lift.

    If `on_dive` is set, it fires AFTER the dive's M400 and BEFORE the
    lift — the planner is flushed and the tip is stationary at dive Z,
    satisfying motion-safety.md "wait for moves before pipetting".

    Returns wall-clock seconds spent in `on_dive` (0.0 if absent).
    """
    print(f"[host] --- {label} ---")
    if gcode_out is not None:
        gcode_out.write(f"\n; --- {label} ---\n")
    # 1. Z first — lift to TRAVEL_Z before any XY motion
    gsend(link, f"G1 Z{TRAVEL_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    # 2. XY only, at TRAVEL_Z (above every slot)
    gsend(link, f"G1 X{x:.3f} Y{y:.3f} F{XY_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    # 3. Dive
    gsend(link, f"G1 Z{dive_z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    # 4. Optional pipette op at the bottom of the dive
    op_dt = 0.0
    if on_dive is not None:
        if gcode_out is not None:
            gcode_out.write(f"; >>> dpette op @ Z{dive_z:.1f}\n")
        t0 = time.perf_counter()
        on_dive()
        op_dt = time.perf_counter() - t0
        print(f"[host]   dpette op: {op_dt:.2f} s")
        if gcode_out is not None:
            gcode_out.write(f"; <<< returned in {op_dt:.2f} s\n")
    # 5. Lift back to TRAVEL_Z (ready for next transit)
    gsend(link, f"G1 Z{TRAVEL_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    return op_dt


def visit_reservoir(
    link: serial.Serial,
    pipette: DPetteDriver,
    *,
    gcode_out: TextIO | None = None,
) -> float:
    """Z-first aspirate visit at the reservoir. Returns dPette wall-clock s."""
    return _visit_xy_dive(
        link,
        RESERVOIR_REF_X,
        RESERVOIR_REF_Y,
        RESERVOIR_Z,
        "reservoir aspirate (B3 SUCK)",
        on_dive=pipette.aspirate,
        gcode_out=gcode_out,
    )


def visit_column(
    link: serial.Serial,
    pipette: DPetteDriver,
    col: int,
    *,
    gcode_out: TextIO | None = None,
) -> float:
    """Z-first dispense visit at SBS column `col`. Returns dPette wall-clock s.

    Per user spec: col 1 at Marlin Y=180, step -10 mm per cycle.
    Invariant: WELL_Z >= RESERVOIR_Z (boundary case — equal). Each well
    starts empty so dispense at aspirate Z is safe.
    """
    y = SBS_COL1_Y + (col - 1) * SBS_COL_PITCH
    return _visit_xy_dive(
        link,
        SBS_REF_X,
        y,
        WELL_Z,
        f"SBS column {col} dispense (B3 BLOW) at Y={y:.2f}",
        on_dive=pipette.dispense,
        gcode_out=gcode_out,
    )


def pickup_tips(
    link: serial.Serial,
    *,
    gcode_out: TextIO | None = None,
) -> None:
    """One-time tip pickup at the back-right tip box.

    Six-step sequence per user spec:
      1. Z → TIP_PICKUP_PRE_Z (90 — defensive pre-XY altitude)
      2. XY → (TIP_PICKUP_X, TIP_PICKUP_Y) at current Z
      3. Z → TIP_PICKUP_Z (70 — engage tips, friction-fit)
      4. Z → TIP_PICKUP_LIFT_Z (140 — lift with tips loaded)
      5. XY → (RESERVOIR_REF_X, RESERVOIR_REF_Y) at current Z
      6. Z → TRAVEL_Z (125 — hand off to cycle 1's Z-first transit)
    """
    print("[host] --- tip pickup (gantry-only, once) ---")
    if gcode_out is not None:
        gcode_out.write("\n; --- tip pickup (gantry-only, once) ---\n")
    gsend(link, f"G1 Z{TIP_PICKUP_PRE_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(
        link,
        f"G1 X{TIP_PICKUP_X:.3f} Y{TIP_PICKUP_Y:.3f} F{XY_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{TIP_PICKUP_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{TIP_PICKUP_LIFT_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(
        link,
        f"G1 X{RESERVOIR_REF_X:.3f} Y{RESERVOIR_REF_Y:.3f} F{XY_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{TRAVEL_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)


def _gcode_header(volume_ul: float) -> str:
    return (
        "; showcase_v0_full_pipettebot.gcode\n"
        "; generated by examples/showcase_v0_full_pipettebot.py\n"
        f"; full plate fill: {NUM_COLUMNS} SBS cols x 8 channels, REAL dPette\n"
        f"; per-channel volume: {volume_ul:.1f} uL (B2 PI_VOLUM set once)\n"
        "; deck layout: docs/deck-layout.md\n"
        "; dPette ops logged inline as `; >>>` / `; <<<` comments\n"
    )


def _phase_comment(gcode_out: TextIO | None, text: str) -> None:
    if gcode_out is not None:
        gcode_out.write(text)


def _run(
    link: serial.Serial,
    pipette: DPetteDriver,
    volume_ul: float,
    gcode_out: TextIO | None,
) -> None:
    """Full tour: bootstrap → tip pickup → NUM_COLUMNS× (aspirate + dispense) → park.

    !!! PRECONDITION !!!
    TIPS MUST BE REMOVED from the dPette before this runs (G28 Z drives
    any mounted tip into the deck; Z=0 = tip-end-on-deck per
    docs/calibration.md).
    """
    _phase_comment(
        gcode_out,
        _gcode_header(volume_ul)
        + "; raise Z max feedrate + accel for snappy moves\n"
        + "; disable software endstops defensively (Y axis positive 0-250)\n",
    )
    gsend(link, "M203 Z20", gcode_out=gcode_out)
    gsend(link, "M201 Z200", gcode_out=gcode_out)
    gsend(link, "M211 S0", gcode_out=gcode_out)

    _phase_comment(
        gcode_out,
        "\n; ===== phase 1: bootstrap (G28 X Y Z + Z raise) =====\n"
        "; PRECONDITION: tips MUST BE REMOVED before G28 fires.\n"
        "; G28 X Y Z (explicit axes) — plain G28 skips Z on AI3M Marlin.\n",
    )
    gsend(link, "G28 X Y Z", gcode_out=gcode_out, max_secs=120)
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{TRAVEL_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)

    _phase_comment(gcode_out, "\n; ===== phase 2: tip pickup (once) =====\n")
    pickup_tips(link, gcode_out=gcode_out)

    _phase_comment(
        gcode_out,
        f"\n; ===== phase 3: column tour ({NUM_COLUMNS} cycles) =====\n"
        f"; volume per cycle: {volume_ul:.1f} uL per channel (8 channels)\n"
        f"; total dispensed: {volume_ul * 8 * NUM_COLUMNS:.0f} uL across "
        f"{NUM_COLUMNS * 8} wells\n",
    )
    tour_start = time.perf_counter()
    suck_total = 0.0
    blow_total = 0.0
    for col in range(1, NUM_COLUMNS + 1):
        cycle_start = time.perf_counter()
        print(f"\n[host] ====== COLUMN {col}/{NUM_COLUMNS} ======")
        _phase_comment(gcode_out, f"\n; ====== COLUMN {col}/{NUM_COLUMNS} ======\n")
        suck_total += visit_reservoir(link, pipette, gcode_out=gcode_out)
        blow_total += visit_column(link, pipette, col, gcode_out=gcode_out)
        cycle_dt = time.perf_counter() - cycle_start
        print(f"[host] column {col} cycle: {cycle_dt:.2f} s wall-clock")
        _phase_comment(gcode_out, f"; column {col} cycle: {cycle_dt:.2f} s\n")
    tour_dt = time.perf_counter() - tour_start
    dpette_total = suck_total + blow_total
    print(
        f"\n[host] phase 3 done: {tour_dt:.1f} s total"
        f" ({dpette_total:.1f} s dPette / {tour_dt - dpette_total:.1f} s gantry)"
    )
    _phase_comment(
        gcode_out,
        f"; phase 3 total: {tour_dt:.1f} s "
        f"({dpette_total:.1f} s dPette / {tour_dt - dpette_total:.1f} s gantry)\n",
    )

    _phase_comment(
        gcode_out,
        "\n; ===== phase 4: park at home corner (Z-first, no G28) =====\n",
    )
    gsend(link, f"G1 Z{TRAVEL_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 X0.000 Y0.000 F{XY_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{PARK_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)


def main() -> int:
    port = os.environ.get("I3MEGA_PORT")
    pipette_port = os.environ.get("PIPETTE_PORT")
    if not port or not pipette_port:
        sys.stderr.write(
            "ERROR: set both I3MEGA_PORT and PIPETTE_PORT.\n"
            "       Run `uv run tools/preflight.py` to discover both.\n"
        )
        return 1
    baud = int(os.environ.get("I3MEGA_BAUD", str(DEFAULT_BAUD)))
    pipette_baud = int(os.environ.get("PIPETTE_BAUD", str(DEFAULT_PIPETTE_BAUD)))
    volume_ul = float(os.environ.get("PIPETTE_VOLUME_UL", str(DEFAULT_VOLUME_UL)))
    gcode_path = os.environ.get("OUTPUT_GCODE", DEFAULT_GCODE_OUT)

    link = open_marlin_port(port, baudrate=baud, timeout=2.0)
    if link is None:
        sys.stderr.write(
            f"ERROR: could not open Marlin port {port} @ {baud}.\n"
            "       Run `uv run tools/preflight.py` to verify.\n"
        )
        return 1

    print(f"[host] connecting dPette on {pipette_port} @ {pipette_baud}")
    pipette = DPetteDriver(SerialConfig(port=pipette_port, baudrate=pipette_baud))
    pipette.connect()  # A0 HELLO → B0 WOL (PI mode) → motor homes
    if pipette.stub_mode:
        sys.stderr.write(
            f"ERROR: dPette on {pipette_port} fell back to stub mode.\n"
            "       Wake it (press its button), replug, and retry.\n"
        )
        link.close()
        return 1
    pipette.set_volume(volume_ul)  # B2 PI_VOLUM once; reused for all 22 ops
    print(f"[host] dPette ready: PI mode, volume={volume_ul:.1f} uL per channel")

    try:
        with link:
            print(f"[host] open {port} @ {baud}; waiting 3s for Marlin boot")
            time.sleep(3)
            link.reset_input_buffer()
            if gcode_path:
                print(f"[host] tee G-code stream to {gcode_path}")
                with open(gcode_path, "w") as gf:
                    _run(link, pipette, volume_ul, gf)
            else:
                _run(link, pipette, volume_ul, None)
            print("[host] done — parked at home corner, Z at PARK_Z")
    finally:
        pipette.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
