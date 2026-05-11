"""Hardware-motion simulation of a full 96-well plate fill — gantry-only, no dPette.

================================================================================
PRECONDITION — READ BEFORE RUNNING:
================================================================================

  TIPS MUST BE REMOVED from the dPette before this script starts.

  Phase 1 issues a full `G28`, which homes Z to its calibrated zero.
  Per docs/calibration.md, Z=0 = tip-end-on-deck WITH tips loaded — so
  if you run this with tips still mounted, the Z homing routine drives
  the tip into the deck. Destructive.

  Workflow:
    1. Remove tips from the dPette manually (or let the prior tour run
       its eject/discard sequence — not yet implemented in v0).
    2. Run this script. Phase 1's `G28` lands Z=0 (safe with no tips),
       then immediately raises to TRAVEL_Z (125 mm).
    3. Tips are picked up from the back-right tip box in phase 2.

================================================================================

8-channel dPette tour: collect tips once from the back-right tip box,
then visit each of the 12 SBS columns (back-to-front) with a round-trip
to the front reservoir before each dispense.

Aspirate and dispense are each a SINGLE descent (no up-and-back plunger
stroke). `WELL_Z >= RESERVOIR_Z` is invariant: the dispense descent
always stops at least as high as the aspirate descent, keeping the tip
above any prior liquid line during dispense.

Phases::

    1. bootstrap     — M203/M201 bump, full G28 (tips MUST be removed
                       first — see PRECONDITION), G1 Z TRAVEL_Z.
    2. tip pickup    — travel to (TIP_PICKUP_X, TIP_PICKUP_Y, TRAVEL_Z),
                       descend to TIP_PICKUP_Z, lift.
    3. column tour   — for col in 1..12 (back→front):
                         travel to reservoir, descend to RESERVOIR_Z, lift
                         travel to SBS col N, descend to WELL_Z, lift
    4. park          — G1 X0 Y0 Z PARK_Z (= 1.5 x tip length).
                       Plain G1, NOT G28: keeps Z above the deck so any
                       forgotten tip on the dPette doesn't drag.

Deck geometry, slot extents, and motion altitudes are defined in
`docs/deck-layout.md` and reproduced here as constants — re-running the
script reproduces the same tour without further calibration.

Talks raw serial to Marlin and reads until `ok` so commands are properly
sequenced — sidesteps the `GcodeGantry._send` one-line-per-ack bug
(issue #26).

Required environment variable:

    I3MEGA_PORT   Marlin USB-serial path. Run `tools/preflight.py` first.

Optional:

    I3MEGA_BAUD   Default 250000 (Anycubic stock + MARLIN-AI3M).
    OUTPUT_GCODE  Path to also tee the G-code stream to disk.
                  Default `showcase_v0_full_plate.gcode` in the cwd.
                  Set to empty (`OUTPUT_GCODE=`) to disable.

**Safety**: the deck holds an SBS plate (back-left, H = 13 mm), tip box
(back-right, H ≥ 59 mm including loaded tips — design minimum), and
reservoir (front, rim H = 24 mm, cavity floor at Z = 19 mm). `TRAVEL_Z
= 125` mm clears the tip box by 66 mm. **Phase 1 runs full `G28` — TIPS
MUST BE REMOVED FIRST** (Z=0 = tip-on-deck per the calibrated zero).
After homing, Z lifts to TRAVEL_Z; from that point on the tip is clear
of every deck slot for the rest of the tour. v0 has no software
soft-limit enforcement (see `.claude/rules/motion-safety.md`).

**Side effect**: raises Marlin's Z max feedrate (`M203 Z20`) and Z
acceleration (`M201 Z200`) for snappier vertical motion. Lasts until
power-cycle unless saved with `M500`.
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
DEFAULT_GCODE_OUT = "showcase_v0_full_plate.gcode"

# --- Deck geometry ------------------------------------------------------
# Canonical source: docs/deck-layout.md "Slot extents" + "Motion constants".
# Any change here must be reflected there (and vice versa).

# Deck-to-Marlin frame offset. Marlin commanded coords = deck-frame + offset.
# Y offset = -50: bed shifted another 5 cm forward on top of the per-slot
# adjustments. Reachable: Marlin Y=0 sits 175 mm behind the physical bed
# front, so the new front-most commanded Y (SBS col 12 at -56) is still
# 119 mm before the physical front limit.
DECK_OFFSET_X = 25.0  # +X = right (commanded X = deck X + 25)
DECK_OFFSET_Y = -50.0  # -Y = forward (commanded Y = deck Y - 50)

# SBS plate (back-left slot; physical position at deck X=5-90, Y=80-207, H=13).
# 8 rows along X at 9 mm pitch, 12 cols along Y at 9 mm pitch.
# Channel-1 (leftmost dPette tip) reference sits over row A: deck X = 16.
# Tour iterates back→front: deck col 1 at Y=193, deck col 12 at Y=94.
#
# BED MOVEMENT ADJUSTMENT (per-slot, not a deck-frame shift): when
# visiting the SBS plate, the bed is commanded 100 mm forward of the
# deck-frame col position to land the dPette on the correct row. So
# Marlin Y for col 1 = 193 - 100 = 93, col 12 = 94 - 100 = -6.
# Negative-Y reachability: Marlin Y=0 sits 175 mm behind the physical
# bed front (per the printer's calibration), so Y=-6 is comfortably
# within reachable travel (169 mm before the physical front limit).
SBS_REF_X = 16.0 + DECK_OFFSET_X  # 41.0
SBS_COL1_Y = (
    93.0 + DECK_OFFSET_Y
)  # 43.0 Marlin = deck col1 (193) - 100 SBS shift - 50 global
SBS_COL_PITCH = 9.0  # absolute pitch (delta, no offset); subtracted per visit

# Reservoir (front slot). 8 channels span 63 mm in X; X-center the
# dPette over the reservoir (deck-frame X = 43–177 still considered
# correct). Cavity heights: rim H = 24 mm, floor at Z = 19 mm, depth 5 mm.
#
# Y anchor (per user calibration, 2026-05-12): the reservoir sits
# RIGHT ABOVE Marlin Y = -50. That is:
#   - 5 cm in front of Marlin Y = 0 (the Marlin home corner, which is
#     itself 17.5 cm behind the physical bed front).
#   - 12.5 cm behind the physical bed front (Y = -175 = mechanical limit).
#   - Comfortably reachable with 125 mm of forward-travel margin.
#
# The earlier deck-frame slot extent (deck Y = 10–53) DID NOT match
# physical reality — kept only as a historical placeholder in
# docs/deck-layout.md. Trust the Marlin-Y anchor below for runtime.
RESERVOIR_REF_X = 78.5 + DECK_OFFSET_X  # 103.5; 110 X-center - 31.5 half span
RESERVOIR_REF_Y = (
    0.0 + DECK_OFFSET_Y
)  # -50.0 Marlin; "right above the reservoir" per user spec

# Tip box (back-right slot; front edge at Y=80, deck X=134-215, Y=80-200,
# H >= 59 with loaded tips).
# Leftmost tip column sits 8.5 mm from the outer-left wall (deck X=134).
# Tour picks up from the back-most tip column (inner Y back 195 - 5.5 margin)
# to minimize Y travel before the first SBS column visit (deck Y=193).
TIP_PICKUP_X = 142.5 + DECK_OFFSET_X  # 167.5; outer-left 134 + 8.5
TIP_PICKUP_Y = 189.5 + DECK_OFFSET_Y  # 139.5 Marlin; back-most tip column center

# --- Motion altitudes (deck-plate frame) --------------------------------
# Canonical source: docs/deck-layout.md "Motion constants".
# Tip box loaded-tips H = 59 mm is the DESIGN MINIMUM — `TRAVEL_Z` is
# derived from that. If a taller tip box is introduced, raise `TRAVEL_Z`
# in lockstep here AND in docs/deck-layout.md.

# Global Z floor: all altitudes bumped +50 mm vs the previous iteration,
# per user spec ("Z +5 cm to the top OVERALL"). Keeps the tip clear of every
# slot for v0 sim — no descents reach into wells, the reservoir cavity, or
# the tip-box tip tops. For real liquid handling, descend points must be
# re-derived against the actual slot geometry.
TRAVEL_Z = 125.0  # 75 + 50; in-tour safe altitude (clears 59 mm tip box + margin)
RESERVOIR_Z = 70.0  # 20 + 50 (was: 1 mm above cavity floor; now ~46 mm above rim)
WELL_Z = (
    72.0  # 22 + 50; INVARIANT: WELL_Z >= RESERVOIR_Z (tip never lower than aspirate)
)
TIP_PICKUP_Z = 57.0  # 7 + 50; body-bottom at deck-Z 111 = 52 mm above 59 mm tip tops

# End-of-tour park altitude: 1.5 × disposable tip length. Sits low enough
# to make the head accessible to the operator but high enough to clear any
# tip still loaded on the dPette (forgotten-tip safety margin).
PARK_TIP_LENGTH_MM = 49.5  # disposable tip length per user spec
PARK_TIP_CLEARANCE_FACTOR = 1.5
PARK_Z = PARK_TIP_LENGTH_MM * PARK_TIP_CLEARANCE_FACTOR  # 74.25 mm
# NOTE on TIP_PICKUP_Z: `Z=0` is calibrated to tip-end-on-deck WITH tips on
# (see docs/calibration.md "Post-strip Z re-cal"). For pickup, no tips are
# attached yet, so commanded Z represents body-bottom-altitude − 54 mm
# (the loaded-tip extension below the carriage). At commanded Z=57, body is
# at deck-Z 111 — 52 mm above the tip tops (no engagement; v0 sim only).
# Real engagement is at body-bottom = tip-top (deck-Z 59 → commanded Z=5).

# --- Feedrates (under M203 X500 Y500 / Z20 caps after the bump below) ---

XY_FEED = 12000  # 200 mm/s — well under the X500/Y500 mm/s cap
Z_FEED = 1200  # 20 mm/s — at the M203 Z20 cap (leadscrew mechanical limit)

NUM_COLUMNS = 12


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


def visit_reservoir(
    link: serial.Serial,
    *,
    gcode_out: TextIO | None = None,
) -> None:
    """Travel to reservoir, single descent to RESERVOIR_Z (aspirate), lift.

    Aspirate is a SINGLE descent — no plunger up-and-back stroke. See
    docs/deck-layout.md "Tour sequence" phase 3.
    """
    print("[host] --- reservoir aspirate (simulated) ---")
    if gcode_out is not None:
        gcode_out.write("\n; --- reservoir aspirate (simulated) ---\n")
    gsend(
        link,
        f"G1 X{RESERVOIR_REF_X:.3f} Y{RESERVOIR_REF_Y:.3f} Z{TRAVEL_Z:.3f} F{XY_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{RESERVOIR_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{TRAVEL_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)


def visit_column(
    link: serial.Serial,
    col: int,
    *,
    gcode_out: TextIO | None = None,
) -> None:
    """Travel to SBS column `col` (1..12, back→front), single descent (dispense), lift.

    Column 1 = back-most ("top-left" of plate, Y=SBS_COL1_Y); column 12 =
    front-most. Dispense is a SINGLE descent — no plunger up-and-back stroke.
    Invariant: WELL_Z >= RESERVOIR_Z (tip never lower at dispense than aspirate).
    See docs/deck-layout.md "Tour sequence" phase 3.
    """
    y = SBS_COL1_Y - (col - 1) * SBS_COL_PITCH
    print(f"[host] --- SBS column {col} dispense (simulated) at Y={y:.2f} ---")
    if gcode_out is not None:
        gcode_out.write(f"\n; --- SBS column {col} dispense at Y={y:.2f} ---\n")
    gsend(
        link,
        f"G1 X{SBS_REF_X:.3f} Y{y:.3f} Z{TRAVEL_Z:.3f} F{XY_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{WELL_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{TRAVEL_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)


def pickup_tips(
    link: serial.Serial,
    *,
    gcode_out: TextIO | None = None,
) -> None:
    """One-time tip pickup at the back-right tip box.

    Friction-fit engagement (no plunger stroke). See docs/deck-layout.md
    "Tour sequence" phase 2 for the geometry and the `TIP_PICKUP_Z` note
    on calibration assumptions.
    """
    print("[host] --- tip pickup (simulated, once) ---")
    if gcode_out is not None:
        gcode_out.write("\n; --- tip pickup (simulated, once) ---\n")
    gsend(
        link,
        f"G1 X{TIP_PICKUP_X:.3f} Y{TIP_PICKUP_Y:.3f} Z{TRAVEL_Z:.3f} F{XY_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{TIP_PICKUP_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{TRAVEL_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)


def _gcode_header() -> str:
    return (
        "; showcase_v0_full_plate.gcode\n"
        "; generated by examples/showcase_v0_full_plate.py\n"
        "; full 96-well fill cycle: 12 SBS columns x 8 channels\n"
        "; deck layout: docs/deck-layout.md\n"
        "; aspirate/dispense simulated via single gantry Z descent (no M820)\n"
    )


def _phase_comment(gcode_out: TextIO | None, text: str) -> None:
    """Write `text` to the tee'd G-code stream if one is attached."""
    if gcode_out is not None:
        gcode_out.write(text)


