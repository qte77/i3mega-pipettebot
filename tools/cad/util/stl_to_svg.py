"""Convert STL files to isometric wireframe SVGs using build123d.

Usage:
    python tools/cad/util/stl_to_svg.py hardware/stl/part.stl hardware/svg/part.svg
    python tools/cad/util/stl_to_svg.py --all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parents[3] / "hardware"
STL_DIR = ASSETS_DIR / "stl"
SVG_DIR = ASSETS_DIR / "svg"


def stl_to_svg(stl_path: Path, svg_path: Path) -> None:
    """Import STL and export as isometric wireframe SVG."""
    from build123d import ExportSVG, Rot, import_stl

    shape = import_stl(str(stl_path))
    iso = Rot(35.264, 0, -45) * shape
    exporter = ExportSVG()
    exporter.add_shape(iso)
    exporter.write(str(svg_path))
    print(f"  {svg_path.name}")


def _convert_all() -> int:
    stls = sorted(STL_DIR.glob("**/*.stl"))
    if not stls:
        print(f"No STL files in {STL_DIR}")
        return 1
    for stl in stls:
        rel = stl.relative_to(STL_DIR)
        svg = SVG_DIR / rel.with_suffix(".svg")
        svg.parent.mkdir(parents=True, exist_ok=True)
        stl_to_svg(stl, svg)
    return 0


def main() -> int:
    """CLI entry point for STL to SVG conversion."""
    parser = argparse.ArgumentParser(description="STL → wireframe SVG via build123d")
    parser.add_argument("stl", nargs="?", help="Input STL file")
    parser.add_argument("svg", nargs="?", help="Output SVG file")
    parser.add_argument("--all", action="store_true", help="Convert all STLs")
    args = parser.parse_args()

    if args.all:
        return _convert_all()

    if args.stl and args.svg:
        stl_to_svg(Path(args.stl), Path(args.svg))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
