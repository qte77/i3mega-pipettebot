"""TDD tests for tools/slicer/resolve_presets.py's inherits-chain resolver.

Pure functions only — synthetic `tmp_path` fixtures, no real PrusaSlicer
bundle or `~/.config` writes. The real end-to-end recipe is covered by
tests/bats/setup_prusa_presets.bats.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SLICER_DIR = Path(__file__).resolve().parents[3] / "tools" / "slicer"


def _import_resolve_presets():
    spec = importlib.util.spec_from_file_location(
        "resolve_presets", SLICER_DIR / "resolve_presets.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


resolve_presets = _import_resolve_presets()


SYNTHETIC_BUNDLE = """\
[printer:*common*]
retract_length = 0.8
nozzle_diameter = 0.4

[printer:*commonMK4*]
inherits = *common*
machine_max_acceleration_x = 4000

[printer:Original Test MK4 nozzle]
inherits = *commonMK4*
renamed_from = "Test MK4"
nozzle_diameter = 0.6

[print:Base]
layer_height = 0.2

[print:Child]
inherits = Base
fill_density = 15%
"""


def _write_bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "bundle.ini"
    bundle.write_text(SYNTHETIC_BUNDLE, encoding="utf-8")
    return bundle


def test_parse_ini_splits_into_named_sections(tmp_path: Path):
    sections = resolve_presets.parse_ini(_write_bundle(tmp_path))
    assert set(sections) == {
        "printer:*common*",
        "printer:*commonMK4*",
        "printer:Original Test MK4 nozzle",
        "print:Base",
        "print:Child",
    }


def test_kv_skips_comments_and_blanks():
    lines = ["# a comment\n", "\n", "key = value\n", "spaced_key =  spaced value \n"]
    assert resolve_presets._kv(lines) == {
        "key": "value",
        "spaced_key": "spaced value",
    }


def test_resolve_flattens_single_level_inherits(tmp_path: Path):
    sections = resolve_presets.parse_ini(_write_bundle(tmp_path))
    resolved = resolve_presets.resolve(sections, "print:Child")
    assert resolved == {"layer_height": "0.2", "fill_density": "15%"}


def test_resolve_child_keys_override_parent(tmp_path: Path):
    sections = resolve_presets.parse_ini(_write_bundle(tmp_path))
    resolved = resolve_presets.resolve(sections, "printer:Original Test MK4 nozzle")
    assert resolved["nozzle_diameter"] == "0.6"  # child wins, not *common*'s 0.4


def test_resolve_walks_multi_level_chain(tmp_path: Path):
    sections = resolve_presets.parse_ini(_write_bundle(tmp_path))
    resolved = resolve_presets.resolve(sections, "printer:Original Test MK4 nozzle")
    assert resolved["retract_length"] == "0.8"  # from *common*, two levels up
    assert resolved["machine_max_acceleration_x"] == "4000"  # from *commonMK4*


def test_resolve_drops_the_inherits_key_itself(tmp_path: Path):
    sections = resolve_presets.parse_ini(_write_bundle(tmp_path))
    resolved = resolve_presets.resolve(sections, "printer:Original Test MK4 nozzle")
    assert "inherits" not in resolved


def test_resolve_missing_parent_returns_partial_result():
    sections = {"printer:orphan": ["inherits = *does_not_exist*\n", "key = ok\n"]}
    resolved = resolve_presets.resolve(sections, "printer:orphan")
    assert resolved == {"key": "ok"}


def test_resolve_breaks_cycles_instead_of_recursing_forever():
    sections = {
        "printer:a": ["inherits = b\n", "from_a = 1\n"],
        "printer:b": ["inherits = a\n", "from_b = 1\n"],
    }
    resolved = resolve_presets.resolve(sections, "printer:a")
    assert resolved == {"from_a": "1", "from_b": "1"}


def test_write_preset_creates_flat_ini(tmp_path: Path):
    out_path = resolve_presets.write_preset(
        "printer", "Some Preset", {"a": "1", "b": "2"}, tmp_path
    )
    assert out_path == tmp_path / "printer" / "Some Preset.ini"
    assert out_path.read_text(encoding="utf-8") == "a = 1\nb = 2\n"
