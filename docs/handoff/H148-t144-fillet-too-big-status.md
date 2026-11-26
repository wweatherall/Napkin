### H148 — T144 step 1: a corner fillet radius too big for its edges says why

Author: Claude (integrator, fretchup-75) | Date: 2026-11-26 | Status: answered | For: either

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

#### Response (Claude Sonnet 5.5, worker, 2026-11-26)

Branch claude/h148-t144-fillet-too-big-status, commit 65e00d3. A typed corner radius that's too big now says
`Radius must be at most <max> for this corner` and leaves the gesture waiting; zero and non-finite stay silent;
`_fillet` is unchanged. Verified: the new message check failed before the change, `50r` still passes after it, and the
quick test passes (viewport 393/0). No IDs added.

Changed from the brief: only a too-big radius changes behaviour; the largest radius is also accepted within
GEOMETRY_TOLERANCE_MM and clamped to the edge's end; typing the suggested `90r` was refused with "at most 90 mm"
because the setback came out a hair long in floats (check "typing the largest radius the message names places the
fillet", seen failing first).

Follow-up: the max is shown through format_length, which can round up (shown with `~`); typing that rounded number is
then still refused. Rounding the suggested max down to what the display shows would fix it; William's choice.

Result: 65e00d3; quick test passed (viewport 393 passed, 0 failed, and the feature tests); a too-big corner fillet radius says the largest that fits, and typing that largest value places it
