---
title: "SBC-on-printer deployment (Path 2)"
status: "DRAFT"
updated: "2026-05-08"
owner: "lambda biolab"
---

Replace the laptop tether with a small Linux board zip-tied to the
printer chassis. The board acts as USB **host** for both the i3 Mega
and the dPette, runs `pipettebot` directly, and turns the
printer + pipette + board into a single self-contained appliance. No
firmware patch, no soldering, no warranty voided — the dPette and
printer keep their stock cables. You give up host-less SD-card
autonomy (that is **Path 3** — `M820` UART tap, see
[`AGENT_REQUESTS.md`](../AGENT_REQUESTS.md)).

> **Status: Draft.** No physical Pi has been bolted to the reference
> i3 Mega yet. BOM, wiring, and mount design are to be confirmed when
> the first unit is built.

## Why this exists

Path 1 (laptop-as-host) is fine for development but ties a $1k+
machine to a benchtop while a $300 robot runs. The dPette and the
i3 Mega are both USB **devices** — they cannot be wired directly to
each other (see [`hardware.md`](hardware.md) and
[issue #18](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/18)).
The cheapest USB host that runs `pipettebot` is a Raspberry Pi Zero
2 W; mounting one to the printer removes the laptop without changing
any cabling on either device.

## Architecture

```text
                                  ┌─ USB-A ──cable──► i3 Mega USB-B (Marlin/Trigorilla)
   Pi Zero 2 W       (host)───────┤
   (zip-tied to                   │
    printer chassis,              └─ USB-A ──cable──► dPette microUSB
    powered by                       (existing dPette cable, unchanged)
    printer 5 V rail
    or own 5 V brick)

   Pi runs pipettebot      ──┐
                             ├──► same `examples/showcase_v0_pipette_sim.py` workflow
                             │    as today, just on the Pi
   SSH from laptop / VS      │
   Code Remote-SSH for       │
   editing & control         │
                             ┘
```

`pipettebot` doesn't change. The Pi sees two `/dev/ttyUSB*` (or
`/dev/serial/by-id/*`) devices — one for the printer, one for the
pipette — exactly like the laptop sees `/dev/cu.*` today.

## BOM

| Item | Approx. cost | Notes |
|---|---|---|
| Raspberry Pi Zero 2 W | $15 | Has one micro-USB OTG data port. Pi 4 / Pi 5 work too if you want more headroom (~$45). |
| microSD card, 16-32 GB, A1 class | $6 | Boot drive. SanDisk / Samsung; avoid no-brand. |
| USB-A OTG adapter, micro-USB → USB-A female | $3 | Pi Zero only has microUSB; both peripheral cables are USB-A. Need one OTG adapter and one passive USB hub *or* a Pi 4 with native USB-A. |
| Powered USB hub (2-port minimum) | $8 | Only if using Pi Zero 2 W and you want both peripherals plus a margin. The Pi Zero supplies limited 5 V — a powered hub avoids brownouts when both serial bridges enumerate. |
| Pi 5 V power supply, 2.5 A | $7 | Or piggyback off the printer's PSU 5 V rail through a buck regulator (riskier; document if you go that route). |
| 3D-printed mount | free (PETG/PLA) | Bolts to a frame extrusion or zip-ties to the chassis. STL placeholder, see backlog. |
| Zip ties / Velcro | $1 | v0 mount. |

Total: **~$25-40** depending on Pi model and whether you reuse cables/PSU you already have.

## Pi software setup (headless, no monitor)

This is a one-time bring-up. After this the Pi runs unattended.

1. **Flash Raspberry Pi OS Lite (64-bit)** to the SD card with
   `rpi-imager`. In the imager's "advanced settings":
    - set hostname (e.g. `pipettebot-01`)
    - enable SSH with public-key auth (paste your laptop's
      `~/.ssh/id_ed25519.pub`)
    - configure Wi-Fi SSID + password
    - set locale / keyboard

2. Boot the Pi from SD; wait ~60 s for first-boot expansion. SSH in:

    ```bash
    ssh pipettebot-01.local      # or use the IP if mDNS isn't working
    ```

3. **Install uv + Git**:

    ```bash
    sudo apt-get update && sudo apt-get install -y git
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source ~/.bashrc
    ```

4. **Clone and sync**:

    ```bash
    git clone https://github.com/Lambda-Biolab/i3mega-pipettebot.git
    cd i3mega-pipettebot
    make init
    ```

5. **Verify** with the test suite (no hardware needed yet):

    ```bash
    make test       # 9 mocked-serial tests should pass
    ```

## Wiring

1. Mount the Pi to the printer chassis with zip-ties or a 3D-printed
   bracket. Avoid moving parts (X-carriage, bed, leadscrew). Keep it
   away from the heatbed cabling.
2. Plug the **i3 Mega's stock USB cable** (USB-B → USB-A) into the
   Pi's USB-A port (or via OTG adapter on a Pi Zero).
3. Plug the **dPette's stock USB cable** (microUSB → USB-A) into the
   Pi's other USB-A port (or via the powered hub).
4. Power the Pi from a dedicated 5 V brick *or*, if you're confident
   in your PSU, a buck regulator off the printer's 24 V → 5 V rail.

## Identifying the two serial ports on the Pi

On Linux you get `/dev/ttyUSB0` and `/dev/ttyUSB1` (assignment depends
on plug order — unreliable). Use VID:PID and the chip's serial number
to disambiguate, exactly as on the Mac:

```bash
for d in /dev/ttyUSB*; do
  echo -n "$d: "
  udevadm info --query=property "$d" | grep -E '^(ID_VENDOR_ID|ID_MODEL_ID|ID_SERIAL_SHORT)=' | tr '\n' ' '
  echo
done
```

Then export stable paths via `/dev/serial/by-id/` (these don't shuffle
on reboot or replug):

```bash
ls /dev/serial/by-id/
# Expect two entries; one per USB-UART chip serial number
```

Set in your shell profile or systemd unit:

```bash
export I3MEGA_PORT=/dev/serial/by-id/usb-1a86_USB2.0-Serial-...   # or 10c4_CP2102N_<serial>
export PIPETTE_PORT=/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_<serial>
```

(Real-hardware unit at the time of writing has the i3 Mega on a
**CP2102N** with serial `12495223cab7e7119d56ec82d4b43ea0`, not the
CH340 the older docs assume — see
[issue #18](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/18).)

## Running

```bash
cd ~/i3mega-pipettebot
uv run tools/preflight.py
uv run examples/showcase_v0_pipette_sim.py
```

The first command confirms ports + firmware on real hardware; the
second runs the v0 demo unchanged on the Pi.

The Pi orchestrates both devices over USB. The laptop is no longer
required after the initial flash.

### Optional: systemd unit for auto-start

Drop in `/etc/systemd/system/pipettebot.service`:

```ini
[Unit]
Description=pipettebot showcase
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/i3mega-pipettebot
Environment=I3MEGA_PORT=/dev/serial/by-id/...
Environment=PIPETTE_PORT=/dev/serial/by-id/...
ExecStart=/home/pi/.local/bin/uv run examples/showcase_v0_pipette_sim.py
Restart=no

[Install]
WantedBy=multi-user.target
```

Then `sudo systemctl enable --now pipettebot` runs it on boot. For v0
you almost certainly don't want auto-start of physical motion — keep
this disabled and trigger runs manually over SSH until safety
interlocks land (see `safety.py` in
[`AGENT_REQUESTS.md`](../AGENT_REQUESTS.md)).

## What this **doesn't** unlock

- **SD-card autonomy** — Marlin still doesn't know how to talk to the
  dPette. Path 2 just moves the orchestrator from your laptop to the
  Pi. To run a `.gcode` file off the printer's SD card and have it
  pipette, you need **Path 3** (`M820` pass-through, UART tap on the
  dPette, level-shifter PCB, Marlin firmware patch). Tracked in
  [`AGENT_REQUESTS.md`](../AGENT_REQUESTS.md) under "Stage 2a".
- **No PC at all** — you still want a laptop or workstation to SSH in
  for editing, debugging, and triggering runs. The Pi is the
  *runtime* host, not a development environment.
- **Hot-swap dPette** — same standby/connectable button-press quirk
  applies (see [`hardware.md`](hardware.md)). The Pi is just a
  smaller laptop.

## Path from DRAFT to confirmed

Tracking items live in [`AGENT_REQUESTS.md`](../AGENT_REQUESTS.md) under
the **SBC deployment (Path 2)** section.
