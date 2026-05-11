"""Push a single part to the ocp-vscode browser viewer.

Loads the named part via the same manifest/importlib path as render.py,
then sends it to the running ocp_vscode server (http://127.0.0.1:3939).

Usage:
    python -m ocp_vscode                              # start the server (in another shell)
    uv run --extra cad python tools/cad/view.py       # list parts
    uv run --extra cad python tools/cad/view.py NAME  # show that part

Edit dimensions in tools/cad/measurements.py or the part script, then
re-run this command — the viewer re-renders on the next show() call.
"""

from __future__ import annotations

import argparse
import sys

# Reuse render.py's loader so we have one source of truth for manifest + module import.
from render import CAD_DIR, _load_module, _to_compound, filter_active, load_manifest


def list_parts() -> None:
    print("Active parts:")
    for part in filter_active(load_manifest()):
        print(f"  {part['name']:50s}  {part.get('notes', '')[:70]}")


def show_part(name: str) -> int:
    from ocp_vscode import show

    for part in filter_active(load_manifest()):
        if part["name"] == name:
            module = _load_module(CAD_DIR / part["cad"])
            shape = _to_compound(getattr(module, part["build_func"])())
            show(shape, names=[name])
            print(f"Pushed {name} to http://127.0.0.1:3939")
            return 0
    print(f"Unknown part: {name}")
    list_parts()
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a part to the ocp-vscode viewer")
    parser.add_argument("name", nargs="?", help="Part name from parts.json")
    args = parser.parse_args()
    if not args.name:
        list_parts()
        return 0
    return show_part(args.name)


if __name__ == "__main__":
    sys.exit(main())
