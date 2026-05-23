"""Interactive G-code REPL for a Geeetech A30 running Smartto firmware.

Companion to `tools/marlin_repl.py` for the second supported gantry
target. Sends arbitrary G/M-codes typed at the prompt and prints replies
until Smartto says `ok`. Useful for one-shots like `M119` (endstops),
`M114` (position), `M115` (firmware identity), or `M220` (feedrate %).

Independent of `pipettebot.gantry` by design: 115200 is a standard baud
that pyserial handles without the Linux `BOTHER` ioctl, so this tool
opens the port directly. Decoupling lets the REPL ship before the
eventual `MarlinGantry` / `SmarttoGantry` split lands.

Smartto's documented G-code surface is smaller than Marlin's. The
cheat-sheet (`?`) lists what was verified live on the A30 plus
untested commands worth trying. Commands outside Smartto's set may
return no reply, an error string, or silence; Ctrl-C unblocks the
prompt if a send hangs.

Required:
    SMARTTO_PORT  USB-serial path (e.g. /dev/ttyUSB0).

Optional:
    BAUD          Default 115200 (Smartto's stock rate, confirmed
                  live on the user's A30 fw v1.xx.58).

Built-in commands:
    ?, help       Print the Smartto cheat-sheet.
    exit, quit    Disconnect and exit.
    Ctrl-D        Same as exit.

Safety:
    - Raw command channel. No soft-limit checking.
    - `G28` (full home) and `G28 Z` dive Z indefinitely on this A30 -
      Smartto's homing routine watches a probe pin that is not wired
      in the head-removed configuration. Use `G28 X Y` only; set
      `G92 Z0` manually once Z is parked where you want.
    - No hotend or heated bed commands (`M104` / `M109` / `M140` /
      `M190`) needed - print head is removed by project policy.
"""

from __future__ import annotations

import os
import sys
import time

import serial  # type: ignore[import-untyped]

DEFAULT_BAUD = 115200
BOOT_WAIT_S = 2.5
ACK_TIMEOUT_S = 30.0
EXIT_WORDS = frozenset({"exit", "quit", ":q"})
HELP_WORDS = frozenset({"?", "help"})

CHEAT_SHEET = """\
Smartto firmware (Geeetech A30, fw v1.xx.58, GTM32 mini s board)

  Identification & state
    M115            firmware identity (MACHINE_TYPE, UUID, FIRMWARE_NAME,
                    PROTOCOL_VERSION, EXTRUDER_COUNT - no Cap: lines)
    M114            current XYZE position
    M119            endstop status (x_min/max, y_min/max, z_min/max)

  Motion
    G90             absolute positioning (default)
    G91             relative positioning
    G0 X10 F600     move X to/by 10 mm at 600 mm/min (per G90/G91)
    G1 ... F...     same as G0 on Smartto (no extrude distinction here)
    G92 X0 Y0 Z0    set current position as origin (no motion)

  Homing
    G28 X           home X only (frame microswitch - x_min in M119)
    G28 Y           home Y only (frame microswitch - y_min in M119)
    G28 Z           DO NOT - dives indefinitely on this head-less A30
    G28             DO NOT - same dive; includes Z

  Speed (only runtime motion lever available)
    M220 S100       reset feedrate scale to 100% (default)
    M220 S150       scale all subsequent F by 1.5x (cap = firmware build)

  Steppers
    M17             energize all steppers (hold position)
    M18 / M84       de-energize steppers (free hand-movement)

  Untested on this firmware - try and report back
    M400            wait for queued moves (not in old Geeetech docs)
    M203 / M204 / M205    raise feedrate / accel / jerk caps
    M500 / M501 / M503    EEPROM save / load / dump

  Project policy on this printer
    - Print head removed; ignore M104 / M109 / M140 / M190.
    - For Z origin: `G28 X Y`, jog Z by hand, then `G92 Z0`.
    - Power switch is the only stop authority during motion tests.

Tip: prefix with `;` to send firmware-side comments (logged, ignored).
"""


def gsend(link: serial.Serial, cmd: str, max_secs: float = ACK_TIMEOUT_S) -> None:
    """Send `cmd`, print every reply line, return when Smartto says `ok`."""
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


def _read_command() -> str | None:
    """Read one REPL line; return None on EOF/Ctrl-C."""
    try:
        return input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def _repl_loop(link: serial.Serial) -> None:
    """Interactive command loop. Returns when the user exits."""
    while True:
        cmd = _read_command()
        if cmd is None:
            return
        if not cmd:
            continue
        low = cmd.lower()
        if low in EXIT_WORDS:
            return
        if low in HELP_WORDS:
            print(CHEAT_SHEET)
            continue
        try:
            gsend(link, cmd)
        except TimeoutError as e:
            print(f"  [timeout] {e}", file=sys.stderr)


def main() -> int:
    port = os.environ.get("SMARTTO_PORT")
    if not port:
        sys.stderr.write(
            "ERROR: set SMARTTO_PORT to your printer's serial port.\n"
            "       Try: ls -l /dev/serial/by-id/   (or /dev/ttyUSB0)\n"
        )
        return 1
    baud = int(os.environ.get("BAUD", str(DEFAULT_BAUD)))

    try:
        link = serial.Serial(port, baud, timeout=2.0)
    except (OSError, serial.SerialException) as e:
        sys.stderr.write(f"ERROR: could not open {port} @ {baud}: {e}\n")
        return 1

    with link:
        print(f"[smartto_repl] connected to {port} @ {baud}")
        print(f"[smartto_repl] waiting {BOOT_WAIT_S}s for firmware boot")
        time.sleep(BOOT_WAIT_S)
        link.reset_input_buffer()
        print("[smartto_repl] ready. Type `?` for cheat-sheet, `exit` to quit.")
        _repl_loop(link)

    print("[smartto_repl] disconnected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
