"""CLI contract tests for tools/preflight.py — in-process, no real serial."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from pipettebot.devices import DiscoveredDevice

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"


def _import_preflight():
    spec = importlib.util.spec_from_file_location(
        "preflight", TOOLS_DIR / "preflight.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


preflight = _import_preflight()


def _make_device(
    family: str, baud: int, machine: str | None = None
) -> DiscoveredDevice:
    return DiscoveredDevice(
        baud=baud,
        raw_m115=f"FIRMWARE_NAME:fake MACHINE_TYPE:{machine or '?'}",
        firmware_family=family,
        firmware_version="fake",
        machine_type=machine,
    )


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("PRINTER_PORT", "PIPETTE_PORT"):
        monkeypatch.delenv(var, raising=False)


def test_preflight_exits_1_when_no_ports_present(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setattr(preflight, "discover_ports", lambda: [])
    monkeypatch.setattr("sys.argv", ["preflight.py"])

    rc = preflight.main()
    assert rc == 1
    out = capsys.readouterr().out
    assert "No USB-serial" in out


@pytest.mark.parametrize(
    ("family", "baud", "machine"),
    [
        ("marlin", 250000, "Anycubic_i3_Mega"),
        ("smartto", 115200, "A30"),
        ("unknown", 115200, "Voron2.4"),
    ],
)
def test_preflight_export_emits_printer_port_regardless_of_family(
    family: str,
    baud: int,
    machine: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The export-var name is firmware-agnostic after the PRINTER_PORT collapse."""
    _clear_env(monkeypatch)
    monkeypatch.setattr(preflight, "discover_ports", lambda: ["/dev/ttyUSB0"])
    monkeypatch.setattr(
        preflight, "discover", lambda port, **_kw: _make_device(family, baud, machine)
    )
    monkeypatch.setattr(
        preflight, "_resolve_dpette_with_retry", lambda *_a, **_kw: (None, None)
    )
    monkeypatch.setattr("sys.argv", ["preflight.py", "--export"])

    rc = preflight.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "export PRINTER_PORT=/dev/ttyUSB0" in out
