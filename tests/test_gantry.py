"""GcodeGantry: verify line framing, M400 sync, and close()."""

from __future__ import annotations

import pytest

from pipettebot.gantry import GantryConfig, GcodeGantry, send_and_wait_for_ok
from tests.conftest import FakeSerial


def _gantry(fake_serial: FakeSerial) -> GcodeGantry:
    return GcodeGantry(GantryConfig(port="/dev/null"), fake_serial)


def test_home_sends_g28(fake_serial: FakeSerial) -> None:
    _gantry(fake_serial).home()
    assert fake_serial.written == [b"G28\n"]


def test_move_to_formats_floats(fake_serial: FakeSerial) -> None:
    _gantry(fake_serial).move_to(100.0, 110.5, 5.25)
    assert fake_serial.written == [b"G1 X100.000 Y110.500 Z5.250 F3000\n"]


def test_move_to_uses_feedrate_override(fake_serial: FakeSerial) -> None:
    _gantry(fake_serial).move_to(0.0, 0.0, 0.0, feedrate=600)
    assert fake_serial.written == [b"G1 X0.000 Y0.000 Z0.000 F600\n"]


def test_wait_for_moves_sends_m400(fake_serial: FakeSerial) -> None:
    _gantry(fake_serial).wait_for_moves()
    assert fake_serial.written == [b"M400\n"]


def test_close_propagates(fake_serial: FakeSerial) -> None:
    _gantry(fake_serial).close()
    assert fake_serial.closed is True


def test_response_is_returned_stripped(fake_serial: FakeSerial) -> None:
    fake_serial.responses = [b"ok\r\n"]
    assert _gantry(fake_serial).home() == "ok"


# send_and_wait_for_ok: lifted gsend helper (PR1).


def test_send_and_wait_for_ok_returns_lines_until_ok(fake_serial: FakeSerial) -> None:
    fake_serial.responses = [b"echo: foo\n", b"echo: bar\n", b"ok\n"]
    assert send_and_wait_for_ok(fake_serial, "M115") == ["echo: foo", "echo: bar", "ok"]
    assert fake_serial.written == [b"M115\n"]


def test_send_and_wait_for_ok_raises_on_timeout() -> None:
    silent = FakeSerial(default_response=b"")
    with pytest.raises(TimeoutError, match=r"no `ok` after"):
        send_and_wait_for_ok(silent, "G28", max_secs=0.05)


def test_send_and_wait_for_ok_accepts_extras_after_ok(fake_serial: FakeSerial) -> None:
    fake_serial.responses = [b"ok N:42 P:3\n"]
    assert send_and_wait_for_ok(fake_serial, "M400") == ["ok N:42 P:3"]
