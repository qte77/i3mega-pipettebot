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
    spec = importlib.util.spec_from_file_location("validate", SLICER_DIR / "validate.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


validate = _import_validate()


def test_build_slicer_cmd_includes_export_gcode_flag():
    cmd = validate._build_slicer_cmd(
        "/usr/bin/orca-slicer",
        Path("hardware/stl/labware/plate_holder.stl"),
        Path("tools/slicer/profiles/i3mega_pla_02mm.ini"),
        Path("/tmp/out.gcode"),
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
    assert profile.name == "i3mega_pla_02mm.ini"


def test_get_profile_petg_override():
    profile = validate.get_profile("plate_holder.stl", override="petg")
    assert profile.name == "i3mega_petg_02mm.ini"


def test_scan_warnings_picks_up_known_keywords():
    output = "Warning: large overhang detected on layer 12\nbridge segment unsupported"
    warns = validate._scan_warnings(output.lower())
    assert "overhang" in warns
    assert "bridge" in warns
    assert "unsupported" in warns


def test_scan_warnings_clean_output():
    assert validate._scan_warnings("sliced ok in 4.2s, no issues") == []


def test_slicer_candidates_order_orca_before_prusa():
    """OrcaSlicer is the default; PrusaSlicer is fallback."""
    backends = [b for b, _ in validate.SLICER_CANDIDATES]
    first_orca = backends.index("orca")
    first_prusa = backends.index("prusa")
    assert first_orca < first_prusa


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
