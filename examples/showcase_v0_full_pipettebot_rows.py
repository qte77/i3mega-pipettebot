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
     rows (Y axis, +9 mm pitch from Y=79) rather than columns. Count
     is `NUM_CYCLES` env var, clamped 1..12. Tip-box rows step in
     lockstep at the same pitch from Y=156.

Per-cycle gantry shape (mirrors the hand-traced G-code calibration):

    --- TIP PICKUP @ tip-box row N ---
    G1 Z90 X171 Y(156+9*(N-1))   ; approach row N from above (no tips on body)
    G1 Z60                       ; press body onto tip tops
    G1 Z130                      ; lift with tips loaded (extra clearance)

    --- ASPIRATE @ reservoir ---
    G1 Y130                      ; intermediate Y — clear tip box footprint
    G1 Z70 Y100                  ; diagonal descend + slide into reservoir
    ; dpette.aspirate()          ; B3 SUCK at the bottom of the dive
    G1 Z100                      ; lift to reservoir clearance

    --- DISPENSE @ 96-well row N ---
    G1 X51 Y(79+9*(N-1))         ; XY to plate row N at travel altitude
    G1 Z70                       ; dive into well
    ; dpette.dispense()          ; B3 BLOW at the bottom of the dive
    G1 Z115                      ; lift to bar-clearance altitude

    --- EJECT @ release bar ---
    G1 X10 Y220                  ; cross-deck transit to release area
    G1 X5                        ; slide onto bar engagement column
    G1 Z98                       ; descend — hook engages bar from above
    G1 Z115                      ; lift — bar holds handle, body rises → tip ejected

Between cycles the head sits at (X=5, Y=220, Z=115); cycle N+1's
first move (`G1 Z90 X171 Y...`) is a single diagonal back to the next
tip-box row.

After the last cycle, the park sequence:

    G1 X50                       ; lateral clear from the bar (≥50 mm)
    G1 Z95                       ; descend below bar engagement (X stays at 50)
    G1 Z50 X10 Y10               ; diagonal — entirely below bar, towards home corner
    G28                          ; home

  The two-stage descent matters: the pure-Z drop happens at X=50 with
  full ≥50 mm bar clearance and ends below bar engagement (Z=98). The
  subsequent diagonal stays below bar height end-to-end, so the X<50
  excursion is risk-free.

Environment variables (all optional — modes chosen from env presence):

    I3MEGA_PORT          Marlin USB-serial path. If unset, gantry G-code
                         is written to the tee file only — no Marlin
                         motion. Discover with `uv run tools/preflight.py`.
    PIPETTE_PORT         dPette USB-serial path. If unset, aspirate /
                         dispense ops are skipped and logged as
                         `; skipped` in the tee.
    NUM_CYCLES           Number of rows to fill. Default 8, range 1..8.
                         Cap lowered 12 → 8 for safety until the
                         bed/plate part layout is re-arranged
                         (tip-box and well-plate footprints clash with
                         fixtures past N=8). See `# FIXME` on
                         `MAX_NUM_CYCLES` and the bed-range warning below.
    I3MEGA_BAUD          Default 250000 (Anycubic stock + MARLIN-AI3M).
    PIPETTE_BAUD         Default 9600 (DLAB dPette CP2102 stock).
    PIPETTE_VOLUME_UL    Per-channel volume in microlitres. Default 100.0.
                         Ignored when PIPETTE_PROFILE is set.
    PIPETTE_PROFILE      Path to a TOML experiment profile that specifies
                         per-cycle volumes. See `examples/experiment_profiles/*.toml`
                         and `src/pipettebot/experiment_profile.py` for the schema.
                         Profile length overrides NUM_CYCLES; per-cycle
                         B2 PI_VOLUM is re-sent only on volume change.
    OUTPUT_GCODE         Path to tee Marlin commands to disk. Default
                         `showcase_v0_full_pipettebot_rows.gcode` in cwd.
                         Set to empty (`OUTPUT_GCODE=`) to disable.

Run modes (auto-selected from env presence):

    FULL          I3MEGA_PORT + PIPETTE_PORT — real gantry + real dPette.
    GANTRY ONLY   I3MEGA_PORT only — gantry moves; dPette ops skipped
                  (useful for path testing without consuming reagent).
    DPETTE ONLY   PIPETTE_PORT only — dPette ops fire with no spatial
                  context; primarily for dPette timing tests.
    DRY RUN       neither set — no serial; G-code tee only (useful for
                  inspecting the generated tour before plugging in).

