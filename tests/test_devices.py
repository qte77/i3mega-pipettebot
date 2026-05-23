"""Device-discovery substrate: classify, parse, policy lookup, port resolve."""

from __future__ import annotations

import dataclasses

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pipettebot.devices import (
    FIRMWARE_POLICIES,
    DiscoveredDevice,
    classify,
    discover,
    parse_m115,
    policy_for,
    resolve_port,
)
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


# resolve_port(): operator env-var resolution with alias fallthrough.


def test_resolve_port_uses_first_alias_set_in_env() -> None:
    device = parse_m115(MARLIN_AI3M_M115_SAMPLE, baud=250000)
    policy = policy_for(device)
    env = {"I3MEGA_PORT": "/dev/ttyUSB1"}
    assert resolve_port(policy, env=env) == "/dev/ttyUSB1"


def test_resolve_port_falls_through_to_gantry_port_when_specific_alias_unset() -> None:
    device = parse_m115(MARLIN_AI3M_M115_SAMPLE, baud=250000)
    policy = policy_for(device)
    env = {"GANTRY_PORT": "/dev/ttyACM0"}
    assert resolve_port(policy, env=env) == "/dev/ttyACM0"


def test_resolve_port_returns_none_when_no_alias_set() -> None:
    device = parse_m115(A30_M115_LIVE, baud=115200)
    policy = policy_for(device)
    assert resolve_port(policy, env={}) is None


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
