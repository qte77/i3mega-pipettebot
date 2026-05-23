"""Preflight check: auto-discover any G-code gantry and/or the dPette, no motion.

Either device alone is enough to pass — the gantry and the pipette are
exercised independently in v0, so requiring both to be present at the
same time was wrong.

Scans candidate `/dev/tty*` / `/dev/cu.*` ports and probes each one:

1. **Gantry probe**: delegates to `pipettebot.devices.discover()`, which
   baud-sweeps and sends `M115`. Returns a `DiscoveredDevice` whose
   `firmware_family` ("marlin", "smartto", or "unknown") drives the
   per-family export-var name via `FIRMWARE_POLICIES`.
2. **dPette probe**: on every port that didn't answer as a gantry, open
   at 9600 baud via `dpette.DPetteDriver.connect()` (sends `A0` HELLO),
   then read EEPROM byte 0 (firmware version). A `None` return means
   the driver fell back to stub mode → not a real dPette.

Env vars `I3MEGA_PORT` / `SMARTTO_PORT` / `GANTRY_PORT` and `PIPETTE_PORT`
win over discovery — useful when discovery picks the wrong port or you
want a stable mapping. First-set wins for the gantry override (checked
in that order).

Pass `--export` to suppress probe chatter on stdout and print only
`export <I3MEGA|SMARTTO|GANTRY>_PORT=...` / `export PIPETTE_PORT=...`
lines, suitable for shell `eval`:

    eval "$(uv run python tools/preflight.py --export)" \
      && uv run python examples/showcase_v0_pipette_sim.py

Probe chatter still goes to stderr in export mode, so you can see
what was happening if the discovery failed.

The dPette will silently power-gate its USB chip off when it goes to
standby — its `/dev/` node disappears entirely, not just the
handshake. To survive that, the dPette probe retries with a
configurable cadence:

  DPETTE_RETRY_ATTEMPTS    Total attempts (default 3).
  DPETTE_RETRY_DELAY_S     Seconds between attempts (default 5).

Between attempts the port list is re-scanned, so a replug that
hands out a new `/dev/cu.usbserial-XXX` is picked up automatically.
"""

from __future__ import annotations

import contextlib
import glob
import os
import sys
import time

from dpette import DPetteDriver, SerialConfig

from pipettebot.devices import DiscoveredDevice, discover, policy_for

DPETTE_BAUD = 9600  # informational; the driver opens the port itself
DPETTE_RETRY_ATTEMPTS_DEFAULT = 3
DPETTE_RETRY_DELAY_S_DEFAULT = 5.0
GANTRY_PORT_ENV_ORDER = ("I3MEGA_PORT", "SMARTTO_PORT", "GANTRY_PORT")

PORT_GLOBS = (
    "/dev/cu.usbserial-*",
    "/dev/cu.wchusbserial*",
    "/dev/cu.usbmodem*",
    "/dev/ttyUSB*",
    "/dev/ttyACM*",
)


def discover_ports() -> list[str]:
    """All USB-serial-style devices visible on this OS, sorted."""
    found: set[str] = set()
    for g in PORT_GLOBS:
        found.update(glob.glob(g))
    return sorted(found)


def probe_dpette(port: str) -> int | None:
    """Try to identify `port` as a dPette. Returns EEPROM[0] byte or None.

    `read_ee(0)` returns a 6-byte `Packet` whose `b2` field carries the
    EEPROM payload. Stub mode / open failure / handshake timeout all
    produce `None`.
    """
    try:
        drv = DPetteDriver(SerialConfig(port=port))
        drv.connect()
    except Exception:
        return None
    try:
        packet = drv.read_ee(0)
    except Exception:
        packet = None
    finally:
        with contextlib.suppress(Exception):
            drv.disconnect()
    if packet is None:
        return None
    return int(getattr(packet, "b2", 0))


def _resolve_gantry(
    ports: list[str], override: str | None
) -> tuple[str | None, DiscoveredDevice | None]:
    """Identify a gantry port (or use override). Returns (port, discovered)."""
    if override:
        print(f"[probe] {override} for gantry (env override) ... ", end="", flush=True)
        device = discover(override)
        if device is not None:
            print(f"FOUND ({device.firmware_family} @ {device.baud})")
            machine = device.machine_type or "?"
            version = device.firmware_version or "?"
            print(f"  > {machine} ({version})")
            return override, device
        print("no reply")
        return None, None
    for p in ports:
        print(f"[probe] {p} for gantry (baud sweep, M115) ... ", end="", flush=True)
        device = discover(p)
        if device is not None:
            print(f"FOUND ({device.firmware_family} @ {device.baud})")
            machine = device.machine_type or "?"
            version = device.firmware_version or "?"
            print(f"  > {machine} ({version})")
            return p, device
        print("no")
    return None, None


