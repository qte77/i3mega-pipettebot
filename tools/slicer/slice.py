"""Slice a registered CAD part into a tracked PrusaSlicer bgcode.

Wraps the PrusaSlicer CLI invocation documented in docs/prusa/README.md
(Quirk 5), referencing the IS-aware printer/print/filament presets that
`make setup_prusa_presets` (tools/slicer/resolve_presets.py) resolves
and writes to `~/.config/PrusaSlicer/{printer,print,filament}/`.

Verified locally: this repo's installed PrusaSlicer (2.7.2) doesn't
recognize the docs' `--printer-profile`/`--print-profile`/
`--material-profile` flags at all ("Unknown option") — those were
confirmed against PrusaSlicer 2.9.4 (see docs' header note). `--load
<resolved-preset-file>` is the version-portable equivalent, and it
does not just accept the files silently and fall back to defaults
(the failure mode Quirk 1 warns about for this repo's own *minimal*
`tools/slicer/profiles/*.ini`): a real, non-mocked `--load`x3 slice
against this environment's PrusaSlicer produced output whose embedded
metadata carried the resolved preset's own values verbatim
(`printer_model=MK4IS`, `layer_height=0.2`, `temperature=210`,
`fill_density=15%` — none of them PrusaSlicer's generic defaults,
which a `--load`-free control slice of the same STL confirmed are
`printer_model=<empty>`/`layer_height=0.3`/200×200 bed). One resolved
key (`binary_gcode`) even flipped the output format to real binary
`GCDE` bgcode without `--binary-gcode` being passed at all. This
module resolves preset *names* to the file paths `resolve_presets.py`
writes, so the CLI surface (`--printer-preset ...`) stays name-based
while the actual slicer invocation uses `--load`.

Reuses tools/cad/parts.json as the single source of truth for
part -> STL path, matching the manifest `make render_parts` already
uses, so `<area>/<part>` naming stays in one place.

Usage:
    python tools/slicer/slice.py --part deck_plate_assembly
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PARTS_JSON = REPO_ROOT / "tools" / "cad" / "parts.json"
STL_DIR = REPO_ROOT / "hardware" / "stl"
BGCODE_DIR = REPO_ROOT / "hardware" / "bgcode"

# Must match resolve_presets.py's DEFAULT_USER_DIR + PRESETS naming
# convention (`<user_dir>/<kind>/<name>.ini`) — that script is what
# populates this directory.
DEFAULT_USER_DIR = Path.home() / ".config" / "PrusaSlicer"
DEFAULT_PRINTER_PRESET = "Original Prusa MK4 Input Shaper 0.4 nozzle"
DEFAULT_PRINT_PRESET = "0.20mm SPEED @MK4IS 0.4"
DEFAULT_FILAMENT_PRESET = "Prusa PLA"


def resolve_part_paths(part: str, parts_json: Path = PARTS_JSON) -> tuple[Path, Path]:
    """Return (stl_path, bgcode_path) for a `parts.json` entry name.

    Both paths are absolute; `hardware/bgcode/` mirrors the `<area>/<part>`
    layout `hardware/stl/` already uses.
    """
    manifest = json.loads(parts_json.read_text(encoding="utf-8"))
    for entry in manifest:
        if entry["name"] == part:
            rel = Path(entry["stl"])
            return STL_DIR / rel, BGCODE_DIR / rel.with_suffix(".bgcode")
    known = ", ".join(sorted(e["name"] for e in manifest))
    raise SystemExit(f"Unknown PART {part!r}. Known parts: {known}")


def preset_paths(
    user_dir: Path,
    printer_preset: str,
    print_preset: str,
    filament_preset: str,
) -> tuple[Path, Path, Path]:
    """Return (printer_ini, print_ini, filament_ini) under `user_dir`.

    Mirrors resolve_presets.py::write_preset's `<user_dir>/<kind>/<name>.ini`
    output layout.
    """
    return (
        user_dir / "printer" / f"{printer_preset}.ini",
        user_dir / "print" / f"{print_preset}.ini",
        user_dir / "filament" / f"{filament_preset}.ini",
    )


def _build_slice_cmd(
    binary: str,
    stl_path: Path,
    bgcode_path: Path,
    printer_ini: Path,
    print_ini: Path,
    filament_ini: Path,
) -> list[str]:
    """Build the `--load`-based PrusaSlicer CLI invocation.

    `--load` (one per file) is the version-portable way to select a
    resolved preset — see the module docstring for why this repo does
    not use `--printer-profile`/`--print-profile`/`--material-profile`.
    """
    return [
        binary,
        "--binary-gcode",
        "--export-gcode",
        "--load",
        str(printer_ini),
        "--load",
        str(print_ini),
        "--load",
        str(filament_ini),
        "--output",
        str(bgcode_path),
        str(stl_path),
    ]


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--part", required=True, help="tools/cad/parts.json name")
    parser.add_argument("--parts-json", type=Path, default=PARTS_JSON)
    parser.add_argument("--user-dir", type=Path, default=DEFAULT_USER_DIR)
    parser.add_argument("--printer-preset", default=DEFAULT_PRINTER_PRESET)
    parser.add_argument("--print-preset", default=DEFAULT_PRINT_PRESET)
    parser.add_argument("--filament-preset", default=DEFAULT_FILAMENT_PRESET)
    args = parser.parse_args()

    binary = shutil.which("prusa-slicer")
    if not binary:
        print("SKIP: prusa-slicer not found. Install via: make setup_slicer")
        return 1

    stl_path, bgcode_path = resolve_part_paths(args.part, args.parts_json)
    if not stl_path.exists():
        print(f"FAIL: {stl_path} not found. Run: make render_parts")
        return 1

    printer_ini, print_ini, filament_ini = preset_paths(
        args.user_dir, args.printer_preset, args.print_preset, args.filament_preset
    )
    missing = [p for p in (printer_ini, print_ini, filament_ini) if not p.exists()]
    if missing:
        for p in missing:
            print(f"FAIL: preset not found: {p}")
        print("Run: make setup_prusa_presets")
        return 1

    bgcode_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = _build_slice_cmd(
        binary, stl_path, bgcode_path, printer_ini, print_ini, filament_ini
    )
    print(f"--- Slicing {stl_path} -> {bgcode_path}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not bgcode_path.exists():
        print(proc.stdout)
        print(proc.stderr)
        print(f"FAIL: slice did not produce {bgcode_path}")
        return 1
    print(f"wrote {bgcode_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
