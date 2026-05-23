"""CLI contract tests for tools/preflight.py — in-process, no real serial."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

from pipettebot.devices import DiscoveredDevice

if TYPE_CHECKING:
    import pytest

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
    for var in ("I3MEGA_PORT", "SMARTTO_PORT", "GANTRY_PORT", "PIPETTE_PORT"):
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


def test_preflight_export_emits_marlin_var_when_marlin_detected(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setattr(preflight, "discover_ports", lambda: ["/dev/ttyUSB0"])
    monkeypatch.setattr(
        preflight,
        "discover",
        lambda port, **_kw: _make_device("marlin", 250000, "Anycubic_i3_Mega"),
    )
    monkeypatch.setattr(
        preflight, "_resolve_dpette_with_retry", lambda *_a, **_kw: (None, None)
    )
    monkeypatch.setattr("sys.argv", ["preflight.py", "--export"])

    rc = preflight.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "export I3MEGA_PORT=/dev/ttyUSB0" in out


def test_preflight_export_emits_smartto_var_when_a30_detected(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setattr(preflight, "discover_ports", lambda: ["/dev/ttyUSB0"])
    monkeypatch.setattr(
        preflight,
        "discover",
        lambda port, **_kw: _make_device("smartto", 115200, "A30"),
    )
    monkeypatch.setattr(
        preflight, "_resolve_dpette_with_retry", lambda *_a, **_kw: (None, None)
    )
    monkeypatch.setattr("sys.argv", ["preflight.py", "--export"])

    rc = preflight.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "export SMARTTO_PORT=/dev/ttyUSB0" in out


def test_preflight_export_emits_gantry_port_for_unknown_family(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setattr(preflight, "discover_ports", lambda: ["/dev/ttyUSB0"])
    monkeypatch.setattr(
        preflight,
        "discover",
        lambda port, **_kw: _make_device("unknown", 115200, "Voron2.4"),
    )
    monkeypatch.setattr(
        preflight, "_resolve_dpette_with_retry", lambda *_a, **_kw: (None, None)
    )
    monkeypatch.setattr("sys.argv", ["preflight.py", "--export"])

    rc = preflight.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "export GANTRY_PORT=/dev/ttyUSB0" in out
