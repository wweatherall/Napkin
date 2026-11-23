### H085 — T83: the Arc tool (2-Point and Centre arcs, exact in FreeCAD, splitting faces)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: either

References: T83, I60 (the gesture, William's call), I49 (arcs exact in FreeCAD), I51 (lines split faces; arcs the
same), I58 (the Line tool's chain), I59 and T66 (typed lengths, as H052 leaves them), I43 (press-and-drag or
click-click), A03, A34 (a tool is one new file), A35 (protocol version), P21 (the viewport's prediction checked
against FreeCAD). Worked example: the Line tool (H046/T82): viewport/tools/line_tool.gd, worker/line.py.

Touches: viewport/tools/arc_tool.gd (new), viewport/tools/tool.gd (`typed_raw`, below), worker/arc.py (new), viewport/presenter.gd (`register_line` and
`lines_on` take an arc; `rebuild_rect_drafts`), viewport/regions.gd
(a drawing that is a polyline), viewport/main.gd (only `redo()`'s op-type branch, line ~1089: an `arc` registers
like a `line`), viewport/measure_box.gd (`apply`: Arc takes lengths; the `r` suffix), viewport/tool_context.gd and
viewport/test_tool_context.gd (only if a capability grows: see "the hint" below), worker/line.py (`native_region`
refines against arcs too), viewport/test_regions.gd, worker/scenario/ (a new numbered file), viewport/test_tools.gd
and viewport/tests/quick/registry.gd (the expected tool lists), a new viewport/tests/quick/arc.gd, both
PROTOCOL_VERSIONs (worker/serve.py, viewport/main.gd). Not ARCHITECTURE.md, docs/protocol.md or the folder
guides: write what changes as "Architecture:" lines and guide changes as "For the integrator:" lines.

Waits for H052 (T66 units): it changes every tool's `vcb_value` and measure_box.gd. Before starting, re-read
measure_box.gd `apply` and line_tool.gd as H052 leaves them; where this brief and that code disagree, follow the
code and say so in the response.

What the user does (I60, exactly):
- Key A selects the Arc tool as 2-Point Arc. Pressing A again while the Arc tool is active switches to Centre
  Arc, and back; a switch cancels a gesture in progress. TOOL: `{"id": "arc", "label": "Arc", "tip": "Arc (A)",
  "key": KEY_A, "order": 38, "show_links": true}`. `tip()` and `hint()` name the current kind.
