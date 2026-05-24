"""Hardware liquid-handling cycle on the Geeetech A30 + dPette.

Drives the A30 gantry (Smartto firmware) through N transfer cycles:

1. Travel above source well at TRAVEL_Z.
2. Descend to WELL_Z, aspirate from dPette.
3. Lift to TRAVEL_Z.
4. Travel above destination well at TRAVEL_Z.
5. Descend to WELL_Z, dispense.
6. Lift to TRAVEL_Z.

Uses the library `safe_home` so the Smartto `xy_then_polled_z` path runs
(`G28 X Y` + operator-confirms Z origin + `G92 Z0`). Plain `G28` would
crash Z into the bed on stock A30 builds — see
`docs/research/gantry-firmware-alternatives.md` (2026-05-23).

Required environment variables:

    PRINTER_PORT   Gantry USB-serial path. Set by `tools/preflight.py
                   --export` or manually.

Optional environment variables:

    PIPETTE_PORT   dPette USB-serial path. When unset the script runs in
                   GANTRY-ONLY mode: motion executes for real but
                   aspirate/dispense calls become log-only stubs. Use this
                   to validate A30 motion before mounting the dPette on
                   the carriage (payload budget is unmeasured — see
                   `docs/research/gantry-firmware-alternatives.md`
                   unknown #5).

Deck-geometry overrides (defaults are A30-sized, ~320x320 bed, well
positions inset by ~80 mm from each edge — adjust to your physical
layout). The defaults place SOURCE and DEST at diagonal corners so a
single cycle exercises both X and Y travel, not just one axis:

    SOURCE_X / SOURCE_Y    Aspirate well (mm). Default 80 / 80
                           (back-left corner area).
    DEST_X   / DEST_Y      Dispense well (mm). Default 240 / 240
                           (front-right corner area).
    WELL_Z                 Tip depth into well (mm above operator Z=0).
                           Default 5.0.
    TRAVEL_Z               Safe transit altitude (mm). Default 60.0.

Volume / cycle count (shared with the other showcases via
`pipettebot.cli_profile.build_volumes`):

    PIPETTE_PROFILE       Path to an experiment-profile TOML (overrides
                          cycle count + per-cycle volume).
    PIPETTE_VOLUME_UL     Constant per-cycle volume. Default 100.0.
    NUM_CYCLES            Default cycle count when no profile. Default 2.

Motion profile (shared with the other showcases):

    MOTION_PROFILE        `slow` / `mid` / `fast` / `off`. Default `mid`.
                          A30 supports M203/M204/M205 — bundled profiles
                          apply verbatim. See ADR 0003.

**Safety**: this script drops the tip to `WELL_Z` at (SOURCE_X, SOURCE_Y)
and (DEST_X, DEST_Y). The Z origin is whatever the operator confirmed
during `safe_home` — `WELL_Z=5.0` descends 5 mm below that. Pick a Z
origin with enough headroom for your tipped dPette. v0 has no software
soft-limit enforcement (see `.claude/rules/motion-safety.md`).

**dPette mount**: this script assumes the dPette is mounted on the A30
carriage and within payload budget. A30 carriage payload budget is
unmeasured (`docs/research/gantry-firmware-alternatives.md` unknown #5)
— operator confirms before running.
"""

from __future__ import annotations

import os
import sys
import time

from dpette import DPetteDriver, SerialConfig

from pipettebot.bot import PipetteBot
from pipettebot.cli_profile import build_volumes
from pipettebot.devices import (
    PRINTER_PORT_ENV,
    discover,
    policy_for,
    resolve_port,
    safe_home,
)
from pipettebot.gantry import GantryConfig, GcodeGantry, open_gcode_port
from pipettebot.motion_profile import select_profile

DEFAULT_NUM_CYCLES = 2
DEFAULT_PIPETTE_BAUD = 9600
DEFAULT_TRANSIT_FEEDRATE = 6000  # 100 mm/s
# Smartto's M400 sometimes returns ack before motion completes; sleep
# this long after the final park so the `with gantry_link:` block doesn't
# close the port mid-motion. Worst-case bed-diagonal at 100 mm/s ~= 4.5 s.
PARK_SETTLE_S = 6.0
# Pre-home Z lift: force safe_home's polled descent to run every demo
# invocation, even if Z is already at the sensor from a prior home. The
# lift overrides any earlier G92 Z origin; safe_home re-establishes Z=0
# at the sensor trigger after descending. 20 mm clears the inductive
# sensor's detection zone (~1-3 mm) with margin to spare.
PRE_HOME_LIFT_MM = 20.0
PRE_HOME_LIFT_FEEDRATE = 1200  # 20 mm/s (at the M203 Z cap)


