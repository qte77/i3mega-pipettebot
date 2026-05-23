"""CLI contract tests for tools/gantry_repl.py — in-process, no real serial."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

from pipettebot.devices import DiscoveredDevice

if TYPE_CHECKING:
    import pytest

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"


def _import_gantry_repl():
    spec = importlib.util.spec_from_file_location(
        "gantry_repl", TOOLS_DIR / "gantry_repl.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gantry_repl = _import_gantry_repl()


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("GANTRY_PORT", "I3MEGA_PORT", "SMARTTO_PORT", "BAUD"):
        monkeypatch.delenv(var, raising=False)


def test_gantry_repl_exits_1_when_port_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_env(monkeypatch)
    rc = gantry_repl.main(argv=[])
    assert rc == 1
    err = capsys.readouterr().err
    assert "GANTRY_PORT" in err or "SMARTTO_PORT" in err or "I3MEGA_PORT" in err


def test_select_cheat_sheet_for_marlin_returns_marlin_content() -> None:
    sheet = gantry_repl.select_cheat_sheet("marlin")
    assert "Marlin" in sheet
    assert "M115" in sheet


def test_select_cheat_sheet_for_smartto_returns_smartto_content() -> None:
    sheet = gantry_repl.select_cheat_sheet("smartto")
    assert "Smartto" in sheet or "smartto" in sheet
    assert "G28 Z" in sheet  # the known-broken caveat must be visible


def test_select_cheat_sheet_for_unknown_returns_generic_content() -> None:
    sheet = gantry_repl.select_cheat_sheet("unknown")
    assert "M115" in sheet  # generic still mentions the identity command


def test_select_cheat_sheet_for_unrecognised_family_falls_back_to_generic() -> None:
    sheet = gantry_repl.select_cheat_sheet("klipper")
    assert sheet == gantry_repl.GENERIC_CHEAT_SHEET


def test_gantry_repl_device_flag_overrides_autodetect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--device smartto must skip discover() entirely."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("GANTRY_PORT", "/dev/null")
    discover_calls: list[str] = []

    def _discover_spy(port: str, *args: object, **kwargs: object) -> DiscoveredDevice:
        _ = args, kwargs
        discover_calls.append(port)
        msg = "discover() must not be called when --device is set"
        raise AssertionError(msg)

    monkeypatch.setattr(gantry_repl, "discover", _discover_spy)
    monkeypatch.setattr(gantry_repl, "open_marlin_port", lambda *_a, **_kw: None)

    rc = gantry_repl.main(argv=["--device", "smartto"])
    # open_marlin_port returns None -> exits 1 before any REPL loop; discover
    # must still not have been invoked.
    assert rc == 1
    assert discover_calls == []
