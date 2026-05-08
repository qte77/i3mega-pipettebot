"""Diagnose Z-axis motion safely after head removal — no G28 Z, no probe.

Sends M119 (endstop status), then steps Z by 1 mm under operator
confirmation. Watch the lead screws and listen for binding or contact
with the bed before approving the next step. Never homes Z.

Required:
    I3MEGA_PORT   Marlin USB-serial path (e.g. /dev/ttyUSB0).

Optional:
    Z_STEP_MM     Default 1.0. Distance per confirmed step.
    Z_FEED        Default 300. Feedrate in mm/min.
    Z_STEPS       Default 5. Max steps per direction.

Safety:
    - Always run with your finger on the power switch.
    - Up-direction first (away from bed) — relatively safe.
    - Down-direction second (toward bed) — risky; watch closely.
    - Restores G90 (absolute mode) before exit, even on error / Ctrl-C.
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
BOOT_WAIT_S = 3.0
ACK_TIMEOUT_S = 30.0


def gsend(link: serial.Serial, cmd: str, max_secs: float = ACK_TIMEOUT_S) -> None:
    """Send `cmd`, print every reply line, return when Marlin says `ok`."""
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
        print(f"      {s}")
        if s == "ok" or s.startswith("ok "):
            return
        if s.startswith(("Resend:", "!! ", "Error:Printer halted", "Error:Thermal")):
            raise RuntimeError(f"Marlin error: {s} (after `{cmd}`)")
    raise TimeoutError(f"no `ok` after {max_secs}s for `{cmd}`")


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
    sign: int,
    step_mm: float,
    feed: int,
    steps: int,
) -> None:
    arrow = "+" if sign > 0 else "-"
    print(f"\n[{label}] move Z {arrow}{step_mm} mm × up to {steps}")
    if sign < 0:
        print("       DOWN direction — watch lead screws and bed clearance.")
    for i in range(1, steps + 1):
        delta = sign * step_mm
        if not confirm(f"  step {i}/{steps}: move Z {delta:+g} mm at F{feed}"):
            print(f"  [{label}] stopped at step {i - 1}/{steps}")
            return
        gsend(link, f"G0 Z{delta:+g} F{feed}")
        gsend(link, "M400")


def main() -> int:
    port = os.environ.get("I3MEGA_PORT")
    if not port:
        sys.stderr.write(
            "ERROR: set I3MEGA_PORT to your printer's serial port.\n"
            "       Run `uv run examples/preflight.py` to discover it.\n"
        )
        return 1
    step_mm = float(os.environ.get("Z_STEP_MM", "1.0"))
    feed = int(os.environ.get("Z_FEED", "300"))
    steps = int(os.environ.get("Z_STEPS", "5"))

    link = open_marlin_port(port, baudrate=DEFAULT_BAUD, timeout=2.0)
    if link is None:
        sys.stderr.write(f"ERROR: could not open {port} @ {DEFAULT_BAUD}.\n")
        return 1

    print(
        "\n[diagnose_z] Finger on the power switch.\n"
        "             Stop on any binding, ratcheting, or bed contact.\n"
    )

    rc = 0
    with link:
        print(
            f"[diagnose_z] open {port} @ {DEFAULT_BAUD}; wait {BOOT_WAIT_S}s for boot"
        )
        time.sleep(BOOT_WAIT_S)
        link.reset_input_buffer()
        try:
            print("\n[step 1] M119 — endstop status")
            gsend(link, "M119")

            if not confirm("\nProceed with Z motion test?"):
                print("[diagnose_z] aborted before motion")
                return 0

            print("\n[step 2] G91 — relative mode")
            gsend(link, "G91")

            step_loop(link, "step 3 / UP", +1, step_mm, feed, steps)
            step_loop(link, "step 4 / DOWN", -1, step_mm, feed, steps)
        except KeyboardInterrupt:
            print("\n[diagnose_z] interrupted by operator", file=sys.stderr)
            rc = 130
        except (RuntimeError, TimeoutError) as e:
            print(f"\n[diagnose_z] aborted: {e}", file=sys.stderr)
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
