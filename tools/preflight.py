"""Preflight check: auto-discover the i3 Mega and the dPette, no motion.

Scans candidate `/dev/tty*` / `/dev/cu.*` ports and probes each one:

1. **Marlin probe**: open at 250000 baud, wait 3 s for boot, send `M115`,
   look for `MACHINE_TYPE:` / `FIRMWARE_NAME:` in the reply.
2. **dPette probe**: on every port that didn't answer as Marlin, open at
   9600 baud via `dpette.DPetteDriver.connect()` (sends `A0` HELLO),
   then read EEPROM byte 0 (firmware version). A `None` return means
   the driver fell back to stub mode → not a real dPette.

Env vars `I3MEGA_PORT` and `PIPETTE_PORT` win over discovery — useful
when discovery picks the wrong port or you want a stable mapping.

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

import serial  # type: ignore[import-untyped]
from dpette import DPetteDriver, SerialConfig

from pipettebot.gantry import open_marlin_port

MARLIN_BAUD = 250000  # Anycubic stock & MARLIN-AI3M; see issue #17
MARLIN_BOOT_WAIT_S = 3.0
MARLIN_PROBE_READ_S = 4.0
DPETTE_BAUD = 9600  # informational; the driver opens the port itself
DPETTE_RETRY_ATTEMPTS_DEFAULT = 3
DPETTE_RETRY_DELAY_S_DEFAULT = 5.0

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


def probe_marlin(port: str) -> str | None:
    """Try to identify `port` as Marlin. Returns firmware string or None."""
    link = open_marlin_port(port, baudrate=MARLIN_BAUD, timeout=1.0)
    if link is None:
        return None
    with link:
        time.sleep(MARLIN_BOOT_WAIT_S)  # DTR-reset boot
        link.reset_input_buffer()
        try:
            link.write(b"M115\n")
        except serial.SerialException:
            return None
        firmware: str | None = None
        deadline = time.time() + MARLIN_PROBE_READ_S
        while time.time() < deadline:
            raw = link.readline()
            if not raw:
                continue
            s = raw.decode("ascii", errors="replace").strip()
            if not s:
                continue
            if "FIRMWARE_NAME" in s or "MACHINE_TYPE" in s:
                firmware = s
            if (s == "ok" or s.startswith("ok ")) and firmware:
                break
        return firmware


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


def _resolve_marlin(
    ports: list[str], override: str | None
) -> tuple[str | None, str | None]:
    """Find the Marlin port (or use override). Returns (port, firmware)."""
    if override:
        print(f"[probe] {override} for Marlin (env override) ... ", end="", flush=True)
        fw = probe_marlin(override)
        if fw:
            print("ok")
            print(f"  > {fw}")
            return override, fw
        print("no reply")
        return None, None
    for p in ports:
        print(f"[probe] {p} for Marlin (M115 @ {MARLIN_BAUD}) ... ", end="", flush=True)
        fw = probe_marlin(p)
        if fw:
            print("FOUND")
            print(f"  > {fw}")
            return p, fw
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


def main() -> int:
    ports = discover_ports()
    if not ports:
        print("No USB-serial ports found. Plug in the printer and dPette.")
        return 1
    print(f"Discovered ports: {ports}\n")

    marlin_port, _ = _resolve_marlin(ports, os.environ.get("I3MEGA_PORT"))
    if not marlin_port:
        print("\nERROR: no port answered as Marlin.")
        return 1

    print()
    print("(press the dPette's button if it's in standby — handshake needs it awake)")
    dpette_port, _ = _resolve_dpette_with_retry(
        ports, os.environ.get("PIPETTE_PORT"), skip=marlin_port
    )
    if not dpette_port:
        print("\nERROR: no port answered as dPette after retries.")
        return 1

    print()
    print("===== preflight passed =====")
    print(f"  I3MEGA_PORT  = {marlin_port}")
    print(f"  PIPETTE_PORT = {dpette_port}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
