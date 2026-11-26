### H148 — T144 step 1: a corner fillet radius too big for its edges says why

Author: Claude (integrator, fretchup-75) | Date: 2026-11-26 | Status: open | For: either

References: T144, I71, I61, H086 (follow-up), T83.

Touches: viewport/tools/arc_tool.gd (`typed`), viewport/tests/quick/arc.gd (`_angled_corner`).

Reading path:
1. `viewport/tools/arc_tool.gd` `typed` (the `txt.ends_with("r")` branch): on a corner it calls `_commit_fillet(_fillet(corner, magnitude / tan(corner.half_angle)))`.
2. `_fillet`: returns an empty array when the setback is above `minf(from.length(), to.length())` (or not finite, or below `GEOMETRY_TOLERANCE_MM`).
3. `_commit_fillet`: returns at once on an empty array, so nothing happens and nothing is said.

Today (checked 2026-11-26 on main e94daf4): a typed `Nr` on a corner whose radius needs a setback longer than the shorter of the two edges places nothing and shows nothing. The chord case beside it already says `ctx.ui.show_status("Radius must be at least half the chord")`.

Request (I71): when the typed radius on a corner is too big for the corner's edges, show
`Radius must be at most <max> for this corner` with `ctx.ui.show_status`, where `<max>` is
`ctx.ui.format_length(minf(corner.from.length(), corner.to.length()) * tan(corner.half_angle))`, the largest radius that
still fits (so the user knows what to type: this is the radius whose setback equals the shorter edge). The gesture stays
where it is (no op, the arc still waiting for a bulge or another typed value), as the chord case does, so the user can
type a smaller radius at once. Only the too-big case gets the message: a zero or non-finite radius stays silent as
today (it isn't the case William asked about). Don't change `_fillet` (the snapping path calls it per frame and must stay
quiet).

Checks: in `viewport/tests/quick/arc.gd` `_angled_corner`, before the `50r` step, type a radius too big for that
corner and check: no new op, `m.ui_sync.text` is exactly the message with the max formatted as the box shows it, the arc
tool still busy; then the existing `50r` step still passes (it proves the gesture survived). Name it
"a fillet radius too big for the corner says the largest that fits". It must fail without the change.

