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

from pipettebot.gantry import open_gcode_port, send_and_wait_for_ok

if TYPE_CHECKING:
    from collections.abc import Mapping

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
    """Per-family behavior decisions: how to home, port aliases, default baud.

    Stable while machine models proliferate. A new printer model running an
    already-known firmware adds zero code; a new firmware family adds one
    entry to `FIRMWARE_POLICIES` plus matching `FIRMWARE_FINGERPRINTS`.
    """

    family: str
    home_strategy: str
    preferred_baud: int
    port_env_aliases: tuple[str, ...]


# Per-firmware policies. The `unknown` entry is the conservative fallback
# returned by `policy_for()` when classification fails — `manual_only`
# homing forbids the gantry layer from calling `G28` blind.
FIRMWARE_POLICIES: tuple[FirmwarePolicy, ...] = (
    FirmwarePolicy(
        family="marlin",
        home_strategy="full_g28",
        preferred_baud=250000,
        port_env_aliases=("I3MEGA_PORT", "GANTRY_PORT"),
    ),
    FirmwarePolicy(
        family="smartto",
        home_strategy="xy_then_polled_z",
        preferred_baud=115200,
        port_env_aliases=("SMARTTO_PORT", "GANTRY_PORT"),
    ),
    FirmwarePolicy(
        family="unknown",
        home_strategy="manual_only",
        preferred_baud=115200,
        port_env_aliases=("GANTRY_PORT",),
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


def resolve_port(
    policy: FirmwarePolicy, env: Mapping[str, str] | None = None
) -> str | None:
    """Return the operator's port for `policy`, iterating its env aliases.

    Args:
        policy: The policy whose `port_env_aliases` tuple is searched in
            order; the first set environment variable wins.
        env: Mapping to read from. Defaults to `os.environ` so operators can
            use the usual shell-export workflow.

    Returns:
        The port string if any alias is set, else None.
    """
    source = env if env is not None else os.environ
    for alias in policy.port_env_aliases:
        value = source.get(alias)
        if value:
            return value
    return None


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
