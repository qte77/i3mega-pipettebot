"""Shared export helpers for CAD part files.

Centralizes STL + SVG export to avoid duplication across part scripts.
"""

from __future__ import annotations

from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent  # tools/cad/
ASSETS_DIR = CODE_DIR.parents[1] / "hardware"  # top-level hardware/
STL_DIR = ASSETS_DIR / "stl"
SVG_DIR = ASSETS_DIR / "svg"
STEP_DIR = ASSETS_DIR / "step"


def _to_compound(shape):
    """Coerce build123d result (Solid, Compound, or ShapeList) to exportable Compound."""
    from build123d import Compound, Solid

    if isinstance(shape, (Solid, Compound)):
        return shape
    if hasattr(shape, "__iter__"):
        return Compound(children=list(shape))
    return shape


def export_part(part, subdir: str, filename: str) -> None:
    """Export a build123d shape to STL, STEP, and an isometric SVG.

    STEP is the FreeCAD-friendly parametric solid; STL is mesh-only.

    Args:
        part: build123d Solid/Compound/ShapeList.
        subdir: output subdirectory (e.g. "i3", "dpette", "labware").
        filename: stem without extension (e.g. "carriage_dpette_mount").
    """
    from build123d import Color, Compound, ExportSVG, LineType, export_step, export_stl

    part = _to_compound(part)

    stl_path = STL_DIR / subdir / f"{filename}.stl"
    svg_path = SVG_DIR / subdir / f"{filename}.svg"
    step_path = STEP_DIR / subdir / f"{filename}.step"
    stl_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    step_path.parent.mkdir(parents=True, exist_ok=True)

    export_stl(part, str(stl_path))
    export_step(part, str(step_path))

    try:
        # Camera at +X −Y +Z (front-right-above) with +Z up gives a standard
        # isometric view that's right-side-up in SVG output.
        visible, hidden = part.project_to_viewport(
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
        exporter.add_layer("Fill", fill_color=Color(0.85, 0.85, 0.85), line_weight=0.0)
        exporter.add_shape(visible, layer="Fill")
        exporter.add_shape(visible, layer="Visible")
        exporter.add_shape(hidden, layer="Hidden")
        exporter.write(str(svg_path))
    except Exception as exc:
        print(f"  SVG failed for {filename}: {exc}")

    print(f"Exported: {stl_path} + {step_path.relative_to(ASSETS_DIR)}")