**Bed-range warning**: tip-box row Y = 156 + 9·(N−1). At N=8 that's
Y=219 — within the Y=0–250 envelope but close to the front of bed
travel. The hard cap is `MAX_NUM_CYCLES=8` for safety until the bed
part layout is re-arranged (see the `# FIXME` on the constant).
`M211 S0` (bootstrap) disables soft endstops so Marlin will obey;
verify your tip-box position before running.

**Safety**: dPette dispense at WELL_DISPENSE_Z = aspirate Z = 70 mm.
Each SBS well starts empty, so the B3 BLOW piston-return suction
draws no extra liquid (per `.claude/rules/motion-safety.md` tip-above-
liquid rule — boundary case).

**Side effect**: installs the liquid-handling motion profile via
`pipettebot.motion_profile.select_profile(MOTION_PROFILE)`. Defaults
to MID when env unset; set `MOTION_PROFILE=slow|fast` to dial, or
`MOTION_PROFILE=off` to skip. Also disables soft endstops (`M211 S0`).
All installed settings last until power cycle unless saved with `M500`.
See `src/pipettebot/motion_profile.py` for the bundled profile values.
"""

from __future__ import annotations

import os
import sys
import time
from typing import TYPE_CHECKING

from dpette import DPetteDriver, SerialConfig

from pipettebot.cli_profile import build_volumes
from pipettebot.gantry import open_marlin_port
from pipettebot.motion_profile import select_profile

if TYPE_CHECKING:
    from typing import TextIO

    import serial  # type: ignore[import-untyped]

DEFAULT_BAUD = 250000
DEFAULT_PIPETTE_BAUD = 9600
DEFAULT_GCODE_OUT = "showcase_v0_full_pipettebot_rows.gcode"

# --- Cycle envelope -----------------------------------------------------
# FIXME: cap lowered 12 → 8 for safety. The current part layout on the
# bed/plate is not yet safety-compliant for the full 12-row tour — at
# N>8 the tip-box and well-plate footprints clash with fixtures on the
# bed. Restore to 12 (96-well plate = 8 channels × 12 rows) once the
# bed layout is re-arranged and re-measured.
DEFAULT_NUM_CYCLES = 8
MAX_NUM_CYCLES = 8
MIN_NUM_CYCLES = 1

# --- Deck geometry (Marlin frame) ---------------------------------------
# Y convention: 0 = back, 250 = front (per docs/deck-layout.md).
# Every constant below names the deck slot it represents
# (per `.claude/rules/motion-safety.md`).

SBS_ROW_PITCH = 9.0  # standard SBS row pitch (mm)

# Tip box: 8-channel grabs one row per cycle, stepping +Y between cycles.
TIP_BOX_X = 171.0
TIP_BOX_Y_ROW1 = 156.0  # cycle 1; cycle N at TIP_BOX_Y_ROW1 + (N-1)*SBS_ROW_PITCH

# Reservoir: same X column as tip box; Y=130 is an intermediate transit
# stop to clear the tip-box footprint before diving to the aspirate
# position at Y=100.
RESERVOIR_X = (
    171.0  # documentation only — _aspirate omits X (carries over from tip box)
)
RESERVOIR_TRANSIT_Y = 130.0  # intermediate Y, clear of tip-box edge
RESERVOIR_Y = 100.0  # aspirate position

# 96-well plate: row 1 at Y=79, +9 mm pitch per cycle.
WELL_X = 51.0
WELL_Y_ROW1 = 79.0  # cycle 1; cycle N at WELL_Y_ROW1 + (N-1)*SBS_ROW_PITCH

# Release bar: a horizontal rod attached to the i3 Mega's FIXED FRAME
# (not the moving bed) at the front of the chassis, oriented along the
# Y axis at carriage X≈5, engagement Z=RELEASE_ENGAGE_Z. To align the
# dPette under the fixed hook, the bed slides forward so the commanded
# Marlin Y reads Y=220 at engagement. X=5 not X=0 — X=0 is too close to
# the X-min endstop, was a stale value. Y=220 re-measured per user
# fixture after an earlier value of Y=190 was found to miss the hook.
RELEASE_APPROACH_X = 10.0
RELEASE_BAR_X = 5.0
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
RELEASE_ENGAGE_Z = 98.0  # hook drops into engagement from above the bar
RELEASE_CLEAR_Z = 115.0  # post-eject lift (= cross-deck transit altitude)
PARK_BELOW_BAR_Z = 50.0  # safe Z near home corner below the bar's bottom edge
PARK_INTERMEDIATE_Z = 95.0  # descend below bar engagement at X=50 before diagonal park
PARK_CLEARANCE_X = 50.0  # X clear of bar (≥50 mm) before any move above bar height
PARK_FINAL_X = 10.0  # final park X — towards home corner, clear of bar footprint
PARK_FINAL_Y = 10.0  # final park Y — towards home corner

# --- Feedrates (under M203 X500 Y500 / Z20 caps after bootstrap bump) ---
XY_FEED = 12000  # 200 mm/s — well under the X/Y caps
Z_FEED = 1200  # 20 mm/s — at the M203 Z20 cap

# Per-dive Z feedrates — slower than Z_FEED for damage / liquid protection.
# Applied only on the DESCENT into critical contact points; lifts always
# use the full Z_FEED (no damage risk on the way up, save cycle time).
TIP_BOX_ENGAGE_FEED = 300  # 5 mm/s — mechanical engagement on tip tops; slow to avoid bending tips or shearing posts
BAR_ENGAGE_FEED = (
    300  # 5 mm/s — mechanical hook engagement on release bar; slow to avoid impact
)
LIQUID_DIVE_FEED = 600  # 10 mm/s — meniscus contact (reservoir + wells); slightly slowed for clean entry

# Touchdown split — descend at full Z_FEED until this distance above the
# target Z, then drop to the slow contact feedrate for the last leg.
# Protects the contact point (tips/posts, bar, meniscus) without paying
# the slow feedrate for the whole dive. All four dive distances exceed
# this approach distance, so the split is always valid.
TOUCHDOWN_APPROACH_MM = 10.0


def gsend(
    link: serial.Serial | None,
    cmd: str,
    *,
    gcode_out: TextIO | None = None,
    max_secs: float = 180.0,
) -> None:
    """Send `cmd` to Marlin and (optionally) tee it into `gcode_out`.

    When `link is None` (DRY RUN / DPETTE ONLY mode), the command is
    written to `gcode_out` only — no serial write, no `ok` wait.

    Tolerates `echo:busy: processing` chatter on long G28/M400 and the
    SD-init noise Marlin emits when the card is unreadable. Raises on
    hard protocol/motion errors.
    """
    print(f"  >>> {cmd}")
    if gcode_out is not None:
        gcode_out.write(cmd + "\n")
    if link is None:
        return
    link.write((cmd + "\n").encode("ascii"))
    _await_ok(link, cmd, max_secs)


def _await_ok(link: serial.Serial, cmd: str, max_secs: float) -> None:
    """Read from Marlin until `ok`, tolerating busy chatter and SD-init noise."""
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
    link: serial.Serial | None,
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
    # Engage descent — touchdown split: fast until 10mm above the tip tops,
    # then slow (damage protection — bend tips / shear posts).
    gsend(
        link,
        f"G1 Z{TIP_PICKUP_Z + TOUCHDOWN_APPROACH_MM:.3f} F{Z_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, f"G1 Z{TIP_PICKUP_Z:.3f} F{TIP_BOX_ENGAGE_FEED}", gcode_out=gcode_out)
    # Lift: full Z_FEED — no damage risk on the way up
    gsend(link, f"G1 Z{TIP_BOX_CLEAR_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)


def _aspirate(
    link: serial.Serial | None,
    pipette: DPetteDriver | None,
    *,
    gcode_out: TextIO | None = None,
) -> float:
    """Transit from tip box to reservoir, dive, B3 SUCK, lift. Returns dPette s."""
    print("[host] --- aspirate @ reservoir (B3 SUCK) ---")
    _phase_comment(gcode_out, "\n; --- aspirate @ reservoir (B3 SUCK) ---\n")
    # Intermediate Y to clear tip-box footprint at TIP_BOX_CLEAR_Z
    gsend(link, f"G1 Y{RESERVOIR_TRANSIT_Y:.3f} F{XY_FEED}", gcode_out=gcode_out)
    # Diagonal descend + slide to aspirate position — touchdown split:
    # fast Z+Y leg reaches the final Y while Z is still 10mm above the
    # meniscus; slow pure-Z leg handles the last 10mm into the liquid.
    gsend(
        link,
        f"G1 Z{RESERVOIR_DIVE_Z + TOUCHDOWN_APPROACH_MM:.3f} Y{RESERVOIR_Y:.3f} F{Z_FEED}",
        gcode_out=gcode_out,
    )
    gsend(
        link,
        f"G1 Z{RESERVOIR_DIVE_Z:.3f} F{LIQUID_DIVE_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, "M400", gcode_out=gcode_out)
    op_dt = _fire_dpette(pipette, "aspirate", RESERVOIR_DIVE_Z, gcode_out=gcode_out)
    gsend(link, f"G1 Z{RESERVOIR_CLEAR_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    return op_dt


def _dispense(
    link: serial.Serial | None,
    pipette: DPetteDriver | None,
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
    # Well dive — touchdown split: fast until 10mm above the meniscus,
    # then slow (clean entry — avoids splashing / suction-side artefacts).
    gsend(
        link,
        f"G1 Z{WELL_DISPENSE_Z + TOUCHDOWN_APPROACH_MM:.3f} F{Z_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, f"G1 Z{WELL_DISPENSE_Z:.3f} F{LIQUID_DIVE_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    op_dt = _fire_dpette(pipette, "dispense", WELL_DISPENSE_Z, gcode_out=gcode_out)
    # Lift to bar-clearance altitude (sets up the cross-deck transit to eject)
    gsend(link, f"G1 Z{WELL_CLEAR_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)
    return op_dt


def _fire_dpette(
    pipette: DPetteDriver | None,
    op: str,
    z: float,
    *,
    gcode_out: TextIO | None = None,
) -> float:
    """Fire `aspirate` or `dispense` on the dPette and return wall-clock s.

    When `pipette is None`, the op is skipped and logged as `; skipped`.
    """
    if pipette is None:
        _phase_comment(gcode_out, f"; >>> dpette.{op}() skipped (no PIPETTE_PORT)\n")
        return 0.0
    _phase_comment(gcode_out, f"; >>> dpette.{op}() @ Z{z:.1f}\n")
    t0 = time.perf_counter()
    getattr(pipette, op)()
    op_dt = time.perf_counter() - t0
    print(f"[host]   dpette {op}: {op_dt:.2f} s")
    _phase_comment(gcode_out, f"; <<< returned in {op_dt:.2f} s\n")
    return op_dt


def _eject(
    link: serial.Serial | None,
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
    # Hook engagement descent — touchdown split: fast until 10mm above
    # the bar (Z=108), then slow (damage protection — avoid impact).
    # Total descent is 17mm, so the fast leg is only 7mm — most of the
    # dive is still slow, but the initial drop is no longer at F300.
    gsend(
        link,
        f"G1 Z{RELEASE_ENGAGE_Z + TOUCHDOWN_APPROACH_MM:.3f} F{Z_FEED}",
        gcode_out=gcode_out,
    )
    gsend(link, f"G1 Z{RELEASE_ENGAGE_Z:.3f} F{BAR_ENGAGE_FEED}", gcode_out=gcode_out)
    # Lift: full Z_FEED — the lift IS the ejection action; speed is fine here
    gsend(link, f"G1 Z{RELEASE_CLEAR_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(link, "M400", gcode_out=gcode_out)


def _cycle(
    link: serial.Serial | None,
    pipette: DPetteDriver | None,
    cycle: int,
    num_cycles: int,
    volume_ul: float,
    prev_volume: float | None,
    *,
    gcode_out: TextIO | None = None,
) -> tuple[float, float]:
    """One full pickup → aspirate → dispense → eject cycle.

    Re-sends B2 PI_VOLUM only when `volume_ul != prev_volume`. Returns
    (suck_s, blow_s).
    """
    print(
        f"\n[host] ====== CYCLE {cycle}/{num_cycles} (volume={volume_ul:.1f} uL) ======"
    )
    _phase_comment(
        gcode_out,
        f"\n; ====== CYCLE {cycle}/{num_cycles} (volume={volume_ul:.1f} uL) ======\n",
    )
    if volume_ul != prev_volume:
        if pipette is not None:
            pipette.set_volume(volume_ul)  # B2 PI_VOLUM
        _phase_comment(gcode_out, f"; >>> dpette.set_volume({volume_ul:.1f} uL)\n")
    _pickup(link, cycle, gcode_out=gcode_out)
    suck_s = _aspirate(link, pipette, gcode_out=gcode_out)
    blow_s = _dispense(link, pipette, cycle, gcode_out=gcode_out)
    _eject(link, gcode_out=gcode_out)
    return suck_s, blow_s


def _format_volumes(volumes_ul: tuple[float, ...]) -> str:
    unique = set(volumes_ul)
    if len(unique) == 1:
        return f"{volumes_ul[0]:.1f} uL (constant; B2 PI_VOLUM set once)"
    return f"per-cycle ({len(volumes_ul)} values: {list(volumes_ul)})"


def _gcode_header(num_cycles: int, volume_desc: str) -> str:
    return (
        "; showcase_v0_full_pipettebot_rows.gcode\n"
        "; generated by examples/showcase_v0_full_pipettebot_rows.py\n"
        f"; row tour: {num_cycles} cycles × 8 channels = {num_cycles * 8} wells\n"
        f"; per-channel volume: {volume_desc}\n"
        "; per-cycle: tip pickup → aspirate → dispense → mechanical eject\n"
        "; deck layout: docs/deck-layout.md\n"
        "; dPette ops logged inline as `; >>>` / `; <<<` comments\n"
    )


def _run(
    link: serial.Serial | None,
    pipette: DPetteDriver | None,
    volumes_ul: tuple[float, ...],
    gcode_out: TextIO | None,
) -> None:
    num_cycles = len(volumes_ul)
    volume_desc = _format_volumes(volumes_ul)
    _phase_comment(
        gcode_out,
        _gcode_header(num_cycles, volume_desc)
        + "; disable software endstops (Y axis positive 0-250; tip-box rows\n"
        + "; safety cap at MAX_NUM_CYCLES=8 — restore to 12 after bed re-layout)\n",
    )
    profile = select_profile(os.environ.get("MOTION_PROFILE"))
    if profile is None:
        print("[host] motion profile: SKIPPED (MOTION_PROFILE opt-out)")
        _phase_comment(
            gcode_out, "; motion profile: SKIPPED (MOTION_PROFILE opt-out)\n"
        )
    else:
        print(f"[host] motion profile: {profile.name}")
        _phase_comment(
            gcode_out,
            f"; motion profile: {profile.name} "
            "(via pipettebot.motion_profile.select_profile)\n",
        )
        for cmd in profile.as_marlin():
            gsend(link, cmd, gcode_out=gcode_out)
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

    total_ul = sum(volumes_ul) * 8
    _phase_comment(
        gcode_out,
        f"\n; ===== phase 2: row tour ({num_cycles} cycles) =====\n"
        f"; per-channel volume: {volume_desc}\n"
        f"; total dispensed: {total_ul:.0f} uL"
        f" across {num_cycles * 8} wells\n",
    )
    tour_start = time.perf_counter()
    suck_total = 0.0
    blow_total = 0.0
    prev_volume: float | None = None
    for n in range(1, num_cycles + 1):
        cycle_start = time.perf_counter()
        v = volumes_ul[n - 1]
        suck_s, blow_s = _cycle(
            link, pipette, n, num_cycles, v, prev_volume, gcode_out=gcode_out
        )
        prev_volume = v
        suck_total += suck_s
        blow_total += blow_s
        cycle_dt = time.perf_counter() - cycle_start
        print(f"[host] cycle {n} wall-clock: {cycle_dt:.2f} s")
        _phase_comment(gcode_out, f"; cycle {n} wall-clock: {cycle_dt:.2f} s\n")
    tour_dt = time.perf_counter() - tour_start
    dpette_total = suck_total + blow_total
    print(
        f"\n[host] phase 2 done: {tour_dt:.1f} s total"
        f" ({dpette_total:.1f} s dPette / {tour_dt - dpette_total:.1f} s gantry)"
    )
    _phase_comment(
        gcode_out,
        f"; phase 2 total: {tour_dt:.1f} s "
        f"({dpette_total:.1f} s dPette / {tour_dt - dpette_total:.1f} s gantry)\n",
    )

    _phase_comment(
        gcode_out,
        "\n; ===== phase 3: park towards home corner then G28 =====\n"
        "; at end of last cycle head sits at (X=5, Y=220, Z=115).\n"
        "; max safe Z near home is the bar's bottom edge — clear X first,\n"
        "; then diagonal descent below bar towards the home corner,\n"
        "; then home.\n",
    )
    gsend(link, f"G1 X{PARK_CLEARANCE_X:.3f} F{XY_FEED}", gcode_out=gcode_out)
    gsend(link, f"G1 Z{PARK_INTERMEDIATE_Z:.3f} F{Z_FEED}", gcode_out=gcode_out)
    gsend(
        link,
        f"G1 Z{PARK_BELOW_BAR_Z:.3f} X{PARK_FINAL_X:.3f} Y{PARK_FINAL_Y:.3f} F{Z_FEED}",
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
            f"ERROR: NUM_CYCLES must be in {MIN_NUM_CYCLES}..{MAX_NUM_CYCLES}, got {n}.\n"
            f"       Cap is temporarily {MAX_NUM_CYCLES} — the current\n"
            f"       bed/plate part layout is not safety-compliant for N>{MAX_NUM_CYCLES}:\n"
            f"       tip-box and well-plate footprints clash with fixtures on\n"
            f"       the bed past that point. Restore to 12 only after the bed\n"
            f"       layout is re-arranged and re-measured."
        )
    return n


def _describe_mode(have_gantry: bool, have_pipette: bool) -> str:
    if have_gantry and have_pipette:
        return "FULL — real gantry + real dPette"
    if have_gantry:
        return "GANTRY ONLY — dPette ops skipped (PIPETTE_PORT unset)"
    if have_pipette:
        return "DPETTE ONLY — gantry moves skipped (I3MEGA_PORT unset)"
    return "DRY RUN — both serial skipped; G-code tee only"


def main() -> int:
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return 0
    port = os.environ.get("I3MEGA_PORT", "").strip()
    pipette_port = os.environ.get("PIPETTE_PORT", "").strip()
    baud = int(os.environ.get("I3MEGA_BAUD", str(DEFAULT_BAUD)))
    pipette_baud = int(os.environ.get("PIPETTE_BAUD", str(DEFAULT_PIPETTE_BAUD)))
    num_cycles_env = _resolve_num_cycles()
    volumes_ul, banner = build_volumes(num_cycles_env, "cycles")
    if len(volumes_ul) > num_cycles_env:
        sys.stderr.write(
            f"ERROR: PIPETTE_PROFILE has {len(volumes_ul)} cycles but NUM_CYCLES\n"
            f"       is {num_cycles_env} (safety cap {MAX_NUM_CYCLES}). The profile\n"
            f"       must not exceed the env-supplied cycle count — trim the\n"
            f"       profile, raise NUM_CYCLES, or both.\n"
        )
        return 1
    num_cycles = len(volumes_ul)
    total_ul = sum(volumes_ul) * 8
    gcode_path = os.environ.get("OUTPUT_GCODE", DEFAULT_GCODE_OUT)

    print(f"[host] mode: {_describe_mode(bool(port), bool(pipette_port))}")
    print(f"[host] {banner}")
    print(
        f"[host] row tour: {num_cycles} cycles "
        f"× 8 channels = {num_cycles * 8} wells, {total_ul:.0f} uL total"
    )

    link: serial.Serial | None = None
    if port:
        link = open_marlin_port(port, baudrate=baud, timeout=2.0)
        if link is None:
            sys.stderr.write(
                f"ERROR: could not open Marlin port {port} @ {baud}.\n"
                "       Run `uv run tools/preflight.py` to verify.\n"
            )
            return 1

    pipette: DPetteDriver | None = None
    if pipette_port:
        print(f"[host] connecting dPette on {pipette_port} @ {pipette_baud}")
        pipette = DPetteDriver(SerialConfig(port=pipette_port, baudrate=pipette_baud))
        pipette.connect()  # A0 HELLO → B0 WOL (PI mode) → motor homes
        if pipette.stub_mode:
            sys.stderr.write(
                f"ERROR: dPette on {pipette_port} fell back to stub mode.\n"
                "       Wake it (press its button), replug, and retry.\n"
            )
            if link is not None:
                link.close()
            return 1

    try:
        if link is not None:
            with link:
                print(f"[host] open {port} @ {baud}; waiting 3s for Marlin boot")
                time.sleep(3)
                link.reset_input_buffer()
                _execute(link, pipette, volumes_ul, gcode_path)
        else:
            _execute(None, pipette, volumes_ul, gcode_path)
        print("[host] done")
    finally:
        if pipette is not None:
            pipette.disconnect()
    return 0


def _execute(
    link: serial.Serial | None,
    pipette: DPetteDriver | None,
    volumes_ul: tuple[float, ...],
    gcode_path: str,
) -> None:
    if gcode_path:
        print(f"[host] tee G-code stream to {gcode_path}")
        with open(gcode_path, "w") as gf:
            _run(link, pipette, volumes_ul, gf)
    else:
        _run(link, pipette, volumes_ul, None)


if __name__ == "__main__":
    sys.exit(main())
