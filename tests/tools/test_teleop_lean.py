"""Unit tests for tools/teleop_lean.py — pure logic, no scservo_sdk, no hardware."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"


def _import_teleop_lean():
    spec = importlib.util.spec_from_file_location(
        "teleop_lean", TOOLS_DIR / "teleop_lean.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so module-level @dataclass introspection
    # (sys.modules.get(cls.__module__)) can resolve our module.
    sys.modules["teleop_lean"] = mod
    spec.loader.exec_module(mod)
    return mod


teleop_lean = _import_teleop_lean()


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
class FakeSyncWriter:
    written: dict[int, int] = field(default_factory=dict)
    clear_calls: int = 0
    tx_calls: int = 0

    def clearParam(self) -> None:  # noqa: N802
        self.clear_calls += 1

    def addParam(self, sid: int, data: list[int]) -> bool:  # noqa: N802
        self.written[sid] = data[0] | (data[1] << 8)
        return True

    def txPacket(self) -> int:  # noqa: N802
        self.tx_calls += 1
        return 0


def test_setup_follower_motion_writes_acc_byte_for_each_servo() -> None:
    packet = FakePacket()
    teleop_lean.setup_follower_motion(packet, port=object(), acc=40, vel_cap=2000)
    expected = [(sid, teleop_lean.ADDR_ACC, 40) for sid in teleop_lean.SERVO_IDS]
    assert packet.byte_writes == expected


def test_setup_follower_motion_writes_velocity_word_for_each_servo() -> None:
    packet = FakePacket()
    teleop_lean.setup_follower_motion(packet, port=object(), acc=40, vel_cap=2000)
    expected = {
        (sid, teleop_lean.ADDR_GOAL_VELOCITY, 2000) for sid in teleop_lean.SERVO_IDS
    }
    assert expected.issubset(set(packet.word_writes))


def test_setup_follower_motion_writes_goal_time_zero_for_each_servo() -> None:
    packet = FakePacket()
    teleop_lean.setup_follower_motion(packet, port=object(), acc=40, vel_cap=2000)
    expected = {(sid, teleop_lean.ADDR_GOAL_TIME, 0) for sid in teleop_lean.SERVO_IDS}
    assert expected.issubset(set(packet.word_writes))


def test_mirror_tick_forwards_all_available_positions() -> None:
    positions = {1: 100, 2: 200, 3: 300, 4: 400, 5: 500, 6: 600}
    reader = FakeSyncReader(available=positions)
    writer = FakeSyncWriter()
    teleop_lean._mirror_tick(reader, writer)
    assert writer.written == positions
    assert writer.tx_calls == 1


def test_mirror_tick_skips_unavailable_servos() -> None:
    reader = FakeSyncReader(available={1: 100, 3: 300})  # 2,4,5,6 unavailable
    writer = FakeSyncWriter()
    teleop_lean._mirror_tick(reader, writer)
    assert writer.written == {1: 100, 3: 300}
    assert writer.tx_calls == 1


def test_mirror_tick_skips_write_when_sync_read_fails() -> None:
    reader = FakeSyncReader(available={1: 100}, txrx_result=-1)
    writer = FakeSyncWriter()
    teleop_lean._mirror_tick(reader, writer)
    assert writer.written == {}
    assert writer.tx_calls == 0


def test_mirror_tick_skips_write_when_no_servo_available() -> None:
    reader = FakeSyncReader(available={})
    writer = FakeSyncWriter()
    teleop_lean._mirror_tick(reader, writer)
    assert writer.tx_calls == 0


def test_env_int_returns_default_when_var_unset(monkeypatch) -> None:
    monkeypatch.delenv("TEST_TELEOP_LEAN_INT", raising=False)
    assert teleop_lean._env_int("TEST_TELEOP_LEAN_INT", 42) == 42


def test_env_int_returns_default_when_var_empty(monkeypatch) -> None:
    monkeypatch.setenv("TEST_TELEOP_LEAN_INT", "")
    assert teleop_lean._env_int("TEST_TELEOP_LEAN_INT", 42) == 42


def test_env_int_reads_value_from_env(monkeypatch) -> None:
    monkeypatch.setenv("TEST_TELEOP_LEAN_INT", "123")
    assert teleop_lean._env_int("TEST_TELEOP_LEAN_INT", 42) == 123


def test_format_capture_line_emits_yaml_paste_line() -> None:
    line = teleop_lean.format_capture_line("demo_grip", [100, 200, 300, 400, 500, 600])
    assert line == "  demo_grip: [100, 200, 300, 400, 500, 600]  # raw STS3215 ticks"


def test_read_follower_positions_returns_full_dict_on_success() -> None:
    available = {1: 100, 2: 200, 3: 300, 4: 400, 5: 500, 6: 600}
    reader = FakeSyncReader(available=available)
    assert teleop_lean.read_follower_positions(reader) == available


def test_read_follower_positions_returns_none_when_sync_read_fails() -> None:
    reader = FakeSyncReader(available={1: 100}, txrx_result=-1)
    assert teleop_lean.read_follower_positions(reader) is None


def test_read_follower_positions_returns_none_when_no_servo_available() -> None:
    reader = FakeSyncReader(available={})
    assert teleop_lean.read_follower_positions(reader) is None


def test_consume_capture_returns_none_when_no_request_pending() -> None:
    state = teleop_lean._CaptureState()
    reader = FakeSyncReader(available={1: 100})
    assert teleop_lean.consume_capture(state, reader) is None
    assert state.counter == 0


def test_consume_capture_emits_line_and_clears_flag_on_success() -> None:
    state = teleop_lean._CaptureState(requested=True)
    reader = FakeSyncReader(available={1: 100, 2: 200, 3: 300, 4: 400, 5: 500, 6: 600})
    line = teleop_lean.consume_capture(state, reader)
    assert line == "  captured_1: [100, 200, 300, 400, 500, 600]  # raw STS3215 ticks"
    assert state.requested is False
    assert state.counter == 1


def test_consume_capture_returns_none_and_clears_flag_on_read_failure() -> None:
    state = teleop_lean._CaptureState(requested=True)
    reader = FakeSyncReader(available={}, txrx_result=-1)
    assert teleop_lean.consume_capture(state, reader) is None
    assert state.requested is False  # flag cleared even on failure (don't re-fire)
    assert state.counter == 1  # counter still increments; aligns with stdout log


def test_mirror_tick_returns_goals_dict_on_success() -> None:
    positions = {1: 100, 2: 200, 3: 300, 4: 400, 5: 500, 6: 600}
    reader = FakeSyncReader(available=positions)
    writer = FakeSyncWriter()
    assert teleop_lean._mirror_tick(reader, writer) == positions


def test_mirror_tick_returns_empty_dict_when_sync_read_fails() -> None:
    reader = FakeSyncReader(available={1: 100}, txrx_result=-1)
    writer = FakeSyncWriter()
    assert teleop_lean._mirror_tick(reader, writer) == {}


def test_mirror_tick_returns_empty_dict_when_no_servo_available() -> None:
    reader = FakeSyncReader(available={})
    writer = FakeSyncWriter()
    assert teleop_lean._mirror_tick(reader, writer) == {}


def test_format_record_line_emits_jsonl_with_timestamp_and_joints() -> None:
    import json

    line = teleop_lean.format_record_line(
        0.5, {1: 100, 2: 200, 3: 300, 4: 400, 5: 500, 6: 600}
    )
    assert line.endswith("\n"), "record lines must terminate with newline for JSONL"
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
    import json

    line = teleop_lean.format_record_line(0.123456789, {1: 100})
    record = json.loads(line)
    # 1 ms precision is enough for STS3215's 30-60 Hz update; keeps lines short.
    assert record["t"] == 0.123
