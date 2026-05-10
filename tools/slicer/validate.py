"""Validate STL printability via OrcaSlicer (preferred) or PrusaSlicer fallback.

Slices each STL with the configured profile and parses output for
overhang / unsupported / bridge warnings. Both slicers share the
PrusaSlicer-style `.ini` profile schema and CLI surface for slicing
operations, so a single command builder serves both.

Usage:
    python tools/slicer/validate.py --all
    python tools/slicer/validate.py --all --structural
    python tools/slicer/validate.py hardware/stl/labware/plate_holder.stl
    python tools/slicer/validate.py --all --profile petg
"""

from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT_SEC = 120
STL_DIR = Path(__file__).resolve().parents[2] / "hardware" / "stl"
PROFILE_DIR = Path(__file__).resolve().parent / "profiles"

# Per-part profile overrides (default profile is PLA)
PETG_PARTS: set[str] = set()  # populate with STL filenames as needed

# Phrases that prusa-slicer / orca-slicer emit as actual print-stability
# warnings (not config-string mentions). Generic terms like "overhang" or
# "bridge" appear in routine slicer chatter (parameter descriptions, log
# messages) and are too noisy to gate on.
OVERHANG_KEYWORDS = (
    "floating object part",
    "floating bridge anchors",
    "loose extrusions",
    "long bridging extrusions",
    "empty layer",
    "could not slice",
)

# Probe order: OrcaSlicer first, PrusaSlicer fallback. Names cover the
# common install methods (native package, AppImage extraction, brew).
SLICER_CANDIDATES: tuple[tuple[str, str], ...] = (
    ("orca", "orca-slicer"),
    ("orca", "OrcaSlicer"),
    ("orca", "OrcaSlicer-console"),
    ("prusa", "prusa-slicer"),
    ("prusa", "PrusaSlicer"),
)


def get_profile(stl_name: str, override: str | None = None) -> Path:
    """Return the slicer profile path for a given STL name."""
    if override == "petg" or stl_name in PETG_PARTS:
        return PROFILE_DIR / "i3mega_petg_02mm.ini"
    return PROFILE_DIR / "i3mega_pla_02mm.ini"


def detect_slicer() -> tuple[str, str] | None:
    """Return (backend_name, binary_path) for the first available slicer."""
    for backend, name in SLICER_CANDIDATES:
        path = shutil.which(name)
        if path:
            return (backend, path)
    return None


def _build_slicer_cmd(
    binary: str, stl_path: Path, profile: Path, gcode_out: Path
) -> list[str]:
    """Build CLI invocation for OrcaSlicer or PrusaSlicer.

    Both accept `--export-gcode --load <ini> --output <gcode> <stl>` for
    headless slicing of an `.ini` profile; OrcaSlicer inherits this from
    its PrusaSlicer/SuperSlicer ancestry.
    """
    return [
        binary,
        "--export-gcode",
        "--load",
        str(profile),
        "--output",
        str(gcode_out),
        str(stl_path),
    ]


def _scan_warnings(text: str) -> list[str]:
    """Pick known printability warnings out of slicer output."""
    return [kw for kw in OVERHANG_KEYWORDS if kw in text]


def validate_stl(stl_path: Path, backend: str, binary: str, profile: Path) -> dict:
    """Slice an STL with the given backend and return a result record."""
    result: dict = {
        "file": stl_path.name,
        "profile": profile.stem,
        "slicer": backend,
        "warnings": [],
        "status": "PASS",
        "error": None,
    }
    with tempfile.TemporaryDirectory() as tmp:
        gcode_out = Path(tmp) / (stl_path.stem + ".gcode")
        cmd = _build_slicer_cmd(binary, stl_path, profile, gcode_out)
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=TIMEOUT_SEC
            )
            output = (proc.stdout + "\n" + proc.stderr).lower()
            result["warnings"] = _scan_warnings(output)
            if proc.returncode != 0:
                result["status"] = "FAIL"
                result["error"] = proc.stderr.strip()[:200]
            elif result["warnings"]:
                result["status"] = "WARN"
        except subprocess.TimeoutExpired:
            result["status"] = "SKIP"
            result["error"] = f"Timeout after {TIMEOUT_SEC}s"
        except FileNotFoundError:
            result["status"] = "SKIP"
            result["error"] = "Slicer binary not found"
    return result


