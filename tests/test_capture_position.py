"""Tests for `pipettebot-capture-position` CLI.

Skipped entirely when the optional `[orchestrator]` extra (so101) isn't installed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("so101")

import yaml

from pipettebot.so101.capture_position import (
    _format_joints_as_yaml_line,
    capture,
)


@pytest.fixture(autouse=True)
def _stub_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SO101_STUB_MODE", "1")


class TestFormatJointsAsYamlLine:
    def test_formats_six_floats_with_four_decimals(self) -> None:
        assert (
            _format_joints_as_yaml_line(
                "demo_pickup_approach", [1.0, -2.5, 3.0, 0.0, 0.0, 0.5]
            )
            == "  demo_pickup_approach: [1.0000, -2.5000, 3.0000, 0.0000, 0.0000, 0.5000]"
        )

    def test_formats_empty_joints_list(self) -> None:
        assert _format_joints_as_yaml_line("foo", []) == "  foo: []"


class TestCapture:
    @pytest.fixture
    def arms_yaml(self, tmp_path: Path) -> Path:
        cfg = {
            "arm_a": {"arm_id": "arm_a", "port": "/dev/null", "role": "follower"},
            "arm_b": {"arm_id": "arm_b", "port": "/dev/null", "role": "follower"},
            "positions": {"park": [0.0, -45.0, -90.0, 0.0, 0.0, 0.0]},
        }
        path = tmp_path / "arms.yaml"
        path.write_text(yaml.dump(cfg))
        return path

    def test_returns_yaml_paste_line_under_stub(self, arms_yaml: Path) -> None:
        line = capture(str(arms_yaml), "arm_a", "demo_pickup_approach")
        assert line == "  demo_pickup_approach: []"
