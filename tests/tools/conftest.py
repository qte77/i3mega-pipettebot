"""Add tools/ to sys.path so tools/* scripts can import sibling modules.

The lean teleop pair (`teleop_lean.py`, `teleop_replay.py`) shares
`_teleop_common.py` via `from _teleop_common import ...`. When tests load
each script via `importlib.util.spec_from_file_location`, Python's import
system looks for the shared module on `sys.path` — so we inject `tools/`
once per test session here.

At script runtime this happens automatically: `python tools/script.py`
puts the script's directory at `sys.path[0]`. Tests bypass that path,
so the injection has to be explicit.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))
