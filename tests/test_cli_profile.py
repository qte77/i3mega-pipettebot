"""Tests for pipettebot.cli_profile (shared showcase env-var resolution)."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

from pipettebot.cli_profile import DEFAULT_VOLUME_UL, build_volumes, resolve_profile

if TYPE_CHECKING:
    from pathlib import Path


def _write(tmp_path: Path, content: str, name: str = "profile.toml") -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content).lstrip())
    return p


# --- resolve_profile ----------------------------------------------------


def test_resolve_profile_returns_none_when_unset() -> None:
    assert resolve_profile(env={}) is None


def test_resolve_profile_returns_none_when_empty() -> None:
    assert resolve_profile(env={"PIPETTE_PROFILE": ""}) is None


def test_resolve_profile_returns_none_when_whitespace() -> None:
    assert resolve_profile(env={"PIPETTE_PROFILE": "   "}) is None


def test_resolve_profile_loads_profile(tmp_path: Path) -> None:
    p = _write(tmp_path, "[volumes]\nper_cycle_ul = [10.0, 20.0]\n")
    profile = resolve_profile(env={"PIPETTE_PROFILE": str(p)})
    assert profile is not None
    assert profile.volumes_ul == (10.0, 20.0)


def test_resolve_profile_strips_path_whitespace(tmp_path: Path) -> None:
    p = _write(tmp_path, "[volumes]\nper_cycle_ul = [5.0]\n")
    profile = resolve_profile(env={"PIPETTE_PROFILE": f"  {p}  "})
    assert profile is not None
    assert profile.volumes_ul == (5.0,)


def test_resolve_profile_raises_on_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "nope.toml"
    with pytest.raises(FileNotFoundError):
        resolve_profile(env={"PIPETTE_PROFILE": str(missing)})


# --- build_volumes — default constant path ------------------------------


def test_build_volumes_default_when_env_empty() -> None:
    volumes, banner = build_volumes(12, "cycles", env={})
    assert volumes == (DEFAULT_VOLUME_UL,) * 12
    assert "100.0 uL" in banner
    assert "12 cycles" in banner


def test_build_volumes_custom_volume_env() -> None:
    volumes, banner = build_volumes(3, "cycles", env={"PIPETTE_VOLUME_UL": "50"})
    assert volumes == (50.0, 50.0, 50.0)
    assert "50.0 uL" in banner
    assert "3 cycles" in banner


def test_build_volumes_uses_unit_label_in_banner() -> None:
    _, banner = build_volumes(11, "columns", env={})
    assert "columns" in banner
    assert "cycles" not in banner


def test_build_volumes_invalid_volume_raises() -> None:
    with pytest.raises(ValueError):
        build_volumes(3, "cycles", env={"PIPETTE_VOLUME_UL": "not-a-float"})


# --- build_volumes — profile path ---------------------------------------


def test_build_volumes_profile_overrides_default_count(tmp_path: Path) -> None:
    p = _write(tmp_path, "[volumes]\nper_cycle_ul = [10.0, 20.0, 30.0, 40.0]\n")
    volumes, _ = build_volumes(12, "cycles", env={"PIPETTE_PROFILE": str(p)})
    assert volumes == (10.0, 20.0, 30.0, 40.0)


def test_build_volumes_profile_banner_has_name_and_count(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
        name = "calib"
        [volumes]
        per_cycle_ul = [10.0, 20.0]
        """,
    )
    _, banner = build_volumes(12, "cycles", env={"PIPETTE_PROFILE": str(p)})
    assert "'calib'" in banner
    assert "2 cycles" in banner


def test_build_volumes_profile_banner_includes_description(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
        name = "calib"
        description = "linear ramp"
        [volumes]
        per_cycle_ul = [10.0]
        """,
    )
    _, banner = build_volumes(12, "cycles", env={"PIPETTE_PROFILE": str(p)})
    assert "linear ramp" in banner


def test_build_volumes_profile_banner_includes_gradient(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """
        [volumes]
        per_cycle_ul = [100.0]
        [gradient]
        description = "1:8 dilution"
        """,
    )
    _, banner = build_volumes(12, "cycles", env={"PIPETTE_PROFILE": str(p)})
    assert "gradient: 1:8 dilution" in banner


def test_build_volumes_profile_takes_priority_over_volume_env(tmp_path: Path) -> None:
    p = _write(tmp_path, "[volumes]\nper_cycle_ul = [7.0, 7.0]\n")
    volumes, banner = build_volumes(
        12,
        "cycles",
        env={"PIPETTE_PROFILE": str(p), "PIPETTE_VOLUME_UL": "999"},
    )
    assert volumes == (7.0, 7.0)
    assert "999" not in banner


def test_build_volumes_profile_uses_unit_label(tmp_path: Path) -> None:
    p = _write(tmp_path, "[volumes]\nper_cycle_ul = [10.0]\n")
    _, banner = build_volumes(12, "columns", env={"PIPETTE_PROFILE": str(p)})
    assert "columns" in banner
