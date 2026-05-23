"""Interactive G-code REPL with per-firmware cheat-sheet dispatch.

Replaces tools/marlin_repl.py and tools/smartto_repl.py with a single tool
that auto-detects firmware via pipettebot.devices.discover() and selects
the matching cheat-sheet. The --device flag overrides auto-detect (useful
when discover() doesn't like the firmware on the wire).

Required (first set wins):
    GANTRY_PORT   Generic gantry serial path.
    SMARTTO_PORT  Geeetech A30 / Smartto port.
    I3MEGA_PORT   Anycubic i3 Mega / Marlin port.

Optional:
    BAUD          Override the policy's preferred_baud (or the discovered
                  baud) before opening.
    --device <family>   Force the cheat-sheet to marlin / smartto /
                  unknown; skips the discover() M115 probe entirely.

Built-in commands:
    ?, help       Print the active cheat-sheet.
    exit, quit    Disconnect and exit.
    Ctrl-D        Same as exit.

Safety:
    - Raw command channel. No soft-limit checking.
    - On Smartto/A30 with head removed, `G28` and `G28 Z` dive
      indefinitely (probe-pin variant). Use `G28 X Y` + manual `G92 Z0`.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import TYPE_CHECKING

from pipettebot.devices import FIRMWARE_POLICIES, discover
from pipettebot.gantry import open_gcode_port, send_and_wait_for_ok

if TYPE_CHECKING:
    import serial  # type: ignore[import-untyped]

BOOT_WAIT_S = 2.5
ACK_TIMEOUT_S = 30.0
EXIT_WORDS = frozenset({"exit", "quit", ":q"})
HELP_WORDS = frozenset({"?", "help"})

MARLIN_CHEAT_SHEET = """\
Common Marlin commands (Marlin 1.1.9 / MARLIN-AI3M v1.4.6)

  Identification & state
    M115            firmware name + capabilities
    M114            current XYZE position
    M119            endstop status (x_min / y_min / z_min / z2_min)
    M503            dump EEPROM-backed settings (steps/mm, feedrates, ...)

  Halt / recovery
    M999            clear `Error:Printer halted` flag (after a kill)
    M112            emergency stop (irreversible - power-cycle to recover)

  Motion
    G90             absolute positioning (default)
    G91             relative positioning
    G0 X10 F600     move X by/to 10 mm at 600 mm/min (depends on G90/G91)
    G1 ... F...     same; G1 is for "extruding" moves but moves identically
    M400            wait for all queued moves to finish
    G92 X0 Y0 Z0    set current position as origin (no motion)

  Homing
    G28             home all axes (uses Z probe - broken without head)
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

SMARTTO_CHEAT_SHEET = """\
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
    M400            wait for queued moves (confirmed on v1.37.58)

  Homing
    G28 X           home X only (frame microswitch - x_min in M119)
    G28 Y           home Y only (frame microswitch - y_min in M119)
    G28 Z           DO NOT - dives indefinitely on this head-less A30
    G28             DO NOT - same dive; includes Z

  Speed
    M203 X500 Y500 Z20    raise max feedrate caps (confirmed working)
    M204 P1000            raise print acceleration (confirmed working)
    M205 X10 Y10 Z0.4     raise jerk (confirmed working)
    M220 S150             scale all subsequent F by 1.5x

  Steppers
    M17             energize all steppers (hold position)
    M18 / M84       de-energize steppers (free hand-movement)

  EEPROM (confirmed)
    M501            load EEPROM into RAM (reverts session sets)
    M503            acknowledged but emits no payload on this build

  Project policy on this printer
    - Print head removed; ignore M104 / M109 / M140 / M190.
    - For Z origin: `G28 X Y`, jog Z by hand, then `G92 Z0`.
    - Power switch is the only stop authority during motion tests.

Tip: prefix with `;` to send firmware-side comments (logged, ignored).
"""

GENERIC_CHEAT_SHEET = """\
G-code REPL - unrecognised firmware

  Identification & state
    M115            firmware identity (vendor-specific format)
    M114            current position (if supported)
    M119            endstop status (if supported)

  Motion
    G90 / G91       absolute / relative positioning
    G28 X / G28 Y   home single axes (avoid blind G28 until verified)
    G0 / G1         move (check firmware's per-axis F units)
    M400            wait for queued moves (if supported)
    G92             set current position as origin

  Safety
    Power switch is the only stop authority.
    Avoid full G28 until you've verified each axis homes correctly.

Tip: prefix with `;` to send firmware-side comments (logged if supported).
"""

CHEAT_SHEETS: dict[str, str] = {
    "marlin": MARLIN_CHEAT_SHEET,
    "smartto": SMARTTO_CHEAT_SHEET,
    "unknown": GENERIC_CHEAT_SHEET,
}


def select_cheat_sheet(family: str) -> str:
    """Return the cheat-sheet for `family`, falling back to GENERIC."""
    return CHEAT_SHEETS.get(family, GENERIC_CHEAT_SHEET)


def _resolve_port() -> str | None:
    for var in ("GANTRY_PORT", "SMARTTO_PORT", "I3MEGA_PORT"):
        val = os.environ.get(var)
        if val:
            return val
    return None


def _read_command() -> str | None:
    try:
        return input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def _repl_loop(link: serial.Serial, cheat_sheet: str) -> None:
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
            print(cheat_sheet)
            continue
        try:
            send_and_wait_for_ok(
                link,
                cmd,
                max_secs=ACK_TIMEOUT_S,
                on_line=lambda s: print(f"  {s}"),
            )
        except TimeoutError as e:
            print(f"  [timeout] {e}", file=sys.stderr)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive G-code REPL with per-firmware cheat-sheet",
    )
    parser.add_argument(
        "--device",
        choices=("marlin", "smartto", "unknown"),
        help="Override the auto-detected firmware family.",
    )
    return parser.parse_args(argv)


def _resolve_family_and_baud(
    port: str, device_override: str | None
) -> tuple[str, int] | None:
    if device_override:
        policy = next(p for p in FIRMWARE_POLICIES if p.family == device_override)
        baud = int(os.environ.get("BAUD", str(policy.preferred_baud)))
        return device_override, baud
    device = discover(port)
    if device is None:
        sys.stderr.write(f"ERROR: no firmware answered on {port}.\n")
        return None
    baud = int(os.environ.get("BAUD", str(device.baud)))
    return device.firmware_family, baud


def main(argv: list[str] | None = None) -> int:
    """CLI entry. Returns 0 on clean disconnect, 1 on configuration error."""
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    port = _resolve_port()
    if not port:
        sys.stderr.write(
            "ERROR: set GANTRY_PORT (or SMARTTO_PORT / I3MEGA_PORT) "
            "to your printer's serial port.\n"
            "       Run `uv run tools/preflight.py` to discover it.\n"
        )
        return 1

    resolved = _resolve_family_and_baud(port, args.device)
    if resolved is None:
        return 1
    family, baud = resolved

    link = open_gcode_port(port, baudrate=baud, timeout=2.0)
    if link is None:
        sys.stderr.write(f"ERROR: could not open {port} @ {baud}.\n")
        return 1

    with link:
        print(f"[gantry_repl] connected to {port} @ {baud} ({family})")
        print(f"[gantry_repl] waiting {BOOT_WAIT_S}s for firmware boot")
        time.sleep(BOOT_WAIT_S)
        link.reset_input_buffer()
        print("[gantry_repl] ready. Type `?` for cheat-sheet, `exit` to quit.")
        _repl_loop(link, select_cheat_sheet(family))

    print("[gantry_repl] disconnected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
