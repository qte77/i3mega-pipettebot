"""Inject light/dark theme support into rendered SVGs.

Adds @media (prefers-color-scheme: dark) CSS so SVGs render readably in
both GitHub light and dark modes without per-file manual editing.

Handles two SVG dialects that coexist under hardware/svg/, detected by
content sniffing (each producer's markup is structurally different, so
one CSS block can't cover both):

- **build123d / CadQuery** (tools/cad/): bare `stroke="rgb(...)"`
  attributes, `.cq-bg` background class already emitted by
  `util/export.py`.
- **matplotlib** (tools/motion_profile_plot.py): inline
  `style="fill: #ffffff"` / `style="stroke: #000000"` attributes; text
  is rendered as vector glyph paths with NO fill set at all (relies on
  SVG's default black) -- there is no `<text>`/`.cq-bg`-equivalent to
  hook, so the dark-mode rule for glyphs is a broad low-specificity
  `path { fill: ... }` fallback. This is safe because every other path
  that must NOT be recolored (data curves, axis spines) sets its own
  `fill: none` inline, which always wins over a non-`!important`
  stylesheet rule regardless of selector specificity.

Usage:
    python tools/cad/util/theme_svgs.py
"""

import re
from pathlib import Path

BUILD123D_STYLE = """\
  <defs>
    <style>
      .cq-bg { fill: #ffffff; }
      @media (prefers-color-scheme: dark) {
        .cq-bg { fill: #0d1117; }
        /* CadQuery / build123d SVG selectors */
        g[stroke="rgb(0,0,0)"] { stroke: #c9d1d9 !important; }
        g[stroke="rgb(160,160,160)"] { stroke: #484f58 !important; }
        path { stroke: #c9d1d9 !important; }
        polygon { stroke: #c9d1d9 !important; fill: #161b22 !important; }
        line { stroke: #c9d1d9 !important; }
        text { stroke: #c9d1d9 !important; fill: #c9d1d9 !important; }
      }
    </style>
  </defs>"""

# Matplotlib inline-styles everything; nothing to `!important`-override for
# the background/spine colors needs more than an attribute-contains match.
# The bare `path { fill }` fallback recolors text glyphs (no competing
# inline fill) -- see module docstring for why this can't clobber data
# curves or spines (they set `fill: none` explicitly).
MATPLOTLIB_STYLE = """\
  <defs>
    <style>
      @media (prefers-color-scheme: dark) {
        path[style*="fill: #ffffff"] { fill: #0d1117 !important; }
        path[style*="stroke: #000000"] { stroke: #c9d1d9 !important; }
        path { fill: #c9d1d9; }
      }
    </style>
  </defs>"""

SVG_DIR = Path(__file__).resolve().parents[3] / "hardware" / "svg"
SKIP: set[str] = set()


def _is_matplotlib(content: str) -> bool:
    """Sniff producer from the SVG's own <dc:creator> metadata."""
    return "Matplotlib" in content[:1500]


def theme_svg(path: Path) -> None:
    """Inject theme CSS into a build123d- or matplotlib-generated SVG."""
    content = path.read_text()

    if "prefers-color-scheme" in content:
        return

    match = re.search(r"<svg\b[^>]*>", content)
    if not match:
        print(f"Skipped: {path.name} (no <svg> tag found)")
        return

    svg_end = match.end()

    if _is_matplotlib(content):
        injection = f"\n{MATPLOTLIB_STYLE}"
    else:
        w_match = re.search(r'width="([^"]+)"', match.group())
        h_match = re.search(r'height="([^"]+)"', match.group())
        w = w_match.group(1) if w_match else "100%"
        h = h_match.group(1) if h_match else "100%"
        bg_rect = f'  <rect width="{w}" height="{h}" class="cq-bg"/>'
        injection = f"\n{BUILD123D_STYLE}\n{bg_rect}"

    themed = content[:svg_end] + injection + content[svg_end:]
    path.write_text(themed)
    print(f"Themed: {path.name}")


def main() -> None:
    """Theme all SVGs in hardware/svg/ (build123d and matplotlib alike)."""
    for svg in sorted(SVG_DIR.glob("**/*.svg")):
        if svg.name in SKIP:
            continue
        theme_svg(svg)


if __name__ == "__main__":
    main()
