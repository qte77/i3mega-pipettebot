"""TDD tests for tools/slicer/validate.py command builders + helpers.

Pure functions only — no slicer binary, no STL on disk. Verifies CLI
assembly, profile selection, warning detection, and slicer probing
order.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SLICER_DIR = Path(__file__).resolve().parents[3] / "tools" / "slicer"


def _import_validate():
    spec = importlib.util.spec_from_file_location(
        "validate", SLICER_DIR / "validate.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


validate = _import_validate()


def test_build_slicer_cmd_includes_export_gcode_flag(tmp_path: Path):
    cmd = validate._build_slicer_cmd(
        "/usr/bin/orca-slicer",
        Path("hardware/stl/labware/plate_holder.stl"),
        Path("tools/slicer/profiles/pla_plus_02mm.ini"),
        tmp_path / "out.gcode",
    )
    assert cmd[0] == "/usr/bin/orca-slicer"
    assert "--export-gcode" in cmd
    assert "--load" in cmd
    assert "--output" in cmd
    assert str(Path("hardware/stl/labware/plate_holder.stl")) in cmd


def test_build_slicer_cmd_works_for_prusa_too():
    """Same builder, same flags — only the binary path differs."""
    orca = validate._build_slicer_cmd(
        "orca-slicer", Path("a.stl"), Path("p.ini"), Path("o.gcode")
    )
    prusa = validate._build_slicer_cmd(
        "prusa-slicer", Path("a.stl"), Path("p.ini"), Path("o.gcode")
    )
    assert orca[1:] == prusa[1:]
    assert orca[0] == "orca-slicer"
    assert prusa[0] == "prusa-slicer"


def test_get_profile_defaults_to_pla():
    profile = validate.get_profile("plate_holder.stl")
    assert profile.name == "pla_plus_02mm.ini"


def test_get_profile_tpu_override():
    profile = validate.get_profile("plate_holder.stl", override="tpu")
    assert profile.name == "tpu_95a_02mm.ini"


def test_scan_warnings_picks_up_known_keywords():
    """Real prusa-slicer / orca-slicer warning lines should be detected."""
    output = (
        "print warning: detected print stability issues:\n"
        "carriage_dpette_mount_main.stl\n"
        "floating object part, floating bridge anchors, loose extrusions"
    )
    warns = validate._scan_warnings(output.lower())
    assert "floating object part" in warns
    assert "floating bridge anchors" in warns
    assert "loose extrusions" in warns


def test_scan_warnings_ignores_routine_chatter():
    """Routine slicer chatter (config strings) must NOT trigger warnings."""
    output = (
        "support overhang threshold = 45 degrees\n"
        "bridge speed = 25 mm/s\n"
        "overhang perimeters = 1\n"
        "sliced ok in 4.2s, no issues"
    )
    assert validate._scan_warnings(output.lower()) == []


def test_slicer_candidates_order_orca_before_prusa():
    """OrcaSlicer is the default; PrusaSlicer is fallback."""
    backends = [b for b, _ in validate.SLICER_CANDIDATES]
    first_orca = backends.index("orca")
    first_prusa = backends.index("prusa")
    assert first_orca < first_prusa


def test_has_outside_volume_detects_real_prusa_message():
    """Real PrusaSlicer 2.9.4 message (docs/prusa/README.md Quirk 3).

    PrusaSlicer exits 0 and prints this to stdout with no output file
    written — the exact case the exit-code-only gate used to miss.
    """
    output = "all objects are outside of the print volume.\n"
    assert validate._has_outside_volume(output) is True


def test_has_outside_volume_detects_issue_phrasing():
    """Also match the shorter phrasing named in issue #127, for safety."""
    output = "3 objects outside the print volume were skipped\n"
    assert validate._has_outside_volume(output) is True


def test_has_outside_volume_ignores_clean_output():
    output = "slicing complete, no issues found\n"
    assert validate._has_outside_volume(output) is False


def test_ini_to_cli_flags_forwards_scalar_keys(tmp_path: Path):
    """Scalar .ini keys become explicit `--key value` CLI flags.

    Needed because PrusaSlicer 2.9.4's `--load <ini>` silently falls back
    to defaults for most keys (docs/prusa/README.md Quirk 1).
    """
    ini = tmp_path / "profile.ini"
    ini.write_text(
        "[print]\n"
        "layer_height = 0.2\n"
        "fill_density = 15%\n"
        "\n"
        "[filament]\n"
        "filament_type = PLA\n"
    )
    flags = validate._ini_to_cli_flags(ini)
    assert "--layer-height" in flags
    assert flags[flags.index("--layer-height") + 1] == "0.2"
    assert "--fill-density" in flags
    assert flags[flags.index("--fill-density") + 1] == "15%"
    assert "--filament-type" in flags
    assert flags[flags.index("--filament-type") + 1] == "PLA"


def test_ini_to_cli_flags_forwards_true_booleans_as_bare_switches(tmp_path: Path):
    """Known boolean keys become bare switches (e.g. `--binary-gcode`).

    Confirmed via docs/prusa/README.md Quirk 1's working invocation and
    the profiles/pla_prototype_03mm.ini comment: PrusaSlicer's boolean
    CLI options take no value.
    """
    ini = tmp_path / "profile.ini"
    ini.write_text("[printer]\nbinary_gcode = 1\n")
    flags = validate._ini_to_cli_flags(ini)
    assert flags == ["--binary-gcode"]


def test_ini_to_cli_flags_omits_false_booleans(tmp_path: Path):
    """A `0`-valued boolean key is omitted (absent = false is the default)."""
    ini = tmp_path / "profile.ini"
    ini.write_text("[print]\nsupport_material = 0\n")
    flags = validate._ini_to_cli_flags(ini)
    assert flags == []


def test_ini_to_cli_flags_tolerates_percent_values(tmp_path: Path):
    """`fill_density = 15%` must not trip ConfigParser's interpolation.

    Plain `configparser.ConfigParser()` raises InterpolationSyntaxError on
    a bare `%` — every profile in tools/slicer/profiles/*.ini uses this
    syntax, so this is a real bug, not a hypothetical.
    """
    ini = tmp_path / "profile.ini"
    ini.write_text("[print]\nfill_density = 15%\n")
    flags = validate._ini_to_cli_flags(ini)
    assert flags == ["--fill-density", "15%"]


def test_ini_to_cli_flags_missing_file_returns_empty(tmp_path: Path):
    """A profile path that doesn't exist yields no flags (no crash)."""
    flags = validate._ini_to_cli_flags(tmp_path / "does_not_exist.ini")
    assert flags == []


def test_build_slicer_cmd_forwards_ini_flags(tmp_path: Path):
    """`_build_slicer_cmd` includes the forwarded flags after `--load`."""
    ini = tmp_path / "profile.ini"
    ini.write_text("[print]\nlayer_height = 0.2\n")
    cmd = validate._build_slicer_cmd(
        "prusa-slicer", Path("a.stl"), ini, tmp_path / "o.gcode"
    )
    assert "--load" in cmd
    assert "--layer-height" in cmd
    assert cmd.index("--layer-height") > cmd.index("--load")


def test_check_mesh_integrity_rejects_truncated():
    """A 10-byte file is too short for an STL header."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
        f.write(b"\x00" * 10)
        path = Path(f.name)
    try:
        result = validate.check_mesh_integrity(path)
        assert result["status"] == "FAIL"
        assert "too small" in (result["error"] or "")
    finally:
        path.unlink()
