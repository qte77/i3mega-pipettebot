"""SO-101 integration — orchestrator, capture CLI, named-position playback.

Optional subpackage gated by the `[orchestrator]` extra. Composition only
over `so101.DualArmController` (no subclassing). The rows showcase imports
`pipettebot.so101.orchestrator` lazily when SO101_CONFIG is set so the rest
of the package works without the so101 dep installed.
"""
