### H086 — T83 step 2: an arc on a corner is tangent to both edges (rounded corners)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: either

References: T83, I61 (William's call: "If you make an arc on the corner, it should default to tangency"), I60
(the Arc tool), I51 (arcs split faces), P21. H085 builds the Arc tool this job extends.

Touches: viewport/tools/arc_tool.gd, viewport/tool_geometry.gd (a pure outline helper, if any), viewport/test_tool_context.gd only if a capability grows, a new
worker/scenario/ file, viewport/tests/quick/arc.gd. Not inference.gd (snapping stays its job; ask before changing
it), ARCHITECTURE.md or the folder guides ("Architecture:" and "For the integrator:" lines instead).

What the user does: with the 2-Point Arc, the start clicked on one edge of a face or profile and the end on an
edge that meets it at a corner (the two edges share an end, and are not parallel), with both points the same
distance from that corner (within the snap distance the tool uses for endpoints; snap the end to the
equal-distance point when the cursor is that close): the bulge snaps to the arc tangent to both edges and the
arc is drawn in magenta, with the tip "Tangent at corner". Moving the cursor off the tangent bulge by more than
the snap distance frees it, as a snap does. Typing `50r` with start and end on the two edges places the fillet of
radius 50 there (start and end move along their edges to the tangent points; the corner's angle sets where). The
committed op is an ordinary `arc` op: nothing new reaches FreeCAD, and the region it cuts off can be pushed down
as a through-cut to round a tabletop's corner.

Checks: worker/scenario: a 600 x 400 board's top corner with a 50 mm tangent arc, the corner region cut through:
FreeCAD's solid has a cylindrical face of radius 50 meeting both side faces tangentially (normals equal at the
seam, within 1e-6), and the viewport's region area agrees with FreeCAD's (P21). viewport/tests/quick/arc.gd: the
tangent snap and its tip on a 90° corner and on a non-square corner (a polygon profile from the Line tool), `50r`
at a corner, a free bulge after leaving the snap, and the corner cut through (draft first, then FreeCAD's mesh).

Reading path: arc_tool.gd as H085 leaves it (the bulge step), then inference.gd `_nearest_visible` (a snap's answer
is the point, its kind and its body, not the edge: today nothing reports which edge a point is on), then
regions.gd `find`'s boundary (a face's outline from its triangles: the edges shared by one triangle only), which
is how the tool finds the two edges through its start and end (from `ctx.model.triangles` or the profile's
`tris`; a pure helper in tool_geometry.gd if it's shared), then presenter.gd
`drawn_region` (the corner region). The tool owns the tangent test and the bulge; the presenter and the worker
don't change.

Not in this job: tangent to the previous arc or line in a chain, rounding all four corners at once, FreeCAD's
fillet on a solid's edges (T108).

End your response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator
lines.

### Response from Codex, 2026-11-23

Branch `codex/h086-t83-arc-corner-tangent`, implementation `d7d6df9`. The 2-Point Arc snaps the end
to equal distance along an adjacent outline edge. At the tangent midpoint it shows a magenta preview and
the tip “Tangent at corner.” Moving away restores free bulge control. A typed radius repositions both
endpoints along the selected edges.

The gate passed with 294 quick viewport checks and all feature and full suites passing. Quick coverage
includes the square snap, release to free bulge, a non-square Line profile, `50r`, and the through-cut
from draft to confirmed mesh. The viewport and FreeCAD region areas agreed within 5 mm². The worker
scenario checked the 50 mm cylinder, both seam normals within 1e-6, and undo back to its fixture.

No new decision IDs or open questions.

Architecture: The Arc tool uses the coplanar triangle outline and the live endpoint snap radius for
corner tangency. It saves the tangent points at viewport precision in the existing arc op.

For the integrator: Add the corner snap and typed corner radius to the Arc entry in viewport/tools/CLAUDE.md.

Result: d7d6df9; gate passed, 294 quick viewport checks and 603 worker scenario checks; tangent 2-Point Arc corner snaps, typed fillets, and verified through-cuts
