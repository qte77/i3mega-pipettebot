"""Hardware-motion: home all axes via plain G28 — end at Marlin (0, 0, 0).

Same semantics as typing `G28` in `tools/marlin_repl.py` — full home,
end at the calibrated zero (`X=0, Y=0, Z=0`). The previous version of
this script tried to be cleverer (lift Z, `G28 X Y`, then `G1 Z0` at
40 mm/s) but the extra motion would stall mid-descent on the AI3M
leadscrew. Reverting to the simplest path: install the liquid-handling
motion profile, then run G28 and let Marlin do its thing.

Per docs/calibration.md, `Z=0` is calibrated to tip-end-on-deck WITH
tips loaded. Any tip mounted on the dPette will end up parked against
the deck at the end of homing — that's the calibrated terminus, not a
bug. Remove tips before running if that matters.

Phases
------

1. Bootstrap — install the liquid-handling motion profile via
   `pipettebot.motion_profile.select_profile(MOTION_PROFILE)`. Defaults
   to MID when env unset; set `MOTION_PROFILE=slow|fast` to dial, or
   `MOTION_PROFILE=off` to skip and keep Marlin's RAM/EEPROM motion
   settings untouched. The profile doesn't affect homing speed
   (compile-time `HOMING_FEEDRATE` on stock Marlin 1.1.x), but it
   governs any G1 after this script and persists until power-cycle —
   aligns this script's post-state with what every `showcase_v0_*.py`
   installs in its own bootstrap.
2. Home      — full `G28`. Ends at (X=0, Y=0, Z=0).

Required environment variable:

    I3MEGA_PORT     Marlin USB-serial path. Run `tools/preflight.py` first.

Optional:

    I3MEGA_BAUD     Default 250000 (Anycubic stock + MARLIN-AI3M).
    MOTION_PROFILE  Bundled profile name: `slow` / `mid` / `fast`
                    (default `mid`). Empty or `off` to skip the install.
                    See `src/pipettebot/motion_profile.py` for values.
"""

from __future__ import annotations

import os
import sys
import time
from typing import TYPE_CHECKING

from pipettebot.gantry import open_gcode_port, send_and_wait_for_ok
from pipettebot.motion_profile import select_profile

if TYPE_CHECKING:
    import serial  # type: ignore[import-untyped]

DEFAULT_BAUD = 250000


_MARLIN_ERROR_PREFIXES = ("Resend:", "!! ", "Error:Printer halted", "Error:Thermal")


def gsend(link: serial.Serial, cmd: str, *, max_secs: float = 120.0) -> None:
    """Send `cmd` to Marlin and read until `ok`. Mirrors showcase_v0_full_plate.py."""
    print(f"  >>> {cmd}")

    def _check(s: str) -> None:
        if "volume.init" in s or "SD init" in s:
            return  # SD-card boot chatter; ignore
        if s.startswith(_MARLIN_ERROR_PREFIXES):
            raise RuntimeError(f"Marlin error: {s} (after `{cmd}`)")

    send_and_wait_for_ok(link, cmd, max_secs=max_secs, on_line=_check)


def main() -> int:
    port = os.environ.get("I3MEGA_PORT")
    if not port:
        sys.stderr.write(
            "ERROR: set I3MEGA_PORT to your printer's serial port.\n"
            "       Run `uv run tools/preflight.py` to discover it.\n"
        )
        return 1
    baud = int(os.environ.get("I3MEGA_BAUD", str(DEFAULT_BAUD)))

    link = open_gcode_port(port, baudrate=baud, timeout=2.0)
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

        profile = select_profile(os.environ.get("MOTION_PROFILE"))
        if profile is None:
            print("[host] phase 1: motion profile SKIPPED (MOTION_PROFILE opt-out)")
        else:
            print(f"[host] phase 1: install motion profile '{profile.name}'")
            for cmd in profile.as_marlin():
                gsend(link, cmd)

        print("[host] phase 2: G28 — return to Marlin default home (0, 0, 0)")
        gsend(link, "G28", max_secs=120)
        gsend(link, "M400")

        elapsed = time.monotonic() - t0
        print(f"[host] done — (X=0, Y=0, Z=0) reached in {elapsed:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
