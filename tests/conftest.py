"""Shared fixtures: fake serial port for the gantry, fake pipette for the bot."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest


@dataclass
class FakeSerial:
    """Records writes, replays canned readline responses (default: 'ok').

    `default_response` is what readline() returns once the responses queue is
    drained. Defaults to b"ok\\n" so existing tests don't need to queue
    anything. Pass b"" to simulate a silent / timed-out serial port.
    """

    written: list[bytes] = field(default_factory=list)
    responses: list[bytes] = field(default_factory=list)
    closed: bool = False
    default_response: bytes = b"ok\n"

    def write(self, data: bytes) -> int:
        self.written.append(data)
        return len(data)

    def readline(self) -> bytes:
        if self.responses:
            return self.responses.pop(0)
        return self.default_response

    def close(self) -> None:
        self.closed = True


@dataclass
class FakePipette:
    aspirated: list[float] = field(default_factory=list)
    dispensed: list[float] = field(default_factory=list)

    def aspirate(self, volume_ul: float = 0.0) -> None:
        self.aspirated.append(volume_ul)

    def dispense(self, volume_ul: float = 0.0) -> None:
        self.dispensed.append(volume_ul)


@pytest.fixture
def fake_serial() -> Iterator[FakeSerial]:
    yield FakeSerial()


@pytest.fixture
def fake_pipette() -> Iterator[FakePipette]:
    yield FakePipette()
