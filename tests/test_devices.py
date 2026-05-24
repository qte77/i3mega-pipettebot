"""Device-discovery substrate: classify, parse, policy lookup, port resolve."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

if TYPE_CHECKING:
    from collections.abc import Callable

from pipettebot.devices import (
    FIRMWARE_POLICIES,
    DiscoveredDevice,
    FirmwarePolicy,
    classify,
    discover,
    parse_m115,
    policy_for,
    resolve_port,
    safe_home,
)
from pipettebot.gantry import GantryConfig, GcodeGantry
from tests.conftest import FakeSerial
from tests.fixtures.m115_replies import (
    A30_M115_LIVE,
    MARLIN_AI3M_M115_SAMPLE,
    UNKNOWN_FIRMWARE_M115_SAMPLE,
)

# classify(): firmware family from M115 reply substring.


def test_classify_recognises_marlin_via_firmware_name_token() -> None:
    assert classify(MARLIN_AI3M_M115_SAMPLE) == "marlin"


def test_classify_recognises_smartto_via_a30_machine_type() -> None:
    assert classify(A30_M115_LIVE) == "smartto"


def test_classify_returns_unknown_for_unrecognised_reply() -> None:
    assert classify(UNKNOWN_FIRMWARE_M115_SAMPLE) == "unknown"


# parse_m115(): structured observation from raw reply.


def test_parse_m115_extracts_firmware_name_field() -> None:
    result = parse_m115(A30_M115_LIVE, baud=115200)
    assert result.firmware_version == "V1.xx.58"


def test_parse_m115_extracts_machine_type_field() -> None:
    result = parse_m115(A30_M115_LIVE, baud=115200)
    assert result.machine_type == "A30"


def test_parse_m115_fills_baud_and_raw_fields() -> None:
    result = parse_m115(A30_M115_LIVE, baud=115200)
    assert result.baud == 115200
    assert result.raw_m115 == A30_M115_LIVE


def test_parse_m115_classifies_firmware_family() -> None:
    assert parse_m115(A30_M115_LIVE, baud=115200).firmware_family == "smartto"
    assert parse_m115(MARLIN_AI3M_M115_SAMPLE, baud=250000).firmware_family == "marlin"


def test_parse_m115_handles_missing_optional_fields() -> None:
    minimal = "FIRMWARE_NAME:foo bar"
    result = parse_m115(minimal, baud=0)
    assert result.firmware_version == "foo"
    assert result.machine_type is None


def test_discovered_device_is_frozen() -> None:
    result = parse_m115(A30_M115_LIVE, baud=115200)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.baud = 999  # type: ignore[misc]


# FirmwarePolicy + policy_for(): per-family behavior lookup.


def test_firmware_policies_registers_marlin_smartto_unknown() -> None:
    families = {p.family for p in FIRMWARE_POLICIES}
    assert {"marlin", "smartto", "unknown"} <= families


def test_policy_for_marlin_returns_full_g28_strategy() -> None:
    device = parse_m115(MARLIN_AI3M_M115_SAMPLE, baud=250000)
    assert policy_for(device).home_strategy == "full_g28"


def test_policy_for_smartto_returns_xy_then_polled_z_strategy() -> None:
    device = parse_m115(A30_M115_LIVE, baud=115200)
    assert policy_for(device).home_strategy == "xy_then_polled_z"


def test_policy_for_unknown_returns_manual_only_strategy() -> None:
    device = parse_m115(UNKNOWN_FIRMWARE_M115_SAMPLE, baud=115200)
    policy = policy_for(device)
    assert policy.family == "unknown"
    assert policy.home_strategy == "manual_only"


# resolve_port(): single PRINTER_PORT env, firmware-agnostic.


def test_resolve_port_returns_printer_port_value_when_set() -> None:
    assert resolve_port(env={"PRINTER_PORT": "/dev/ttyUSB1"}) == "/dev/ttyUSB1"


def test_resolve_port_returns_none_when_printer_port_unset() -> None:
    assert resolve_port(env={}) is None


def test_resolve_port_returns_none_when_printer_port_empty_string() -> None:
    assert resolve_port(env={"PRINTER_PORT": ""}) is None


# safe_home(): policy-driven home dispatch + polled-Z descent for smartto.


def _gantry_with(fake_serial: FakeSerial) -> GcodeGantry:
    return GcodeGantry(GantryConfig(port="/dev/null"), fake_serial)


def _policy(family: str) -> FirmwarePolicy:
    return next(p for p in FIRMWARE_POLICIES if p.family == family)


def _triggers_after(n_polls: int) -> Callable[[GcodeGantry], bool]:
    """Return a probe that says False `n_polls` times, then True forever."""
    state = {"polls": 0}

    def _probe(_gantry: GcodeGantry) -> bool:
        triggered = state["polls"] >= n_polls
        state["polls"] += 1
        return triggered

    return _probe


def test_safe_home_full_g28_sends_single_g28(fake_serial: FakeSerial) -> None:
    safe_home(_gantry_with(fake_serial), _policy("marlin"))
    assert fake_serial.written == [b"G28\n"]


def test_safe_home_full_g28_does_not_poll_z_min(fake_serial: FakeSerial) -> None:
    def _raises(_gantry: GcodeGantry) -> bool:
        raise AssertionError("z_min_triggered must not fire on full_g28")

    safe_home(_gantry_with(fake_serial), _policy("marlin"), z_min_triggered=_raises)


def test_safe_home_polled_z_skips_descent_when_already_triggered(
    fake_serial: FakeSerial,
) -> None:
    """Carriage already at sensor trigger zone: G28 X Y then G92 Z0, no descent."""
    safe_home(
        _gantry_with(fake_serial),
        _policy("smartto"),
        z_min_triggered=_triggers_after(0),
    )
    assert fake_serial.written == [b"G28 X Y\n", b"G92 Z0\n"]


def test_safe_home_polled_z_descends_in_absolute_mode_until_triggered(
    fake_serial: FakeSerial,
) -> None:
    """Absolute-mode descent: targets walk max_travel down to 0, no G91/G90."""
    safe_home(
        _gantry_with(fake_serial),
        _policy("smartto"),
        z_min_triggered=_triggers_after(3),
        max_steps=3,
        step_mm=1.0,
        feedrate=300,
    )
    # G92 Z3.000 declares current Z as max_travel; absolute descent walks
    # 2.000 -> 1.000 -> 0.000. No G91 (relative mode is broken on Smartto)
    # and no G90 (we never left absolute).
    assert fake_serial.written == [
        b"G28 X Y\n",
        b"G92 Z3.000\n",
        b"G1 Z2.000 F300\n",
        b"M400\n",
        b"G1 Z1.000 F300\n",
        b"M400\n",
        b"G1 Z0.000 F300\n",
        b"M400\n",
        b"G92 Z0\n",
    ]


def test_safe_home_polled_z_does_not_send_g91_or_g90(
    fake_serial: FakeSerial,
) -> None:
    """Polled descent must stay in absolute mode — G91 broke Z on Smartto."""

    def _never_triggers(_gantry: GcodeGantry) -> bool:
        return False

    with pytest.raises(RuntimeError):
        safe_home(
            _gantry_with(fake_serial),
            _policy("smartto"),
            z_min_triggered=_never_triggers,
            max_steps=5,
            step_mm=2.0,
            feedrate=300,
        )
    assert b"G91\n" not in fake_serial.written
    assert b"G90\n" not in fake_serial.written
    # max_travel = max_steps * step_mm = 10.0 — headroom must be set before
    # any G1 Z command.
    g92_headroom_idx = fake_serial.written.index(b"G92 Z10.000\n")
    first_g1_idx = next(
        i for i, w in enumerate(fake_serial.written) if w.startswith(b"G1 Z")
    )
    assert g92_headroom_idx < first_g1_idx


def test_safe_home_polled_z_raises_when_max_steps_exceeded(
    fake_serial: FakeSerial,
) -> None:
    """Sensor never triggers within max_steps; expect RuntimeError + restored G90."""

    def _never_triggers(_gantry: GcodeGantry) -> bool:
        return False

    with pytest.raises(RuntimeError, match=r"z_min did not trigger"):
        safe_home(
            _gantry_with(fake_serial),
            _policy("smartto"),
            z_min_triggered=_never_triggers,
            max_steps=2,
            step_mm=1.0,
            feedrate=300,
        )
    # No G92 Z0 on failure — origin is not declared if the sensor never fired.
    assert b"G92 Z0\n" not in fake_serial.written
    # Failure path queries M119 + M114 to capture endstop state and
    # firmware-recorded position for the diagnostic error message.
    assert fake_serial.written.count(b"M119\n") == 1
    assert fake_serial.written.count(b"M114\n") == 1


def test_safe_home_polled_z_failure_message_includes_diagnostic_prefix(
    fake_serial: FakeSerial,
) -> None:
    """The RuntimeError must carry the 'Last M119 reply:' diagnostic prefix."""

    def _never_triggers(_gantry: GcodeGantry) -> bool:
        return False

    with pytest.raises(RuntimeError, match=r"Last M119 reply"):
        safe_home(
            _gantry_with(fake_serial),
            _policy("smartto"),
            z_min_triggered=_never_triggers,
            max_steps=1,
            step_mm=1.0,
            feedrate=300,
        )


def test_safe_home_manual_only_raises_and_writes_nothing(
    fake_serial: FakeSerial,
) -> None:
    with pytest.raises(RuntimeError, match=r"manual_only"):
        safe_home(_gantry_with(fake_serial), _policy("unknown"))
    assert fake_serial.written == []


def test_safe_home_manual_only_does_not_poll_z_min(
    fake_serial: FakeSerial,
) -> None:
    def _raises(_gantry: GcodeGantry) -> bool:
        raise AssertionError("z_min_triggered must not fire on manual_only")

    with pytest.raises(RuntimeError):
        safe_home(
            _gantry_with(fake_serial), _policy("unknown"), z_min_triggered=_raises
        )


# _read_z_min_triggered(): default probe — sends M119, matches "z_min:TRIGGERED".


def test_read_z_min_triggered_true_on_smartto_style_reply() -> None:
    from pipettebot.devices import _read_z_min_triggered

    triggered_reply = (
        b"x_min:OPEN  x_max:OPEN  y_min:OPEN  y_max:OPEN  z_min:TRIGGERED z_max:OPEN\n"
    )
    fake = FakeSerial(responses=[triggered_reply, b"ok\n"])
    gantry = GcodeGantry(GantryConfig(port="/dev/null"), fake)
    assert _read_z_min_triggered(gantry) is True
    assert fake.written == [b"M119\n"]


def test_read_z_min_triggered_false_when_z_min_open() -> None:
    from pipettebot.devices import _read_z_min_triggered

    open_reply = (
        b"x_min:OPEN  x_max:OPEN  y_min:OPEN  y_max:OPEN  z_min:OPEN z_max:OPEN\n"
    )
    fake = FakeSerial(responses=[open_reply, b"ok\n"])
    gantry = GcodeGantry(GantryConfig(port="/dev/null"), fake)
    assert _read_z_min_triggered(gantry) is False


# discover(): the only I/O entry point. Tests monkeypatch the port opener.


def _fake_with_m115(raw_m115: str) -> FakeSerial:
    """FakeSerial pre-loaded with line-split M115 body + terminating `ok`."""
    line_responses = [line.encode("ascii") + b"\n" for line in raw_m115.split("\n")]
    return FakeSerial(responses=[*line_responses, b"ok\n"])


def test_discover_returns_none_when_port_silent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    silent = FakeSerial(default_response=b"")
    monkeypatch.setattr(
        "pipettebot.devices.open_gcode_port",
        lambda *_a, **_kw: silent,
    )
    assert discover("/dev/null", bauds=(115200,), boot_wait_s=0.0) is None


def test_discover_returns_smartto_when_m115_matches_at_first_baud(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    link = _fake_with_m115(A30_M115_LIVE)
    monkeypatch.setattr(
        "pipettebot.devices.open_gcode_port",
        lambda *_a, **_kw: link,
    )
    device = discover("/dev/null", bauds=(115200,), boot_wait_s=0.0)
    assert device is not None
    assert device.firmware_family == "smartto"
    assert device.machine_type == "A30"
    assert device.baud == 115200


def test_discover_falls_through_bauds_until_one_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    silent = FakeSerial(default_response=b"")
    answering = _fake_with_m115(MARLIN_AI3M_M115_SAMPLE)
    calls: list[int] = []

    def _opener(port: str, *, baudrate: int, timeout: float) -> FakeSerial:
        _ = port, timeout
        calls.append(baudrate)
        return silent if baudrate == 115200 else answering

    monkeypatch.setattr("pipettebot.devices.open_gcode_port", _opener)
    device = discover("/dev/null", bauds=(115200, 250000), boot_wait_s=0.0)
    assert device is not None
    assert device.firmware_family == "marlin"
    assert device.baud == 250000
    assert calls == [115200, 250000]


def test_discover_returns_unknown_observation_when_firmware_unrecognised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    link = _fake_with_m115(UNKNOWN_FIRMWARE_M115_SAMPLE)
    monkeypatch.setattr(
        "pipettebot.devices.open_gcode_port",
        lambda *_a, **_kw: link,
    )
    device = discover("/dev/null", bauds=(115200,), boot_wait_s=0.0)
    assert device is not None
    assert device.firmware_family == "unknown"
    assert device.machine_type == "Voron2.4"


# Robustness: the parser must survive arbitrary printable-ASCII input.


@given(st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126)))
def test_parse_m115_never_raises_on_arbitrary_printable_ascii(raw: str) -> None:
    device = parse_m115(raw, baud=115200)
    assert isinstance(device, DiscoveredDevice)
    assert device.baud == 115200
    assert device.raw_m115 == raw
