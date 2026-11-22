### H046 — T82: the Line tool, closed outlines and split faces

Author: Claude (integrator) | Date: 2026-11-22 | Status: answered | For: Codex

References: T82, I51 (lines split faces; Push/Pull acts on the region under the cursor; one op to FreeCAD), I49,
A34 (a new tool is one file), A35 (bump the protocol version for a new op), P21 (the viewport's region must be
tested against FreeCAD's result), A03; Circle (H041, docs/handoff-archive.md) for the pattern: profiles, exact
sketches, push of a profile.

Touches: viewport/tools/line_tool.gd (new), worker/line.py (new, a LineActions class), viewport/regions.gd (new:
the region finding, pure functions) and viewport/test_regions.gd (new, headless; give its feature-test line in your response: H049 owns that script
and the integrator adds it),
viewport/tools/push_tool.gd and worker/push.py (pushing a region), viewport/presenter.gd (line drafts, the region
overlay), viewport/inference.gd (snapping to lines), viewport/test_tools.gd, viewport/tests/quick/registry.gd,
worker/scenario/99_op_registry.py (the pinned lists), viewport/tests/quick/line.gd and worker/scenario/NN_lines.py
(new), viewport/tools/CLAUDE.md, docs/protocol.md, ARCHITECTURE.md. Not viewport/tests/harness.gd,
quick_runner.gd or tools/quicktest.sh (H045).

Request, in two stages (a commit and a gate run each):
1. Lines and closed outlines: the Line tool draws on the ground or a face, snapping like Rectangle and Circle;
   lines are kept as drawings (an op each, undoable, saved) and change no solid; lines that close a loop make a
   face that Push/Pull turns into a board, a cut or a boss, like a rectangle.
2. Split faces (I51): a line across a face splits it into regions; Push/Pull over a face finds the region under the
   cursor from the face's outline and every line on it (regions.gd), previews it at once, and sends one op with
   that region's closed outline. Test the awkward cases in test_regions.gd: crossing lines, a line ending partway
   (it doesn't split), a line ending exactly on an edge or a corner, two lines meeting on an edge, near-overlaps.
   P21: compare the predicted region with the face FreeCAD made (area and bounds) in the scenario.
William's answers (2026-11-22, logged as I58): the key is L; the gesture is the click-click chain (each click
ends a line and starts the next; Esc or clicking the start point ends it; a typed length sets the current line) plus
press-drag-release for a single line (I43's rule). Build on ToolContext (H051, merged 9581352; docs/specs/T88-tool-interface.md) from
the first file: no m.* in line_tool.gd, and uses_main() returns false. What ctx lacks for Line (loose lines,
regions), add to its capability with a test in test_tool_context.gd and say so. Push/Pull hasn't moved to the context yet when you start (it moves after
Line): change push_tool.gd as little as the region push needs.

Response — Codex, 2026-11-22:

Ready on `codex/h046-t82-lines-split-faces`. Stage 1: 47c3c2f (Line and closed outlines); stage 2: 0c1c9d3 (split regions). Main's later documentation commits are merged into the branch. Follows I49/I51/I58, A03/A34/A35 and P21. No new decisions or placeholders; nothing open.

Verification: stage-one post-commit gate passed (219 UI quick checks, all feature tests and full test, 48 s). Stage-two gate passed (232 UI quick checks, all features and full test, 42 s), zero known failures. This includes 59 pure region checks, 528 native scenario checks, 71 ToolContext checks and the real gesture tests. Native scenarios execute the actual Godot region finder and compare its predicted area, bounds and volume against FreeCAD for crossings, dangling ends, edge/corner meetings, overlaps, near-overlaps, holes, concavity, tilted/reversed planes and curved boundaries. UI checks cover chains, drag release, fractional typed lengths, snapping, Esc, undo/redo, quadrant edits, loops/pockets, annular previews and exact circular-segment volume. Drawing-only work and solids both survive reopening. Region lookup measured 1.8 / 5.1 / 16.9 ms for grids of 10 / 20 / 40 lines (scratch/region-bench-after.log).

Additional necessary paths beyond the original Touches: viewport/tool_context.gd and test_tool_context.gd (explicitly requested capability extension); viewport/main.gd (redo and region rejection dependencies); viewport/measure_box.gd (Line typed lengths); worker/serve.py (matching protocol version). tools/number_ids.py also needed a five-line root check: a temporary fixture under scratch must enumerate itself rather than inherit its ancestor repository's tracked files; the existing feature test exposed this under P25. These were declared in chat before editing. ARCHITECTURE.md and docs/protocol.md were not edited, per P28.

Architecture: Add viewport/tools/line_tool.gd, the first context-only tool (uses_main false, no Main access), L / Line / Line (L), order 37. It constructs a saved line op per segment, supports click chains and single press-drag-release, typed lengths along the cursor direction, Esc and closing at the start. ToolContext.view.register_line passes a deep copy; model.lines_on returns filtered snapshots with ids. Presenter owns loose_lines, saved segment drafts, optional polygon profiles and open/undo/redo reconstruction. Inference snaps to line endpoints, midpoints and edges. New files are discovered by the existing tool/op/test registries.
Architecture: Add worker/line.py LineActions: op_line, polygon_face, region_face and native_region. Each segment is a fully constrained native Sketcher line tagged SSLineId, grouped in Lines; a simple closed outline also produces a Part::Feature profile tagged RectId and SSRole=line-profile. Existing r counters and target.rect support polygon profiles. Self-crossing chains remain drawings, with their bounded cells found by the viewport. Native region pushes create a face base and Part::Extrusion, then the existing join/cut or separate board, including definition-frame conversion on linked/mirrored stock.
Architecture: Wire protocol increments 4 to 5 on both sides. New line payload: id, type=line, existing Plane, end (world-mm 3-vector), optional outline (ordered world-mm polygon, no repeated final vertex), optional snap_start/snap_end booleans. These flags preserve explicit geometry-snap intent across the existing 0.1 mm difference between native-edge and face tessellations; unsnapped free endpoints retain 0.001 mm tolerance. Line anchors and all later points are projected onto the source geometry plane, avoiding physics-hit float offsets.
Architecture: New pure viewport/regions.gd splits planar intersections, welds at native tolerance using spatial buckets, cancels subdivided internal boundaries, prunes dangling branches and walks bounded half-edges. It classifies holes, bridges/triangulates them, and finds the cell containing the cursor. Presenter.drawn_region builds the hover region; Push/Pull previews it immediately and sends optional target.region={outline, holes, normal, lines}, with full-precision world-mm points and saved line ids. With target.face or target.rect it must fit that source; alone it is free closed stock. Main's rejection dependencies include region.lines. A changed region bypasses whole-stock resizing and plane fits; an unsplit source keeps its original exact profile/stock path.
Architecture: Worker validates coplanarity, simple outlines, holes, normal, source containment and drawing references. Straight boundaries extrude the submitted polygon. For curved source edges, native_region refines the already-selected preview cell with native face slices along saved drawing lines, preserving exact arcs; symmetric area discrepancy is bounded by the existing export deflection/circle preview approximation. One push_pull op still owns the edit and undo transaction. test_regions.gd is auto-discovered; scenario/99_regions.py exports its actual predictions for native comparisons.

For the integrator: Apply the Architecture lines to the responsibilities, native-model/state and protocol sections at merge (P28); retain/renumber wire version 5 per A35. Update the I49/I51/I58 code-location cells to the implemented T82 paths. No featuretest.sh registration is needed after H057.

Result: 0c1c9d3; both stage gates pass (219 then 232 UI checks, all feature tests and full tests, zero known failures); added context-only Line chains and saved drawings, closed polygon profiles, immediate split-face regions with holes, and native region Push/Pull preserving exact curved boundaries.
