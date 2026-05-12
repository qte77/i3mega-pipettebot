"""Hardware-motion simulation of a full 96-well plate fill — gantry-only, no dPette.

================================================================================
PRECONDITION — READ BEFORE RUNNING:
================================================================================

  TIPS MUST BE REMOVED from the dPette before this script starts.

  Phase 1 issues `G28 X Y Z` (explicit axes — plain `G28` on the
  AI3M Marlin variant has been observed to skip Z), which homes Z to
  its calibrated zero. Per docs/calibration.md, Z=0 = tip-end-on-deck
  WITH tips loaded — so if you run this with tips still mounted, the
  Z homing routine drives the tip into the deck. Destructive.

  Workflow:
    1. Remove tips from the dPette manually (or let the prior tour run
       its eject/discard sequence — not yet implemented in v0).
    2. Run this script. Phase 1's `G28` lands Z=0 (safe with no tips),
       then immediately raises to TRAVEL_Z (95 mm).
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

    1. bootstrap     — M203/M201 bump, `M211 S0` (disable software
                       endstops so negative-Y reservoir/SBS targets are
                       not clamped), `G28 X Y Z` (explicit axes; plain
                       `G28` has been observed to skip Z on the AI3M
                       Marlin variant — tips MUST be removed first,
                       see PRECONDITION), G1 Z TRAVEL_Z.
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
= 125` mm clears the tip box by 66 mm. **Phase 1 runs `G28 X Y Z` — TIPS
MUST BE REMOVED FIRST** (Z=0 = tip-on-deck per the calibrated zero).
Plain `G28` skips Z on the AI3M Marlin variant; explicit axes force
all three to home. After homing, Z lifts to TRAVEL_Z; from that point
on the tip is clear of every deck slot for the rest of the tour. v0
has no software soft-limit enforcement (see `.claude/rules/motion-safety.md`).

**Side effect**: raises Marlin's Z max feedrate (`M203 Z20`) and Z
acceleration (`M201 Z200`) for snappier vertical motion, AND disables
software endstops (`M211 S0`) for robustness in case any commanded Y
falls outside the firmware-configured `Y_MIN`/`Y_MAX`. With the
positive-Y convention (Y=0 back, Y=250 front) all current targets
sit between 0 and ~140, so soft endstops would not typically clamp
— `M211 S0` is kept defensively. Both settings last until power-cycle
unless saved with `M500`.
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
# Y convention (per user spec): Y axis is positive 0–250 mm, with Y=0 at
# the BACK of the bed and Y=250 at the FRONT. All commanded Y values
# should be positive. DECK_OFFSET_Y = 0 — no Y offset needed.
DECK_OFFSET_X = 25.0  # +X = right (commanded X = deck X + 25)
DECK_OFFSET_Y = 0.0  # Y axis positive (Y=0 back, Y=250 front)

# SBS plate (per user spec): X=50, cycle 1 Y=190, step -10 mm per cycle.
# 11-cycle ladder:
#   190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90
# Cycle 1 sits one SBS pitch further from Y=0 (back) than the prior
# Y=180 anchor — pushes the whole ladder 10 mm toward the bed front.
SBS_REF_X = 25.0 + DECK_OFFSET_X  # 50.0 Marlin
SBS_COL1_Y = 190.0 + DECK_OFFSET_Y  # 190.0 Marlin (cycle 1)
SBS_COL_PITCH = -10.0  # -10 mm per cycle (Y decreases each visit)

# Reservoir (per user spec): X=155, Y=115.
RESERVOIR_REF_X = 130.0 + DECK_OFFSET_X  # 155.0 Marlin
RESERVOIR_REF_Y = 115.0 + DECK_OFFSET_Y  # 115.0 Marlin

# Tip box (per user spec): X=155, Y=217.5.
TIP_PICKUP_X = 130.0 + DECK_OFFSET_X  # 155.0 Marlin
TIP_PICKUP_Y = 217.5 + DECK_OFFSET_Y  # 217.5 Marlin

# --- Motion altitudes (deck-plate frame) --------------------------------
# Canonical source: docs/deck-layout.md "Motion constants".
# Tip box loaded-tips H = 59 mm is the DESIGN MINIMUM — `TRAVEL_Z` is
# derived from that. If a taller tip box is introduced, raise `TRAVEL_Z`
# in lockstep here AND in docs/deck-layout.md.

# Visit dive altitudes. Z-first transit pattern uses TRAVEL_Z (95) for
# all inter-slot XY motion — every slot top (SBS plate 13 mm, reservoir
# rim 24 mm, tip box 59 mm loaded) is below 95 mm so the bed is always
# above obstacles during XY transit. No hover-Z step (each visit
# descends directly from TRAVEL_Z to dive Z). NB: the column tour never
# crosses the tip box (tip box Y=217.5 vs SBS Y_max=190), so the 36 mm
# tip-box clearance only applies to the one-time tip-pickup phase.
#
# WELL_Z == RESERVOIR_Z == 70 — dispense and aspirate dive to the same Z,
# preserving the WELL_Z >= RESERVOIR_Z invariant from motion-safety.md
# (tip never lower at dispense than at aspirate).
TRAVEL_Z = 95.0  # transit altitude — all XY motion happens here
WELL_Z = 70.0  # dive Z into SBS well
RESERVOIR_Z = 70.0  # dive Z into reservoir

# Tip-pickup phase Z sequence (per user spec) — opens with a single
# combined XYZ move from (0, 0, TRAVEL_Z) straight to tip engagement.
# 1. Combined XYZ → (TIP_PICKUP_X, TIP_PICKUP_Y, TIP_PICKUP_Z)
# 2. Lift to TIP_PICKUP_LIFT_Z (clear of tip box with tips loaded)
# 3. Travel to reservoir XY at TIP_PICKUP_LIFT_Z
# 4. Descend to TRAVEL_Z (hand off to cycle 1)
TIP_PICKUP_Z = 70.0  # tip engagement Z (body bottom on tip tops); combined-axis target
TIP_PICKUP_LIFT_Z = 140.0  # post-engagement lift; clears tip box + tips

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
    gcode_out: TextIO | None = None,
) -> None:
    """Collision-safe Z-first visit: lift → XY at TRAVEL_Z → dive → lift.

    All inter-slot XY motion happens at `TRAVEL_Z` (above every slot),
    so the carriage never clips a fixture on its way past. The aspirate
    and dispense visits both use this — the only differences are the
    target XY and the dive Z.
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
    # 4. Lift back to TRAVEL_Z (ready for next transit)
    gsend(link, f"G1 Z{TRAVEL_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)


def visit_reservoir(
    link: serial.Serial,
    *,
    gcode_out: TextIO | None = None,
) -> None:
    """Z-first aspirate visit at the reservoir."""
    _visit_xy_dive(
        link,
        RESERVOIR_REF_X,
        RESERVOIR_REF_Y,
        RESERVOIR_Z,
        "reservoir aspirate (simulated)",
        gcode_out=gcode_out,
    )


def visit_column(
    link: serial.Serial,
    col: int,
    *,
    gcode_out: TextIO | None = None,
) -> None:
    """Z-first dispense visit at SBS column `col` (1..NUM_COLUMNS).

    Per user spec: col 1 at Marlin Y=180, step -10 mm per cycle.
    Invariant: WELL_Z >= RESERVOIR_Z. See docs/deck-layout.md.
    """
    y = SBS_COL1_Y + (col - 1) * SBS_COL_PITCH
    _visit_xy_dive(
        link,
        SBS_REF_X,
        y,
        WELL_Z,
        f"SBS column {col} dispense (simulated) at Y={y:.2f}",
        gcode_out=gcode_out,
    )


def pickup_tips(
    link: serial.Serial,
    *,
    gcode_out: TextIO | None = None,
) -> None:
    """One-time tip pickup at the back-right tip box.

    Six-step Z-first sequence per user spec. Phase 1 parked the head at
    TRAVEL_Z=95 (36 mm over the loaded tip box — adequate but not
    generous), so this phase OPENS WITH A Z ASCENT to
    `TIP_PICKUP_LIFT_Z=140` (81 mm clearance over the tip box) before
    any XY motion crosses the tip-box footprint. Symmetric pre/post:
    same LIFT_Z serves both the approach and the post-engagement lift.

      1. Z UP → TIP_PICKUP_LIFT_Z (clearance above tip box).
      2. XY → (TIP_PICKUP_X, TIP_PICKUP_Y) at TIP_PICKUP_LIFT_Z.
      3. Z DOWN → TIP_PICKUP_Z (engage tips — friction-fit).
      4. Z UP → TIP_PICKUP_LIFT_Z (lift with tips loaded).
      5. XY → (RESERVOIR_REF_X, RESERVOIR_REF_Y) at TIP_PICKUP_LIFT_Z.
      6. Z DOWN → TRAVEL_Z (hand off to cycle 1's Z-first transit).
    """
    print("[host] --- tip pickup (simulated, once) ---")
    if gcode_out is not None:
        gcode_out.write("\n; --- tip pickup (simulated, once) ---\n")
    # 1. Ascend to tip-box clearance BEFORE any XY
    gsend(link, f"G1 Z{TIP_PICKUP_LIFT_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    # 2. XY to tip box at clearance altitude
    gsend(
        link,
        f"G1 X{TIP_PICKUP_X:.3f} Y{TIP_PICKUP_Y:.3f} F{XY_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, "M400", gcode_out=gcode_out)
    # 3. Engage
    gsend(link, f"G1 Z{TIP_PICKUP_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    # 4. Lift with tips loaded
    gsend(link, f"G1 Z{TIP_PICKUP_LIFT_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    # 5. XY to reservoir at clearance altitude
    gsend(
        link,
        f"G1 X{RESERVOIR_REF_X:.3f} Y{RESERVOIR_REF_Y:.3f} F{XY_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, "M400", gcode_out=gcode_out)
    # 6. Descend to TRAVEL_Z (cycle 1's Z-first transit takes over)
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
    Phase 1 issues `G28 X Y Z` (explicit axes — plain `G28` on the
    AI3M Marlin variant has been observed to skip Z). Z=0 is
    calibrated to tip-end-on-deck (per docs/calibration.md), so Z
    homing drives any mounted tip into the deck — destructive. After
    phase 1 the Z is raised to TRAVEL_Z, then the tour picks up tips
    from the box in phase 2.
    """
    _phase_comment(
        gcode_out,
        _gcode_header()
        + "; raise Z max feedrate + accel for snappy moves\n"
        + "; disable software endstops defensively (Y axis is positive\n"
        + "; 0-250 in this convention; soft endstops kept off in case any\n"
        + "; commanded Y falls outside the firmware Y_MIN/Y_MAX range)\n",
    )
    gsend(link, "M203 Z20", gcode_out=gcode_out)
    gsend(link, "M201 Z200", gcode_out=gcode_out)
    gsend(link, "M211 S0", gcode_out=gcode_out)

    _phase_comment(
        gcode_out,
        "\n; ===== phase 1: bootstrap (G28 X Y Z + Z raise) =====\n"
        "; PRECONDITION: tips MUST BE REMOVED from the dPette before this\n"
        "; G28 fires. Z=0 is calibrated to tip-end-on-deck per\n"
        "; docs/calibration.md, so G28 Z drives the tip into the deck if\n"
        "; tips are still mounted — destructive. After G28 lands, phase 1\n"
        "; raises Z to TRAVEL_Z; you can re-mount tips manually then, OR\n"
        "; let the tour's tip-pickup phase load tips from the box.\n"
        ";\n"
        "; G28 X Y Z (explicit axes) — observed that plain `G28` on this\n"
        "; AI3M firmware skips Z. Listing axes forces all three to home.\n",
    )
    gsend(link, "G28 X Y Z", gcode_out=gcode_out, max_secs=120)
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{TRAVEL_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)

    _phase_comment(gcode_out, "\n; ===== phase 2: tip pickup (once) =====\n")
    pickup_tips(link, gcode_out=gcode_out)

    _phase_comment(
        gcode_out,
        f"\n; ===== phase 3: column tour ({NUM_COLUMNS} cycles) =====\n",
    )
    for col in range(1, NUM_COLUMNS + 1):
        print(f"\n[host] ====== COLUMN {col}/{NUM_COLUMNS} ======")
        _phase_comment(gcode_out, f"\n; ====== COLUMN {col}/{NUM_COLUMNS} ======\n")
        visit_reservoir(link, gcode_out=gcode_out)
        visit_column(link, col, gcode_out=gcode_out)

    _phase_comment(
        gcode_out,
        "\n; ===== phase 4: park at home corner (Z-first, no G28) =====\n",
    )
    # Z first — at TRAVEL_Z already from last visit_column lift
    gsend(link, f"G1 Z{TRAVEL_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    # XY to home corner at TRAVEL_Z
    gsend(link, f"G1 X0.000 Y0.000 F{XY_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    # Descend to PARK_Z
    gsend(link, f"G1 Z{PARK_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
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
