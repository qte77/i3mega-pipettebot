"""Diagnose an axis (X, Y, or Z) safely — no homing, no probe needed.

Sends M119 (endstop status), then steps the axis by 1 mm under operator
confirmation. Watch motion before approving the next step. Never homes.

Required:
    I3MEGA_PORT   Marlin USB-serial path (e.g. /dev/ttyUSB0).
    AXIS          One of X, Y, Z.

Optional:
    STEP_MM       Default 1.0. Distance per confirmed step.
    FEED          Default 300. Feedrate in mm/min.
    STEPS         Default 5. Max steps per direction.

Per-axis risk:
    Z   Up safe within Z_max. DOWN crashes into bed.
    X   BOTH directions can crash into the frame side rails.
    Y   BOTH directions can crash into the front/back frame.

Safety:
    - Always run with your finger on the power switch.
    - Restores G90 (absolute mode) before exit, even on error / Ctrl-C.
"""

from __future__ import annotations

import os
import sys
import time
from typing import TYPE_CHECKING

from pipettebot.gantry import open_marlin_port, send_and_wait_for_ok

if TYPE_CHECKING:
    import serial  # type: ignore[import-untyped]

DEFAULT_BAUD = 250000
BOOT_WAIT_S = 3.0
ACK_TIMEOUT_S = 30.0
VALID_AXES = frozenset({"X", "Y", "Z"})

RISK_NOTES = {
    "Z": "Up safe within Z_max. DOWN direction crashes into bed.",
    "X": "BOTH directions can crash into the frame side rails.",
    "Y": "BOTH directions can crash into the front/back frame.",
}


_MARLIN_ERROR_PREFIXES = ("Resend:", "!! ", "Error:Printer halted", "Error:Thermal")


def gsend(link: serial.Serial, cmd: str, max_secs: float = ACK_TIMEOUT_S) -> None:
    """Send `cmd`, print every reply line, return when Marlin says `ok`."""
    print(f"  >>> {cmd}")

    def _check(s: str) -> None:
        print(f"      {s}")
        if s.startswith(_MARLIN_ERROR_PREFIXES):
            raise RuntimeError(f"Marlin error: {s} (after `{cmd}`)")

    send_and_wait_for_ok(link, cmd, max_secs=max_secs, on_line=_check)


def confirm(prompt: str) -> bool:
    while True:
        ans = input(f"{prompt} [y/N]: ").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("", "n", "no"):
            return False


def step_loop(
    link: serial.Serial,
    label: str,
    axis: str,
    sign: int,
    step_mm: float,
    feed: int,
    steps: int,
) -> None:
    arrow = "+" if sign > 0 else "-"
    print(f"\n[{label}] move {axis} {arrow}{step_mm} mm × up to {steps}")
    for i in range(1, steps + 1):
        delta = sign * step_mm
        if not confirm(f"  step {i}/{steps}: move {axis} {delta:+g} mm at F{feed}"):
            print(f"  [{label}] stopped at step {i - 1}/{steps}")
            return
        gsend(link, f"G0 {axis}{delta:+g} F{feed}")
        gsend(link, "M400")


def main() -> int:
    port = os.environ.get("I3MEGA_PORT")
    if not port:
        sys.stderr.write(
            "ERROR: set I3MEGA_PORT to your printer's serial port.\n"
            "       Run `uv run tools/preflight.py` to discover it.\n"
        )
        return 1
    axis = os.environ.get("AXIS", "").upper()
    if axis not in VALID_AXES:
        sys.stderr.write(f"ERROR: set AXIS to one of {sorted(VALID_AXES)}.\n")
        return 1
    step_mm = float(os.environ.get("STEP_MM", "1.0"))
    feed = int(os.environ.get("FEED", "300"))
    steps = int(os.environ.get("STEPS", "5"))

    link = open_marlin_port(port, baudrate=DEFAULT_BAUD, timeout=2.0)
    if link is None:
        sys.stderr.write(f"ERROR: could not open {port} @ {DEFAULT_BAUD}.\n")
        return 1

    print(
        f"\n[diagnose_axis] axis={axis}. Finger on the power switch.\n"
        f"                Risk: {RISK_NOTES[axis]}\n"
    )

    rc = 0
    with link:
        print(f"[diagnose_axis] open {port} @ {DEFAULT_BAUD}; wait {BOOT_WAIT_S}s")
        time.sleep(BOOT_WAIT_S)
        link.reset_input_buffer()
        try:
            print("\n[step 1] M119 — endstop status")
            gsend(link, "M119")

            if not confirm(f"\nProceed with {axis} motion test?"):
                print("[diagnose_axis] aborted before motion")
                return 0

            print("\n[step 2] G91 — relative mode")
            gsend(link, "G91")

            step_loop(link, f"step 3 / +{axis}", axis, +1, step_mm, feed, steps)
            step_loop(link, f"step 4 / -{axis}", axis, -1, step_mm, feed, steps)
        except KeyboardInterrupt:
            print("\n[diagnose_axis] interrupted by operator", file=sys.stderr)
            rc = 130
        except (RuntimeError, TimeoutError) as e:
            print(f"\n[diagnose_axis] aborted: {e}", file=sys.stderr)
            rc = 1
        finally:
            try:
                print("\n[cleanup] G90 — restore absolute mode")
                gsend(link, "G90", max_secs=5.0)
            except Exception as e:
                print(f"[cleanup] G90 send failed: {e}", file=sys.stderr)

    return rc


if __name__ == "__main__":
    sys.exit(main())
