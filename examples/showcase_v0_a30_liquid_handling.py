"""Hardware liquid-handling cycle on the Geeetech A30 + dPette.

End-to-end demo that exercises the full A30 stack: firmware discovery,
M203/M204/M205 motion-profile caps, automatic Z homing via polled
descent (firmware `G28 Z` is broken on stock Smartto builds), N
transfer cycles with split-feedrate dives, post-cycle re-home for
origin verification, and a park at (0, 0, 0).

Execution outline:

1. `tools/preflight.py --export` discovers `PRINTER_PORT` (+ optionally
   `PIPETTE_PORT`); operator runs this script via shell eval.
2. Apply MOTION_PROFILE (M203 caps + M204 accel + M205 jerk).
3. Pre-home Z lift (20 mm) so the inductive sensor reads OPEN, forcing
   `safe_home` to run a fresh polled descent every invocation rather
   than short-circuiting on a still-triggered sensor from a prior home.
4. `safe_home`: `G28 X Y`, then absolute-mode polled-Z descent
   (G92 Z<max> + G1 Z<absolute> + M119 polling + G92 Z0 at trigger).
   See `docs/research/gantry-firmware-alternatives.md` for why this
   replaces firmware `G28 Z`.
5. Linger 3 s at Z=0 for visual verification (LED should be on).
6. Lift to TRAVEL_Z, then N transfer cycles. Each cycle uses the
   Z-first pattern (lift -> XY at TRAVEL_Z -> dive -> op -> lift) with
   a split-feedrate dive: fast (`Z_FAST_FEED`) until
   `TOUCHDOWN_APPROACH_MM` above target, slow (`LIQUID_DIVE_FEED`) for
   the last leg of meniscus contact. Same pattern as
   `showcase_v0_i3_full_pipettebot_rows.py`.
7. Post-cycle Z-only re-home (`safe_home(..., home_xy=False)`): skips
   `G28 X Y` because XY is already at the bootstrap home and Smartto's
   M400 race can stall a fresh `G28 X Y` ack after the cycle queue.
   Just runs the polled descent for origin verification.
8. Linger 3 s at Z=0 (second visual check — confirms no drift).
9. Park at (0, 0, 0): XY move to home corner at Z=0, no lift. The
   carriage finishes at the known-good sensor reference.

Required environment variables:

    PRINTER_PORT   Gantry USB-serial path. Set by `tools/preflight.py
                   --export` or manually.

Optional environment variables:

    PIPETTE_PORT   dPette USB-serial path. When unset the script runs in
                   GANTRY-ONLY mode: motion executes for real but
                   aspirate/dispense calls become log-only stubs. Use
                   this to validate A30 motion before mounting the
                   dPette on the carriage (payload budget unmeasured —
                   `docs/research/gantry-firmware-alternatives.md`
                   unknown #5).
    MOTION_PROFILE `slow` / `mid` / `fast` / `off`. Default `mid`. A30
                   supports M203/M204/M205; bundled profiles apply
                   verbatim. See ADR 0003.
    NUM_CYCLES     Default cycle count when no profile. Default 2.
    PIPETTE_PROFILE  Path to an experiment-profile TOML (overrides
                   cycle count + per-cycle volume).
    PIPETTE_VOLUME_UL  Constant per-cycle volume. Default 100.0.

Deck-geometry overrides (defaults are A30-sized, ~320x320 bed; SOURCE
and DEST sit at diagonal corners so each cycle exercises both X and Y):

    SOURCE_X / SOURCE_Y    Aspirate well (mm). Default 80 / 80
                           (back-left corner area).
    DEST_X   / DEST_Y      Dispense well (mm). Default 240 / 240
                           (front-right corner area).
    WELL_Z                 Tip depth at well (mm above sensor Z=0).
                           Default 5.0.
    TRAVEL_Z               Safe transit altitude (mm). Default 60.0.

Per-leg feedrates (constants in this module — operator can edit but
not env-overridable yet; under the M203 caps from MOTION_PROFILE):

    XY_FEED              100 mm/s — cross-deck XY transit.
    Z_FAST_FEED          20 mm/s — lifts, pre-home lift, fast portion
                         of every dive.
    LIQUID_DIVE_FEED     10 mm/s — meniscus contact (last leg).
    TOUCHDOWN_APPROACH_MM 10 mm — Z above target at which the dive
                         splits from fast to slow.

**Safety**: this script drops the tip to `WELL_Z` at (SOURCE_X,
SOURCE_Y) and (DEST_X, DEST_Y). The Z origin is the sensor's
calibrated trigger point (declared by `safe_home`'s polled descent).
`WELL_Z=5.0` descends 5 mm below the sensor — verify your physical
setup has headroom there. v0 has no software soft-limit enforcement
(see `.claude/rules/motion-safety.md`).

**dPette mount**: GANTRY-ONLY mode (no PIPETTE_PORT) is safe for
validating motion before mounting the dPette. A30 carriage payload
budget is unmeasured — `docs/research/gantry-firmware-alternatives.md`
unknown #5 — operator confirms mount before running with PIPETTE_PORT
set.
"""

