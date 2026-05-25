# Alternative pipettes — research log

Append-only survey of electronic and programmable pipettes evaluated
against the `_Pipette` Protocol surface in `src/pipettebot/bot.py`.
Supports the pipette-agnostic library design and future "what else
could mount on the carriage" decisions.

The DLAB dPette+ is the reference pipette for the **dpette+i3** build
and is driven via [`dpette-usb-driver`][drv]. That repo's own
[competition matrix][drv-why] frames the broader landscape from the
pipette-driver angle; this log focuses on whether each candidate could
be a *second supported pipette* under the existing `_Pipette` Protocol.

[drv]: https://github.com/Lambda-Biolab/dpette-usb-driver
[drv-why]: https://github.com/Lambda-Biolab/dpette-usb-driver#why-this-matters

## Evaluation criteria

Hard requirements:

- Disposable-tip workflow — matches the v0 "no tip recycling" target
  (rules out continuous-flow peristaltic pumps and bonded-syringe
  pipettes).
- Documented or community-reverse-engineered control protocol over
  USB-serial or a comparable host-side bus. A closed protocol with
  no public RE makes the candidate unimplementable.
- Physically mountable on the i3 or A30 carriage within the payload
  budget (i3 cap 300 g; A30 cap TBD per
  [`docs/roadmap.md`](../roadmap.md)).

Soft preferences:

- Cheap or used-market-available — aligns with the
  resource-constrained researcher persona in
  [`docs/UserStory.md`](../UserStory.md).
- Multichannel option for 96-well plate throughput.

## Entries

### 2026-05-26 — DLAB dPette+ (reference) and DLAB multichannel dPette

- **Status:** **SUPPORTED** (single-channel reference) /
  **CANDIDATE** (multichannel, untested in this repo).
- **Protocol:** 6-byte serial frames over CP2102 USB-to-UART at 9600
  baud; B3 SUCK / B3 BLOW for aspirate / dispense. Documented via
  the dpette-usb-driver project, originally reverse-engineered from
  the official Chinese dPette+ protocol document — see
  [`xg590/Learn_dPettePlus`][xg] for the intellectual lineage.
- **Multichannel note:** The DLAB 8-channel dPette uses the same
  CP2102 bridge and 6-byte protocol per the dpette-usb-driver device
  list. Has not been bench-validated in this repo; a separate cradle
  is already designed (`dpette_multi_cradle` in
  [`tools/cad/parts.json`](../../tools/cad/parts.json)).

[xg]: https://github.com/xg590/Learn_dPettePlus

### 2026-05-26 — Opentrons GEN2 pipette (P20 / P300 / P1000 single + multi)

- **Status:** **NOT VIABLE** as a second supported pipette in v0.
- **Why not:** Opentrons GEN2 pipettes are physically mountable in
  principle (used units appear on the secondary market) but the
  control protocol is proprietary and runs over a CAN bus internal
  to the OT-2 chassis. There is no public documentation of the
  on-the-wire format and no community driver. Without a separated
  USB-serial control surface this candidate fails the hard
  requirement on documented protocol.
- **Revisit if:** an open driver lands upstream or Opentrons
  publishes the GEN2 protocol.

### 2026-05-26 — ac-rad Digital Pipette (academic open-hardware)

- **Status:** **OUT OF SCOPE** for the disposable-tip workflow.
- **What:** Open-hardware syringe-based pipette built around a
  10 mL NORM-JECT Luer syringe and an Actuonix linear actuator,
  Arduino-controlled. Published 2023 in *Digital Discovery*. Source
  at [`ac-rad/digital-pipette`][acrad].
- **Why not adopted:** Syringe with Luer coupling rather than
  disposable-tip — does not satisfy the v0 disposable-tip
  requirement. Useful as a reference for the *Arduino + Python host*
  control pattern (analogous to dpette-usb-driver's CP2102 bridge),
  but not as a drop-in second pipette.

[acrad]: https://github.com/ac-rad/digital-pipette