def _run(
    link: serial.Serial,
    gcode_out: TextIO | None,
) -> None:
    """Full tour — see docs/deck-layout.md "Tour sequence" for phase breakdown.

    Phases: bootstrap → tip pickup (once) → 12× (reservoir + SBS column,
    back→front) → park at home corner.

    !!! PRECONDITION !!!
    TIPS MUST BE REMOVED from the dPette before this function runs.
    Phase 1 issues a full `G28` to home all axes. Z=0 is calibrated to
    tip-end-on-deck (per docs/calibration.md), so Z homing drives any
    mounted tip into the deck — destructive. After phase 1 the Z is
    raised to TRAVEL_Z, then the tour picks up tips from the box in
    phase 2.
    """
    _phase_comment(
        gcode_out,
        _gcode_header() + "; raise Z max feedrate + accel for snappy moves\n",
    )
    gsend(link, "M203 Z20", gcode_out=gcode_out)
    gsend(link, "M201 Z200", gcode_out=gcode_out)

    _phase_comment(
        gcode_out,
        "\n; ===== phase 1: bootstrap (G28 + Z raise) =====\n"
        "; PRECONDITION: tips MUST BE REMOVED from the dPette before this\n"
        "; G28 fires. Z=0 is calibrated to tip-end-on-deck per\n"
        "; docs/calibration.md, so G28 Z drives the tip into the deck if\n"
        "; tips are still mounted — destructive. After G28 lands, phase 1\n"
        "; raises Z to TRAVEL_Z; you can re-mount tips manually then, OR\n"
        "; let the tour's tip-pickup phase load tips from the box.\n",
    )
    gsend(link, "G28", gcode_out=gcode_out, max_secs=120)
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{TRAVEL_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)

    _phase_comment(gcode_out, "\n; ===== phase 2: tip pickup (once) =====\n")
    pickup_tips(link, gcode_out=gcode_out)

    _phase_comment(
        gcode_out,
        "\n; ===== phase 3: column tour (back->front, 12 columns) =====\n",
    )
    for col in range(1, NUM_COLUMNS + 1):
        print(f"\n[host] ====== COLUMN {col}/{NUM_COLUMNS} ======")
        _phase_comment(gcode_out, f"\n; ====== COLUMN {col}/{NUM_COLUMNS} ======\n")
        visit_reservoir(link, gcode_out=gcode_out)
        visit_column(link, col, gcode_out=gcode_out)

    _phase_comment(
        gcode_out,
        "\n; ===== phase 4: park at home corner, Z = 1.5 x tip length (no G28) =====\n",
    )
    gsend(
        link,
        f"G1 X0.000 Y0.000 Z{PARK_Z:.3f} F{XY_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, "M400", gcode_out=gcode_out)


def main() -> int:
    port = os.environ.get("I3MEGA_PORT")
    if not port:
        sys.stderr.write(
            "ERROR: set I3MEGA_PORT to your printer's serial port.\n"
            "       Run `uv run tools/preflight.py` to discover it.\n"
        )
        return 1
    baud = int(os.environ.get("I3MEGA_BAUD", str(DEFAULT_BAUD)))
    gcode_path = os.environ.get("OUTPUT_GCODE", DEFAULT_GCODE_OUT)

    link = open_marlin_port(port, baudrate=baud, timeout=2.0)
    if link is None:
        sys.stderr.write(
            f"ERROR: could not open {port} @ {baud} baud.\n"
            "       Run `uv run tools/preflight.py` to verify the port.\n"
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
        print("[host] done — parked at home corner, Z at PARK_Z")
    return 0


if __name__ == "__main__":
    sys.exit(main())
