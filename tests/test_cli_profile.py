"""Tests for pipettebot.cli_profile.resolve_profile + build_volumes."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

from pipettebot.cli_profile import build_volumes, resolve_profile

if TYPE_CHECKING:
    from pathlib import Path


def _write_profile(tmp_path: Path, content: str, name: str = "profile.toml") -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content).lstrip())
    return p


# resolve_profile() ----------------------------------------------------------


def test_resolve_profile_returns_none_for_empty_env() -> None:
    assert resolve_profile(env={}) is None


def test_resolve_profile_returns_none_for_empty_string() -> None:
    assert resolve_profile(env={"PIPETTE_PROFILE": ""}) is None


def test_resolve_profile_returns_none_for_whitespace() -> None:
    assert resolve_profile(env={"PIPETTE_PROFILE": "   "}) is None


def test_resolve_profile_loads_toml_when_path_set(tmp_path: Path) -> None:
    p = _write_profile(
        tmp_path,
        """
        name = "calib"

        [volumes]
        per_cycle_ul = [10.0, 20.0, 30.0]
        """,
    )
    profile = resolve_profile(env={"PIPETTE_PROFILE": str(p)})
    assert profile is not None
    assert profile.name == "calib"
    assert profile.volumes_ul == (10.0, 20.0, 30.0)


def test_resolve_profile_strips_whitespace_around_path(tmp_path: Path) -> None:
    p = _write_profile(
        tmp_path,
        "[volumes]\nconstant_ul = 50.0\nnum_cycles = 1\n",
    )
    profile = resolve_profile(env={"PIPETTE_PROFILE": f"  {p}  "})
    assert profile is not None
    assert profile.volumes_ul == (50.0,)


# build_volumes() — constant fallback path -----------------------------------


def test_build_volumes_default_uses_default_volume_constant() -> None:
    volumes, banner = build_volumes(default_count=11, unit_label="columns", env={})
    assert volumes == (100.0,) * 11
    assert "constant volume 100.0 uL x 11 columns" in banner


def test_build_volumes_uses_pipette_volume_ul_env_when_set() -> None:
    volumes, banner = build_volumes(
        default_count=12,
        unit_label="cycles",
        env={"PIPETTE_VOLUME_UL": "75.5"},
    )
    assert volumes == (75.5,) * 12
    assert "constant volume 75.5 uL x 12 cycles" in banner


def test_build_volumes_banner_columns_label() -> None:
    _, banner = build_volumes(default_count=11, unit_label="columns", env={})
    assert "11 columns" in banner


def test_build_volumes_banner_cycles_label() -> None:
    _, banner = build_volumes(default_count=12, unit_label="cycles", env={})
    assert "12 cycles" in banner


# build_volumes() — profile-driven path --------------------------------------


def test_build_volumes_uses_profile_volumes_when_path_set(tmp_path: Path) -> None:
    p = _write_profile(
        tmp_path,
        """
        name = "ramp"

        [volumes]
        per_cycle_ul = [25.0, 50.0, 75.0]
        """,
    )
    volumes, _ = build_volumes(
        default_count=11,
        unit_label="columns",
        env={"PIPETTE_PROFILE": str(p)},
    )
    assert volumes == (25.0, 50.0, 75.0)


def test_build_volumes_profile_length_drives_count(tmp_path: Path) -> None:
    """Profile length must override default_count when profile is set."""
    p = _write_profile(
        tmp_path,
        """
        [volumes]
        per_cycle_ul = [10.0, 20.0, 30.0, 40.0, 50.0]
        """,
    )
    volumes, _ = build_volumes(
        default_count=11,  # overridden
        unit_label="columns",
        env={"PIPETTE_PROFILE": str(p)},
    )
    assert len(volumes) == 5


def test_build_volumes_banner_with_profile_name(tmp_path: Path) -> None:
    p = _write_profile(
        tmp_path,
        """
        name = "my_curve"

        [volumes]
        constant_ul = 100.0
        num_cycles = 4
        """,
    )
    _, banner = build_volumes(
        default_count=11,
        unit_label="columns",
        env={"PIPETTE_PROFILE": str(p)},
    )
    assert "'my_curve'" in banner
    assert "4 columns" in banner


def test_build_volumes_banner_includes_description(tmp_path: Path) -> None:
    p = _write_profile(
        tmp_path,
        """
        description = "linear calibration ramp"

        [volumes]
        per_cycle_ul = [10.0, 20.0]
        """,
    )
    _, banner = build_volumes(
        default_count=11,
        unit_label="columns",
        env={"PIPETTE_PROFILE": str(p)},
    )
    assert "linear calibration ramp" in banner


def test_build_volumes_banner_includes_gradient(tmp_path: Path) -> None:
    p = _write_profile(
        tmp_path,
        """
        [volumes]
        constant_ul = 100.0
        num_cycles = 11

        [gradient]
        description = "1:8 dilution along Y"
        """,
    )
    _, banner = build_volumes(
        default_count=11,
        unit_label="columns",
        env={"PIPETTE_PROFILE": str(p)},
    )
    assert "gradient: 1:8 dilution along Y" in banner


# Package re-export sanity ---------------------------------------------------


def test_cli_profile_re_exported_from_package() -> None:
    import pipettebot

    assert pipettebot.resolve_profile is resolve_profile
    assert pipettebot.build_volumes is build_volumes


def test_unused_pytest_helper_import() -> None:
    """Guards against accidentally dropping the pytest import via ruff."""
    assert pytest.raises is not None
