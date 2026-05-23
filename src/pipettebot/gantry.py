"""Thin G-code wrapper for a Marlin-based 3-axis gantry over USB-serial."""

from __future__ import annotations

import array
import fcntl
import sys
import termios
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import serial

if TYPE_CHECKING:
    from collections.abc import Callable

# Linux termios2 fallback: some Python builds don't expose `termios.B250000`
# (depends on the headers CPython was compiled against, not the distro), so
# pyserial's `tcsetattr` path bails with EINVAL. The kernel still accepts
# arbitrary rates via TCSETS2+BOTHER on every Linux since 2.6.20.
_TCGETS2 = 0x802C542A
_TCSETS2 = 0x402C542B
_BOTHER = 0o010000
_CBAUD = 0o010017


def set_custom_baud_linux(fd: int, baudrate: int) -> None:
    """Set arbitrary baud on Linux via TCSETS2 ioctl + BOTHER."""
    buf = array.array("i", [0] * 64)
    fcntl.ioctl(fd, _TCGETS2, buf, True)
    buf[2] = (buf[2] & ~_CBAUD) | _BOTHER
    buf[9] = buf[10] = baudrate  # c_ispeed, c_ospeed
    fcntl.ioctl(fd, _TCSETS2, buf, True)


def open_marlin_port(
    port: str, baudrate: int = 250000, timeout: float = 2.0
) -> serial.Serial | None:
    """Open `port` at `baudrate` with a Linux termios2 fallback.

    When pyserial can't set the rate (e.g. missing `termios.B250000`), retries
    via the TCSETS2 + BOTHER ioctl. Returns None if the port can't be opened
    at all (permission, ENOENT, etc.).
    """
    try:
        return serial.Serial(port, baudrate, timeout=timeout)
    except (OSError, serial.SerialException, termios.error):
        if not sys.platform.startswith("linux"):
            return None
    try:
        link = serial.Serial(port, 9600, timeout=timeout)
    except (OSError, serial.SerialException):
        return None
    try:
        set_custom_baud_linux(link.fileno(), baudrate)
    except OSError:
        link.close()
        return None
    return link


class _SerialPort(Protocol):
    """Subset of pyserial.Serial used by GcodeGantry; lets tests inject fakes."""

    def write(self, data: bytes) -> int: ...
    def readline(self) -> bytes: ...
    def close(self) -> None: ...


def send_and_wait_for_ok(
    link: _SerialPort,
    cmd: str,
    *,
    max_secs: float = 30.0,
    on_line: Callable[[str], None] | None = None,
) -> list[str]:
    """Send `cmd` to `link` and read lines until firmware acknowledges with `ok`.

    Returns every non-empty reply line collected (the terminating `ok` line
    included). If `on_line` is given, it's called with each line as it arrives
    — useful for streaming display in interactive REPLs.

    Args:
        link: Serial-like object exposing `write(bytes)` and `readline()`.
        cmd: Command to send. A trailing newline is appended.
        max_secs: Maximum wall-clock seconds to wait for `ok` before raising.
        on_line: Optional callback invoked per received line.

    Returns:
        The non-empty reply lines, in order, with the terminating `ok` line last.

    Raises:
        TimeoutError: if no `ok` arrives within `max_secs`.
    """
    link.write((cmd + "\n").encode("ascii"))
    lines: list[str] = []
    deadline = time.time() + max_secs
    while time.time() < deadline:
        raw = link.readline()
        if not raw:
            continue
        s = raw.decode("ascii", errors="replace").rstrip()
        if not s:
            continue
        lines.append(s)
        if on_line is not None:
            on_line(s)
        if s == "ok" or s.startswith("ok "):
            return lines
    raise TimeoutError(f"no `ok` after {max_secs}s for `{cmd}`")


@dataclass(frozen=True)
class GantryConfig:
    """Serial transport + default feedrate for a `GcodeGantry`."""

    port: str
    baudrate: int = 115200
    feedrate_mm_per_min: int = 3000


class GcodeGantry:
    """Sends G-code to Marlin and waits for `ok` after each command.

    Marlin echoes `ok` (often with extras) once a command is parsed and queued.
    `wait_for_moves()` issues `M400` to flush the planner, blocking until all
    queued moves complete — required before any pipette aspirate/dispense.
    """

    def __init__(self, cfg: GantryConfig, port: _SerialPort) -> None:
        """Bind `cfg` to an already-open `port` (tests inject a fake)."""
        self._cfg = cfg
        self._port = port

    def _send(self, line: str) -> str:
        # Delegate to the lifted helper; return the terminating `ok` line so
        # the public method signatures stay backward-compatible.
        return send_and_wait_for_ok(self._port, line)[-1]

    def home(self) -> str:
        """Home all axes via `G28`. Returns the firmware reply line."""
        return self._send("G28")

    def move_to(self, x: float, y: float, z: float, feedrate: int | None = None) -> str:
        """Move to `(x, y, z)` at `feedrate` mm/min (or the config default)."""
        f = feedrate if feedrate is not None else self._cfg.feedrate_mm_per_min
        return self._send(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{f}")

    def wait_for_moves(self) -> str:
        """Block until the planner queue drains (`M400`)."""
        return self._send("M400")

    def close(self) -> None:
        """Close the underlying serial port."""
        self._port.close()