class _LoggingPipette:
    """Stub pipette for gantry-only runs. Satisfies the `_Pipette` protocol."""

    def aspirate(self, volume_ul: float = 0.0) -> None:
        print(f"[host] (sim) aspirate {volume_ul:.1f} uL — no dPette wired")

    def dispense(self, volume_ul: float = 0.0) -> None:
        _ = volume_ul
        print("[host] (sim) dispense — no dPette wired")


# A30 deck-frame defaults — operator-overridable via env. SOURCE and
# DEST sit at diagonal corners (back-left vs. front-right) so each cycle
# crosses ~160 mm in X AND ~160 mm in Y — validates both axes per pass.
DEFAULT_SOURCE_X = 80.0
DEFAULT_SOURCE_Y = 80.0
DEFAULT_DEST_X = 240.0
DEFAULT_DEST_Y = 240.0
DEFAULT_WELL_Z = 5.0
DEFAULT_TRAVEL_Z = 60.0


def _coord(name: str, default: float) -> float:
    return float(os.environ.get(name, str(default)))


def _read_deck() -> tuple[tuple[float, float], tuple[float, float], float, float]:
    """Return ((source_x, source_y), (dest_x, dest_y), well_z, travel_z)."""
    source = (
        _coord("SOURCE_X", DEFAULT_SOURCE_X),
        _coord("SOURCE_Y", DEFAULT_SOURCE_Y),
    )
    dest = (_coord("DEST_X", DEFAULT_DEST_X), _coord("DEST_Y", DEFAULT_DEST_Y))
    well_z = _coord("WELL_Z", DEFAULT_WELL_Z)
    travel_z = _coord("TRAVEL_Z", DEFAULT_TRAVEL_Z)
    return source, dest, well_z, travel_z


def transfer_cycle(
    gantry: GcodeGantry,
    bot: PipetteBot,
    source: tuple[float, float],
    dest: tuple[float, float],
    well_z: float,
    travel_z: float,
    volume_ul: float,
) -> None:
    """Z-first aspirate at `source`, transit, Z-first dispense at `dest`.

    The Z-first pattern (lift -> XY at travel altitude -> pure Z dive) keeps
    the tip above every deck obstacle during transit. `PipetteBot.aspirate_at`
    and `dispense_at` issue a single `G1 X Y Z` move; with X/Y already at the
    target the move is effectively pure-Z, which is the safe descent.
    """
    sx, sy = source
    dx, dy = dest
    print(
        f"[host] cycle: aspirate {volume_ul:.1f} uL @ ({sx},{sy}) -> dispense @ ({dx},{dy})"
    )
    # Transit to source at travel altitude.
    gantry.move_to(sx, sy, travel_z, feedrate=DEFAULT_TRANSIT_FEEDRATE)
    gantry.wait_for_moves()
    # Pure-Z dive + aspirate (wait_for_moves is inside aspirate_at).
    bot.aspirate_at(sx, sy, well_z, volume_ul)
    # Lift before transit — tip-above-liquid rule (motion-safety.md).
    gantry.move_to(sx, sy, travel_z, feedrate=DEFAULT_TRANSIT_FEEDRATE)
    gantry.wait_for_moves()
    # Transit to destination at travel altitude.
    gantry.move_to(dx, dy, travel_z, feedrate=DEFAULT_TRANSIT_FEEDRATE)
    gantry.wait_for_moves()
    # Pure-Z dive + dispense.
    bot.dispense_at(dx, dy, well_z)
    # Lift back to travel altitude — ready for the next cycle or park.
    gantry.move_to(dx, dy, travel_z, feedrate=DEFAULT_TRANSIT_FEEDRATE)
    gantry.wait_for_moves()


def _apply_motion_profile(gantry: GcodeGantry) -> None:
    profile = select_profile(os.environ.get("MOTION_PROFILE"))
    if profile is None:
        print("[host] motion profile: SKIPPED (MOTION_PROFILE opt-out)")
        return
    print(f"[host] motion profile: {profile.name}")
    for cmd in profile.as_marlin():
        gantry.send(cmd)


