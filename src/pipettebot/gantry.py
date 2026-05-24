"""Thin G-code wrapper for a Marlin-based 3-axis gantry over USB-serial."""

from __future__ import annotations

import array
import fcntl
import sys
import termios
import time
import warnings
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


def open_gcode_port(
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


def open_marlin_port(
    port: str, baudrate: int = 250000, timeout: float = 2.0
) -> serial.Serial | None:
    """Deprecated alias for `open_gcode_port`.

    The helper is firmware-agnostic (a Linux baud helper, not Marlin-specific);
    the old name is preserved for one release cycle so operators with downstream
    scripts can migrate without breakage.
    """
    warnings.warn(
        "open_marlin_port() is deprecated; use open_gcode_port() instead "
        "(the helper is firmware-agnostic, not Marlin-specific).",
        DeprecationWarning,
        stacklevel=2,
    )
    return open_gcode_port(port, baudrate=baudrate, timeout=timeout)


class _SerialPort(Protocol):
    """Subset of pyserial.Serial used by GcodeGantry; lets tests inject fakes.

    `write` is typed to match `serial.Serial.write` (positional-only, returns
    `int | None`) so the helper accepts real pyserial ports without Pyright
    protocol-mismatch noise.
    """

    def write(self, data: bytes, /) -> int | None: ...
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

    def send(self, line: str) -> str:
        """Send a raw G-code `line`; return the firmware's terminating `ok` line.

        Prefer the named methods (`home`, `move_to`, `wait_for_moves`) when one
        fits. Use `send` for G-code outside the wrapped surface — e.g. single-
        axis homes, `G92`, motion-profile setters from
        `pipettebot.motion_profile.MotionProfile.as_marlin()`.
        """
        return send_and_wait_for_ok(self._port, line)[-1]

    def query(self, line: str) -> list[str]:
        """Send `line`; return every non-empty reply (including the final `ok`).

        Use for commands whose reply payload matters — `M119` (endstops),
        `M114` (position), `M115` (identity), `M503` (settings dump). For
        fire-and-forget commands where only the ack matters, use `send`.
        """
        return send_and_wait_for_ok(self._port, line)

    def flush_input(self) -> None:
        """Drop any received-but-unread bytes from the OS serial buffer.

        Use after long bursts of multi-line-reply commands (`M119`, `M114`)
        where pyserial's `select()` may falsely report data-ready against an
        empty OS buffer, throwing `SerialException` on the next read.
        """
        # `_SerialPort` doesn't formally declare this — both pyserial.Serial
        # and tests/conftest.py::FakeSerial expose it; we call it lazily so
        # ports without the method (none in this codebase) would error
        # loudly at runtime rather than silently no-op.
        self._port.reset_input_buffer()  # type: ignore[attr-defined]

    def home(self) -> str:
        """Home all axes via `G28`. Returns the firmware reply line."""
        return self.send("G28")

    def move_to(self, x: float, y: float, z: float, feedrate: int | None = None) -> str:
        """Move to `(x, y, z)` at `feedrate` mm/min (or the config default)."""
        f = feedrate if feedrate is not None else self._cfg.feedrate_mm_per_min
        return self.send(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{f}")

    def wait_for_moves(self) -> str:
        """Block until the planner queue drains (`M400`)."""
        return self.send("M400")

    def close(self) -> None:
        """Close the underlying serial port."""
        self._port.close()
