"""Unit tests for tools/teleop_record.py — solo-arm recording (torque off)."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import itertools
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"


def _import_teleop_record():
    spec = importlib.util.spec_from_file_location(
        "teleop_record", TOOLS_DIR / "teleop_record.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["teleop_record"] = mod
    spec.loader.exec_module(mod)
    return mod


teleop_record = _import_teleop_record()


def _import_teleop_common():
    spec = importlib.util.spec_from_file_location(
        "_teleop_common", TOOLS_DIR / "_teleop_common.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("_teleop_common", mod)
    spec.loader.exec_module(mod)
    return mod


teleop_common = _import_teleop_common()


@dataclass
class FakeSyncReader:
    available: dict[int, int]
    txrx_result: int = 0

    def txRxPacket(self) -> int:  # noqa: N802
        return self.txrx_result

    def isAvailable(self, sid: int, _addr: int, _length: int) -> bool:  # noqa: N802
        return sid in self.available

    def getData(self, sid: int, _addr: int, _length: int) -> int:  # noqa: N802
        return self.available[sid]


@dataclass
class FakeFallbackPacket:
    per_servo: dict[int, int] = field(default_factory=dict)

    def read2ByteTxRx(self, _port: object, sid: int, _addr: int):  # noqa: N802
        if sid in self.per_servo:
            return self.per_servo[sid], 0, 0
        return 0, -1, 0


def test_record_loop_writes_one_jsonl_line_per_successful_read(monkeypatch) -> None:
    monkeypatch.setattr(teleop_record.time, "sleep", lambda _s: None)
    out = io.StringIO()
    reader = FakeSyncReader(available={1: 100, 2: 200, 3: 300, 4: 400, 5: 500, 6: 600})
    packet = FakeFallbackPacket()
    ticks = list(
        itertools.islice(
            teleop_record._record_loop(reader, packet, object(), out, rate_hz=60.0),
            3,
        )
    )
    assert ticks == [1, 2, 3]
    lines = out.getvalue().strip().splitlines()
    assert len(lines) == 3
    record = json.loads(lines[0])
    assert record["joints"] == {
        "1": 100,
        "2": 200,
        "3": 300,
        "4": 400,
        "5": 500,
        "6": 600,
    }


class _BailoutError(Exception):
    """Test-only sentinel for breaking out of the infinite record loop."""


def test_record_loop_skips_writes_when_both_paths_fail(monkeypatch) -> None:
    monkeypatch.setattr(teleop_record.time, "sleep", lambda _s: None)
    out = io.StringIO()
    reader = FakeSyncReader(available={}, txrx_result=-1)
    packet = FakeFallbackPacket()  # nothing — fallback also fails
    # The loop never yields on failed reads, so islice can't bound it.
    # Use perf_counter to count iterations and raise our own exception
    # (not StopIteration, which PEP 479 wraps as RuntimeError inside
    # generators).
    iterations = {"n": 0}

    def fake_perf_counter():
        iterations["n"] += 1
        if iterations["n"] > 10:
            raise _BailoutError
        return iterations["n"] * 0.001

    monkeypatch.setattr(teleop_record.time, "perf_counter", fake_perf_counter)
    with contextlib.suppress(_BailoutError):
        list(teleop_record._record_loop(reader, packet, object(), out, rate_hz=60.0))
    assert out.getvalue() == ""


def test_record_loop_round_trips_through_parse_record_line(monkeypatch) -> None:
    monkeypatch.setattr(teleop_record.time, "sleep", lambda _s: None)
    out = io.StringIO()
    reader = FakeSyncReader(available={1: 100, 2: 200, 3: 300, 4: 400, 5: 500, 6: 600})
    packet = FakeFallbackPacket()
    list(
        itertools.islice(
            teleop_record._record_loop(reader, packet, object(), out, rate_hz=60.0),
            1,
        )
    )
    t, joints = teleop_common.parse_record_line(out.getvalue().strip())
    assert t >= 0.0
    assert joints == {1: 100, 2: 200, 3: 300, 4: 400, 5: 500, 6: 600}