- 2-Point Arc: click the start (on a face, a profile or the ground, picked and snapped as the Line tool does),
  click the end, then move to set the bulge (the arc's height above the chord's midpoint, on the side of the
  cursor); click to finish. Press-drag-release from start to end, then a click for the bulge, works too (I43, as
  the Line tool's drag). Typed after the end is placed: a bare length is the bulge; a length followed by `r` is the
  radius (`50r`, `2"r`; the minor arc on the cursor's side; refused with the status note "Radius must be at least
  half the chord" when it's shorter than half the chord). Typed before the end is placed: the chord length along
  the direction you're pointing, as the Line tool's typed length. Measurements label: "Length" before the end,
  "Bulge" after; value as H052 formats lengths.
- Arcs don't chain (I60): each arc ends after its last click; Esc during a gesture cancels it.
- Centre Arc: click the centre, click the start (sets the radius; typed: the radius), sweep to the end (typed:
  the angle in degrees, counter-clockwise seen from the plane's normal when positive). The sweep follows the
  cursor's angle continuously, so a sweep past 180° is reachable; a full 360° is refused (that's a circle: the
  Circle tool). It ends after the end click. Labels "Radius", then "Angle" (shown as e.g. "90°").
- Hints: "2-Point Arc: click the start, then the end, then the bulge; A for Centre Arc" and "Centre Arc: click
  the centre, then the start, then sweep to the end; A for 2-Point Arc".

The op (one per arc; a new op type, so bump PROTOCOL_VERSION by one on both sides, A35):
`{"id": next_id("r"), "type": "arc", "plane": <exactly as line's: origin = the arc's start, or "on": {body,
normal, point}>, "mid": [x, y, z], "end": [x, y, z], "snap_start": bool, "snap_end": bool}`, world mm; `mid` is
the point on the arc halfway along it (both kinds reduce to start, mid, end).

Worker (worker/arc.py, `ArcActions.op_arc`, found by file, A34): as `op_line`, a Sketcher sketch in the Lines group
with one `Part.ArcOfCircle` made from the three points (`Part.Arc(start, mid, end)`), `Block`-constrained,
`SSLineId` = op id, `OnBody`; the same on-face projection as op_line. Refuse (OpError) three collinear or
coincident points, points off the plane, non-finite values.

Viewport:
- Facets: draw an arc with `ceil(CIRCLE_SEGMENTS * sweep / (2π))` segments, at least 2 (presenter.gd
  CIRCLE_SEGMENTS = 64): the same density as circles, so native_region's existing bound (it cites the 64-segment
  circle preview) holds for arcs.
- Drawings: `register_line` takes an `arc` op too: its `loose_lines` entry keeps `a` (start) and `b` (end) and
  gains `"pts"`, the facet points from a to b; a line has no `pts`. `lines_on` checks every point of `pts` against
  the plane, not only a and b. `Regions.find` turns an entry with `pts` into its consecutive segments; only the
  first segment's start and the last one's end get the snap_start / snap_end boundary bridging (the arc's ends
  are its only snapped points). The draft is the facets in the line colour.
- `rebuild_rect_drafts` and main.gd's `redo` treat `arc` like `line`.
- Push/Pull on a region whose drawings include an arc sends `target.region` exactly as today (the facet
  outline and the drawing ids); nothing in push_tool.gd changes.
- The hint after an A switch: main.gd sets `ui_hint.text` only in `set_tool`. If no ToolContext member refreshes
  the hint, add `ui.refresh_hint()` (snapshot rules as the others; extend the allowlist in test_tool_context.gd
  and the spec's UI section by an "Architecture:" line).
- measure_box.gd `apply`: Arc takes lengths like Line (today a list, `["rect", "circle", "line", "push", "move"]`,
  unless H052 changed it). A trailing `r` (any case, spaces allowed before it) while the Arc tool is active is
  taken off, the rest worked out as a length, and the tool's `typed` gets `"<mm>r"`; what units.gd declines goes
  to FreeCAD as today, with the `r` added back to the reply. Angles for Centre Arc are a plain number (degrees),
  passed raw (as Move's count syntax is), not as a length: add `typed_raw() -> bool` to tool.gd (false by
  default; Arc returns true during the sweep) and have `apply` pass the text as typed when it's true, instead of
  naming Arc there. `accepts` lets `r` through once something is typed
  (it does today: letters after the first character).

FreeCAD stays exact (I49): `native_region` (worker/line.py) today returns the facet polygon unchanged when every
edge of the source face is a straight line. Change: also refine when any of the region's drawings
(`spec["lines"]`) is an arc sketch; slice the source with the drawings' edges, lines extended as today and arcs as
they are (their ends lie on the boundary or on other drawings), pick the pieces as today, same discrepancy bound.
Report the refined face's edges: a region bounded by an arc must have a circular edge of the arc's radius in
FreeCAD (checked in the scenario).

Cases that must still work: every Line case (chains, closing, single drags, regions with holes, lines on curved
faces, test_regions.gd and worker/scenario/99_regions.py unchanged and passing), Circle profiles, Push/Pull of
plain faces and profiles, undo / redo of a drawing, reopening a model with lines (rebuild_rect_drafts).

Checks:
- worker/scenario/ (a new numbered file, first, P07): an arc on a board's top from edge to edge, the region on
  its convex side pushed up 10 mm, joined: FreeCAD's solid has a cylindrical face of the arc's radius, and the
  viewport's predicted region area (the facet polygon) agrees with FreeCAD's face area within the native_region
  bound (P21); the same region pushed down as a cut; collinear points refused.
- viewport/test_regions.gd: a polyline drawing splits a square into two regions with the arc's facets on the
  shared boundary; an arc touching the boundary only through its end snaps (bridging) still closes.
- viewport/tests/quick/arc.gd: A selects 2-Point Arc, A again Centre, A again 2-Point (hint each time); a
  2-Point arc typed `20` bulge and `50r` radius (checking the op's mid); a Centre arc typed radius then `90`;
  Esc cancels an arc mid-gesture; an arc across a board's face then Push/Pull on one
  side changes only that side (the draft first, then FreeCAD's mesh).
- test_tools.gd and quick registry.gd: the new tool in the expected lists (key A, order 38).

Reading path (an arc's whole lifetime): line_tool.gd `click` → `_drag` → `_commit` (how a drawing becomes an op
and a draft) → presenter.gd `register_line` → `lines_on` → `drawn_region` → regions.gd `find` (how drawings
become a region under Push/Pull) → push_tool.gd's use of `ctx.model.drawn_region` (the `target.region` it sends)
→ worker/line.py `op_line` (the drawing in FreeCAD) → push.py `op_push_pull`'s region branch (line ~105) →
line.py `region_face` and `native_region` (the exact face). Who owns what: the tool owns its gesture state and
builds the op; the presenter owns `loose_lines`, `rects`, every draft node and the facets; regions.gd is pure (no
Main, no presenter); the worker owns exactness: the viewport's facet polygon is only the prediction, and
native_region replaces it with FreeCAD's real edges.

Not in this job: arcs tangent at corners (I61; the next job, queued after this one), arcs tangent to the previous
arc or line, editing an arc after it's drawn, loops of lines and arcs closing into a face (T109), FreeCAD's fillet (T108).

End your response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator
lines.