def check_mesh_integrity(stl_path: Path) -> dict:
    """Verify STL binary mesh integrity (no external deps)."""
    result: dict = {
        "file": stl_path.name,
        "status": "PASS",
        "triangle_count": 0,
        "error": None,
    }
    try:
        data = stl_path.read_bytes()
    except OSError as exc:
        result["status"] = "FAIL"
        result["error"] = str(exc)
        return result
    if len(data) < 84:
        result["status"] = "FAIL"
        result["error"] = f"File too small ({len(data)} bytes, need >= 84)"
        return result
    (num_triangles,) = struct.unpack_from("<I", data, 80)
    result["triangle_count"] = num_triangles
    if num_triangles == 0:
        result["status"] = "FAIL"
        result["error"] = "Zero triangles in STL"
        return result
    expected_size = 84 + 50 * num_triangles
    if len(data) < expected_size:
        result["status"] = "FAIL"
        result["error"] = (
            f"File truncated ({len(data)} bytes, expected {expected_size})"
        )
    return result


def collect_stls(paths: list[str]) -> list[Path]:
    """Collect STL files from args (file paths or directories)."""
    stls: list[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_file():
            stls.append(path)
        elif path.is_dir():
            stls.extend(sorted(path.glob("*.stl")))
    return stls


def print_report(results: list[dict]) -> int:
    """Print validation report. Exit non-zero if any FAIL."""
    if not results:
        print("No STL files found to validate.")
        return 1
    print(f"\n{'Part':<35} {'Profile':<22} {'Slicer':<8} {'Warnings':<25} {'Status'}")
    print("-" * 99)
    exit_code = 0
    for r in results:
        warns = ", ".join(r["warnings"]) if r["warnings"] else "none"
        err = f" ({r['error']})" if r["error"] else ""
        row = f"{r['file']:<35} {r['profile']:<22} {r['slicer']:<8} {warns:<25}"
        print(f"{row} {r['status']}{err}")
        if r["status"] == "FAIL":
            exit_code = 1
    passed = sum(1 for r in results if r["status"] == "PASS")
    print(f"\n{passed}/{len(results)} parts passed printability check.\n")
    return exit_code


def _print_mesh_report(results: list[dict]) -> int:
    failed = [r for r in results if r["status"] == "FAIL"]
    print("\n=== Mesh Integrity Check ===")
    for r in results:
        err = f" ({r['error']})" if r["error"] else ""
        print(
            f"  {r['file']:<35} {r['triangle_count']:>6} triangles  {r['status']}{err}"
        )
    if failed:
        print(f"\n{len(failed)} STL(s) failed mesh integrity check.\n")
        return 1
    print(f"\n{len(results)}/{len(results)} STLs passed mesh integrity.\n")
    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Validate STL printability via slicer")
    parser.add_argument("files", nargs="*", help="STL files to validate")
    parser.add_argument(
        "--all", action="store_true", help="Validate all STLs in hardware/stl/"
    )
    parser.add_argument(
        "--profile", choices=["pla", "petg"], help="Force profile override"
    )
    parser.add_argument(
        "--structural", action="store_true", help="Run mesh integrity check"
    )
    args = parser.parse_args()

    slicer = detect_slicer()
    if not slicer and not args.structural:
        print("SKIP: No slicer found. Install via: make setup_slicer")
        return 0

    if args.all:
        stls = sorted(STL_DIR.glob("**/*.stl"))
    elif args.files:
        stls = collect_stls(args.files)
    else:
        parser.print_help()
        return 1

    if not stls:
        print(f"No STL files found in {STL_DIR}. Run: make render_parts")
        return 1

    if args.structural and _print_mesh_report([check_mesh_integrity(s) for s in stls]):
        return 1

    if slicer is None:
        return 0
    backend, binary = slicer
    print(f"--- Validating with {backend} ({binary})")
    results = [
        validate_stl(s, backend, binary, get_profile(s.name, args.profile))
        for s in stls
    ]
    return print_report(results)


if __name__ == "__main__":
    sys.exit(main())
