"""TDD tests for tools/slicer/slice.py's part/preset path resolvers and CLI
builder.

Pure functions only — synthetic `parts.json` fixtures via `tmp_path`, no
real slicer binary or STL round-trip. The real end-to-end recipe (mocked
slicer) is covered by tests/bats/slice.bats; a real (non-mocked)
`prusa-slicer` round-trip using this exact `--load`x3 invocation was
verified manually in this environment — see the module docstring in
tools/slicer/slice.py for why it doesn't use `--printer-profile` et al.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SLICER_DIR = Path(__file__).resolve().parents[3] / "tools" / "slicer"


def _import_slice():
    spec = importlib.util.spec_from_file_location("slice", SLICER_DIR / "slice.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


slice_mod = _import_slice()


def _write_manifest(tmp_path: Path) -> Path:
    manifest = tmp_path / "parts.json"
    manifest.write_text(
        json.dumps([{"name": "widget", "stl": "labware/widget.stl"}]),
        encoding="utf-8",
    )
    return manifest


def test_resolve_part_paths_maps_stl_to_matching_bgcode_path(tmp_path: Path):
    stl_path, bgcode_path = slice_mod.resolve_part_paths(
        "widget", _write_manifest(tmp_path)
    )
    assert stl_path == slice_mod.STL_DIR / "labware" / "widget.stl"
    assert bgcode_path == slice_mod.BGCODE_DIR / "labware" / "widget.bgcode"


def test_resolve_part_paths_unknown_part_lists_known_names(tmp_path: Path):
    with pytest.raises(SystemExit, match="widget"):
        slice_mod.resolve_part_paths("nope", _write_manifest(tmp_path))


def test_preset_paths_mirrors_resolve_presets_layout(tmp_path: Path):
    printer_ini, print_ini, filament_ini = slice_mod.preset_paths(
        tmp_path, "MyPrinter", "MyPrint", "MyFilament"
    )
    assert printer_ini == tmp_path / "printer" / "MyPrinter.ini"
    assert print_ini == tmp_path / "print" / "MyPrint.ini"
    assert filament_ini == tmp_path / "filament" / "MyFilament.ini"


def test_build_slice_cmd_uses_binary_gcode_and_load_per_preset():
    cmd = slice_mod._build_slice_cmd(
        "prusa-slicer",
        Path("hardware/stl/labware/widget.stl"),
        Path("hardware/bgcode/labware/widget.bgcode"),
        Path("printer.ini"),
        Path("print.ini"),
        Path("filament.ini"),
    )
    assert cmd[0] == "prusa-slicer"
    assert "--binary-gcode" in cmd
    assert "--export-gcode" in cmd
    # --load appears once per preset file, each immediately followed by
    # that file's path (order: printer, print, filament).
    load_indices = [i for i, arg in enumerate(cmd) if arg == "--load"]
    assert len(load_indices) == 3
    assert [cmd[i + 1] for i in load_indices] == [
        "printer.ini",
        "print.ini",
        "filament.ini",
    ]
    assert cmd[cmd.index("--output") + 1] == str(
        Path("hardware/bgcode/labware/widget.bgcode")
    )
    assert cmd[-1] == str(Path("hardware/stl/labware/widget.stl"))
