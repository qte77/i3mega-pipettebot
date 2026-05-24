"""Device-discovery substrate: M115-based firmware identification.

Pure data + parser layer. No I/O beyond `discover()`, which opens a serial
port to elicit an `M115` reply. Every other function is pure-Python and
testable without hardware.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pipettebot.gantry import GcodeGantry, open_gcode_port, send_and_wait_for_ok

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

# Single env var operators set to point at the gantry's USB-serial path.
# Resolved by `resolve_port()`. Used uniformly by every example, tool, and
# discover-driven helper; printer model is identified by `discover()`, not
# by which env var was set.
PRINTER_PORT_ENV = "PRINTER_PORT"

# (substring to match in M115 reply, firmware family it identifies).
# Order matters: the first matching fingerprint wins. Keep more-specific
# matches before less-specific ones.
FIRMWARE_FINGERPRINTS: tuple[tuple[str, str], ...] = (
    ("MARLIN", "marlin"),
    ("Marlin", "marlin"),
    ("MACHINE_TYPE:A30", "smartto"),
    ("PROTOCOL_VERSION:V1.0", "smartto"),
)


@dataclass(frozen=True)
class DiscoveredDevice:
    """Pure observation: what the device replied to M115 at what baud.

    No behavior, no policy decisions. `firmware_family` is the result of
    `classify(raw_m115)`; `firmware_version` and `machine_type` are
    extracted whitespace-bounded values of `FIRMWARE_NAME:` and
    `MACHINE_TYPE:` fields (None if absent).
    """

    baud: int
    raw_m115: str
    firmware_family: str
    firmware_version: str | None
    machine_type: str | None


@dataclass(frozen=True)
class FirmwarePolicy:
    """Per-family behavior decisions: how to home, default baud.

    Stable while machine models proliferate. A new printer model running an
    already-known firmware adds zero code; a new firmware family adds one
    entry to `FIRMWARE_POLICIES` plus matching `FIRMWARE_FINGERPRINTS`.

    Port resolution is firmware-agnostic: every operator sets a single
    `PRINTER_PORT` env var (see `resolve_port()`). Per-family port aliases
    were collapsed when the env-var convention was unified.
    """

    family: str
    home_strategy: str
    preferred_baud: int


# Per-firmware policies. The `unknown` entry is the conservative fallback
# returned by `policy_for()` when classification fails — `manual_only`
# homing forbids the gantry layer from calling `G28` blind.
FIRMWARE_POLICIES: tuple[FirmwarePolicy, ...] = (
    FirmwarePolicy(family="marlin", home_strategy="full_g28", preferred_baud=250000),
    FirmwarePolicy(
        family="smartto", home_strategy="xy_then_polled_z", preferred_baud=115200
    ),
    FirmwarePolicy(
        family="unknown", home_strategy="manual_only", preferred_baud=115200
    ),
)


def classify(raw_m115: str) -> str:
    """Return the firmware family inferred from a raw M115 reply.

    Substring-matches each fingerprint in `FIRMWARE_FINGERPRINTS` in order;
    the first hit wins. Returns `"unknown"` if no fingerprint matches —
    callers should fall through to the conservative `unknown` policy.

    Args:
        raw_m115: Concatenated, newline-separated reply lines (no `ok`
            terminator).

    Returns:
        Firmware family identifier (lowercase short name).
    """
    for fingerprint, family in FIRMWARE_FINGERPRINTS:
        if fingerprint in raw_m115:
            return family
    return "unknown"


def _extract(raw: str, key: str) -> str | None:
    """Pull `key:VALUE` from `raw` (VALUE = next whitespace-bounded token)."""
    match = re.search(rf"\b{re.escape(key)}:(\S+)", raw)
    return match.group(1) if match else None


def parse_m115(raw: str, baud: int) -> DiscoveredDevice:
    """Parse an M115 reply body into a DiscoveredDevice observation.

    Pure function — no I/O. Extracts whitespace-bounded values of
    `FIRMWARE_NAME:` and `MACHINE_TYPE:` if present, classifies firmware
    family via `classify()`, and packages everything with the supplied
    `baud`.

    Args:
        raw: Joined-line text body of an M115 reply (no `ok` terminator).
        baud: Baud rate at which the reply was received.

    Returns:
        Observation snapshot suitable for `policy_for()` lookup.
    """
    return DiscoveredDevice(
        baud=baud,
        raw_m115=raw,
        firmware_family=classify(raw),
        firmware_version=_extract(raw, "FIRMWARE_NAME"),
        machine_type=_extract(raw, "MACHINE_TYPE"),
    )


def policy_for(device: DiscoveredDevice) -> FirmwarePolicy:
    """Return the FirmwarePolicy matching `device.firmware_family`.

    Falls back to the `unknown` policy (conservative `manual_only` homing)
    when no registered policy matches the observed firmware family.

    Args:
        device: Observation from `parse_m115()`.

    Returns:
        The matching policy, or the `unknown` fallback.
    """
    for policy in FIRMWARE_POLICIES:
        if policy.family == device.firmware_family:
            return policy
    return next(p for p in FIRMWARE_POLICIES if p.family == "unknown")


def resolve_port(env: Mapping[str, str] | None = None) -> str | None:
    """Return the operator's `PRINTER_PORT` env value, or None if unset.

    Args:
        env: Mapping to read from. Defaults to `os.environ` so operators can
            use the usual shell-export workflow.

    Returns:
        The port string if `PRINTER_PORT` is set and non-empty, else None.
    """
    source = env if env is not None else os.environ
    value = source.get(PRINTER_PORT_ENV)
    return value if value else None


# Polled-descent parameters for `xy_then_polled_z`. Defaults match the
# `docs/research/gantry-firmware-alternatives.md` recipe — 1 mm steps at
# 300 mm/min (5 mm/s) is slow enough for the inductive z_min sensor to
# trigger cleanly without overshoot. `MAX_STEPS` caps the descent at
# 250 mm — the A30's full Z travel — so a missing sensor raises rather
# than dives forever.
_POLLED_Z_STEP_MM = 1.0
_POLLED_Z_FEEDRATE = 300
_POLLED_Z_MAX_STEPS = 250
# After the descent burst (many G1/M400/M119 round-trips) Smartto sometimes
# needs a beat before it can process the next command. Without this, the
# final G92 Z0 reliably throws "device reports readiness to read but
# returned no data" on the live A30.
_POLLED_Z_SETTLE_S = 1.0
# Case-insensitive, whitespace-tolerant match for the Z-min "triggered" state.
# Catches Smartto's `z_min:TRIGGERED`, Marlin's `Z_min: TRIGGERED`, and the
# `z min :triggered` variants observed in the wild on different firmware
# builds. Substring match was too brittle — see PR #157 hardware notes.
_Z_MIN_TRIGGERED_RE = re.compile(r"z[_\s-]?min\s*:\s*triggered", re.IGNORECASE)


def _read_z_min_triggered(gantry: GcodeGantry) -> bool:
    """Return True if `M119` reports a triggered Z-min endstop.

    Sends `M119` and applies `_Z_MIN_TRIGGERED_RE` to every reply line.
    Smartto emits a single status line + `ok`; Marlin emits one line per
    endstop. The regex tolerates case + separator variation so both pass
    without per-firmware branching.
    """
    return any(_Z_MIN_TRIGGERED_RE.search(line) for line in gantry.query("M119"))


def _read_m119_raw(gantry: GcodeGantry) -> list[str]:
    """Return every `M119` reply line (terminating `ok` included).

    Used on polled-Z descent failure to surface what the firmware
    actually said — most descent failures are parser misses (token
    casing / spacing) rather than physical sensor issues.
    """
    return gantry.query("M119")


def safe_home(
    gantry: GcodeGantry,
    policy: FirmwarePolicy,
    *,
    z_min_triggered: Callable[[GcodeGantry], bool] = _read_z_min_triggered,
    max_steps: int = _POLLED_Z_MAX_STEPS,
    step_mm: float = _POLLED_Z_STEP_MM,
    feedrate: int = _POLLED_Z_FEEDRATE,
) -> None:
    """Home `gantry` per `policy.home_strategy`.

    Branches on the policy's home strategy:

    - `full_g28`: sends `G28`. Suitable for Marlin with working Z endstop.
    - `xy_then_polled_z`: sends `G28 X Y`, then drives Z down `step_mm`
      mm at a time at `feedrate` mm/min, polling `z_min_triggered` after
      each step. Stops when triggered, declares `G92 Z0`. Required on
      Smartto/A30 builds where firmware `G28 Z` dives indefinitely
      (probe-pin variant ignores the working `z_min` switch). The
      operator-jog path it replaced was unworkable on stepper-energized
      leadscrew Z axes — see
      `docs/research/gantry-firmware-alternatives.md`.
    - `manual_only`: raises. Unknown firmware: the caller must home by
      hand and set origin via direct G-code, not via `safe_home`.

    Args:
        gantry: Live `GcodeGantry` bound to an open serial port.
        policy: From `policy_for(discover(port))`.
        z_min_triggered: Sensor probe. Default sends `M119` and matches
            `z_min:TRIGGERED` in the reply. Inject a fake for tests or
            to read a different endstop pin.
        max_steps: Descent ceiling for `xy_then_polled_z` — raises if
            the sensor doesn't trigger within `max_steps * step_mm` mm.
            Default 250 (one full A30 Z travel).
        step_mm: Per-step descent distance (mm). Default 1.0.
        feedrate: Z descent feedrate (mm/min). Default 300.

    Raises:
        RuntimeError: if `policy.home_strategy` is `manual_only`,
            unhandled, or if polled descent exceeds `max_steps` without
            triggering the sensor.
    """
    if policy.home_strategy == "full_g28":
        gantry.home()
        return
    if policy.home_strategy == "xy_then_polled_z":
        _polled_z_home(
            gantry,
            z_min_triggered=z_min_triggered,
            max_steps=max_steps,
            step_mm=step_mm,
            feedrate=feedrate,
        )
        return
    raise RuntimeError(
        f"home strategy {policy.home_strategy!r} (firmware family "
        f"{policy.family!r}) requires manual operator action; safe_home "
        "cannot proceed. Home and set origin via tools/gantry_repl.py."
    )


def _polled_z_home(
    gantry: GcodeGantry,
    *,
    z_min_triggered: Callable[[GcodeGantry], bool],
    max_steps: int,
    step_mm: float,
    feedrate: int,
) -> None:
    """G28 X Y, descend Z in steps until z_min triggers, declare G92 Z0.

    Soft endstops bypassed via `G92 Z<max_travel>` rather than `M211 S0`:
    after `G28 X Y` the firmware's Z reference is uninitialized; declaring
    current Z as `max_steps * step_mm` puts the entire descent in
    positive-Z territory (249, 248, ..., 0), so soft endstops never
    engage. This is firmware-independent — Smartto's `M211` support is
    unconfirmed and the firmware silently accepts unsupported commands.
    Origin is redeclared via `G92 Z0` at the sensor trigger point.
    """
    gantry.send("G28 X Y")
    if z_min_triggered(gantry):
        gantry.send("G92 Z0")
        return
    # Declare current Z as max_travel so the descent loop stays positive
    # (Z=max_travel down to Z=0). Soft endstops, if active, do not engage.
    max_travel = max_steps * step_mm
    gantry.send(f"G92 Z{max_travel:.3f}")
    gantry.send("G91")  # relative
    triggered = False
    try:
        for _ in range(max_steps):
            gantry.send(f"G1 Z-{step_mm:.3f} F{feedrate}")
            gantry.wait_for_moves()
            if z_min_triggered(gantry):
                triggered = True
                break
    finally:
        gantry.send("G90")  # restore absolute regardless of outcome
        if triggered:
            # The descent's M119/M400 burst leaves stale received bytes in
            # the OS serial buffer; pyserial's select() then false-reports
            # data-ready against empty data, throwing SerialException on the
            # next read. Drop those bytes before the origin declaration.
            # The settle sleep gives the firmware time to be ready too.
            gantry.flush_input()
            time.sleep(_POLLED_Z_SETTLE_S)
            try:
                gantry.send("G92 Z0")
            except OSError as e:
                # OSError covers serial.SerialException (subclass of
                # IOError = OSError). Z is at the sensor trigger right
                # now — re-running this script will short-circuit on the
                # pre-loop M119 check and declare origin without descending.
                raise RuntimeError(
                    "polled Z home: descent SUCCEEDED — carriage is at "
                    "the sensor trigger point — but the final G92 Z0 "
                    f"failed with a serial-level error: {e}. The firmware "
                    "is in an inconsistent state where it thinks Z is "
                    f"near {max_travel * 1.0:.0f} mm rather than 0. "
                    "Recovery: re-run this same script — the pre-loop "
                    "M119 check will see TRIGGERED and declare G92 Z0 "
                    "from a fresh serial connection."
                ) from e
    if not triggered:
        # Capture both endstop state AND firmware-recorded position so the
        # operator can tell whether Z motion was rejected (M114 Z unchanged
        # = blocked) vs. Z moved but missed the sensor (M114 Z changed).
        last_m119 = _read_m119_raw(gantry)
        last_m114 = gantry.query("M114")
        raise RuntimeError(
            f"polled Z home: z_min did not trigger within "
            f"{max_steps * step_mm:.1f} mm of descent. Last M119 reply: "
            f"{last_m119!r}. Last M114 reply: {last_m114!r}. Diagnostic: "
            "(a) if M114 Z is near 0 (descent's endpoint), Z motion DID "
            "happen but the carriage missed the sensor — likely started "
            "below the trigger zone; ascend via tools/gantry_repl.py and "
            f"retry. (b) if M114 Z is near {max_travel:.0f} (descent's "
            "start), Z motion was REJECTED by firmware — try M17 to "
            "energize steppers, or verify Z mechanics via the REPL."
        )


_DEFAULT_BAUDS: tuple[int, ...] = (115200, 250000, 57600, 9600)
_BOOT_WAIT_S = 2.5
_M115_READ_WINDOW_S = 4.0


def discover(
    port: str,
    bauds: tuple[int, ...] = _DEFAULT_BAUDS,
    *,
    boot_wait_s: float = _BOOT_WAIT_S,
) -> DiscoveredDevice | None:
    """Open `port` at each baud, send M115, return the first observation.

    Iterates `bauds` in order. For each baud: open, wait for firmware boot,
    flush input, send `M115`, wait up to `_M115_READ_WINDOW_S` for `ok`.
    The first baud that elicits any reply yields a DiscoveredDevice (even
    if firmware classification falls through to `"unknown"` — operators
    benefit from seeing what the device actually said).

    Args:
        port: USB-serial path (e.g. `/dev/ttyUSB0`).
        bauds: Baud rates to try, in order.
        boot_wait_s: Seconds to sleep after open before sending M115 (for
            STM32 / DTR-reset boards). Pass 0 to skip in tests.

    Returns:
        DiscoveredDevice observation, or None if every baud opened silent.
    """
    for baud in bauds:
        link = open_gcode_port(port, baudrate=baud, timeout=1.0)
        if link is None:
            continue
        try:
            if boot_wait_s > 0:
                time.sleep(boot_wait_s)
            link.reset_input_buffer()
            try:
                lines = send_and_wait_for_ok(link, "M115", max_secs=_M115_READ_WINDOW_S)
            except TimeoutError:
                continue
            raw = "\n".join(lines[:-1])  # drop trailing `ok`
            return parse_m115(raw, baud=baud)
        finally:
            link.close()
    return None
