"""Clean and reorient a raw 3D scan of a dPette pipette.

The raw scan typically arrives with the pipette laying diagonally on a
turntable in the scanner's reference frame, plus a few floating scan
artifacts and a non-watertight surface (open ends where the scanner
couldn't see).

This script normalizes the scan so it can be used as a parametric-CAD
reference in build123d:

  1. drop small disconnected components (noise)
  2. PCA on vertices to find the pipette's long axis
  3. rotate so long axis aligns with +Z
  4. orient tip-down (narrower end at z=0) to match how the dPette mounts
     on the i3 carriage
  5. PCA on the head section in XY to align its long axis with +X
  6. translate so XY centroid is at origin and base at z=0
  7. fill small holes for watertightness (best-effort)

Run:
    uv run --with trimesh --with networkx --with numpy \
        tools/cad/scan/clean_pipette_scan.py \
        --input  hardware/3d-scan/_scan_temp.stl \
        --output hardware/3d-scan/dpette_scan.stl
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import trimesh


def _largest_components(mesh: trimesh.Trimesh, min_faces: int) -> trimesh.Trimesh:
    parts = mesh.split(only_watertight=False)
    kept = [p for p in parts if len(p.faces) >= min_faces]
    if not kept:
        raise RuntimeError("no components survived min_faces filter")
    return trimesh.util.concatenate(kept) if len(kept) > 1 else kept[0]


def _align_principal_axis_to_z(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    verts = mesh.vertices - mesh.vertices.mean(axis=0)
    _, _, vt = np.linalg.svd(verts, full_matrices=False)
    long_axis = vt[0]
    if long_axis[2] < 0:
        long_axis = -long_axis
    rot = trimesh.geometry.align_vectors(long_axis, np.array([0.0, 0.0, 1.0]))
    mesh.apply_transform(rot)
    return mesh


def _orient_tip_down(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    # The dPette tip end is narrower than the display-housing head end.
    # Compare cross-sectional spread in the lower-20% vs upper-20% Z bands.
    z = mesh.vertices[:, 2]
    z_min, z_max = z.min(), z.max()
    span = z_max - z_min
    lower = mesh.vertices[z < z_min + 0.2 * span][:, :2]
    upper = mesh.vertices[z > z_max - 0.2 * span][:, :2]
    lower_spread = float(np.linalg.norm(lower.std(axis=0)))
    upper_spread = float(np.linalg.norm(upper.std(axis=0)))
    if lower_spread > upper_spread:
        # Currently head-down; flip 180° around X so tip goes to z=0.
        flip = trimesh.transformations.rotation_matrix(
            np.pi, [1.0, 0.0, 0.0], [0.0, 0.0, (z_min + z_max) / 2.0]
        )
        mesh.apply_transform(flip)
    return mesh


def _align_head_to_x(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    # After the primary alignment, the dPette head section sits at the top
    # of the mesh but its display-housing rectangle may be diagonal in XY.
    # PCA on the top-20% XY footprint finds that long axis; rotate around
    # Z to put it on +X.
    z = mesh.vertices[:, 2]
    z_min, z_max = z.min(), z.max()
    head = mesh.vertices[z > z_max - 0.2 * (z_max - z_min)][:, :2]
    head_centered = head - head.mean(axis=0)
    _, _, vt = np.linalg.svd(head_centered, full_matrices=False)
    head_axis = np.array([vt[0, 0], vt[0, 1], 0.0])
    rot = trimesh.geometry.align_vectors(head_axis, np.array([1.0, 0.0, 0.0]))
    mesh.apply_transform(rot)
    return mesh


def _recenter(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    bounds = mesh.bounds
    cx = (bounds[0, 0] + bounds[1, 0]) / 2.0
    cy = (bounds[0, 1] + bounds[1, 1]) / 2.0
    zmin = bounds[0, 2]
    mesh.apply_translation([-cx, -cy, -zmin])
    return mesh


def clean(input_path: Path, output_path: Path, min_faces: int = 200) -> None:
    mesh = trimesh.load(input_path)
    print(f"input: {len(mesh.faces):,} tris, watertight={mesh.is_watertight}")

    mesh = _largest_components(mesh, min_faces=min_faces)
    print(f"after orphan drop: {len(mesh.faces):,} tris")

    _align_principal_axis_to_z(mesh)
    _orient_tip_down(mesh)
    _align_head_to_x(mesh)
    _recenter(mesh)

    trimesh.repair.fill_holes(mesh)
    print(
        f"after orient+recenter: extents "
        f"{mesh.extents[0]:.1f} x {mesh.extents[1]:.1f} x {mesh.extents[2]:.1f} mm, "
        f"watertight={mesh.is_watertight}"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(output_path)
    print(f"wrote {output_path}")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--input",
        type=Path,
        default=repo_root / "hardware" / "3d-scan" / "_scan_temp.stl",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=repo_root / "hardware" / "3d-scan" / "dpette_scan.stl",
    )
    ap.add_argument("--min-faces", type=int, default=200)
    args = ap.parse_args()
    clean(args.input, args.output, args.min_faces)


if __name__ == "__main__":
    main()
