"""TDD tests for tools/slicer/validate.py::validate_stl end-to-end gating.

Mocks subprocess.run (never invokes a real slicer binary). Uses tmp_path
for the slicer output file so the file-exists check can be exercised in
both directions.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from unittest.mock import patch

SLICER_DIR = Path(__file__).resolve().parents[3] / "tools" / "slicer"


def _import_validate():
    spec = importlib.util.spec_from_file_location(
        "validate_stl_module", SLICER_DIR / "validate.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


validate = _import_validate()


def _fake_run_writing_output(stdout: str = "", returncode: int = 0):
    """Build a subprocess.run fake that writes the `--output` target."""

    def _run(cmd, **_kwargs):
        out_path = Path(cmd[cmd.index("--output") + 1])
        out_path.write_text("; fake gcode\n")
        return subprocess.CompletedProcess(cmd, returncode, stdout, "")

    return _run


def _fake_run_no_output(stdout: str = "", returncode: int = 0):
    """Build a subprocess.run fake that does NOT write any output file."""

    def _run(cmd, **_kwargs):
        return subprocess.CompletedProcess(cmd, returncode, stdout, "")

    return _run


def test_validate_stl_fails_on_outside_print_volume_exit_zero(tmp_path: Path):
    """PrusaSlicer 2.9.4 prints this and exits 0 (docs/prusa/README.md Quirk 3).

    The gate must treat it as FAIL, not PASS/WARN, even though the process
    exit code is 0 and no output file exists.
    """
    stdout = "All objects are outside of the print volume.\n"
    with patch.object(
        validate.subprocess, "run", side_effect=_fake_run_no_output(stdout, 0)
    ):
        result = validate.validate_stl(
            tmp_path / "part.stl",
            "prusa",
            "prusa-slicer",
            tmp_path / "profile.ini",
        )
    assert result["status"] == "FAIL"


def test_validate_stl_fails_when_output_file_missing_despite_exit_zero(
    tmp_path: Path,
):
    """Exit code 0 with clean stdout but no output file must still FAIL."""
    with patch.object(
        validate.subprocess, "run", side_effect=_fake_run_no_output("", 0)
    ):
        result = validate.validate_stl(
            tmp_path / "part.stl",
            "prusa",
            "prusa-slicer",
            tmp_path / "profile.ini",
        )
    assert result["status"] == "FAIL"


def test_validate_stl_passes_when_exit_zero_and_output_file_exists(tmp_path: Path):
    """Regression guard: the happy path must still PASS."""
    with patch.object(
        validate.subprocess, "run", side_effect=_fake_run_writing_output("", 0)
    ):
        result = validate.validate_stl(
            tmp_path / "part.stl",
            "prusa",
            "prusa-slicer",
            tmp_path / "profile.ini",
        )
    assert result["status"] == "PASS"
