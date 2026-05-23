"""Read-only bring-up probe for Smartto-firmware printers (Geeetech A30).

Three phases at the working baud:
  1. Identity + position (`M115`, `M114`).
  2. Endstop state (`M119` once; optionally again after operator sensor press).
  3. Command capability sweep — sends a curated list of non-motion commands
     (EEPROM, sync, motion-tuning setters) and classifies each response as
     SUPPORTED / UNSUPPORTED / PARTIAL / SILENT. Final summary table lists
     what this Smartto build actually accepts.

Phase 3 setters (`M203` / `M204` / `M205`) are followed by `M501` (EEPROM
reload) so any RAM-only changes get reverted before exit. No persistence
is requested — `M500` is never sent.

Never sends motion: no `G0`, `G1`, `G28`, `G29`, `G30`, `G92`, or `M84`.
Refuses them explicitly if someone wires this script into a larger flow.

Use when Z homing dives past the sensor and you need to know which
commands the firmware actually supports before designing around it.

Required:
    SMARTTO_PORT  USB-serial path (e.g. /dev/ttyUSB0).

Optional:
    BAUDS         Comma-separated rates to try
                  (default: 115200,250000,57600,9600).

Tip: pipe through `tee captures/smartto_probe_$(date +%s).log` to keep
a permanent copy of what the A30 reported.

Safety:
    - Read-only by design; no motion commands are emitted.
    - Open/close on each baud attempt may pulse DTR and reset the board.
      Expect a ~2.5 s boot wait per attempt; harmless.
    - Power switch remains the only stop authority. Stand next to it.
"""

from __future__ import annotations

import os
import sys
import time
from typing import TYPE_CHECKING

from pipettebot.gantry import open_marlin_port

if TYPE_CHECKING:
    import serial  # type: ignore[import-untyped]

DEFAULT_BAUDS = (115200, 250000, 57600, 9600)
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

# (command, description, read_window_secs)
PROBE_CANDIDATES: tuple[tuple[str, str, float], ...] = (
    ("M503", "dump persisted settings", EEPROM_READ_WINDOW_S),
    ("M400", "wait for queued moves (no moves -> instant)", READ_WINDOW_S),
    ("M203 X500 Y500 Z20", "raise XY/Z feedrate caps", READ_WINDOW_S),
    ("M204 P1000", "raise print acceleration", READ_WINDOW_S),
    ("M205 X10 Y10 Z0.4", "raise XY/Z jerk", READ_WINDOW_S),
    ("M501", "load EEPROM into RAM (reverts session sets)", EEPROM_READ_WINDOW_S),
)


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


def _try_baud(port: str, baud: int) -> bool:
    """Open `port` at `baud`, send M115, return True if anything came back."""
    print(f"\n[baud {baud}] opening {port}")
    link = open_marlin_port(port, baudrate=baud, timeout=1.0)
    if link is None:
        print(f"[baud {baud}] could not open")
        return False
    with link:
        time.sleep(BOOT_WAIT_S)
        link.reset_input_buffer()
        lines = _send(link, "M115")
    if lines:
        print(f"[baud {baud}] firmware answered ({len(lines)} line(s))")
        return True
    print(f"[baud {baud}] silent")
    return False


def _confirm(prompt: str) -> bool:
    try:
        return input(f"{prompt} [y/N]: ").strip().lower() in {"y", "yes"}
    except (EOFError, KeyboardInterrupt):
        return False


def _run_session(port: str, baud: int) -> int:
    """Full identity + endstop + capability-probe sequence at a known baud."""
    link = open_marlin_port(port, baudrate=baud, timeout=1.0)
    if link is None:
        sys.stderr.write(f"ERROR: lost {port} @ {baud} after sweep.\n")
        return 1
    with link:
        time.sleep(BOOT_WAIT_S)
        link.reset_input_buffer()

        print(f"\n=== Identity (baud {baud}) ===")
        _send(link, "M115")
        _send(link, "M114")

        print("\n=== Endstops (first poll) ===")
        _send(link, "M119")

        if _confirm(
            "\nManually press / engage the Z sensor and HOLD it, then continue"
        ):
            print("\n=== Endstops, sensor PRESSED ===")
            _send(link, "M119")
        else:
            print("[skip] sensor-press confirmation; proceeding to capability probe")

        results = _probe_commands(link)
        _print_summary(results)
    return 0


def _parse_bauds(env_val: str | None) -> tuple[int, ...]:
    if not env_val:
        return DEFAULT_BAUDS
    return tuple(int(b.strip()) for b in env_val.split(",") if b.strip())


def main() -> int:
    port = os.environ.get("SMARTTO_PORT")
    if not port:
        sys.stderr.write("ERROR: set SMARTTO_PORT (e.g. /dev/ttyUSB0).\n")
        return 1
    bauds = _parse_bauds(os.environ.get("BAUDS"))

    print(
        "\n[smartto_probe] read-only diagnostic - no motion will be commanded.\n"
        "                Power switch is your only stop authority.\n"
    )

    working: int | None = None
    for b in bauds:
        try:
            if _try_baud(port, b):
                working = b
                break
        except (OSError, RuntimeError) as e:
            print(f"[baud {b}] error: {e}")
            continue

    if working is None:
        sys.stderr.write("\nERROR: no baud rate elicited a reply.\n")
        return 1

    rc = _run_session(port, working)
    if rc == 0:
        print(
            "\n[smartto_probe] done. Paste the output above back to the agent.\n"
            f"                Working baud: {working}\n"
        )
    return rc


if __name__ == "__main__":
    sys.exit(main())
