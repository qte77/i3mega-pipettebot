"""Read-only bring-up probe for any G-code firmware on USB-serial.

Replaces tools/smartto_probe.py with a device-agnostic version that
auto-detects firmware via pipettebot.devices.discover() and tags the
final report with per-family operator notes.

Three phases:
  1. Discovery: baud-sweep + M115 via `discover()`. Reports identity.
  2. Endstop state: `M119` once; optionally again after operator presses
     the Z sensor (helpful when bring-up uncovers a homing issue).
  3. Command capability sweep: nine non-motion commands classified
     SUPPORTED / UNSUPPORTED / PARTIAL / SILENT in a final table. Setters
     (`M203` / `M204` / `M205`) are followed by `M501` to revert any
     RAM-only changes; `M500` is hard-banned to prevent persistence.

Never sends motion: `G0`, `G1`, `G2`, `G3`, `G28`, `G29`, `G30`, `G92`,
`M84`, `M18`, `M500` are all refused at the `_send` boundary.

Required:
    PRINTER_PORT  Gantry serial path. Run `tools/preflight.py` to discover.

Tip: pipe through `tee captures/gantry_probe_$(date +%s).log` for a
permanent capture of what the device reported.

Safety:
    - Read-only by design; no motion commands are emitted.
    - Power switch remains the only stop authority.
"""

from __future__ import annotations

import os
import sys
import time
from typing import TYPE_CHECKING

from pipettebot.devices import PRINTER_PORT_ENV, discover

if TYPE_CHECKING:
    import serial  # type: ignore[import-untyped]

BOOT_WAIT_S = 2.5
READ_WINDOW_S = 3.0
EEPROM_READ_WINDOW_S = 5.0

BANNED_PREFIXES = (
    "G0",
    "G1",
    "G2",
    "G3",
    "G28",
    "G29",
    "G30",
    "G92",
    "M84",
    "M18",
    "M500",
)

UNSUPPORTED_MARKERS = (
    "unknown",
    "unrecognized",
    "error:",
    "not supported",
    "invalid",
)

# (command, description, read_window_secs). Nine non-motion commands:
# six original (EEPROM, sync, motion-tuning setters) plus three
# operational levers (feedrate scale, soft endstops, idle timeout).
PROBE_CANDIDATES: tuple[tuple[str, str, float], ...] = (
    ("M503", "dump persisted settings", EEPROM_READ_WINDOW_S),
    ("M400", "wait for queued moves (no moves -> instant)", READ_WINDOW_S),
    ("M203 X500 Y500 Z20", "raise XY/Z feedrate caps", READ_WINDOW_S),
    ("M204 P1000", "raise print acceleration", READ_WINDOW_S),
    ("M205 X10 Y10 Z0.4", "raise XY/Z jerk", READ_WINDOW_S),
    (
        "M220 S100",
        "global feedrate scale (only runtime lever on some fw)",
        READ_WINDOW_S,
    ),
    (
        "M211 S1",
        "software endstops on/off (relevant for polled descent)",
        READ_WINDOW_S,
    ),
    ("M85 S0", "idle stepper-disable timeout (0 = never)", READ_WINDOW_S),
    ("M501", "load EEPROM into RAM (reverts session sets)", EEPROM_READ_WINDOW_S),
)

# Per-firmware-family operator notes printed after the capability table.
# Text-only; no behavior. Captures known-but-not-fatal quirks the operator
# should know about.
QUIRKS: dict[str, str] = {
    "marlin": (
        "Marlin emits `Cap:` lines in M115 (capability auto-report).\n"
        "  Multi-line M115 reply includes EEPROM/AUTOREPORT_TEMP/etc capabilities.\n"
        "  M503 dumps the full EEPROM-backed settings block."
    ),
    "smartto": (
        "Smartto v1.xx.58 quirks:\n"
        "  - M115 emits no `Cap:` lines; runtime feature detection unavailable.\n"
        "  - M503 acknowledged but emits no payload — can't read back current\n"
        "    motion caps from the firmware.\n"
        "  - Setters (M203/M204/M205) prepend `*_set_ok` confirmation before `ok`.\n"
        "  - `G1 X Y` (no values) silently accepts as a no-op — typo'd scripts\n"
        "    will not raise errors; script-side validation matters more.\n"
        "  - `G28 Z` dives indefinitely on head-removed builds (probe-pin variant);\n"
        "    use `G28 X Y` + manual `G92 Z0` instead."
    ),
    "unknown": (
        "Unknown firmware family — capability matrix is purely empirical.\n"
        "  Operator should cross-reference the SUPPORTED/UNSUPPORTED results above\n"
        "  with the firmware's own G-code reference before scripting against it."
    ),
}


