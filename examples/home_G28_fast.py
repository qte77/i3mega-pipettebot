"""Hardware-motion: home → end at Marlin default home (0, 0, 0), ~2× faster than G28.

Stock Marlin 1.1.x (MARLIN-AI3M) homes Z at the compile-time
`HOMING_FEEDRATE_Z` (4 mm/s) and ignores `M203` during homing. Full
`G28` therefore takes ~20 s on the i3 Mega, dominated by the Z
leadscrew move. This script gets the same end state (X=0, Y=0, Z=0)
in roughly half the time by replacing the slow `G28 Z` with a fast
`G1 Z0` after `G28 X Y`:

    1. M203 / M201 bump      → bump caps to 20 mm/s / 200 mm/s² for Z
                               (matches the showcase; conservative
                               values to avoid skipped steps)
    2. G1 Z 30 (defensive)   → small lift if Z is currently low, so XY
                               home doesn't drag a loaded tip
    3. G28 X Y               → home X and Y via endstops (the fast part)
    4. G1 Z 0                → move Z to default home altitude (no endstop)

End state: (X=0, Y=0, Z=0) ≡ Marlin default home.

Caveats
-------

- Step 4 trusts the tracked Z position rather than re-referencing the
  endstop. If Z has drifted (steps lost, manual axis movement),
  the Z=0 here may be off. Run a full `G28` manually to re-reference.
- Z=0 is calibrated to tip-end-on-deck WITH tips loaded
  (docs/calibration.md). Any tip still loaded ends up parked on the
  deck — same as full `G28`'s Z homing terminus.
- Requires Z to have been referenced earlier in the session. Marlin
  refuses G1 on un-homed axes, so step 2 will error on a freshly
  power-cycled printer. In that case, run a full `G28` manually first.

Required environment variable:

    I3MEGA_PORT   Marlin USB-serial path. Run `tools/preflight.py` first.

Optional:

    I3MEGA_BAUD   Default 250000 (Anycubic stock + MARLIN-AI3M).
"""

from __future__ import annotations

import os
import sys
import time
from typing import TYPE_CHECKING

from pipettebot.gantry import open_marlin_port

if TYPE_CHECKING:
    import serial  # type: ignore[import-untyped]

DEFAULT_BAUD = 250000

Z_LIFT_BEFORE_XY = 30.0  # mm; safe altitude for XY home (small lift to avoid drag)
Z_FEED = 1200  # 20 mm/s — at the M203 Z20 cap (leadscrew mechanical limit)


def gsend(link: serial.Serial, cmd: str, *, max_secs: float = 60.0) -> None:
    """Send `cmd` to Marlin and read until `ok`.

    Mirrors the `gsend` in `showcase_v0_full_plate.py`.
    """
    print(f"  >>> {cmd}")
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


def main() -> int:
    port = os.environ.get("I3MEGA_PORT")
    if not port:
        sys.stderr.write(
            "ERROR: set I3MEGA_PORT to your printer's serial port.\n"
            "       Run `uv run tools/preflight.py` to discover it.\n"
        )
        return 1
    baud = int(os.environ.get("I3MEGA_BAUD", str(DEFAULT_BAUD)))

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

        t0 = time.monotonic()

        print("[host] phase 1: raise feedrate + accel caps")
        gsend(link, "M203 X1000 Y1000 Z20")
        gsend(link, "M201 X2000 Y2000 Z200")

        print(f"[host] phase 2: lift Z to {Z_LIFT_BEFORE_XY:.0f} mm (defensive)")
        gsend(link, f"G1 Z{Z_LIFT_BEFORE_XY:.3f} F{Z_FEED}")
        gsend(link, "M400")

        print("[host] phase 3: G28 X Y (skip slow Z home)")
        gsend(link, "G28 X Y", max_secs=60)
        gsend(link, "M400")

        print(f"[host] phase 4: G1 Z0 F{Z_FEED} (move Z to default home)")
        gsend(link, f"G1 Z0.000 F{Z_FEED}")
        gsend(link, "M400")

        elapsed = time.monotonic() - t0
        print(f"[host] done — (X=0, Y=0, Z=0) reached in {elapsed:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
