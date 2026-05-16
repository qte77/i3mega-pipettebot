"""Row-tour plate fill — i3 Mega gantry + REAL dPette + per-cycle tip recycle.

================================================================================
PRECONDITION — READ BEFORE RUNNING:
================================================================================

  TIPS MUST BE REMOVED from the dPette before this script starts.

  Phase 1 issues `G28` (homes Z to its calibrated zero). Per
  docs/calibration.md, Z=0 = tip-end-on-deck WITH tips loaded — running
  with tips mounted drives the tip into the deck. Destructive.

  The dPette must also be:
    - Awake (press its button if standby has dropped the USB chip).
    - On `PIPETTE_PORT` (CP2102 USB-UART, default 9600 baud).
    - **Unloaded at start**. Each cycle picks fresh tips from the box,
      dispenses, then ejects at the release bar before the next pickup.

================================================================================

Sibling of `showcase_v0_full_pipettebot.py`, but with two structural changes:

  1. **Per-cycle tip recycle.** Each cycle does its own pickup from a
     fresh tip-box row and ejects at the release bar before the next
     cycle. The single one-time `pickup_tips()` from full_pipettebot
     is gone — `_cycle()` now contains pickup → aspirate → dispense →
     eject.
  2. **Row-major fill, configurable count.** Cycles traverse 96-well
     rows (Y axis, +9 mm pitch from Y=75) rather than columns. Count
     is `NUM_CYCLES` env var, clamped 1..12. Tip-box rows step in
     lockstep at the same pitch from Y=154.

Per-cycle gantry shape (mirrors the hand-traced G-code calibration):

    --- TIP PICKUP @ tip-box row N ---
    G1 Z90 X170 Y(154+9*(N-1))   ; approach row N from above (no tips on body)
    G1 Z60                       ; press body onto tip tops
    G1 Z130                      ; lift with tips loaded (extra clearance)

    --- ASPIRATE @ reservoir ---
    G1 Y130                      ; intermediate Y — clear tip box footprint
    G1 Z70 Y95                   ; diagonal descend + slide into reservoir
    ; dpette.aspirate()          ; B3 SUCK at the bottom of the dive
    G1 Z100                      ; lift to reservoir clearance

    --- DISPENSE @ 96-well row N ---
    G1 X50 Y(75+9*(N-1))         ; XY to plate row N at travel altitude
    G1 Z70                       ; dive into well
    ; dpette.dispense()          ; B3 BLOW at the bottom of the dive
    G1 Z115                      ; lift to bar-clearance altitude

    --- EJECT @ release bar ---
    G1 X10 Y220                  ; cross-deck transit to release area
    G1 X0                        ; slide onto bar engagement column
    G1 Z95                       ; descend — hook engages bar from above
    G1 Z115                      ; lift — bar holds handle, body rises → tip ejected

Between cycles the head sits at (X=0, Y=220, Z=115); cycle N+1's
first move (`G1 Z90 X170 Y...`) is a single diagonal back to the next
tip-box row.

After the last cycle, the park sequence:

    G1 X30                       ; lateral clear from the bar
    G1 Z70 X0                    ; diagonal — descend below bar AND return X=0
    G28                          ; home

  The Z=70 descent BEFORE X=0 is mandatory — at X=0 Y near 0, anything
  above Z=70 fouls the release-bar hook on the homing sweep.

Required environment variables:

    I3MEGA_PORT          Marlin USB-serial path.
    PIPETTE_PORT         dPette USB-serial path. Run `tools/preflight.py`
                         to discover both.

Optional:

    NUM_CYCLES           Number of rows to fill. Default 12, range 1..12.
                         12 is the natural 96-well max (8 channels × 12
                         rows = 96 wells). See bed-range warning below.
    I3MEGA_BAUD          Default 250000 (Anycubic stock + MARLIN-AI3M).
    PIPETTE_BAUD         Default 9600 (DLAB dPette CP2102 stock).
    PIPETTE_VOLUME_UL    Per-channel volume in microlitres. Default 100.0.
    OUTPUT_GCODE         Path to tee Marlin commands to disk. Default
                         `showcase_v0_full_pipettebot_rows.gcode` in cwd.
                         Set to empty (`OUTPUT_GCODE=`) to disable.

**Bed-range warning**: tip-box row Y = 154 + 9·(N−1). At N=12 that's
Y=253 — outside the i3 Mega Y=0–250 envelope. Cycles 11 and 12 will
drive the head past the front frame. `M211 S0` (bootstrap) disables
soft endstops so Marlin will obey; verify your tip-box position
allows N>10 before running.

**Safety**: dPette dispense at WELL_DISPENSE_Z = aspirate Z = 70 mm.
Each SBS well starts empty, so the B3 BLOW piston-return suction
draws no extra liquid (per `.claude/rules/motion-safety.md` tip-above-
liquid rule — boundary case).

**Side effect**: raises Marlin's Z max feedrate (M203 Z20), Z accel
(M201 Z200), and disables soft endstops (M211 S0). All last until
power cycle unless saved with M500.
"""

