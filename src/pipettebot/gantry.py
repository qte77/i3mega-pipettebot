"""Thin G-code wrapper for a Marlin-based 3-axis gantry over USB-serial."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class _SerialPort(Protocol):
    """Minimal subset of pyserial.Serial used by GcodeGantry (lets tests inject fakes)."""

    def write(self, data: bytes) -> int: ...
    def readline(self) -> bytes: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class GantryConfig:
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
        self._cfg = cfg
        self._port = port

    def _send(self, line: str) -> str:
        self._port.write((line + "\n").encode("ascii"))
        return self._port.readline().decode("ascii", errors="replace").strip()

    def home(self) -> str:
        return self._send("G28")

    def move_to(self, x: float, y: float, z: float, feedrate: int | None = None) -> str:
        f = feedrate if feedrate is not None else self._cfg.feedrate_mm_per_min
        return self._send(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{f}")

    def wait_for_moves(self) -> str:
        return self._send("M400")

    def close(self) -> None:
        self._port.close()
