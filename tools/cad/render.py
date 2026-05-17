"""Render all parts from tools/cad/parts.json manifest.

Loads each `cad` script via importlib, calls its `build_func()`, exports
STL + SVG to top-level `hardware/{stl,svg}/`. Build123d only — no
OpenSCAD fallback in this repo (we don't ship `.scad` files).

Usage:
    uv run --extra cad python tools/cad/render.py
    uv run --extra cad python tools/cad/render.py --solid    # filled SVG faces
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import types

CAD_DIR = Path(__file__).resolve().parent  # tools/cad/
MANIFEST = CAD_DIR / "parts.json"
ASSETS_DIR = CAD_DIR.parents[1] / "hardware"  # top-level hardware/
STL_DIR = ASSETS_DIR / "stl"
SVG_DIR = ASSETS_DIR / "svg"
STEP_DIR = ASSETS_DIR / "step"

DEFERRED_STATUSES = frozenset({"deferred", "planned"})


def load_manifest() -> list[dict[str, Any]]:
    """Load and return the parts manifest."""
    return json.loads(MANIFEST.read_text())


def filter_active(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only parts whose status is not deferred/planned."""
    return [p for p in parts if p.get("status") not in DEFERRED_STATUSES]


def _load_module(cad_path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(cad_path.stem, cad_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load CAD module from {cad_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _to_compound(shape: Any) -> Any:
    from build123d import Compound, Solid

    if isinstance(shape, (Solid, Compound)):
        return shape
    if hasattr(shape, "__iter__"):
        return Compound(children=list(shape))
    return shape


def _export_svg(shape: Any, svg_out: Path, *, solid: bool) -> None:
    """Export a 3D shape as an isometric SVG with proper hidden-line removal.

    Uses build123d's `project_to_viewport` (the documented API for 3D-to-2D
    projection). The earlier `Rot(...) * shape` + `ExportSVG.add_shape` pattern
    triggers a "non-planar shape" warning and produces a flat XY squash that
    misrepresents 3D geometry.
    """
    from build123d import Color, Compound, ExportSVG, LineType

    # Camera at +X +Y +Z gives a front-right-above iso view; +Z is up.
    visible, hidden = shape.project_to_viewport(
        viewport_origin=(200.0, -200.0, 200.0),
        viewport_up=(0.0, 0.0, 1.0),
        look_at=(0.0, 0.0, 0.0),
    )
    bbox_all = Compound(children=list(visible) + list(hidden)).bounding_box()
    scale = 200.0 / max(bbox_all.size.X, bbox_all.size.Y, 1.0)

    exporter = ExportSVG(scale=scale)
    exporter.add_layer("Visible", line_color=Color(0, 0, 0), line_weight=0.5)
    exporter.add_layer(
        "Hidden",
        line_color=Color(0.6, 0.6, 0.6),
        line_weight=0.25,
        line_type=LineType.ISO_DOT,
    )
    if solid:
        exporter.add_layer("Fill", fill_color=Color(0.85, 0.85, 0.85), line_weight=0.0)
        exporter.add_shape(visible, layer="Fill")
    exporter.add_shape(visible, layer="Visible")
    exporter.add_shape(hidden, layer="Hidden")
    exporter.write(str(svg_out))


def _render_one(
    part: dict[str, Any],
    modules: dict[str, Any],
    shapes: dict[tuple[str, str], Any],
    *,
    solid: bool,
) -> None:
    from build123d import export_step, export_stl

    cad_rel = part["cad"]
    func_name = part["build_func"]
    cache_key = (cad_rel, func_name)

    if cache_key not in shapes:
        if cad_rel not in modules:
            modules[cad_rel] = _load_module(CAD_DIR / cad_rel)
        shapes[cache_key] = _to_compound(getattr(modules[cad_rel], func_name)())

    shape = shapes[cache_key]
    stl_out = STL_DIR / part["stl"]
    svg_out = SVG_DIR / part["svg"]
    # STEP path mirrors STL layout but with a .step extension — FreeCAD-ready
    # parametric solid (vs. STL which imports as a non-editable mesh).
    step_out = STEP_DIR / Path(part["stl"]).with_suffix(".step")
    stl_out.parent.mkdir(parents=True, exist_ok=True)
    svg_out.parent.mkdir(parents=True, exist_ok=True)
    step_out.parent.mkdir(parents=True, exist_ok=True)

    export_stl(shape, str(stl_out))
    export_step(shape, str(step_out))
    try:
        _export_svg(shape, svg_out, solid=solid)
        print(f"  {part['stl']} + {part['svg']} + {step_out.relative_to(ASSETS_DIR)}")
    except Exception as exc:
        print(
            f"  {part['stl']} + {step_out.relative_to(ASSETS_DIR)} (SVG failed: {exc})"
        )


def render_cad(parts: list[dict[str, Any]], *, solid: bool = False) -> None:
    """Render every part via build123d using its manifest entry."""
    print("--- Rendering via build123d")
    modules: dict[str, Any] = {}
    shapes: dict[tuple[str, str], Any] = {}
    for part in parts:
        if "cad" not in part or "build_func" not in part:
            print(f"  SKIP {part['name']} — no CAD script")
            continue
        _render_one(part, modules, shapes, solid=solid)


def run_theme() -> None:
    """Inject dark-mode CSS into all generated SVGs."""
    theme_script = CAD_DIR / "util" / "theme_svgs.py"
    subprocess.run([sys.executable, str(theme_script)], check=True)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Render parts from manifest")
    parser.add_argument(
        "--solid", action="store_true", help="Filled SVG faces (default: wireframe)"
    )
    args = parser.parse_args()

    parts = filter_active(load_manifest())
    if not parts:
        print("No active parts in manifest")
        return 0

    render_cad(parts, solid=args.solid)
    run_theme()
    print(f"=== {len(parts)} parts rendered ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