def _drain(link: serial.Serial, secs: float) -> list[str]:
    """Read for `secs`, printing every non-empty line. Return the lines."""
    deadline = time.time() + secs
    lines: list[str] = []
    while time.time() < deadline:
        raw = link.readline()
        if not raw:
            continue
        s = raw.decode("ascii", errors="replace").rstrip()
        if not s:
            continue
        print(f"    {s}")
        lines.append(s)
    return lines


def _send(link: serial.Serial, cmd: str, secs: float = READ_WINDOW_S) -> list[str]:
    """Send `cmd`; refuse motion commands; print and return reply lines."""
    upper = cmd.upper()
    if any(upper.startswith(p) for p in BANNED_PREFIXES):
        raise RuntimeError(f"refusing banned motion/stepper command: {cmd}")
    print(f"  >>> {cmd}")
    link.write((cmd + "\n").encode("ascii"))
    return _drain(link, secs)


def _classify_reply(lines: list[str]) -> str:
    """SUPPORTED / UNSUPPORTED / PARTIAL / SILENT from a command's reply."""
    if not lines:
        return "SILENT"
    text = "\n".join(lines).lower()
    if any(marker in text for marker in UNSUPPORTED_MARKERS):
        return "UNSUPPORTED"
    if any(line == "ok" or line.startswith("ok ") for line in lines):
        return "SUPPORTED"
    return "PARTIAL"


def _probe_commands(link: serial.Serial) -> list[tuple[str, str]]:
    """Send every PROBE_CANDIDATE and return (command, verdict) pairs."""
    print("\n=== Command capability probe ===")
    results: list[tuple[str, str]] = []
    for cmd, desc, secs in PROBE_CANDIDATES:
        print(f"\n[probe] {cmd}  -- {desc}")
        try:
            lines = _send(link, cmd, secs)
        except RuntimeError as e:
            print(f"  [skip] {e}")
            results.append((cmd, "BANNED"))
            continue
        verdict = _classify_reply(lines)
        print(f"  [verdict] {verdict}")
        results.append((cmd, verdict))
    return results


def _print_summary(results: list[tuple[str, str]]) -> None:
    """Print a final aligned table of every probed command + verdict."""
    print("\n=== Capability summary ===")
    print(f"  {'Command':24s} Verdict")
    print(f"  {'-' * 24} -----------")
    for cmd, verdict in results:
        print(f"  {cmd:24s} {verdict}")


def _confirm(prompt: str) -> bool:
    try:
        return input(f"{prompt} [y/N]: ").strip().lower() in {"y", "yes"}
    except (EOFError, KeyboardInterrupt):
        return False


def _resolve_port() -> str | None:
    val = os.environ.get(PRINTER_PORT_ENV)
    return val if val else None


def _run_session(link: serial.Serial, family: str) -> int:
    """Identity + endstop + capability sweep + quirks footer."""
    _send(link, "M114")
    print("\n=== Endstops (first poll) ===")
    _send(link, "M119")

    if _confirm("\nManually press / engage the Z sensor and HOLD it, then continue"):
        print("\n=== Endstops, sensor PRESSED ===")
        _send(link, "M119")
    else:
        print("[skip] sensor-press confirmation; proceeding to capability probe")

    results = _probe_commands(link)
    _print_summary(results)

    quirks = QUIRKS.get(family)
    if quirks:
        print(f"\n=== Known quirks for {family} ===\n  {quirks}")
    return 0


def main() -> int:
    port = _resolve_port()
    if not port:
        sys.stderr.write(f"ERROR: set {PRINTER_PORT_ENV}.\n")
        return 1

    print(
        "\n[gantry_probe] read-only diagnostic - no motion will be commanded.\n"
        "               Power switch is your only stop authority.\n"
    )

    device = discover(port)
    if device is None:
        sys.stderr.write(f"\nERROR: no firmware answered on {port}.\n")
        return 1

    print(
        f"[gantry_probe] detected: {device.firmware_family} "
        f"({device.machine_type or '?'}, fw {device.firmware_version or '?'}) "
        f"@ {device.baud}"
    )

    from pipettebot.gantry import open_gcode_port

    link = open_gcode_port(port, baudrate=device.baud, timeout=2.0)
    if link is None:
        sys.stderr.write(f"ERROR: lost {port} @ {device.baud} after discover.\n")
        return 1

    with link:
        time.sleep(BOOT_WAIT_S)
        link.reset_input_buffer()
        rc = _run_session(link, device.firmware_family)

    if rc == 0:
        print(
            "\n[gantry_probe] done. Paste the output above back for review.\n"
            f"                Working baud: {device.baud}\n"
        )
    return rc


if __name__ == "__main__":
    sys.exit(main())
