"""Tests for pipettebot.motion_profile.select_profile + MotionProfile."""

from __future__ import annotations

import dataclasses

import pytest

from pipettebot.motion_profile import (
    FAST,
    MID,
    PROFILES,
    SLOW,
    MotionProfile,
    select_profile,
)


def test_mid_is_default_when_env_unset() -> None:
    assert select_profile(None) is MID


def test_select_by_name_lowercase() -> None:
    assert select_profile("slow") is SLOW
    assert select_profile("mid") is MID
    assert select_profile("fast") is FAST


def test_select_is_case_insensitive() -> None:
    assert select_profile("MID") is MID
    assert select_profile("Fast") is FAST
    assert select_profile("SLOW") is SLOW


def test_select_trims_whitespace() -> None:
    assert select_profile("  slow  ") is SLOW
    assert select_profile("\tfast\n") is FAST


def test_opt_out_empty_string() -> None:
    assert select_profile("") is None


def test_opt_out_off() -> None:
    assert select_profile("off") is None
    assert select_profile("OFF") is None
    assert select_profile("  off  ") is None


def test_unknown_profile_raises() -> None:
    with pytest.raises(ValueError, match="Unknown motion profile"):
        select_profile("turbo")


def test_unknown_profile_error_message_lists_valid_options() -> None:
    with pytest.raises(ValueError) as exc:
        select_profile("turbo")
    msg = str(exc.value)
    assert "slow" in msg
    assert "mid" in msg
    assert "fast" in msg
    assert "off" in msg


def test_motion_profile_is_frozen_dataclass() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        MID.name = "mutated"  # type: ignore[misc]


def test_mid_as_marlin_returns_four_strings() -> None:
    cmds = MID.as_marlin()
    assert len(cmds) == 4
    assert all(isinstance(c, str) for c in cmds)


def test_mid_as_marlin_m203_format() -> None:
    assert MID.as_marlin()[0] == "M203 X500 Y500 Z20"


def test_mid_as_marlin_m201_format() -> None:
    assert MID.as_marlin()[1] == "M201 X600 Y800 Z200"


def test_mid_as_marlin_m204_format() -> None:
    assert MID.as_marlin()[2] == "M204 P600 R600 T600"


def test_mid_as_marlin_m205_format() -> None:
    assert MID.as_marlin()[3] == "M205 X3 Y5 Z0.2 E0"


def test_slow_z_accel_is_below_mid() -> None:
    assert SLOW.accel_z < MID.accel_z


def test_fast_z_accel_is_above_mid() -> None:
    assert FAST.accel_z > MID.accel_z


def test_all_profiles_share_feedrate_caps() -> None:
    for p in (SLOW, MID, FAST):
        assert p.feed_x == 500
        assert p.feed_y == 500
        assert p.feed_z == 20


def test_profiles_registry_has_three_entries() -> None:
    assert set(PROFILES.keys()) == {"slow", "mid", "fast"}


def test_motion_profile_is_exported_from_package() -> None:
    import pipettebot

    assert pipettebot.MotionProfile is MotionProfile
    assert pipettebot.select_profile is select_profile
