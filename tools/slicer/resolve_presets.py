"""Extract PrusaSlicer Input-Shaper presets from the system bundle.

Wraps the preset-resolution workaround documented in docs/prusa/README.md
(Quirk 5): the PrusaSlicer CLI only finds printer/print/filament presets
in `~/.config/PrusaSlicer/{printer,print,filament}/`, never in the system
vendor bundle. This walks the `inherits` chain for a fixed IS-aware
printer/print/filament trio and writes each as a flat `.ini` into the
user config dir so `make slice` (tools/slicer/slice.py) can reference
them by name.

Usage:
    python tools/slicer/resolve_presets.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_USER_DIR = Path.home() / ".config" / "PrusaSlicer"

# Confirmed present at this path (PrusaSlicer 2.9.4, this repo's
# devcontainer). If your install differs, point BUNDLE at your system's
# bundle — see docs/prusa/README.md.
BUNDLE = Path("/usr/share/PrusaSlicer/profiles/PrusaResearch.ini")

# The IS-aware trio this repo standardizes on (MK4 + Input Shaper).
PRESETS: tuple[tuple[str, str], ...] = (
    ("printer", "Original Prusa MK4 Input Shaper 0.4 nozzle"),
    ("print", "0.20mm SPEED @MK4IS 0.4"),
    ("filament", "Prusa PLA"),
)


def parse_ini(path: Path) -> dict[str, list[str]]:
    """Split a PrusaSlicer bundle .ini into {section_name: raw_lines}."""
    sections: dict[str, list[str]] = {}
    name: str | None = None
    buf: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines(keepends=True):
        header = re.match(r"^\[([^\]]+)\]\s*$", line)
        if header:
            if name is not None:
                sections[name] = buf
            name, buf = header.group(1), []
        else:
            buf.append(line)
    if name is not None:
        sections[name] = buf
    return sections


def _kv(lines: list[str]) -> dict[str, str]:
    """Parse `key = value` lines, skipping comments and blanks."""
    out: dict[str, str] = {}
    for raw in lines:
        stripped = raw.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _, value = stripped.partition("=")
            out[key.strip()] = value.strip()
    return out


def resolve(
    sections: dict[str, list[str]],
    full: str,
    visited: set[str] | None = None,
) -> dict[str, str]:
    """Flatten a preset's `inherits` chain into one dict of resolved keys.

    Child keys win over inherited ones. Cycles are broken by `visited`; a
    missing parent section resolves to `{}` rather than raising, since
    some bundle entries reference wildcard parents that don't need every
    listed ancestor to exist.
    """
    seen = visited if visited is not None else set()
    if full in seen or full not in sections:
        return {}
    seen.add(full)
    body = _kv(sections[full])
    inherits = body.pop("inherits", None)
    if inherits:
        kind = full.split(":", 1)[0]
        for parent in re.split(r"[;,]", inherits):
            parent_name = parent.strip().strip("\"'")
            if parent_name:
                parent_body = resolve(sections, f"{kind}:{parent_name}", seen)
                for key, value in parent_body.items():
                    body.setdefault(key, value)
    return body


def write_preset(
    kind: str, name: str, resolved: dict[str, str], user_dir: Path
) -> Path:
    """Write a flattened preset as `<user_dir>/<kind>/<name>.ini`."""
    out_dir = user_dir / kind
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{name}.ini"
    body = "".join(f"{key} = {value}\n" for key, value in resolved.items())
    out_path.write_text(body, encoding="utf-8")
    return out_path


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=BUNDLE)
    parser.add_argument(
        "--user-dir",
        type=Path,
        default=DEFAULT_USER_DIR,
        help="PrusaSlicer user config dir (default: ~/.config/PrusaSlicer)",
    )
    args = parser.parse_args()

    if not args.bundle.exists():
        print(f"SKIP: PrusaSlicer bundle not found at {args.bundle}.")
        print("Install PrusaSlicer or point --bundle at your system's bundle.")
        return 1
    sections = parse_ini(args.bundle)
    for kind, name in PRESETS:
        full = f"{kind}:{name}"
        if full not in sections:
            print(f"FAIL: {full!r} not found in {args.bundle}")
            return 1
        resolved = resolve(sections, full)
        out_path = write_preset(kind, name, resolved, args.user_dir)
        print(f"wrote {out_path} ({len(resolved)} keys)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
