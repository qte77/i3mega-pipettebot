# Aspirate monitoring — research log

Append-only notes on aspirate verification (clog / dry-well / volume
confirmation) technologies, evaluated against the open-loop dPette+
pipetting path that this repo currently runs.

v0 has no aspirate verification. The dPette protocol
([`dpette-usb-driver`](https://github.com/Lambda-Biolab/dpette-usb-driver),
6-byte B3 SUCK / B3 BLOW frames) gives no feedback on internal piston
state or actual liquid moved. This log tracks what closing that gap
would look like, and why nothing has been adopted yet.

## Evaluation criteria

Hard requirements for any candidate to make it into v0+:

- Non-invasive to the dPette+ — the nozzle / piston / motor are not
  user-serviceable and tampering voids the factory calibration.
- Compatible with disposable tips — no per-tip wiring or
  conductivity requirement that prevents standard 200 / 1000 µL tips.
- Single USB-serial integration surface — matches the existing
  `PIPETTE_PORT` / `PRINTER_PORT` pattern, no extra bus.
- Bench-characterizable on the dPette+ before being trusted in a
  workflow.

## Entries

### 2026-05-26 — Hamilton MAD / TADM (Monitored Air Displacement)

Reference industry technology for pressure-based aspirate verification
on Hamilton MICROLAB STAR liquid handlers.

- **What:** A miniature pressure transducer in the air column above
  each CO-RE pipetting channel piston. During every aspirate and
  dispense stroke the transducer streams pressure-vs-time to host
  firmware, which classifies the stroke against a learned "golden"
  envelope. Hamilton calls the sensing layer **MAD (Monitored Air
  Displacement)** and the software classifier **TADM (Total
  Aspiration and Dispense Monitoring)**. Companion features on the
  same hardware: **pLLD** (pressure-bump liquid-surface detection
  during Z descent) and the unrelated **cLLD** (capacitive
  surface detection through the conductive tip — separate sense
  circuit, not pneumatic).
- **First-party source:** Hamilton's [MICROLAB STAR product
  page][star] (accessed 2026-05-26) describes MAD as "non-contact
  technology" that during liquid aspiration "immediately identifies
  clots, empty wells, or other aspiration issues" and "delivers a
  confirmation of successful aspiration in each pipetting channel."
  No standalone MAD or TADM URL — the copy is inline on the STAR
  page, and the
  [technologies sitemap](https://www.hamiltoncompany.com/sitemaps/entries.xml?section=technologies)
  lists only six entries, none of them MAD or TADM.

[star]: https://www.hamiltoncompany.com/microlab-star

- **Can we reuse the hardware?** No, not without an external sensor.
  The dPette+ nozzle is a sealed coupling: no exposed port between
  the internal piston and the disposable tip. Adding a T-fitting
  would modify the tip coupling and introduce dead volume that
  changes aspiration behavior. Even with an inline sensor, the
  dPette's internal motor creates its own pressure signature during
  B3 SUCK / B3 BLOW that would have to be characterized and separated
  before any "clog signal" is trustworthy.
- **Bolt-on sketch (speculative, not recommended for v0):** an inline
  ~0–10 kPa gauge sensor (e.g. BMP388, ~$3) plus a microcontroller
  (Raspberry Pi Pico, ~$4) presenting as a second USB-serial device —
  rough BOM ~$15–25. Would need a custom tip-coupling adapter and a
  characterization campaign for the dPette+ motor profile. Filed
  here for future contributors; not on the near-term roadmap.
- **Verdict:** **DOCUMENT-ONLY for v0.** The honest reuse is naming
  the gap: v0 is open-loop with no aspirate verification, and
  Hamilton's TADM is the canonical industry reference for what
  closing it would mean. A bolt-on inline sensor is conceivable but
  blocked on dPette+ internal characterization that is out of scope.
