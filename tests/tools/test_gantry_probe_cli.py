"""CLI contract tests for tools/gantry_probe.py — in-process, no real serial."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

    from tests.conftest import FakeSerial

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"


def _import_gantry_probe():
    spec = importlib.util.spec_from_file_location(
        "gantry_probe", TOOLS_DIR / "gantry_probe.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gantry_probe = _import_gantry_probe()


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("GANTRY_PORT", "I3MEGA_PORT", "SMARTTO_PORT"):
        monkeypatch.delenv(var, raising=False)


def test_gantry_probe_exits_1_when_port_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_env(monkeypatch)
    rc = gantry_probe.main()
    assert rc == 1
    err = capsys.readouterr().err
    assert "PORT" in err


def test_gantry_probe_candidate_count_is_9() -> None:
    """9 = the original 6 plus M220, M211, M85 (per the plan)."""
    assert len(gantry_probe.PROBE_CANDIDATES) == 9


def test_gantry_probe_candidates_include_motion_lever_and_idle_timeout() -> None:
    cmds = [cmd for cmd, _desc, _secs in gantry_probe.PROBE_CANDIDATES]
    for needle in ("M220", "M211", "M85"):
        assert any(needle in c for c in cmds), f"missing {needle} in candidates"


def test_gantry_probe_send_refuses_banned_motion_commands(
    fake_serial: FakeSerial,
) -> None:
    """_send must hard-refuse G0/G1/G28/G92/M84/M18/M500/etc."""
    import pytest

    for banned in ("G0 X10", "G1 Y5", "G28", "G29", "G30", "G92 Z0", "M84", "M500"):
        with pytest.raises(RuntimeError, match="refusing banned"):
            gantry_probe._send(fake_serial, banned)


def test_gantry_probe_quirks_for_smartto_mention_m503_noop() -> None:
    smartto_quirks = gantry_probe.QUIRKS["smartto"]
    assert "M503" in smartto_quirks


def test_gantry_probe_quirks_for_marlin_exist() -> None:
    # A marlin-specific quirks blurb should exist (even if short).
    assert "marlin" in gantry_probe.QUIRKS
    assert gantry_probe.QUIRKS["marlin"]
