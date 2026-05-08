---
title: "Hardware setup"
status: "DRAFT"
updated: "2026-05-07"
owner: "lambda biolab"
---

This guide covers the **physical and electrical setup** of an Anycubic i3
Mega 3D printer and a DLAB dPette electronic pipette so the v0 demo
(`examples/showcase_v0_pipette_sim.py`) can run end-to-end. Software install is
covered in the [README](../README.md) and contributor setup in
[CONTRIBUTING](../CONTRIBUTING.md).

## Topology

Two USB cables, one to the printer and one to the pipette:

```text
PC ──USB-B──► Anycubic i3 Mega   (Trigorilla, ATmega2560, Marlin) /dev/tty?  115200 8N1
PC ──CP2102──► DLAB dPette                                         /dev/tty?  9600 8N1
```

The PC is the orchestrator. Marlin executes G-code; the dPette executes
6-byte serial commands via `dpette-usb-driver`. They never talk to each
other directly in v0.

## Anycubic i3 Mega

| Item | Value |
|---|---|
| Mainboard | Trigorilla 0.0.4 (ATmega2560 + A4988 drivers, stock) |
| Firmware | Anycubic stock Marlin 1.4.x **or** upstream Marlin 2.x |
| USB bridge chip | CH340 |
| VID:PID | `1a86:7523` |
| Baud | 115200 8N1 |
| Connector | USB-B on the LCD/board housing |

We use **stock Marlin without modifications** in v0. The G-code surface we
need is small: `G28`, `G1`, `M114`, `M115`, `M400`. Both 1.4.x and 2.x
support all of these.

### Confirming the printer port

After plugging in the printer, find its `/dev/tty*` device:

```bash
# Linux — newest CH340 enumeration shows in dmesg
dmesg | tail -20 | grep -i ch34
# Expected: usb 1-1: ch341-uart converter now attached to ttyUSB0

# Or query udev directly
udevadm info /dev/ttyUSB0 | grep -E 'ID_VENDOR_ID|ID_MODEL_ID|ID_VENDOR'
# Expected: ID_VENDOR_ID=1a86, ID_MODEL_ID=7523
```

```bash
# macOS
system_profiler SPUSBDataType | grep -A8 -i 'CH34\|wch'
ls /dev/cu.wchusbserial* /dev/cu.usbserial-* 2>/dev/null
```

If the printer enumerates differently on your build (e.g. SKR/Spider
upgrade swapping CH340 for CP2102 or FTDI), substitute the matching
VID:PID in the table below.

### Marlin firmware sanity check

Once you have the port, send `M115` and read the firmware string. The
[`examples/preflight.py`](../examples/preflight.py) script does this for
you; manually it looks like:

```bash
# Replace /dev/ttyUSB0 with your printer port
stty -F /dev/ttyUSB0 115200 raw
printf 'M115\n' > /dev/ttyUSB0 && timeout 2 cat /dev/ttyUSB0
# Expected first line: FIRMWARE_NAME:Marlin 1.1.X (Anycubic Mega ...) ...
```

## DLAB dPette

The pipette's USB cable terminates in a Silicon Labs CP2102 USB-UART
bridge. Full details — including the standby/connectable button-press
quirk and the protocol — are in
[`dpette-usb-driver/docs/HARDWARE.md`](https://github.com/Lambda-Biolab/dpette-usb-driver/blob/main/docs/HARDWARE.md).

| Item | Value |
|---|---|
| USB bridge chip | CP2102 |
| VID:PID | `10c4:ea60` |
| Baud | 9600 8N1 |
| Driver | `cp210x` (built into Linux kernel; native on macOS) |

### Wake the pipette before connecting

The dPette has two states:

1. **Standby** — screen dim or off. Serial connect will time out.
2. **Connectable** — press the operation button. Screen shows volume/mode.

The driver handshake (`A0 HELLO` via `DPetteDriver.connect()`) only
succeeds in state 2. If `preflight.py` reports a handshake timeout,
press the dPette's button and retry.

## Distinguishing the two ports

When both the printer and the pipette are plugged in, your `/dev/tty*`
list has two entries. You disambiguate them by USB VID:PID, **not by
which port number got assigned** (assignment depends on plug order).

```bash
for d in /dev/ttyUSB*; do
  echo "$d: $(udevadm info "$d" | grep -E 'ID_VENDOR_ID|ID_MODEL_ID' | tr '\n' ' ')"
done
```

| Device | VID:PID | Bridge | Baud | Role |
|---|---|---|---|---|
| Anycubic i3 Mega | `1a86:7523` | CH340 | 115200 | gantry (G-code) |
| DLAB dPette | `10c4:ea60` | CP2102 | 9600 | pipette (6-byte protocol) |

## Workspace constraints

- The dPette **must be hard-mounted** to the X-carriage so its tip moves
  with the gantry. v0 assumes a mount exists; the design is on the
  backlog (see [AGENT_REQUESTS.md](../AGENT_REQUESTS.md)).
- The extruder (hot-end and bed thermistors) is unused. Leave the heater
  cable disconnected and **do not preheat**. Stage 1 firmware patches to
  disable thermal-runaway on E0 are deferred — for now stock Marlin's
  thermal-runaway routine will trigger if the bed/hot-end thermistors
  are unplugged. Either keep them dummy-plugged or send `M302 P1`
  (cold-extrusion override) before motion.
- Tip racks and well plates live on the bed. Tape them down with
  removable tape; the bed surface is the deck origin.
- Soft limits are not enforced in software (deferred). Treat any
  hardcoded coordinate as untrusted.

## Next steps

Once the topology is wired up:

1. Run [`python examples/preflight.py`](../examples/preflight.py) to confirm
   firmware versions and port mapping.
2. Calibrate well-A1 origin: see [`calibration.md`](calibration.md).
3. Run [`python examples/showcase_v0_pipette_sim.py`](../examples/showcase_v0_pipette_sim.py) — the
   end-to-end aspirate/dispense demo.