from __future__ import annotations

import os
import sys
import time
from typing import TYPE_CHECKING

from dpette import DPetteDriver, SerialConfig

from pipettebot.gantry import open_marlin_port

if TYPE_CHECKING:
    from typing import TextIO

    import serial  # type: ignore[import-untyped]

DEFAULT_BAUD = 250000
DEFAULT_PIPETTE_BAUD = 9600
DEFAULT_GCODE_OUT = "showcase_v0_full_pipettebot_rows.gcode"
DEFAULT_VOLUME_UL = 100.0

# --- Cycle envelope -----------------------------------------------------
DEFAULT_NUM_CYCLES = 12
MAX_NUM_CYCLES = 12  # 96-well plate = 8 channels × 12 rows
MIN_NUM_CYCLES = 1

# --- Deck geometry (Marlin frame) ---------------------------------------
# Y convention: 0 = back, 250 = front (per docs/deck-layout.md).
# Every constant below names the deck slot it represents
# (per `.claude/rules/motion-safety.md`).

SBS_ROW_PITCH = 9.0  # standard SBS row pitch (mm)

# Tip box: 8-channel grabs one row per cycle, stepping +Y between cycles.
TIP_BOX_X = 170.0
TIP_BOX_Y_ROW1 = 154.0  # cycle 1; cycle N at TIP_BOX_Y_ROW1 + (N-1)*SBS_ROW_PITCH

# Reservoir: same X column as tip box; Y=130 is an intermediate transit
# stop to clear the tip-box footprint before diving to the aspirate
# position at Y=95.
RESERVOIR_X = 170.0
RESERVOIR_TRANSIT_Y = 130.0  # intermediate Y, clear of tip-box edge
RESERVOIR_Y = 95.0  # aspirate position

# 96-well plate: row 1 at Y=75, +9 mm pitch per cycle.
WELL_X = 50.0
WELL_Y_ROW1 = 75.0  # cycle 1; cycle N at WELL_Y_ROW1 + (N-1)*SBS_ROW_PITCH

# Release bar: approach diagonally to (X=10, Y=220) above the slide,
# slide laterally to X=0, then engage from above.
RELEASE_APPROACH_X = 10.0
RELEASE_BAR_X = 0.0
RELEASE_BAR_Y = 220.0  # shared Y for both approach and engagement

# --- Motion altitudes ---------------------------------------------------
POST_HOME_LIFT_Z = 45.0  # initial lift after G28 before any XY
TIP_BOX_APPROACH_Z = 90.0  # above tip box, body alone (no tips on)
TIP_PICKUP_Z = 60.0  # press body onto tip tops
TIP_BOX_CLEAR_Z = 130.0  # post-pickup clearance with tips loaded
RESERVOIR_DIVE_Z = 70.0  # aspirate dive
RESERVOIR_CLEAR_Z = 100.0  # post-aspirate lift
WELL_DISPENSE_Z = 70.0  # dispense dive (= aspirate Z; each well empty)
WELL_CLEAR_Z = 115.0  # post-dispense lift; also clears the release bar
RELEASE_ENGAGE_Z = 95.0  # hook drops into engagement from above the bar
RELEASE_CLEAR_Z = 115.0  # post-eject lift (= cross-deck transit altitude)
PARK_BELOW_BAR_Z = 70.0  # safe Z at X=0 below the bar's bottom edge
PARK_CLEARANCE_X = 30.0  # X clear of bar before the final descent

