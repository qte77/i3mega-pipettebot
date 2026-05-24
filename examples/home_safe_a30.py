"""Home the Geeetech A30 via `safe_home` and exit — no motion afterwards.

Counterpart to `home_G28_fast_i3.py` but for the Smartto firmware path:
sends `G28 X Y`, then polled-Z descent (`G91`, loop[`G1 Z-1 F300`, `M119`,
break-on-`z_min:TRIGGERED`], `G90`, `G92 Z0`). Uses the *working*
inductive `z_min` sensor — firmware `G28 Z` is broken on this build but
`M119` correctly reports the sensor state.

Use this when you want a known-good Z=0 reference before running a
showcase, jogging via `tools/gantry_repl.py`, or any motion test.

Required environment variables:

    PRINTER_PORT     Gantry USB-serial path. Run `tools/preflight.py
                     --export` first, or set manually.

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

BOOT_WAIT_S = 3.0


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
        try:
            safe_home(gantry, policy)
        except RuntimeError as e:
            sys.stderr.write(f"ERROR: safe_home failed: {e}\n")
            return 1
        print("[host] homed — Z=0 declared at the sensor trigger point")

    return 0


if __name__ == "__main__":
    sys.exit(main())
