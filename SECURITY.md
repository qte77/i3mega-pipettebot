# Security

This project drives physical hardware (a 3-axis gantry and a serial pipette).
The primary risks are operational, not network-based.

## Reporting

For software issues with security implications (e.g. malformed serial input
that could brick a pipette), open a private security advisory at
<https://github.com/qte77/i3mega-pipettebot/security/advisories/new>.

## Operational safety

- Never run untrusted G-code on hardware without checking soft limits.
- Never send raw bytes to the dPette directly — go through
  `dpette.DPetteDriver` so safety validations run.
- The dPette `A5 b2=1` calibration command causes persistent Err4 and is
  blocked in `dpette-usb-driver`. Do not work around that block.

## Secrets

This repo contains no secrets and no `.env` is required. CI does not need
any tokens beyond default `GITHUB_TOKEN`.
