"""Tests for pipettebot.profiles.load_profile."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

from pipettebot.profiles import load_profile

if TYPE_CHECKING:
    from pathlib import Path


def _write(tmp_path: Path, content: str, name: str = "profile.toml") -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content).lstrip())
    return p


def test_per_cycle_list(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
        name = "calib"
        description = "linear ramp"

        [volumes]
        per_cycle_ul = [10.0, 20.0, 30.0]
        """,
    )
    profile = load_profile(p)
    assert profile.name == "calib"
    assert profile.description == "linear ramp"
    assert profile.volumes_ul == (10.0, 20.0, 30.0)
    assert profile.num_cycles == 3
    assert profile.gradient_description == ""


def test_constant_plus_count(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
        [volumes]
        constant_ul = 100.0
        num_cycles = 4
        """,
    )
    profile = load_profile(p)
    assert profile.volumes_ul == (100.0, 100.0, 100.0, 100.0)


def test_name_defaults_to_stem(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "[volumes]\nconstant_ul = 50.0\nnum_cycles = 1\n",
        name="my_profile.toml",
    )
    profile = load_profile(p)
    assert profile.name == "my_profile"


def test_gradient_description(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
        [volumes]
        constant_ul = 100.0
        num_cycles = 11

        [gradient]
        description = "1:8 dilution along Y"
        """,
    )
    profile = load_profile(p)
    assert profile.gradient_description == "1:8 dilution along Y"


def test_error_both_specified(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
        [volumes]
        per_cycle_ul = [10.0]
        constant_ul = 100.0
        num_cycles = 1
        """,
    )
    with pytest.raises(ValueError, match="EITHER"):
        load_profile(p)


def test_error_neither_specified(tmp_path: Path) -> None:
    p = _write(tmp_path, "[volumes]\n")
    with pytest.raises(ValueError, match="must set one of"):
        load_profile(p)


def test_error_empty_per_cycle(tmp_path: Path) -> None:
    p = _write(tmp_path, "[volumes]\nper_cycle_ul = []\n")
    with pytest.raises(ValueError, match="non-empty list"):
        load_profile(p)


def test_error_negative_volume(tmp_path: Path) -> None:
    p = _write(tmp_path, "[volumes]\nper_cycle_ul = [10.0, -5.0]\n")
    with pytest.raises(ValueError, match="> 0"):
        load_profile(p)


def test_error_bad_num_cycles(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
        [volumes]
        constant_ul = 100.0
        num_cycles = 0
        """,
    )
    with pytest.raises(ValueError, match="positive int"):
        load_profile(p)


def test_sample_profiles_load() -> None:
    """The two checked-in sample profiles parse without errors."""
    from pathlib import Path as _Path

    repo_root = _Path(__file__).resolve().parents[1]
    samples = repo_root / "examples" / "profiles"
    calib = load_profile(samples / "calibration_curve_demo.toml")
    gradient = load_profile(samples / "gradient_reservoir_demo.toml")

    assert calib.num_cycles == 11
    assert calib.volumes_ul[0] == 20.0
    assert calib.volumes_ul[-1] == 220.0

    assert gradient.num_cycles == 11
    assert all(v == 100.0 for v in gradient.volumes_ul)
    assert "100.00 %" in gradient.gradient_description
