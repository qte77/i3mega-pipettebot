"""Unit tests for tools/teleop_replay.py — pure logic, no scservo_sdk, no hardware."""

from __future__ import annotations

import importlib.util
import io
import sys
from dataclasses import dataclass, field
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"


def _import_teleop_replay():
    spec = importlib.util.spec_from_file_location(
        "teleop_replay", TOOLS_DIR / "teleop_replay.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["teleop_replay"] = mod
    spec.loader.exec_module(mod)
    return mod


teleop_replay = _import_teleop_replay()


@dataclass
class FakeSyncWriter:
    """Captures the sequence of sync_write batches produced by replay."""

    batches: list[dict[int, int]] = field(default_factory=list)
    clear_calls: int = 0
    _pending: dict[int, int] = field(default_factory=dict)

    def clearParam(self) -> None:  # noqa: N802
        self.clear_calls += 1
        self._pending = {}

    def addParam(self, sid: int, data: list[int]) -> bool:  # noqa: N802
        self._pending[sid] = data[0] | (data[1] << 8)
        return True

    def txPacket(self) -> int:  # noqa: N802
        self.batches.append(dict(self._pending))
        return 0


def test_replay_loop_writes_goals_in_recorded_order(monkeypatch) -> None:
    monkeypatch.setattr(teleop_replay.time, "sleep", lambda _s: None)
    writer = FakeSyncWriter()
    recording = io.StringIO(
        '{"t": 0.0, "joints": {"1": 100, "2": 200}}\n'
        '{"t": 0.016, "joints": {"1": 110, "2": 210}}\n'
        '{"t": 0.033, "joints": {"1": 120, "2": 220}}\n'
    )
    ticks = list(teleop_replay._replay_loop(writer, recording))
    assert ticks == [1, 2, 3]
    assert writer.batches == [
        {1: 100, 2: 200},
        {1: 110, 2: 210},
        {1: 120, 2: 220},
    ]


def test_replay_loop_skips_blank_lines(monkeypatch) -> None:
    monkeypatch.setattr(teleop_replay.time, "sleep", lambda _s: None)
    writer = FakeSyncWriter()
    recording = io.StringIO(
        '{"t": 0.0, "joints": {"1": 100}}\n\n{"t": 0.016, "joints": {"1": 110}}\n'
    )
    list(teleop_replay._replay_loop(writer, recording))
    assert writer.batches == [{1: 100}, {1: 110}]
