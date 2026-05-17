"""Generate and slice the 4-piece carriage mount assembly.

Pieces: top plate, 2x post, lower clamp.

Each piece is exported in its print orientation (laid flat, longest face on
the bed), then all four are passed to prusa-slicer for a single G-code that
prints the complete set in one job. Pieces are glued together after print.

Usage:
    uv run --extra cad python tools/slicer/print_carriage_assembly.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAD_DIR = REPO / "tools" / "cad"
PROFILE = REPO / "tools" / "slicer" / "profiles" / "pla_plus_02mm.ini"
OUT_STL_DIR = REPO / "hardware" / "stl" / "i3" / "assembly"
OUT_GCODE = REPO / "hardware" / "gcode" / "carriage_assembly.gcode"

sys.path.insert(0, str(CAD_DIR))


def _post_height_mm() -> float:
    """Mirror the post-length math from build_carriage_dpette_mount_main."""
    from i3.carriage_dpette_mount import (  # type: ignore[import-not-found]
        LOWER_CLAMP_H_PLUS_MM,
        TOP_PLATE_T_MM,
    )
    from measurements import (  # type: ignore[import-not-found]
        LOWER_CLAMP_H_MM,
        UPPER_TO_LOWER_SEPARATION_MM,
    )

    upper_axis_z = -TOP_PLATE_T_MM / 2
    lower_axis_z = upper_axis_z - UPPER_TO_LOWER_SEPARATION_MM
    lower_clamp_h = LOWER_CLAMP_H_MM + LOWER_CLAMP_H_PLUS_MM
    lower_top = lower_axis_z + lower_clamp_h / 2
    return -TOP_PLATE_T_MM - lower_top  # z_top - z_bottom


def build_pieces() -> dict[str, object]:
    """Return {name: build123d_shape} for the 4 print pieces, all flat-oriented."""
    from build123d import Box, Pos

    # 1. Top plate — already flat (Z is thickness). Shift so bottom face sits at Z=0.
    from i3.carriage_dpette_mount import (  # type: ignore[import-not-found]
        POST_D_MM,
        POST_W_MM,
        TOP_PLATE_T_MM,  # type: ignore[import-not-found]
        _build_lower_clamp,
        _build_top_plate_with_upper_clamp_back,
    )

    top_plate = Pos(0, 0, TOP_PLATE_T_MM / 2) * _build_top_plate_with_upper_clamp_back()

    # 2. Lower clamp — _build_lower_clamp takes z_center; place at
    #    half-height so bottom face sits at Z=0.
    from i3.carriage_dpette_mount import (
        LOWER_CLAMP_H_PLUS_MM,  # type: ignore[import-not-found]
    )
    from measurements import LOWER_CLAMP_H_MM  # type: ignore[import-not-found]

    h_lc = LOWER_CLAMP_H_MM + LOWER_CLAMP_H_PLUS_MM
    lower_clamp = _build_lower_clamp(z_center=h_lc / 2)

    # 3. Posts — laid flat: footprint = (post_length, POST_D_MM),
    #    height = POST_W_MM (narrower dimension prints up). Two
    #    identical instances.
    post_len = _post_height_mm()
    post = Pos(0, 0, POST_W_MM / 2) * Box(post_len, POST_D_MM, POST_W_MM)

    return {
        "top_plate": top_plate,
        "post_a": post,
        "post_b": post,
        "lower_clamp": lower_clamp,
    }


def export_stls(pieces: dict[str, object]) -> list[Path]:
    """Write each piece to its own STL; return paths in slicer-input order."""
    from build123d import export_stl  # type: ignore[import-not-found]

    OUT_STL_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name, shape in pieces.items():
        stl_path = OUT_STL_DIR / f"{name}.stl"
        export_stl(shape, str(stl_path))
        paths.append(stl_path)
        print(f"  exported {stl_path.relative_to(REPO)}")
    return paths


def export_arranged_stl(pieces: dict[str, object]) -> Path:
    """Arrange all four pieces on the Prusa MK3S+ bed (220×220) and write one STL.

    prusa-slicer's CLI does NOT auto-arrange when given multiple STL inputs —
    everything stacks at origin and only the topmost gets sliced cleanly. So we
    bake the bed layout into a single merged STL with explicit XY positions.

    Uses bbox-aware placement: each piece's CENTER lands at the target (x, y),
    and the piece's lowest Z point sits at Z=0 (flat on the bed). Naïve Pos(x, y, 0)
    can cause overlaps because the CAD origin of each piece is not necessarily
    centered in its own bounding box.
    """
    from build123d import Compound, Pos, export_stl  # type: ignore[import-not-found]

    # Target bed centers (220×220 origin at corner; chosen so pieces
    # don't overlap).
    layout = {
        "top_plate": (110.0, 50.0),  # 35 × 85 → X[92.5, 127.5], Y[7.5, 92.5]
        "lower_clamp": (
            110.0,
            120.0,
        ),  # 83.5 × 36.5 → X[68.25, 151.75], Y[101.75, 138.25]
        "post_a": (60.0, 165.0),  # 75 × 12 → X[22.5, 97.5], Y[159, 171]
        "post_b": (160.0, 165.0),  # 75 × 12 → X[122.5, 197.5], Y[159, 171]
    }

    arranged = []
    for name, shape in pieces.items():
        target_x, target_y = layout[name]
        bb = shape.bounding_box()
        cx = (bb.min.X + bb.max.X) / 2
        cy = (bb.min.Y + bb.max.Y) / 2
        dx = target_x - cx
        dy = target_y - cy
        dz = -bb.min.Z  # so lowest Z point sits at Z=0
        arranged.append(Pos(dx, dy, dz) * shape)
    bed = Compound(children=arranged)

    OUT_STL_DIR.mkdir(parents=True, exist_ok=True)
    bed_path = OUT_STL_DIR / "bed_layout.stl"
    export_stl(bed, str(bed_path))
    print(f"  arranged 4 pieces → {bed_path.relative_to(REPO)}")
    return bed_path


def slice_bed(bed_stl: Path) -> int:
    """Call prusa-slicer with the pre-arranged bed STL + explicit print settings.

    The minimal .ini profile is unreliable across PrusaSlicer versions (sections
    silently ignored, no start_gcode emitted). Passing the few values we care
    about as CLI flags guarantees they take effect — most importantly the bed
    heat block in start_gcode (without it, PLA won't stick).
    """
    binary = shutil.which("prusa-slicer") or shutil.which("PrusaSlicer")
    if not binary:
        print("ERROR: prusa-slicer not found in PATH")
        return 1

    OUT_GCODE.parent.mkdir(parents=True, exist_ok=True)
    # prusa-slicer CLI takes actual newline characters in the start_gcode value.
    # Use placeholders so the temps actually pick up the CLI --temperature flags
    # (hardcoded temps here would override them silently).
    start_gcode = (
        "M140 S[first_layer_bed_temperature]\n"
        "M104 S[first_layer_temperature]\n"
        "G28 ; home\n"
        "M190 S[first_layer_bed_temperature] ; wait bed\n"
        "M109 S[first_layer_temperature] ; wait nozzle\n"
        "G92 E0"
    )
    end_gcode = "M104 S0\nM140 S0\nG91\nG1 Z10 F600\nG90\nG28 X Y\nM84"
    cmd: list[str] = [
        binary,
        "--slice",
        "--output",
        str(OUT_GCODE),
        # Geometry / quality — moderate draft (2 perimeters back for reliability)
        "--layer-height",
        "0.3",
        "--first-layer-height",
        "0.3",
        "--perimeters",
        "2",  # 2 perimeters → reliable walls
        "--top-solid-layers",
        "3",
        "--bottom-solid-layers",
        "3",
        "--fill-density",
        "12%",
        "--fill-pattern",
        "grid",
        # Speeds — back near PrusaSlicer defaults; 0.3 mm layer already saves ~33%
        "--perimeter-speed",
        "55",
        "--infill-speed",
        "80",
        "--travel-speed",
        "150",
        "--external-perimeter-speed",
        "35",
        "--first-layer-speed",
        "25",  # slow first layer for adhesion
        "--default-acceleration",
        "1000",
        "--perimeter-acceleration",
        "800",
        "--infill-acceleration",
        "1000",
        "--travel-acceleration",
        "1500",
        "--max-volumetric-speed",
        "11",  # PLA default
        # Temperatures (now picked up by start_gcode placeholders)
        "--temperature",
        "210",
        "--first-layer-temperature",
        "215",  # +5°C on first layer for adhesion
        "--bed-temperature",
        "60",
        "--first-layer-bed-temperature",
        "65",  # +5°C on first layer for adhesion
        # Start/end blocks — ensures bed heats before printing
        "--start-gcode",
        start_gcode,
        "--end-gcode",
        end_gcode,
        # Bed shape (220×220 MK3S+; MK4 250×210 also accepts this)
        "--bed-shape",
        "0x0,220x0,220x220,0x220",
        str(bed_stl),
    ]
    print("Slicing:")
    print(f"  {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    if result.returncode != 0:
        print("--- prusa-slicer stderr ---")
        print(result.stderr)
        print("--- prusa-slicer stdout ---")
        print(result.stdout)
        return result.returncode
    print(f"  G-code: {OUT_GCODE.relative_to(REPO)} ({OUT_GCODE.stat().st_size} bytes)")
    return 0


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate, slice, and optionally upload the 4-piece carriage mount."
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="After slicing, push the .gcode to PrusaLink via upload_to_prusalink.py",
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help=(
            "With --upload: auto-start the print on the printer "
            "(no touchscreen confirmation)."
        ),
    )
    args = parser.parse_args()

    pieces = build_pieces()
    # Individual STLs (for inspection) — keep
    export_stls(pieces)
    # Pre-arranged combined STL — what we actually slice
    bed_stl = export_arranged_stl(pieces)
    rc = slice_bed(bed_stl)
    if rc != 0 or not args.upload:
        return rc

    # Delegate the upload to the dedicated script (creds live in ~/.cloud-credentials)
    uploader = REPO / "tools" / "slicer" / "upload_to_prusalink.py"
    cmd: list[str] = [sys.executable, str(uploader), str(OUT_GCODE)]
    if args.start:
        cmd.append("--start")
    print(f"\nUploading: {' '.join(cmd)}")
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
