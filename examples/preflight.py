"""Preflight check: confirm port mapping and firmware versions; no motion.

Run before `examples/showcase_v0.py`. This script:

1. Opens the Marlin port (`I3MEGA_PORT`, default `/dev/ttyUSB0`) at
   115200 8N1, sends `M115`, prints the firmware string.
2. Opens the dPette port (`PIPETTE_PORT`, default `/dev/ttyUSB1`) via
   `dpette.DPetteDriver.connect()` (sends `A0` HELLO), prints the
   firmware version byte from EEPROM address 0.
3. Asks the operator to confirm the port mapping is correct.

It does not home, move, aspirate, or dispense. Safe to run anytime.
"""

from __future__ import annotations

import os
import sys

import serial  # type: ignore[import-untyped]
from dpette import DPetteDriver, SerialConfig

DEFAULT_MARLIN_PORT = "/dev/ttyUSB0"
DEFAULT_PIPETTE_PORT = "/dev/ttyUSB1"
MARLIN_BAUD = 115200
MARLIN_READ_TIMEOUT_S = 2.0


def check_marlin(port: str) -> str:
    """Open `port`, send M115, return the first line of Marlin's reply."""
    with serial.Serial(port, MARLIN_BAUD, timeout=MARLIN_READ_TIMEOUT_S) as link:
        link.write(b"M115\n")
        line: bytes = link.readline()
    return line.decode("ascii", errors="replace").strip()


def check_dpette(port: str) -> int:
    """Open `port` via DPetteDriver, return EEPROM byte 0 (firmware version)."""
    drv = DPetteDriver(SerialConfig(port=port))
    drv.connect()
    try:
        version: int = drv.read_ee(0)
    finally:
        drv.disconnect()
    return version


def main() -> int:
    marlin_port = os.environ.get("I3MEGA_PORT", DEFAULT_MARLIN_PORT)
    pipette_port = os.environ.get("PIPETTE_PORT", DEFAULT_PIPETTE_PORT)

    print(f"Marlin port:  {marlin_port}")
    print(f"Pipette port: {pipette_port}")
    print()

    print(f"[1/2] Querying Marlin firmware via {marlin_port} ...")
    try:
        firmware = check_marlin(marlin_port)
    except (OSError, serial.SerialException) as exc:
        print(f"  ERROR: {exc}")
        return 1
    print(f"  > {firmware}")
    if "Marlin" not in firmware:
        print("  WARN: response did not contain 'Marlin' — wrong port?")

    print()
    print(f"[2/2] Connecting to dPette via {pipette_port} ...")
    print("      (press the dPette's button if it's in standby)")
    try:
        version = check_dpette(pipette_port)
    except (OSError, serial.SerialException) as exc:
        print(f"  ERROR: {exc}")
        return 1
    print(f"  > EEPROM[0] (firmware version) = 0x{version:02X} ({version})")

    print()
    answer = (
        input("Confirm port mapping is correct (printer + pipette)? [y/N] ")
        .strip()
        .lower()
    )
    if answer != "y":
        print("Aborted by operator.")
        return 1
    print("OK — preflight passed. Proceed to examples/showcase_v0.py once well")
    print("coordinates are calibrated (see docs/calibration.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
