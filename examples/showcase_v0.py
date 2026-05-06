"""v0 showcase: home → move to A1 → aspirate 100 µL → move to B1 → dispense → home.

Hardcoded coordinates. No deck calibration, no tip handling, no 8-channel.
This is the smallest end-to-end demonstration that the i3 Mega + dPette
composition works. Everything else is in AGENT_REQUESTS.md as backlog.

Run with two USB-serial ports connected:
    /dev/ttyUSB0 — i3 Mega (Marlin)  @ 115200 8N1
    /dev/ttyUSB1 — dPette (CP2102)   @ 9600 8N1
"""

from __future__ import annotations

import serial  # type: ignore[import-untyped]
from dpette import DPetteDriver, SerialConfig

from pipettebot import GcodeGantry, PipetteBot
from pipettebot.gantry import GantryConfig

WELL_A1 = (100.0, 100.0, 5.0)
WELL_B1 = (100.0, 110.0, 5.0)  # 9 mm pitch
TRAVEL_Z = 40.0
ASPIRATE_VOLUME_UL = 100.0


def main() -> None:
    gantry_cfg = GantryConfig(port="/dev/ttyUSB0")
    marlin = serial.Serial(gantry_cfg.port, gantry_cfg.baudrate, timeout=10)
    gantry = GcodeGantry(gantry_cfg, marlin)

    pipette = DPetteDriver(SerialConfig(port="/dev/ttyUSB1"))
    pipette.connect()

    bot = PipetteBot(gantry, pipette)

    try:
        bot.home()
        gantry.move_to(WELL_A1[0], WELL_A1[1], TRAVEL_Z)
        bot.aspirate_at(*WELL_A1, volume_ul=ASPIRATE_VOLUME_UL)
        gantry.move_to(WELL_A1[0], WELL_A1[1], TRAVEL_Z)
        gantry.move_to(WELL_B1[0], WELL_B1[1], TRAVEL_Z)
        bot.dispense_at(*WELL_B1)
        gantry.move_to(WELL_B1[0], WELL_B1[1], TRAVEL_Z)
        bot.home()
    finally:
        pipette.disconnect()
        gantry.close()


if __name__ == "__main__":
    main()
