# Pipette delegation

## Never re-encode the dPette protocol

dPette communication is a 6-byte serial protocol with checksum, mode
state machine, and several known-destructive commands (notably
`A5 b2=1`, which causes a permanent Err4). All of this is implemented
once in `dpette-usb-driver`.

**Rule**: this repo imports `dpette.DPetteDriver` and calls its public
methods. It never:

- constructs raw `[0xFE] [CMD] [B2] [B3] [B4] [CHECKSUM]` packets
- writes to the dPette serial port directly
- duplicates the `WorkingMode` / `KeyAction` enum logic

If `dpette` is missing a feature you need, open a PR to
[Lambda-Biolab/dpette-usb-driver](https://github.com/Lambda-Biolab/dpette-usb-driver)
rather than working around it here.

## Tests use a `_Pipette` Protocol

`PipetteBot` depends on a structural type (`_Pipette` in `bot.py`) with
just `aspirate(volume_ul)` and `dispense(volume_ul)`. Tests inject
`tests.conftest.FakePipette`. Don't import `dpette.DPetteDriver` into
test code.