# --- Feedrates (under M203 X500 Y500 / Z20 caps after bootstrap bump) ---
XY_FEED = 12000  # 200 mm/s — well under the X/Y caps
Z_FEED = 1200  # 20 mm/s — at the M203 Z20 cap


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


def _phase_comment(gcode_out: TextIO | None, text: str) -> None:
    if gcode_out is not None:
        gcode_out.write(text)


def _tip_box_y(cycle: int) -> float:
    return TIP_BOX_Y_ROW1 + (cycle - 1) * SBS_ROW_PITCH


def _well_y(cycle: int) -> float:
    return WELL_Y_ROW1 + (cycle - 1) * SBS_ROW_PITCH


def _pickup(
    link: serial.Serial,
    cycle: int,
    *,
    gcode_out: TextIO | None = None,
) -> None:
    """Approach tip-box row N from above, press tips on, lift to clearance."""
    y = _tip_box_y(cycle)
    print(f"[host] --- pickup @ tip-box row {cycle} (Y={y:.1f}) ---")
    _phase_comment(gcode_out, f"\n; --- pickup @ tip-box row {cycle} (Y={y:.1f}) ---\n")
    gsend(
        link,
        f"G1 Z{TIP_BOX_APPROACH_Z:.3f} X{TIP_BOX_X:.3f} Y{y:.3f} F{XY_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{TIP_PICKUP_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, f"G1 Z{TIP_BOX_CLEAR_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)


def _aspirate(
    link: serial.Serial,
    pipette: DPetteDriver,
    *,
    gcode_out: TextIO | None = None,
) -> float:
    """Transit from tip box to reservoir, dive, B3 SUCK, lift. Returns dPette s."""
    print("[host] --- aspirate @ reservoir (B3 SUCK) ---")
    _phase_comment(gcode_out, "\n; --- aspirate @ reservoir (B3 SUCK) ---\n")
    # Intermediate Y to clear tip-box footprint at TIP_BOX_CLEAR_Z
    gsend(link, f"G1 Y{RESERVOIR_TRANSIT_Y:.3f} F{XY_FEED}", gcode_out=gcode_out)
    # Diagonal descend + slide to aspirate position
    gsend(
        link,
        f"G1 Z{RESERVOIR_DIVE_Z:.3f} Y{RESERVOIR_Y:.3f} F{Z_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, "M400", gcode_out=gcode_out)
    _phase_comment(gcode_out, f"; >>> dpette.aspirate() @ Z{RESERVOIR_DIVE_Z:.1f}\n")
    t0 = time.perf_counter()
    pipette.aspirate()
    op_dt = time.perf_counter() - t0
    print(f"[host]   dpette aspirate: {op_dt:.2f} s")
    _phase_comment(gcode_out, f"; <<< returned in {op_dt:.2f} s\n")
    gsend(link, f"G1 Z{RESERVOIR_CLEAR_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    return op_dt


def _dispense(
    link: serial.Serial,
    pipette: DPetteDriver,
    cycle: int,
    *,
    gcode_out: TextIO | None = None,
) -> float:
    """Cross to 96-well row N, dive, B3 BLOW, lift to bar clearance. Returns dPette s."""
    y = _well_y(cycle)
    print(f"[host] --- dispense @ 96-well row {cycle} (Y={y:.1f}) (B3 BLOW) ---")
    _phase_comment(
        gcode_out,
        f"\n; --- dispense @ 96-well row {cycle} (Y={y:.1f}) (B3 BLOW) ---\n",
    )
    gsend(
        link,
        f"G1 X{WELL_X:.3f} Y{y:.3f} F{XY_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, f"G1 Z{WELL_DISPENSE_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    _phase_comment(gcode_out, f"; >>> dpette.dispense() @ Z{WELL_DISPENSE_Z:.1f}\n")
    t0 = time.perf_counter()
    pipette.dispense()
    op_dt = time.perf_counter() - t0
    print(f"[host]   dpette dispense: {op_dt:.2f} s")
    _phase_comment(gcode_out, f"; <<< returned in {op_dt:.2f} s\n")
    # Lift to bar-clearance altitude (sets up the cross-deck transit to eject)
    gsend(link, f"G1 Z{WELL_CLEAR_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    return op_dt


def _eject(
    link: serial.Serial,
    *,
    gcode_out: TextIO | None = None,
) -> None:
    """Cross to release bar, hook from above, lift to eject the tip."""
    print("[host] --- eject @ release bar ---")
    _phase_comment(
        gcode_out,
        "\n; --- eject @ release bar ---\n"
        "; approach from above (Z115), drop hook into engagement (Z95),\n"
        "; then lift (Z115): bar holds the handle, body rises, handle\n"
        "; descends relative to body → tip ejected.\n",
    )
    gsend(
        link,
        f"G1 X{RELEASE_APPROACH_X:.3f} Y{RELEASE_BAR_Y:.3f} F{XY_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, f"G1 X{RELEASE_BAR_X:.3f} F{XY_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{RELEASE_ENGAGE_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, f"G1 Z{RELEASE_CLEAR_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)


def _cycle(
    link: serial.Serial,
    pipette: DPetteDriver,
    cycle: int,
    num_cycles: int,
    *,
    gcode_out: TextIO | None = None,
) -> tuple[float, float]:
    """One full pickup → aspirate → dispense → eject cycle. Returns (suck_s, blow_s)."""
    print(f"\n[host] ====== CYCLE {cycle}/{num_cycles} ======")
    _phase_comment(gcode_out, f"\n; ====== CYCLE {cycle}/{num_cycles} ======\n")
    _pickup(link, cycle, gcode_out=gcode_out)
    suck_s = _aspirate(link, pipette, gcode_out=gcode_out)
    blow_s = _dispense(link, pipette, cycle, gcode_out=gcode_out)
    _eject(link, gcode_out=gcode_out)
    return suck_s, blow_s


def _gcode_header(num_cycles: int, volume_ul: float) -> str:
    return (
        "; showcase_v0_full_pipettebot_rows.gcode\n"
        "; generated by examples/showcase_v0_full_pipettebot_rows.py\n"
        f"; row tour: {num_cycles} cycles × 8 channels = {num_cycles * 8} wells\n"
        f"; per-channel volume: {volume_ul:.1f} uL (B2 PI_VOLUM set once)\n"
        "; per-cycle: tip pickup → aspirate → dispense → mechanical eject\n"
        "; deck layout: docs/deck-layout.md\n"
        "; dPette ops logged inline as `; >>>` / `; <<<` comments\n"
    )


def _run(
    link: serial.Serial,
    pipette: DPetteDriver,
    num_cycles: int,
    volume_ul: float,
    gcode_out: TextIO | None,
) -> None:
    _phase_comment(
        gcode_out,
        _gcode_header(num_cycles, volume_ul)
        + "; raise Z max feedrate + accel for snappy moves\n"
        + "; disable software endstops (Y axis positive 0-250; tip-box rows\n"
        + "; can reach Y=253 at cycle 12 — verify clearance before N>10)\n",
    )
    gsend(link, "M203 Z20", gcode_out=gcode_out)
    gsend(link, "M201 Z200", gcode_out=gcode_out)
    gsend(link, "M211 S0", gcode_out=gcode_out)

    _phase_comment(
        gcode_out,
        "\n; ===== phase 1: bootstrap (G28, then Z lift to clearance) =====\n"
        "; PRECONDITION: tips MUST BE REMOVED before G28 fires.\n",
    )
    gsend(link, "G28", gcode_out=gcode_out, max_secs=120)
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, f"G1 Z{POST_HOME_LIFT_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)

    _phase_comment(
        gcode_out,
        "\n; ===== phase 2: set per-channel volume (once) =====\n"
        f"; >>> dpette.set_volume({volume_ul:.1f} uL)\n",
    )
    pipette.set_volume(volume_ul)  # B2 PI_VOLUM

    _phase_comment(
        gcode_out,
        f"\n; ===== phase 3: row tour ({num_cycles} cycles) =====\n"
        f"; total dispensed: {volume_ul * num_cycles * 8:.0f} uL"
        f" across {num_cycles * 8} wells\n",
    )
    tour_start = time.perf_counter()
    suck_total = 0.0
    blow_total = 0.0
    for n in range(1, num_cycles + 1):
        cycle_start = time.perf_counter()
        suck_s, blow_s = _cycle(link, pipette, n, num_cycles, gcode_out=gcode_out)
        suck_total += suck_s
        blow_total += blow_s
        cycle_dt = time.perf_counter() - cycle_start
        print(f"[host] cycle {n} wall-clock: {cycle_dt:.2f} s")
        _phase_comment(gcode_out, f"; cycle {n} wall-clock: {cycle_dt:.2f} s\n")
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
        "\n; ===== phase 4: park below bar then G28 =====\n"
        "; at end of last cycle head sits at (X=0, Y=220, Z=115).\n"
        "; max safe Z at X=0 near home is 70 (release-bar hook clearance):\n"
        "; clear X first, then descend below bar, then home.\n",
    )
    gsend(link, f"G1 X{PARK_CLEARANCE_X:.3f} F{XY_FEED}", gcode_out=gcode_out)
    gsend(
        link,
        f"G1 Z{PARK_BELOW_BAR_Z:.3f} X{RELEASE_BAR_X:.3f} F{Z_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, "M400", gcode_out=gcode_out)
    gsend(link, "G28", gcode_out=gcode_out, max_secs=120)
    gsend(link, "M400", gcode_out=gcode_out)


def _resolve_num_cycles() -> int:
    raw = os.environ.get("NUM_CYCLES", str(DEFAULT_NUM_CYCLES)).strip()
    try:
        n = int(raw)
    except ValueError:
        raise SystemExit(f"ERROR: NUM_CYCLES must be an integer, got {raw!r}") from None
    if not MIN_NUM_CYCLES <= n <= MAX_NUM_CYCLES:
        raise SystemExit(
            f"ERROR: NUM_CYCLES must be in {MIN_NUM_CYCLES}..{MAX_NUM_CYCLES}, got {n}"
        )
    return n


def main() -> int:
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return 0
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
    num_cycles = _resolve_num_cycles()
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
    print(
        f"[host] row tour: {num_cycles} cycles "
        f"× 8 channels × {volume_ul:.1f} uL = "
        f"{num_cycles * 8 * volume_ul:.0f} uL total"
    )
    pipette = DPetteDriver(SerialConfig(port=pipette_port, baudrate=pipette_baud))
    pipette.connect()  # A0 HELLO → B0 WOL (PI mode) → motor homes
    if pipette.stub_mode:
        sys.stderr.write(
            f"ERROR: dPette on {pipette_port} fell back to stub mode.\n"
            "       Wake it (press its button), replug, and retry.\n"
        )
        link.close()
        return 1

    try:
        with link:
            print(f"[host] open {port} @ {baud}; waiting 3s for Marlin boot")
            time.sleep(3)
            link.reset_input_buffer()
            if gcode_path:
                print(f"[host] tee G-code stream to {gcode_path}")
                with open(gcode_path, "w") as gf:
                    _run(link, pipette, num_cycles, volume_ul, gf)
            else:
                _run(link, pipette, num_cycles, volume_ul, None)
            print("[host] done — homed; gantry parked at G28 origin")
    finally:
        pipette.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
