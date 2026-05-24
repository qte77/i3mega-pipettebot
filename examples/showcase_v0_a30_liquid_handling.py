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
    PIPETTE_PORT   dPette USB-serial path. Same source.

Deck-geometry overrides (defaults are A30-sized, ~320x320 bed, well
positions inset by ~80 mm from edges — adjust to your physical layout):

    SOURCE_X / SOURCE_Y    Aspirate well (mm). Default 160 / 80.
    DEST_X   / DEST_Y      Dispense well (mm). Default 160 / 240.
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

# A30 deck-frame defaults — operator-overridable via env.
DEFAULT_SOURCE_X = 160.0
DEFAULT_SOURCE_Y = 80.0
DEFAULT_DEST_X = 160.0
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
    if not port or not pipette_port:
        sys.stderr.write(
            f"ERROR: set {PRINTER_PORT_ENV} and PIPETTE_PORT (run "
            "`tools/preflight.py --export`).\n"
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

    pipette = DPetteDriver(SerialConfig(port=pipette_port))
    pipette.connect()

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
            safe_home(gantry, policy)
            # Lift to travel altitude before the first XY move so the tip
            # clears any obstacle the operator placed near the Z origin.
            gantry.send(f"G1 Z{travel_z:.3f} F1200")
            gantry.wait_for_moves()

            for n, vol in enumerate(volumes, start=1):
                print(f"\n[host] ====== cycle {n}/{len(volumes)} ======")
                transfer_cycle(gantry, bot, source, dest, well_z, travel_z, vol)

            print("\n[host] done — parking at travel altitude over destination")
    finally:
        pipette.disconnect()

    return 0


if __name__ == "__main__":
    sys.exit(main())
