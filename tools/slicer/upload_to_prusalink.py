"""Upload a G-code file to the Prusa MK4 over PrusaLink HTTP API.

Credentials are read from ~/.cloud-credentials (chmod 600, never in this repo).
Expected keys there:

    PRUSA_HOST=192.168.1.86
    PRUSA_USER=maker
    PRUSA_PASSWORD=...

Usage:
    uv run python tools/slicer/upload_to_prusalink.py [GCODE] \
        [--storage usb|local] [--start]

Defaults:
    GCODE   = hardware/gcode/carriage_assembly.gcode
    storage = usb
    start   = False  (file uploaded only; tap Print on the touchscreen)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

CREDS_PATH = Path.home() / ".cloud-credentials"
REQUIRED_KEYS = ("PRUSA_HOST", "PRUSA_USER", "PRUSA_PASSWORD")
DEFAULT_GCODE = (
    Path(__file__).resolve().parents[2]
    / "hardware"
    / "gcode"
    / "carriage_assembly.gcode"
)

# Matches:  export KEY="value"   |   export KEY='value'   |   KEY=value
ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)=(.*)$")


def _strip_quotes(value: str) -> str:
    value = value.strip()
    # Drop trailing comments (only when value isn't quoted)
    if value and value[0] not in {'"', "'"} and "#" in value:
        value = value.split("#", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value


def load_creds() -> dict[str, str]:
    if not CREDS_PATH.exists():
        sys.exit(f"ERROR: {CREDS_PATH} not found")
    mode = CREDS_PATH.stat().st_mode & 0o777
    if mode & 0o077:
        sys.exit(
            f"ERROR: {CREDS_PATH} is world/group readable "
            f"(mode={oct(mode)}); chmod 600 it"
        )

    found: dict[str, str] = {}
    for raw in CREDS_PATH.read_text().splitlines():
        match = ENV_LINE.match(raw)
        if not match:
            continue
        key = match.group(1)
        if key in REQUIRED_KEYS:
            found[key] = _strip_quotes(match.group(2))

    missing = [k for k in REQUIRED_KEYS if k not in found]
    if missing:
        sys.exit(f"ERROR: missing keys in {CREDS_PATH}: {missing}")
    return found


def _opener(host: str, user: str, password: str) -> urllib.request.OpenerDirector:
    mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    mgr.add_password(None, f"http://{host}/", user, password)
    return urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(mgr))


def upload(
    gcode: Path,
    host: str,
    user: str,
    password: str,
    storage: str,
    start: bool,
) -> int:
    if not gcode.exists():
        sys.exit(f"ERROR: {gcode} not found")

    data = gcode.read_bytes()
    url = f"http://{host}/api/v1/files/{storage}/{gcode.name}"
    headers = {
        "Content-Type": "application/octet-stream",
        # Structured Field boolean syntax — ?1 is true, ?0 is false.
        "Overwrite": "?1",
    }
    if start:
        headers["Print-After-Upload"] = "?1"

    opener = _opener(host, user, password)
    req = urllib.request.Request(url, data=data, method="PUT", headers=headers)
    try:
        with opener.open(req, timeout=120) as r:
            body = r.read().decode(errors="replace")
            print(
                f"HTTP {r.status} — uploaded {gcode.name} "
                f"({len(data):,} bytes) → {storage}"
            )
            try:
                meta = json.loads(body)
                print(f"  display_name: {meta.get('display_name')}")
                print(f"  short_name:   {meta.get('name')}")
            except json.JSONDecodeError:
                pass
            if start:
                print("Print-After-Upload sent — printer should start automatically.")
            else:
                print("Tap on the printer: USB → carriage_assembly.gcode → Print.")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        sys.exit(f"ERROR: HTTP {e.code} {e.reason}\n  {body[:400]}")
    except urllib.error.URLError as e:
        sys.exit(f"ERROR: cannot reach {host}: {e.reason}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload G-code to PrusaLink (MK4)")
    parser.add_argument(
        "gcode",
        nargs="?",
        default=str(DEFAULT_GCODE),
        help=f"G-code file to upload (default: {DEFAULT_GCODE.name})",
    )
    parser.add_argument("--storage", choices=("usb", "local"), default="usb")
    parser.add_argument(
        "--start",
        action="store_true",
        help="Auto-start the print after upload (no touchscreen confirmation)",
    )
    args = parser.parse_args()

    creds = load_creds()
    host = creds["PRUSA_HOST"]
    print(
        f"PrusaLink: http://{host}/  user: {creds['PRUSA_USER']}  "
        f"storage: {args.storage}"
    )
    return upload(
        Path(args.gcode),
        host,
        creds["PRUSA_USER"],
        creds["PRUSA_PASSWORD"],
        args.storage,
        args.start,
    )


if __name__ == "__main__":
    sys.exit(main())