from __future__ import annotations

import os
import sys
import time

from dpette import DPetteDriver, SerialConfig

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

# --- Per-leg feedrates (under the M203 caps applied by MOTION_PROFILE) -----
# Pattern mirrors examples/showcase_v0_i3_full_pipettebot_rows.py:
# fast where motion is over open deck, slow where the tip approaches
# liquid or a contact surface.
XY_FEED = 6000  # 100 mm/s — cross-deck XY transit
Z_FAST_FEED = 1200  # 20 mm/s — at the M203 Z20 cap; safe lifts and
# the initial portion of every dive
# Per-dive Z slowdowns — applied only on the DESCENT into the well's
# last leg. Lifts always use Z_FAST_FEED (no damage risk on the way up).
LIQUID_DIVE_FEED = 600  # 10 mm/s — meniscus / well contact

# Touchdown split — descend at Z_FAST_FEED until this distance above the
# target Z, then drop to LIQUID_DIVE_FEED for the final approach. Cuts
# per-cycle wall-clock without paying the slow feedrate for the whole
# dive. See ADR 0003 + the i3 rows showcase for the pattern's origin.
TOUCHDOWN_APPROACH_MM = 10.0

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
# Linger at Z=0 after each safe_home so the operator can visually verify
# the carriage lands on the sensor's calibrated trigger point.
HOME_LINGER_S = 3.0


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


def _split_dive(
    gantry: GcodeGantry, x: float, y: float, well_z: float, travel_z: float
) -> None:
    """Two-stage descent: Z_FAST_FEED for approach, LIQUID_DIVE_FEED for last leg.

    Caller has just transitted XY at travel_z. We then drop fast to the
    approach altitude (well_z + TOUCHDOWN_APPROACH_MM) and slow to well_z
    for the final mm of meniscus contact. If the dive is shorter than the
    approach distance (e.g. well_z near travel_z), skips straight to the
    slow leg.
    """
    approach_z = well_z + TOUCHDOWN_APPROACH_MM
    if approach_z < travel_z:
        gantry.move_to(x, y, approach_z, feedrate=Z_FAST_FEED)
        gantry.wait_for_moves()
    gantry.move_to(x, y, well_z, feedrate=LIQUID_DIVE_FEED)
    gantry.wait_for_moves()


