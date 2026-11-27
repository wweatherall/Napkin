### H151 — T147 step 2: circles and polygons fit flush against a sloped face

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: answered | For: either

References: T147, T145 (finding 6), P21 (where the viewport predicts FreeCAD, a test compares the two), H127, T84.

Touches: worker/plane_fit.py (`geometry`, `source_frame`, `update`), worker/scenario/99_plane_fit_flush.py (new).

Reading path:
1. `worker/plane_fit.py` `source_frame`: for a non-rectangular board (sketch circle, polygon, any sketch) it returns
   the **bounding rectangle** of the profile in the extrusion's frame (`origin`, `axes`, `sizes`).
2. `geometry`: takes the 4 corners of that rectangle (`corners`), measures each corner's distance along the push to
   the target plane (`depths`), and Butt to plane uses `min(depths)`, Fully reach `max(depths)`.
3. `update` (non-rectangular branch): sets `ext.LengthFwd = min(depths)` (Butt) or `max(depths)` (Fully reach).
4. `viewport/tools/push_tool.gd` `_edge_inference`: the preview measures `depth` and `far` over `state.tris`, the
   profile's own triangles, so the viewport already predicts the flush length; the worker doesn't match it.

Today (rechecked 2026-11-26 on main 4e3e051, after H150: `update` now finds the target plane with `_resolve_face`; the depths are measured as before): a 100 mm circle butted to a face at 30° stops short by about the distance
between the bounding square's nearest corner and the circle (around 12 mm, the review's figure); the draft shows a
flush fit, FreeCAD's mesh replaces it with a gap. Rectangles are unaffected (the profile is its bounding rectangle).

Request: for a non-rectangular source, Butt to plane and Fully reach measure the depths over the profile itself, not
its bounding rectangle: the extrusion base's edges, discretized as `source_frame` already does (`Deflection=0.25`), or
exactly for a circle (centre distance minus or plus radius times the in-plane slope). Slice at plane already cuts with
the plane itself (`_sliced_shape`) and stays as it is. The result line's length (`dimension`) uses the same depths.
Rectangular stock keeps its 4-corner path unchanged (it is exact, and `SSFitCorners` stays the 8 points it stores).

Checks: a new `worker/scenario/99_plane_fit_flush.py`, each failing without the change:
- "a circle butted to a sloped face touches it" (100 mm circle, target face at 30°: the nearest point of the fitted
  solid lies on the plane within 0.01 mm);
- "a polygon fully reaching a sloped face touches it at its far point";
- "a rectangle's fit is unchanged" (same LengthFwd as before the change);
- P21: "the viewport's predicted fit length matches FreeCAD's" for the circle case (the depth `_edge_inference` would
  compute from the profile, worked out in the test, equals the worker's within 0.01 mm).

**Response (Gemini, gemini-cedar-1126-1909, 2026-11-26):**
Branch `gemini/h151-t147-flush-fits-curved-profiles`, commit `712d414`.
- Extracted `_source_frame_and_profile` in `worker/plane_fit.py` (with `source_frame` returning the frame tuple unchanged) so non-rectangular profiles carry either exact circle parameters `('circle', center, u_sketch, v_sketch, radius)` or discretized edge points `('points', pts)` (`Deflection=0.25`).
- Updated `geometry` (with optional `profile=None`), `update`, and `apply` so Butt to plane and Fully reach measure depths over the profile itself for non-rectangular sources (exact `d_center ± r * slope` for circles, discretized edge points for polygons/other sketches), while Slice at plane and rectangular stock keep their 4-corner path and 8-point `SSFitCorners` unchanged.
- Added `worker/scenario/99_plane_fit_flush.py` covering all four checks (100 mm circle butted at 30°, hexagon fully reaching at 30°, unchanged rectangle fit, and P21 viewport-to-worker depth parity).
- Verified with `python3 tools/job.py test` on `712d414`: all feature tests (`SCENARIO TESTS: 714 passed, 0 failed`) and viewport tests (`QUICK 399 passed, 0 failed`) passed.
- IDs added: none. Open questions: none.

Result: 712d414; job.py test passed (714 scenario, 399 viewport); circles and polygons fit flush against sloped faces
