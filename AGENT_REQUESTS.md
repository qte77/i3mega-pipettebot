# Agent Requests

Inbox for agent-to-human and agent-to-agent communication: requests,
observations, hand-off notes, decisions that need input. Each entry is
a message, not a work item.

Plain backlogs, task lists, and per-area issue rosters do not belong
here. Actionable work goes in GitHub issues; stable repo conventions
go in [AGENTS.md](AGENTS.md); architectural decisions go in
[`docs/adr/`](docs/adr/). When an entry below is acted on, remove it —
the resolving issue or PR is the record.

## Open requests

### 2026-05-11 — Fit-test the scheme b L-bracket V-plate Y assumption

@user — The L-bracket geometry in
[`build_carriage_dpette_mount_main_lbracket`](tools/cad/i3/carriage_dpette_mount.py)
(landed in [PR #48](https://github.com/Lambda-Biolab/i3mega-pipettebot/pull/48))
assumes the V-plate front face sits at `Y_mount = TOP_PLATE_D_MM`
(30 mm from the 4-hole pattern centroid in the +Y direction).
`measurements.py` locks the V-plate top hole X-pitch, Ø, and Z offset
but does not specify Y. Please verify against the real i3 Mega
carriage in a fit test before printing scheme b at scale, and tune
`LBRACKET_FLANGE_D_MM` and the bolt-Y position in
`_build_lbracket_reinforcement()` if the measured offset differs.

### 2026-05-11 — Decide button-vs-tip-column XY relationship for `tip_ejection_bar`

@user — [PR #52](https://github.com/Lambda-Biolab/i3mega-pipettebot/pull/52)
fixed the primitive-stacking bug in
[`tools/cad/dpette/tip_ejection_bar.py`](tools/cad/dpette/tip_ejection_bar.py)
but the slicer still warns "floating object part" because the Ø8 post
sits centred over the Ø25 waste hole — its bottom layer needs to
bridge the hole. Resolving this requires deciding how the dPette
eject-button XY relates to the tip-column XY (coincident? offset by a
known vector?). The post and waste-hole positions follow from that
decision. Until you have a target geometry, I left the WARN as-is per
[`.claude/rules/cad-printability-gate.md`](.claude/rules/cad-printability-gate.md).
