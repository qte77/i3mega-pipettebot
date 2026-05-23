"""Captured M115 replies for device-discovery parser tests.

Each constant is the joined-line text body of an `M115` reply with the
terminating `ok` line stripped (parsers see the body without the ack).
"""

from __future__ import annotations

# Captured live on the user's Geeetech A30 at /dev/ttyUSB0, 115200 baud.
# See docs/research/gantry-firmware-alternatives.md (2026-05-23 entry).
A30_M115_LIVE = (
    "MACHINE_TYPE:A30 UUID:181010A3000515A FIRMWARE_NAME:V1.xx.58\n"
    "PROTOCOL_VERSION:V1.0 EXTRUDER_COUNT:1"
)

# Representative MARLIN-AI3M reply shape (single-line FIRMWARE_NAME field
# followed by Cap: lines). The actual values match what an Anycubic i3
# Mega running MARLIN-AI3M v1.4.6 emits at 250000 baud.
MARLIN_AI3M_M115_SAMPLE = (
    "FIRMWARE_NAME:Marlin V1.4.6 "
    "SOURCE_CODE_URL:https://github.com/davidramiro/Marlin-AI3M "
    "PROTOCOL_VERSION:1.0 MACHINE_TYPE:Anycubic_i3_Mega "
    "EXTRUDER_COUNT:1 UUID:cede2a2f-41a2-4748-9b12-c55c62f367ff\n"
    "Cap:SERIAL_XON_XOFF:0\n"
    "Cap:EEPROM:1\n"
    "Cap:AUTOREPORT_TEMP:1\n"
    "Cap:AUTOLEVEL:1\n"
    "Cap:Z_PROBE:0\n"
    "Cap:THERMAL_PROTECTION:1"
)

# Plausible-but-unrecognised reply — used to exercise the `unknown`
# fallback in classify() and policy_for().
UNKNOWN_FIRMWARE_M115_SAMPLE = (
    "FIRMWARE_NAME:Klipper v0.12.0 PROTOCOL_VERSION:1.0 "
    "MACHINE_TYPE:Voron2.4 EXTRUDER_COUNT:1"
)
