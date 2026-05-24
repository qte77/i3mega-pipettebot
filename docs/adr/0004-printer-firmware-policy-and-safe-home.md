# ADR 0004: Single `PRINTER_PORT` env + policy-driven `safe_home` dispatcher

- **Status:** Accepted
- **Date:** 2026-05-24
- **Scope:** [qte77/i3mega-pipettebot](https://github.com/qte77/i3mega-pipettebot) only

## Context

A30 bring-up (`docs/research/gantry-firmware-alternatives.md`, 2026-05-23
entries) confirmed Smartto v1.xx.58 as a second supported gantry firmware
family. Two operational problems followed from supporting more than one
printer in the same repo:

1. **Per-model port env vars proliferated.** Each new firmware/printer
   pair earned its own alias (`I3MEGA_PORT`, `SMARTTO_PORT`) plus a
   generic fallback (`GANTRY_PORT`). `tools/preflight.py`,
   `tools/gantry_repl.py`, and `tools/gantry_probe.py` each carried a
   private `("I3MEGA_PORT", "SMARTTO_PORT", "GANTRY_PORT")` resolution
   order. A third printer would have multiplied the surface again.
2. **`G28` is unsafe on Smartto/A30 with head removed.** The probe-pin
   variant in stock Smartto firmware drives Z indefinitely; only
   `G28 X Y` + manual `G92 Z0` is safe. Examples that hardcode `G28`
   crash the gantry into the bed when pointed at an A30. The runbook in
   the research log spells out the correct sequence step-by-step, but
   nothing in the library prevents an unsafe call.

The `FirmwarePolicy.home_strategy` field already classified this
(`"full_g28"` for Marlin, `"xy_then_polled_z"` for Smartto,
`"manual_only"` for unknown), but no code consumed it — homing was
implicit `gantry.home()` (== `G28`) at every call site. The classification
was advisory text, not enforcement.

## Decision

### 1. Collapse all port aliases to a single `PRINTER_PORT` env var.

`FirmwarePolicy` no longer carries `port_env_aliases`. `devices.py`
exposes a module-level `PRINTER_PORT_ENV = "PRINTER_PORT"` and
`resolve_port(env=os.environ)` reads exactly that name. Firmware family
is identified by `discover()` post-open, not by which env var the
operator chose to set.

`tools/preflight.py --export` prints `export PRINTER_PORT=...`
regardless of the detected family. Operators set one env var; the same
shell session can drive any supported printer.

### 2. Introduce `safe_home(gantry, policy, *, confirm_z=input)` as a
free function in `devices.py`.

```python
def safe_home(
    gantry: GcodeGantry,
    policy: FirmwarePolicy,
    *,
    confirm_z: Callable[[str], str] = input,
) -> None:
```

Branches on `policy.home_strategy`:

- `full_g28` → `gantry.home()` (sends `G28`).
- `xy_then_polled_z` → `gantry.send("G28 X Y")`, invoke `confirm_z`
  prompt, `gantry.send("G92 Z0")`. The callback blocks on stdin by
  default; tests and unattended runners inject `lambda _: ""`.
- `manual_only` → raise `RuntimeError`. Operator must home via
  `tools/gantry_repl.py` and set origin by hand.

`GcodeGantry._send` was promoted to public `send()` so `safe_home` can
issue the two-step Smartto sequence without poking a private helper —
the same surface is reusable by any future caller emitting G-code
outside the wrapped method set (`home`, `move_to`, `wait_for_moves`).

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| **Two adapter classes (`MarlinGantry` / `SmarttoGantry`) behind a `GantryProtocol`** | Original recommendation in `docs/research/gantry-firmware-alternatives.md` was revised same-session: the two diverge on three fields only (default baud, home strategy, capability metadata). A second class would duplicate `move_to` / `wait_for_moves` for zero behavioral gain. Free function + policy data is the AHA-compliant scope. |
| **Method on `GcodeGantry`: `gantry.home(policy)`** | Requires moving `FirmwarePolicy` from `devices.py` into `gantry.py` (else circular import — `devices.py` already imports from `gantry.py`). Composition-over-coupling preferred: `safe_home` lives in `devices.py` alongside `policy_for()` and `discover()`, where firmware-identity concerns already cluster. |
| **Keep `port_env_aliases` on `FirmwarePolicy` for forward flexibility** | YAGNI. After collapse, every policy held the same single-element tuple `("PRINTER_PORT",)`. The field added indirection without supporting any actual divergence. Re-add if a future firmware genuinely needs a different env name. |
| **Inline the safe-home sequence in each example script** | Duplication smell at three (soon: more) call sites, none of which would consistently emit the correct `G28 X Y` + `G92 Z0` pair. The whole point of `home_strategy` is to centralize this; honoring it requires a central consumer. |
| **Make `safe_home` always interactive (no callback injection)** | Untestable without monkeypatching stdin; locks out unattended scripts and future schedulers. Default-to-`input` preserves the interactive UX while keeping the seam open. |

## Consequences

### Pros

- **One env var across the project.** Operators set `PRINTER_PORT` once;
  `tools/preflight.py --export` produces it; every script, tool, and
  example reads the same name.
- **Unsafe homing is no longer the path of least resistance.**
  `safe_home(gantry, policy_for(discover(port)))` is shorter to type
  than rebuilding the `G28 X Y` / `G92 Z0` pair by hand, so new
  examples will reach for it.
- **`manual_only` policy is now enforceable.** Unknown firmware can
  no longer accidentally receive a `G28` — `safe_home` raises before
  any G-code is written.
- **Callback injection keeps tests pure.** All three branches covered
  with `FakeSerial` + `lambda _: ""` injection; no monkeypatching.

### Cons

- **One-time migration cost for any out-of-tree script** that read
  `I3MEGA_PORT` / `SMARTTO_PORT` / `GANTRY_PORT`. None exist in this
  repo, but the v0.1.0 tag did expose those names in tool docstrings.
  CHANGELOG entry called out as breaking.
- **`safe_home` knows about both `full_g28` and `xy_then_polled_z`.**
  Adding a new home strategy requires editing one function — but that
  was already true of the `home_strategy` field's enum-string design.

### Neutral

- **`GcodeGantry.send()` is now public.** Internal callers were already
  using `_send`; the rename is mechanical. External callers that
  reached for `_send` (none in-repo) should migrate.
- **Existing examples were renamed with an `_i3` infix** to flag them
  as i3-Mega-only (hardcoded 210x210 deck coords + plain `G28`). New
  A30 scripts live alongside under their own naming convention. This is
  the "rename to indicate constraint" alternative to a flag-driven
  generic example, and is consistent with not invoking `safe_home`
  from the legacy scripts in this PR.

## Out of scope

- **Porting the seven `_i3` showcases to use `safe_home`.** They use
  raw serial sends bypassing `GcodeGantry` (the
  `_send` one-line-readline bug, issue #26); porting them needs the
  bug fixed first. Tracked separately.
- **A `BAUD` env var as the printer-agnostic equivalent of
  `PRINTER_PORT`.** Each script still defaults baud per its target;
  the discovered baud (from `pipettebot.devices.discover()`) is
  authoritative when present. Promote to a single env if/when a third
  baud appears.
- **Auto-discovery inside example scripts.** Examples take `PRINTER_PORT`
  explicitly; `tools/preflight.py --export` is the supported discovery
  surface. Implicit discovery in examples would couple every demo to
  the full port-scan logic.

## References

- `docs/research/gantry-firmware-alternatives.md` — 2026-05-23 A30
  bring-up entries; the `xy_then_polled_z` recipe and the architecture
  revision (single class + policy, not two adapter classes) originate
  there.
- `src/pipettebot/devices.py` — `FirmwarePolicy`, `safe_home`,
  `resolve_port`, `PRINTER_PORT_ENV`.
- [ADR 0003](./0003-motion-profile-bundled-constants.md) — sibling
  env-var selector pattern (`MOTION_PROFILE`) this ADR's
  `PRINTER_PORT` aligns with.