def _resolve_dpette(
    ports: list[str], override: str | None, skip: str
) -> tuple[str | None, int | None]:
    """Find the dPette port (or use override), skipping the Marlin port."""
    if override:
        print(f"[probe] {override} for dPette (env override) ... ", end="", flush=True)
        v = probe_dpette(override)
        if v is not None:
            print("ok")
            print(f"  > EEPROM[0] = 0x{v:02X} ({v})")
            return override, v
        print("no reply / stub mode")
        return None, None
    for p in ports:
        if p == skip:
            continue
        print(
            f"[probe] {p} for dPette (A0 HELLO @ {DPETTE_BAUD}) ... ",
            end="",
            flush=True,
        )
        v = probe_dpette(p)
        if v is not None:
            print("FOUND")
            print(f"  > EEPROM[0] = 0x{v:02X} ({v})")
            return p, v
        print("no")
    return None, None


def _resolve_dpette_with_retry(
    initial_ports: list[str], override: str | None, skip: str
) -> tuple[str | None, int | None]:
    """Probe for the dPette, retrying with port-rescan on each attempt.

    Survives standby drops where the dPette's USB chip power-gates off
    and reappears at a different `/dev/` path on replug.
    """
    attempts = int(
        os.environ.get("DPETTE_RETRY_ATTEMPTS", str(DPETTE_RETRY_ATTEMPTS_DEFAULT))
    )
    delay = float(
        os.environ.get("DPETTE_RETRY_DELAY_S", str(DPETTE_RETRY_DELAY_S_DEFAULT))
    )
    ports = initial_ports
    for attempt in range(1, attempts + 1):
        if attempt > 1:
            print(
                f"\n[retry {attempt}/{attempts}] dPette not found — "
                "replug it / press its button / wait for re-enumeration"
            )
            time.sleep(delay)
            ports = discover_ports()  # rescan after sleep
            print(f"Discovered ports: {ports}")
        dpette_port, version = _resolve_dpette(ports, override, skip=skip)
        if dpette_port:
            return dpette_port, version
    return None, None


def _gantry_env_override() -> str | None:
    """Return the first set gantry-port env var, in I3MEGA->SMARTTO->GANTRY order."""
    for var in GANTRY_PORT_ENV_ORDER:
        value = os.environ.get(var)
        if value:
            return value
    return None


def main() -> int:
    export_mode = "--export" in sys.argv
    original_stdout = sys.stdout
    if export_mode:
        # Route probe chatter to stderr; stdout stays clean for `eval` consumers.
        sys.stdout = sys.stderr

    gantry_port: str | None = None
    gantry_device: DiscoveredDevice | None = None
    dpette_port: str | None = None

    try:
        ports = discover_ports()
        if not ports:
            print("No USB-serial ports found. Plug in the printer or dPette.")
            return 1
        print(f"Discovered ports: {ports}\n")

        gantry_port, gantry_device = _resolve_gantry(ports, _gantry_env_override())

        print()
        print("(press the dPette's button if it's asleep — handshake needs it awake)")
        dpette_port, _ = _resolve_dpette_with_retry(
            ports, os.environ.get("PIPETTE_PORT"), skip=gantry_port or ""
        )

        print()
        if not gantry_port and not dpette_port:
            print("ERROR: no port answered as a gantry or dPette.")
            return 1
    finally:
        sys.stdout = original_stdout

    gantry_export_name: str | None = None
    if gantry_device is not None:
        # First alias in the policy is canonical (e.g. I3MEGA_PORT for marlin,
        # SMARTTO_PORT for smartto, GANTRY_PORT for unknown).
        gantry_export_name = policy_for(gantry_device).port_env_aliases[0]

    if export_mode:
        if gantry_port and gantry_export_name:
            print(f"export {gantry_export_name}={gantry_port}")
        if dpette_port:
            print(f"export PIPETTE_PORT={dpette_port}")
    else:
        print("===== preflight =====")
        label = gantry_export_name or "GANTRY_PORT"
        print(f"  {label:12} = {gantry_port or '(not found)'}")
        print(f"  PIPETTE_PORT = {dpette_port or '(not found)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