def transfer_cycle(
    gantry: GcodeGantry,
    pipette: DPetteDriver | _LoggingPipette,
    source: tuple[float, float],
    dest: tuple[float, float],
    well_z: float,
    travel_z: float,
    volume_ul: float,
) -> None:
    """Z-first aspirate at `source`, transit, Z-first dispense at `dest`.

    Z-first pattern (lift -> XY at travel altitude -> dive -> op -> lift)
    keeps the tip above every deck obstacle during transit. The dive uses
    the split-feedrate pattern from `showcase_v0_i3_full_pipettebot_rows`:
    fast (Z_FAST_FEED) until `TOUCHDOWN_APPROACH_MM` above the target,
    then slow (LIQUID_DIVE_FEED) for the last leg into the meniscus. Lifts
    use Z_FAST_FEED throughout — no contact risk on the way up.

    Pipette ops fire only after the dive completes (motion-safety.md rule:
    "wait for moves before pipetting"). Bypasses `PipetteBot.aspirate_at`
    so the per-leg feedrates are visible at the call site rather than
    hidden inside a single-move composer.
    """
    sx, sy = source
    dx, dy = dest
    print(
        f"[host] cycle: aspirate {volume_ul:.1f} uL @ ({sx},{sy}) "
        f"-> dispense @ ({dx},{dy})"
    )
    # 1. Transit to source at travel altitude (fast XY).
    gantry.move_to(sx, sy, travel_z, feedrate=XY_FEED)
    gantry.wait_for_moves()
    # 2. Split-feedrate dive into source well + aspirate.
    _split_dive(gantry, sx, sy, well_z, travel_z)
    pipette.aspirate(volume_ul)
    # 3. Lift before transit — tip-above-liquid rule (motion-safety.md).
    gantry.move_to(sx, sy, travel_z, feedrate=Z_FAST_FEED)
    gantry.wait_for_moves()
    # 4. Transit to destination at travel altitude.
    gantry.move_to(dx, dy, travel_z, feedrate=XY_FEED)
    gantry.wait_for_moves()
    # 5. Split-feedrate dive into destination well + dispense.
    _split_dive(gantry, dx, dy, well_z, travel_z)
    pipette.dispense(volume_ul)
    # 6. Lift back to travel altitude — ready for the next cycle.
    gantry.move_to(dx, dy, travel_z, feedrate=Z_FAST_FEED)
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
            gantry.send(f"G1 Z{PRE_HOME_LIFT_MM:.3f} F{Z_FAST_FEED}")
            gantry.wait_for_moves()
            # Smartto M400 race: block for motion time + margin so the lift
            # is physically complete before safe_home polls M119.
            time.sleep(PRE_HOME_LIFT_MM / (Z_FAST_FEED / 60.0) + 1.5)
            safe_home(gantry, policy)
            print(
                f"[host] lingering at Z=0 (sensor trigger) for "
                f"{HOME_LINGER_S:.0f} s — verify carriage is at the LED point"
            )
            time.sleep(HOME_LINGER_S)
            # Lift to travel altitude before the first XY move so the tip
            # clears any obstacle the operator placed near the Z origin.
            gantry.send(f"G1 Z{travel_z:.3f} F{Z_FAST_FEED}")
            gantry.wait_for_moves()

            for n, vol in enumerate(volumes, start=1):
                print(f"\n[host] ====== cycle {n}/{len(volumes)} ======")
                transfer_cycle(gantry, pipette, source, dest, well_z, travel_z, vol)

            # Z-only re-home after the cycles: confirms the origin is
            # still at the sensor (no drift / accidental loss of
            # reference) and gives the operator a second visible Z=0
            # verification. home_xy=False skips the G28 X Y because XY
            # is already homed from the bootstrap and Smartto's M400
            # race can leave the cycle's queued moves blocking a fresh
            # G28 X Y from completing within the ack timeout. Before
            # the descent: drain the firmware motion queue explicitly
            # (long-timeout M400) — without G28 X Y as a sync barrier,
            # the first G92 inside safe_home was timing out at the
            # default 30 s ack window while the firmware finished
            # cycle motion. 5 s sleep then 120 s M400 ack window covers
            # the deepest plausible queue depth.
            print("\n[host] draining firmware motion queue before post-cycle home")
            time.sleep(5.0)
            gantry.wait_for_moves(max_secs=120.0)
            print("[host] post-cycle Z verification (polled descent only)")
            safe_home(gantry, policy, home_xy=False)
            print(
                f"[host] lingering at Z=0 for {HOME_LINGER_S:.0f} s "
                "— post-cycle home verification"
            )
            time.sleep(HOME_LINGER_S)

            # End-of-run park at full origin (0, 0, 0): XY moves to the
            # home corner while Z stays at the sensor trigger. No lift —
            # the carriage finishes at the known-good Z=0 reference
            # rather than at travel altitude.
            print("\n[host] parking at (0, 0, 0) — Z stays at sensor")
            gantry.move_to(0.0, 0.0, 0.0, feedrate=XY_FEED)
            gantry.wait_for_moves()
            time.sleep(PARK_SETTLE_S)
            print("[host] done — carriage at (0, 0, 0)")
    finally:
        if isinstance(pipette, DPetteDriver):
            pipette.disconnect()

    return 0


if __name__ == "__main__":
    sys.exit(main())
