"""Unit tests for tools/_teleop_common.py — shared STS3215 protocol helpers."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"


def _import_teleop_common():
    spec = importlib.util.spec_from_file_location(
        "_teleop_common", TOOLS_DIR / "_teleop_common.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_teleop_common"] = mod
    spec.loader.exec_module(mod)
    return mod


teleop_common = _import_teleop_common()


@dataclass
class FakePacket:
    byte_writes: list[tuple[int, int, int]] = field(default_factory=list)
    word_writes: list[tuple[int, int, int]] = field(default_factory=list)

    def write1ByteTxRx(self, _port: object, sid: int, addr: int, val: int) -> int:  # noqa: N802
        self.byte_writes.append((sid, addr, val))
        return 0

    def write2ByteTxRx(self, _port: object, sid: int, addr: int, val: int) -> int:  # noqa: N802
        self.word_writes.append((sid, addr, val))
        return 0


@dataclass
class FakeSyncWriter:
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


def test_env_int_returns_default_when_var_unset(monkeypatch) -> None:
    monkeypatch.delenv("TEST_TELEOP_COMMON_INT", raising=False)
    assert teleop_common.env_int("TEST_TELEOP_COMMON_INT", 42) == 42


def test_env_int_returns_default_when_var_empty(monkeypatch) -> None:
    monkeypatch.setenv("TEST_TELEOP_COMMON_INT", "")
    assert teleop_common.env_int("TEST_TELEOP_COMMON_INT", 42) == 42


def test_env_int_reads_value_from_env(monkeypatch) -> None:
    monkeypatch.setenv("TEST_TELEOP_COMMON_INT", "123")
    assert teleop_common.env_int("TEST_TELEOP_COMMON_INT", 42) == 123


def test_set_torque_writes_enable_byte_for_each_servo() -> None:
    packet = FakePacket()
    teleop_common.set_torque(packet, port=object(), enabled=1)
    expected = [
        (sid, teleop_common.ADDR_TORQUE_ENABLE, 1) for sid in teleop_common.SERVO_IDS
    ]
    assert packet.byte_writes == expected


def test_setup_follower_motion_writes_acc_byte_for_each_servo() -> None:
    packet = FakePacket()
    teleop_common.setup_follower_motion(packet, port=object(), acc=40, vel_cap=2000)
    expected = [(sid, teleop_common.ADDR_ACC, 40) for sid in teleop_common.SERVO_IDS]
    assert packet.byte_writes == expected


def test_setup_follower_motion_writes_velocity_word_for_each_servo() -> None:
    packet = FakePacket()
    teleop_common.setup_follower_motion(packet, port=object(), acc=40, vel_cap=2000)
    expected = {
        (sid, teleop_common.ADDR_GOAL_VELOCITY, 2000) for sid in teleop_common.SERVO_IDS
    }
    assert expected.issubset(set(packet.word_writes))


def test_setup_follower_motion_writes_goal_time_zero_for_each_servo() -> None:
    packet = FakePacket()
    teleop_common.setup_follower_motion(packet, port=object(), acc=40, vel_cap=2000)
    expected = {
        (sid, teleop_common.ADDR_GOAL_TIME, 0) for sid in teleop_common.SERVO_IDS
    }
    assert expected.issubset(set(packet.word_writes))


def test_write_follower_goals_sync_writes_each_servo() -> None:
    writer = FakeSyncWriter()
    goals = {1: 100, 2: 200, 3: 300}
    teleop_common.write_follower_goals(writer, goals)
    assert writer.batches == [goals]
    assert writer.clear_calls == 1


def test_write_follower_goals_is_noop_when_goals_empty() -> None:
    writer = FakeSyncWriter()
    teleop_common.write_follower_goals(writer, {})
    assert writer.batches == []
    assert writer.clear_calls == 0


def test_format_record_line_emits_jsonl_with_timestamp_and_joints() -> None:
    line = teleop_common.format_record_line(
        0.5, {1: 100, 2: 200, 3: 300, 4: 400, 5: 500, 6: 600}
    )
    assert line.endswith("\n")
    record = json.loads(line)
    assert record["t"] == 0.5
    assert record["joints"] == {
        "1": 100,
        "2": 200,
        "3": 300,
        "4": 400,
        "5": 500,
        "6": 600,
    }


def test_format_record_line_rounds_timestamp_to_milliseconds() -> None:
    line = teleop_common.format_record_line(0.123456789, {1: 100})
    record = json.loads(line)
    assert record["t"] == 0.123


def test_parse_record_line_round_trips_with_format_record_line() -> None:
    original_t = 0.456
    original_joints = {1: 100, 2: 200, 3: 300}
    line = teleop_common.format_record_line(original_t, original_joints)
    t, joints = teleop_common.parse_record_line(line)
    assert t == original_t
    assert joints == original_joints
    assert all(isinstance(k, int) for k in joints)
