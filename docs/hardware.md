---
title: "Hardware setup"
status: "DRAFT"
updated: "2026-05-17"
owner: "qte77"
---

This guide covers the **physical and electrical setup** of an Anycubic
i3 Mega chassis (stripped to a 3-axis motion platform — see "Workspace
constraints" below) and a DLAB dPette electronic pipette so the v0 demo
(`examples/showcase_v0_i3_pipette_sim.py`) can run end-to-end. Software
install is covered in the [README](../README.md) and contributor setup
in [CONTRIBUTING](../CONTRIBUTING.md).

## Topology

Two USB cables, one to the printer and one to the pipette:

```text
PC ──USB-B──► Anycubic i3 Mega   (Trigorilla, ATmega2560, Marlin) /dev/tty?  250000 8N1
PC ──CP2102──► DLAB dPette                                         /dev/tty?  9600 8N1
```

The PC is the orchestrator. Marlin executes G-code; the dPette executes
6-byte serial commands via [`dpette-usb-driver`](https://github.com/Lambda-Biolab/dpette-usb-driver). They never talk to each
other directly in v0.

## Anycubic i3 Mega

| Item | Value |
|---|---|
| Mainboard | Trigorilla 0.0.4 (ATmega2560 + A4988 drivers, stock) |
| Firmware | Anycubic stock Marlin 1.4.x **or** upstream Marlin 2.x **or** community MARLIN-AI3M |
| USB bridge chip | CH340 *(older boards)* **or** CP2102N *(newer batches and many MARLIN-AI3M-flashed units)* |
| VID:PID | `1a86:7523` (CH340) **or** `10c4:ea60` (CP2102N) |
| Baud | 250000 8N1 (Anycubic stock and MARLIN-AI3M); some custom builds use 115200 |
| Connector | USB-B on the LCD/board housing |

> The dPette also uses a Silicon Labs CP210x at `10c4:ea60` (see below). On
> a CP2102N-equipped i3 Mega the two devices share VID:PID, so you cannot
> tell them apart by descriptor alone — fall back on the chip's serial
> number, or use the `M115` probe in [Distinguishing the two ports](#distinguishing-the-two-ports).

We use **stock Marlin without modifications** in v0. The G-code surface we
need is small: `G28`, `G1`, `M114`, `M115`, `M400`. Both 1.4.x and 2.x
support all of these.

For project provenance, fork lineage, license posture, and OSS
alternatives to the Marlin/slicer stack, see
[`research-oss-toolchain.md`](research-oss-toolchain.md).

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
[`tools/preflight.py`](../tools/preflight.py) script does this for
you; manually it looks like:

```bash
# Replace /dev/ttyUSB0 with your printer port
stty -F /dev/ttyUSB0 250000 raw
printf 'M115\n' > /dev/ttyUSB0 && timeout 2 cat /dev/ttyUSB0
# Expected first line: FIRMWARE_NAME:Marlin 1.1.X (Anycubic Mega ...) ...
```

## DLAB dPette / dPette+

The pipette's USB cable terminates in a Silicon Labs CP2102 USB-UART
bridge. Full protocol details — including the standby/connectable
button-press quirk and the 6-byte packet format — are in
[`dpette-usb-driver/docs/HARDWARE.md`](https://github.com/Lambda-Biolab/dpette-usb-driver/blob/main/docs/HARDWARE.md).

### USB connection

| Item | Value |
|---|---|
| USB bridge chip | CP2102 |
| VID:PID | `10c4:ea60` |
| Baud | 9600 8N1 |
| Driver | `cp210x` (built into Linux kernel; native on macOS) |

### Product variants

DLAB ships two pipette families that share the same 6-byte protocol:

| Variant | Channels | Use |
|---|---|---|
| dPette / dPette 7016 | 1 | Single-channel — well-by-well dispensing |
| **dPette+ multi-channel** | 8 or 12 | Parallel dispensing across a row at SBS 9 mm pitch |

The qte77 v0 setup targets the **8-channel dPette+**.

### dPette+ 8-channel specs

| Item | Value | Source |
|---|---|---|
| Volume ranges (programmable) | 0.5–10 µL, 5–50 µL, 15–300 µL, 30–300 µL | [DLAB product page](https://www.dlabsci.com/product/en/dpette-multi-functional-8-channel-electronic-pipette) |
| Channel pitch | 9.0 mm (SBS 96-well) | SBS / ANSI-SLAS 2004-1 |
| Operating modes | aspirate/dispense, continuous mixing, continuous distribution, dilution | DLAB product page |
| Display | LCD with dual rotary knobs | DLAB product page |
| Charging | USB or charging stand | DLAB product page |
| Top-section rotation | 360° (relieves cabling stress when mounted) | DLAB product page |
| Body height (tip → top of ejector) | **~230 mm** | measured on the unit |
| Mass (no tips) | **~250 g** | measured on the unit |
| Body geometry — clamp candidates | upper barrel: Ø ~27 mm round; lower body: 75 × 16 mm rectangular | measured on the unit |
| Tip extension when mounted | ~50 mm (300 µL standard tip) | conventional pipette tip length |
| Total length with tips mounted | **~280 mm** | derived |

The 250 g pipette is the dominant fraction of the carriage payload
budget. Canonical rule (`mount + pipette + tips < 300 g`) and the
mount-design rationale live in [`3d-parts.md`](3d-parts.md).

### Wake the pipette before connecting

The dPette has two states:

1. **Standby** — screen dim or off. Serial connect will time out.
2. **Connectable** — press the operation button. Screen shows volume/mode.

The driver handshake (`A0 HELLO` via `DPetteDriver.connect()`) only
succeeds in state 2. If `preflight.py` reports a handshake timeout,
press the dPette's button and retry.

## Distinguishing the two ports

When both the printer and the pipette are plugged in, your `/dev/tty*`
list has two entries. You disambiguate them by USB VID:PID **when the
bridges differ** (CH340 i3 Mega + CP2102 dPette), or by **probing with
`M115`** when they match (CP2102N i3 Mega + CP2102 dPette — same
VID:PID `10c4:ea60`).

```bash
for d in /dev/ttyUSB*; do
  echo "$d: $(udevadm info "$d" | grep -E 'ID_VENDOR_ID|ID_MODEL_ID|ID_SERIAL_SHORT' | tr '\n' ' ')"
done
```

| Device | VID:PID | Bridge | Baud | Role |
|---|---|---|---|---|
| Anycubic i3 Mega (older) | `1a86:7523` | CH340 | 250000 | gantry (G-code) |
| Anycubic i3 Mega (newer / MARLIN-AI3M) | `10c4:ea60` | CP2102N | 250000 | gantry (G-code) |
| DLAB dPette | `10c4:ea60` | CP2102 | 9600 | pipette (6-byte protocol) |

### Tiebreaker when both ports are CP210x

`tools/preflight.py` already handles this: it probes each candidate
port for Marlin (`M115` @ 250000) first, then dPette (`A0` HELLO @ 9600).
Manually:

```bash
for d in /dev/ttyUSB* /dev/cu.usbserial-* /dev/cu.wchusbserial*; do
  [ -e "$d" ] || continue
  stty -F "$d" 250000 raw 2>/dev/null || continue
  printf 'M115\n' > "$d"
  reply=$(timeout 2 head -c 200 "$d")
  case "$reply" in
    *FIRMWARE_NAME:Marlin*) echo "$d → i3 Mega" ;;
    *) echo "$d → not Marlin (probably dPette)" ;;
  esac
done
```

## Workspace constraints

- The print head, hotend, fan, sensor PCB, and heater wiring have been
  **physically removed** from the carriage. The bare carriage face is
  the mounting surface for the dPette mount (see [`3d-parts.md`](3d-parts.md)).
  The i3 Mega is no longer a 3D printer — it is a 3-axis motion
  platform.
- The dPette mount design is tracked in
  [#40](https://github.com/qte77/i3mega-pipettebot/issues/40)
  (carriage measurement) and
  [#41](https://github.com/qte77/i3mega-pipettebot/issues/41)
  (barrel-bore module).
- Tip racks and well plates live on the moving bed (i3 Mega is a
  bed-slinger: bed = Y axis). Tape them down with removable tape; the
  bed surface is the deck origin.
- Stock Marlin will still try to monitor the absent hotend/bed
  thermistors. Either keep dummy thermistors plugged in **or** send
  `M302 P1` (cold-extrusion override) before motion to suppress
  thermal-runaway aborts. A Stage 1 firmware patch to disable thermal
  monitoring is deferred (see AGENT_REQUESTS.md).
- Soft limits are not enforced in software (deferred). Treat any
  hardcoded coordinate as untrusted.

## Next steps

Once the topology is wired up:

1. Run [`python tools/preflight.py`](../tools/preflight.py) to confirm
   firmware versions and port mapping.
2. Calibrate well-A1 origin: see [`calibration.md`](calibration.md).
3. Run [`python examples/showcase_v0_i3_pipette_sim.py`](../examples/showcase_v0_i3_pipette_sim.py) — the
   end-to-end aspirate/dispense demo.
