"""PipetteBot: verify move-then-pipette ordering with M400 between."""

from __future__ import annotations

from pipettebot.bot import PipetteBot
from pipettebot.gantry import GantryConfig, GcodeGantry
from tests.conftest import FakePipette, FakeSerial


def _bot(fake_serial: FakeSerial, fake_pipette: FakePipette) -> PipetteBot:
    gantry = GcodeGantry(GantryConfig(port="/dev/null"), fake_serial)
    return PipetteBot(gantry, fake_pipette)


def test_aspirate_at_orders_move_wait_aspirate(
    fake_serial: FakeSerial, fake_pipette: FakePipette
) -> None:
    _bot(fake_serial, fake_pipette).aspirate_at(100.0, 100.0, 5.0, volume_ul=200.0)
    assert fake_serial.written == [
        b"G1 X100.000 Y100.000 Z5.000 F3000\n",
        b"M400\n",
    ]
    assert fake_pipette.aspirated == [200.0]
    assert fake_pipette.dispensed == []


def test_dispense_at_orders_move_wait_dispense(
    fake_serial: FakeSerial, fake_pipette: FakePipette
) -> None:
    _bot(fake_serial, fake_pipette).dispense_at(100.0, 110.0, 5.0)
    assert fake_serial.written == [
        b"G1 X100.000 Y110.000 Z5.000 F3000\n",
        b"M400\n",
    ]
    assert fake_pipette.dispensed == [0.0]


def test_home_sends_g28_then_m400(
    fake_serial: FakeSerial, fake_pipette: FakePipette
) -> None:
    _bot(fake_serial, fake_pipette).home()
    assert fake_serial.written == [b"G28\n", b"M400\n"]
