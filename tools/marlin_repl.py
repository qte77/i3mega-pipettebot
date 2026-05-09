"""Interactive G-code REPL for an i3 Mega running Marlin.

Sends arbitrary G/M-codes typed at the prompt and prints replies until
Marlin says `ok`. Useful for one-shots like `M119` (endstop status),
`M999` (clear halt), `M114` (current position), or `M115` (firmware).

Required:
    I3MEGA_PORT   Marlin USB-serial path (e.g. /dev/ttyUSB0).

Optional:
    BAUD          Default 250000.

Built-in commands:
    ?, help       Print the cheat-sheet of common Marlin commands.
    exit, quit    Disconnect and exit.
    Ctrl-D        Same as exit.

Safety:
    - Raw command channel. No soft-limit checking.
    - G28 / G0 / G1 will move the gantry. Use diagnose_axis.py for safer
      stepped motion.
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
EXIT_WORDS = frozenset({"exit", "quit", ":q"})
HELP_WORDS = frozenset({"?", "help"})

CHEAT_SHEET = """\
Common Marlin commands (Marlin 1.1.9 / MARLIN-AI3M v1.4.6)

  Identification & state
    M115            firmware name + capabilities
    M114            current XYZE position
    M119            endstop status (x_min / y_min / z_min / z2_min)
    M503            dump EEPROM-backed settings (steps/mm, feedrates, ...)

  Halt / recovery
    M999            clear `Error:Printer halted` flag (after a kill)
    M112            emergency stop (irreversible — power-cycle to recover)

  Motion
    G90             absolute positioning (default)
    G91             relative positioning
    G0 X10 F600     move X by/to 10 mm at 600 mm/min (depends on G90/G91)
    G1 ... F...     same; G1 is for "extruding" moves but moves identically
    M400            wait for all queued moves to finish
    G92 X0 Y0 Z0    set current position as origin (no motion)

  Homing
    G28             home all axes (uses Z probe — broken without head)
    G28 X           home X only (frame microswitch)
    G28 Y           home Y only (frame microswitch)
    G28 Z           home Z only (DON'T without a working Z endstop)

  Steppers / power
    M17             energize all steppers (hold position)
    M18 / M84       de-energize steppers (free hand-movement)
    M84 S30         auto-disable steppers after 30 s idle

  Sensors / safety overrides
    M302 P1         allow cold extrusion (no hotend? doesn't matter)
    M211 S0         disable software endstops (use with care)
    M412 S0         disable filament runout sensor (Marlin 2.0+ only)

  EEPROM
    M500            save current settings to EEPROM
    M501            restore EEPROM settings to RAM
    M502            reset settings to firmware defaults (RAM only)

Tip: prefix with `;` to send Marlin-side comments (logged but ignored).
"""


def gsend(link: serial.Serial, cmd: str, max_secs: float = ACK_TIMEOUT_S) -> None:
    """Send `cmd`, print every reply line, return when Marlin says `ok`."""
    link.write((cmd + "\n").encode("ascii"))
    deadline = time.time() + max_secs
    while time.time() < deadline:
        raw = link.readline()
        if not raw:
            continue
        s = raw.decode("ascii", errors="replace").rstrip()
        if not s:
            continue
        print(f"  {s}")
        if s == "ok" or s.startswith("ok "):
            return
    raise TimeoutError(f"no `ok` after {max_secs}s for `{cmd}`")


def main() -> int:
    port = os.environ.get("I3MEGA_PORT")
    if not port:
        sys.stderr.write(
            "ERROR: set I3MEGA_PORT to your printer's serial port.\n"
            "       Run `uv run tools/preflight.py` to discover it.\n"
        )
        return 1
    baud = int(os.environ.get("BAUD", str(DEFAULT_BAUD)))

    link = open_marlin_port(port, baudrate=baud, timeout=2.0)
    if link is None:
        sys.stderr.write(f"ERROR: could not open {port} @ {baud}.\n")
        return 1

    with link:
        print(f"[marlin_repl] connected to {port} @ {baud}")
        print(f"[marlin_repl] waiting {BOOT_WAIT_S}s for Marlin boot")
        time.sleep(BOOT_WAIT_S)
        link.reset_input_buffer()
        print("[marlin_repl] ready. Type `?` for cheat-sheet, `exit` to quit.")
        while True:
            try:
                cmd = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not cmd:
                continue
            low = cmd.lower()
            if low in EXIT_WORDS:
                break
            if low in HELP_WORDS:
                print(CHEAT_SHEET)
                continue
            try:
                gsend(link, cmd)
            except TimeoutError as e:
                print(f"  [timeout] {e}", file=sys.stderr)

    print("[marlin_repl] disconnected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
