"""Home the Geeetech A30 via `safe_home` and exit — no motion afterwards.

Counterpart to `home_G28_fast_i3.py` but for the Smartto firmware path:
sends `G28 X Y`, then absolute-mode polled-Z descent (`G92 Z<max>`, loop
[`G1 Z<target> F300`, `M119`, break-on-`z_min:TRIGGERED`], `G92 Z0`).
Uses the *working* inductive `z_min` sensor — firmware `G28 Z` is broken
on this build but `M119` correctly reports the sensor state.

Applies the motion profile (M203/M204/M205 caps + jerk) before
`safe_home` because Smartto's default Z motion parameters (no caps set)
make the polled descent's M119 polling unreliable on the live A30 —
matches the showcase's pattern. Operator can opt out via
`MOTION_PROFILE=off` but the smartto path may not home reliably without
caps applied.

Use this when you want a known-good Z=0 reference before running a
showcase, jogging via `tools/gantry_repl.py`, or any motion test.

Required environment variables:

    PRINTER_PORT     Gantry USB-serial path. Run `tools/preflight.py
                     --export` first, or set manually.

Optional environment variables:

    MOTION_PROFILE   `slow` / `mid` / `fast` / `off`. Default `mid`.
                     See ADR 0003. On smartto, the caps applied here
                     are required for reliable polled descent.

Pre-conditions for safe polled descent:

    The carriage must start ABOVE the z_min sensor's trigger zone, OR
    already triggered (in which case the descent loop is skipped and
    origin is declared immediately). Typical power-up state — carriage
    near the top — satisfies this. If you've left the carriage near the
    bed, raise it first via `tools/gantry_repl.py`.

Safety:

    - Polled descent moves Z down 1 mm at a time at 300 mm/min (5 mm/s).
      The mechanical Z-min hardstop, the sensor itself, and the max-step
      cap (250 mm = full A30 Z travel) are the three layers preventing
      runaway.
    - On Marlin (i3 Mega) this script issues a plain `G28` — same effect
      as `home_G28_fast_i3.py` minus the motion-profile bootstrap.
    - Power switch remains the only stop authority during motion.
"""

from __future__ import annotations

import os
import sys
import time

from pipettebot.devices import (
    PRINTER_PORT_ENV,
    discover,
    policy_for,
    resolve_port,
    safe_home,
)
from pipettebot.gantry import GantryConfig, GcodeGantry, open_gcode_port
from pipettebot.motion_profile import select_profile

BOOT_WAIT_S = 3.0
# Pre-home Z lift: force safe_home's polled descent to run every
# invocation, even when Z is already at the sensor from a prior home.
# Without this, the pre-loop M119 short-circuits to G92 Z0 and the
# operator sees no descent. 5 mm clears the inductive sensor's
# detection zone (operator-validated on live A30). Same value as the
# A30 liquid-handling showcase.
PRE_HOME_LIFT_MM = 5.0
PRE_HOME_LIFT_FEEDRATE = 1200  # 20 mm/s — at the M203 Z cap


def _apply_motion_profile(gantry: GcodeGantry) -> None:
    """Send M203/M204/M205 caps so polled-Z descent has predictable motion."""
    profile = select_profile(os.environ.get("MOTION_PROFILE"))
    if profile is None:
        print("[host] motion profile: SKIPPED (MOTION_PROFILE opt-out)")
        return
    print(f"[host] motion profile: {profile.name}")
    for cmd in profile.as_marlin():
        gantry.send(cmd)


def main() -> int:
    port = resolve_port()
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
    print(f"[host] home strategy: {policy.home_strategy}")

    link = open_gcode_port(port, baudrate=device.baud, timeout=2.0)
    if link is None:
        sys.stderr.write(f"ERROR: could not open {port} @ {device.baud}.\n")
        return 1

    with link:
        print(f"[host] open {port} @ {device.baud}; waiting {BOOT_WAIT_S}s for boot")
        time.sleep(BOOT_WAIT_S)
        link.reset_input_buffer()
        gantry = GcodeGantry(GantryConfig(port=port, baudrate=device.baud), link)
        _apply_motion_profile(gantry)
        # Force fresh descent: lift Z 20 mm so safe_home's pre-loop M119
        # reads OPEN even if Z is at the sensor from a prior run.
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
        try:
            safe_home(gantry, policy)
        except RuntimeError as e:
            sys.stderr.write(f"ERROR: safe_home failed: {e}\n")
            return 1
        print("[host] homed — Z=0 declared at the sensor trigger point")

    return 0


if __name__ == "__main__":
    sys.exit(main())