def main() -> int:
    port = resolve_port()
    pipette_port = os.environ.get("PIPETTE_PORT")
    if not port:
        sys.stderr.write(
            f"ERROR: set {PRINTER_PORT_ENV} (run `tools/preflight.py --export`).\n"
        )
        return 1

    device = discover(port)
    if device is None:
        sys.stderr.write(f"ERROR: no firmware answered on {port}.\n")
        return 1
    policy = policy_for(device)
    print(
        f"[host] discovered: {device.firmware_family} "
        f"({device.machine_type or '?'}, fw {device.firmware_version or '?'}) "
        f"@ {device.baud}"
    )
    if policy.family != "smartto":
        print(
            f"[host] WARNING: this script targets the A30 (smartto) but found "
            f"'{policy.family}'. The Z-origin prompt and deck defaults still "
            "apply; press Ctrl-C if you wanted a different printer."
        )

    gantry_link = open_gcode_port(port, baudrate=device.baud, timeout=2.0)
    if gantry_link is None:
        sys.stderr.write(f"ERROR: could not open {port} @ {device.baud}.\n")
        return 1

    pipette: DPetteDriver | _LoggingPipette
    if pipette_port:
        pipette = DPetteDriver(SerialConfig(port=pipette_port))
        pipette.connect()
    else:
        print(
            "[host] GANTRY-ONLY mode — PIPETTE_PORT unset; aspirate/dispense "
            "calls will log but not actuate any pipette."
        )
        pipette = _LoggingPipette()

    source, dest, well_z, travel_z = _read_deck()
    print(
        f"[host] deck: source=({source[0]},{source[1]}) dest=({dest[0]},{dest[1]}) "
        f"well_z={well_z} travel_z={travel_z}"
    )

    num_cycles = int(os.environ.get("NUM_CYCLES", str(DEFAULT_NUM_CYCLES)))
    volumes, banner = build_volumes(default_count=num_cycles, unit_label="cycles")
    print(f"[host] volume schedule: {banner}")

    try:
        with gantry_link:
            print(f"[host] open {port} @ {device.baud}; waiting 3s for firmware boot")
            time.sleep(3)
            gantry_link.reset_input_buffer()
            gantry = GcodeGantry(
                GantryConfig(port=port, baudrate=device.baud), gantry_link
            )
            bot = PipetteBot(gantry, pipette)

            _apply_motion_profile(gantry)
            # Force fresh polled descent every run: lift Z so the sensor
            # reads OPEN at safe_home's pre-loop check, even if Z is at
            # the trigger from a prior home. Temporary G92 Z0 sets a
            # local frame (safe_home redeclares it after the descent).
            # See PRE_HOME_LIFT_* constants for sizing rationale.
            print(
                f"[host] lifting Z {PRE_HOME_LIFT_MM:.0f} mm so safe_home runs a "
                "fresh descent (otherwise pre-loop M119 may short-circuit)"
            )
            gantry.send("G92 Z0")
            gantry.send(f"G1 Z{PRE_HOME_LIFT_MM:.3f} F{PRE_HOME_LIFT_FEEDRATE}")
            gantry.wait_for_moves()
            # Smartto M400 race: block for motion time + margin so the lift
            # is physically complete before safe_home polls M119.
            time.sleep(PRE_HOME_LIFT_MM / (PRE_HOME_LIFT_FEEDRATE / 60.0) + 1.5)
            safe_home(gantry, policy)
            # Lift to travel altitude before the first XY move so the tip
            # clears any obstacle the operator placed near the Z origin.
            gantry.send(f"G1 Z{travel_z:.3f} F1200")
            gantry.wait_for_moves()

            for n, vol in enumerate(volumes, start=1):
                print(f"\n[host] ====== cycle {n}/{len(volumes)} ======")
                transfer_cycle(gantry, bot, source, dest, well_z, travel_z, vol)

            # End-of-run park at the home corner. Z stays at travel_z
            # (tip lifted above origin) and XY returns to (0, 0) — the
            # known reference established by safe_home. Mirrors the
            # "always finish at a known state" pattern in the i3
            # showcases.
            print("\n[host] parking at home corner (0, 0) at travel altitude")
            gantry.move_to(0.0, 0.0, travel_z, feedrate=DEFAULT_TRANSIT_FEEDRATE)
            gantry.wait_for_moves()
            time.sleep(PARK_SETTLE_S)
            print("[host] done")
    finally:
        if isinstance(pipette, DPetteDriver):
            pipette.disconnect()

    return 0


if __name__ == "__main__":
    sys.exit(main())
