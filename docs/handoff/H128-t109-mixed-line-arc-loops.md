### H128 — T109: closed loops of mixed lines and arcs form pushable faces with exact arcs

Author: Gemini (integrator, gemini-cedar-1123-1844) | Date: 2026-11-23 | Status: open | For: either

References: T109, I49, I51, I60.

Touches: worker/line.py, worker/push.py (`op_push_pull` region branch), worker/scenario/99_mixed_loops.py (new), viewport/regions.gd, viewport/presenter.gd (`register_line`, `forget_op`, `rebuild_rect_drafts`, `drawn_region`, `reset`, and a closed-loop draft helper), viewport/test_regions.gd, viewport/tests/quick/arc.gd. Not viewport/tools/push_tool.gd (its `_push_hover` already calls `ctx.model.drawn_region` for both ground and face hits; ask with `job.py wait --scope` if it needs a change).

Why: I49 / I51 / I60 say drawings that meet end-to-end and close (lines and arcs mixed, on the ground or on a face) make a pushable face, and arcs stay exact FreeCAD curves (only the viewport tessellates them). Today two things are missing: (1) on the ground (no existing board face), `worker/push.py` builds a faceted `region_face` and skips `native_region`, turning arcs into straight segments in FreeCAD; (2) closing a loop with an arc or a second line chain shows no translucent profile face in the viewport until Push/Pull hovers inside it.

Today (checked 2026-11-23):
- `viewport/regions.gd`: `find(source, lines, normal, point)` already accepts empty `source` (ground) and faceted arc polylines (`line.get("pts", ...)`), returning `{outline, holes, tris, area}` for the cell containing `point`. It has no helper that returns *all* closed cells of a planar arrangement (for showing closed loop fills in the viewport).
- `viewport/presenter.gd`: `register_line(op)` stores lines and arcs in `loose_lines`, draws blue edges in `drafts["line:" + op.id]`, and calls `register_rect(op)` only when a single continuous Line click-chain sets `op["outline"]`. Separate chains or mixed line + arc loops show only edges, with no profile fill.
- `worker/push.py` (`op_push_pull`, ~189–207):
  - When `"region" in tgt` with `"face"` or `"rect"`, it calls `self.native_region(source, world_face, tgt["region"])` so arcs stay exact FreeCAD edges.
  - When `"region" in tgt` alone (ground loop), it runs `world_face, n = self.region_face(tgt["region"])` and skips `native_region`, producing a faceted polygon extrusion instead of exact FreeCAD `Part.Circle` / arc edges.
- `worker/line.py` (`native_region`, ~41–71): slices `source` with `drawings` (`Part.Arc` edges kept exact; `Part.Line` edges extended across `span` and re-merged with `removeSplitter()` after picking pieces matching `predicted`).

Request:
1. **Worker (`worker/line.py`, `worker/push.py`)**:
   - In `worker/push.py`, when `"region" in tgt` with no `"face"` and no `"rect"` (a ground loop), refine `world_face` through `native_region` as well whenever any referenced drawing edge in `tgt["region"].get("lines", [])` is curved (not `Part.Line`): build a planar bounding sheet on the region's plane larger than `predicted` + the referenced drawings' bounding box, and pass that sheet as `source` to `self.native_region(sheet, world_face, tgt["region"])`.
   - Ensure `native_region` handles closed ground loops cleanly:
     - mixed lines + arcs (e.g. a rectangle with one arched end, a D-shape of one line + one arc, a lens of two arcs, a concave/U-shaped loop with arcs, and a loop with an inner closed-loop hole);
     - the resulting extruded FreeCAD solid keeps exact curved edges (`Part.Circle` / circular arc curves, not faceted line segments), survives save + reopen and undo/redo, and still rejects a region whose drawings don't close or refer to a missing line id.
2. **Viewport (`viewport/regions.gd`, `viewport/presenter.gd`)**:
   - Add a pure helper in `viewport/regions.gd` (e.g. `all_faces(lines, normal) -> Array` of `{tris, area}`) that finds all closed bounded faces formed by coplanar `loose_lines` on a plane (ignoring dangling edges, handling holes so a nested loop doesn't double-fill).
   - In `viewport/presenter.gd`, when ground `loose_lines` (`on == ""`) are registered, rebuilt, or forgotten (after `register_line`, `forget_op`, `rebuild_rect_drafts`; cleared on `reset`), refresh a translucent profile fill mesh (using `m.mat_rect`, without replacing `rects` or breaking `target.region` pushing) for closed loops formed by `loose_lines` that aren't already covered by an explicit `line-profile` `rect` draft. That way closing a loop on the ground with mixed lines and arcs immediately shows a face fill, just like a closed Line outline, and Push/Pull hovers and pushes it as a `target.region`.
   - Verify on-face mixed line + arc loops also continue to split the face and push cleanly (join and cut, preserving exact arcs in FreeCAD).

Cases that must still work:
- Existing Line closed-outline profiles (`op["outline"]`), Arc face-splitting, region Push/Pull keeping split profile drafts (H096), `viewport/test_regions.gd`, `worker/scenario/99_regions.py`, `worker/scenario/99_arcs.py`, `worker/scenario/99_tangent_corner.py`, and the full gate with no change to `tests/reference/`.

Checks (new, named):
- `worker/scenario/99_mixed_loops.py`:
  1. Ground loop of 3 lines + 1 arc (arch/tombstone shape) pushed into a board: exact `Part.Circle` edge(s) on the FreeCAD solid (not faceted), expected area/volume, survives undo/redo and save + reopen.
  2. Ground loop of 2 arcs (lens/circle) pushed into a board: exact curved edges on both sides.
  3. On-face loop of lines + arc pushed up (boss) and pushed down (cut pocket/through-hole): exact curved walls in FreeCAD.
  4. Ground loop with an inner mixed-loop hole pushed into a board: valid solid with hole and exact curved edges.
- `viewport/test_regions.gd`:
  1. `Regions.find` and the new `all_faces` helper on a ground loop of 3 lines + 1 arc, a 2-arc lens, dangling tails pruned, and a loop with an inner hole.
- `viewport/tests/quick/arc.gd`:
  1. Draw a closed ground loop of lines + an arc, confirm the closed-loop face fill appears in the viewport, hover and Push/Pull it into a confirmed board, and verify the board appears with the expected height.

Reading path: `viewport/regions.gd` (`_cycles`, `find`) → `viewport/presenter.gd` (`register_line`, `drawn_region`, `register_rect`, `forget_op`, `rebuild_rect_drafts`) → `viewport/tools/push_tool.gd` (`_push_hover`, lines 114–134) → `worker/line.py` (`region_face`, `native_region`) → `worker/push.py` (`op_push_pull`, lines 189–208) → `worker/scenario/99_regions.py` and `worker/scenario/99_arcs.py`.

Run `tools/featuretest.sh` while building, quick test after viewport changes, then `python3 tools/job.py test`. End your response with `Architecture:` lines (for `worker/line.py` / `worker/push.py` ground-loop native arcs and `viewport/regions.gd` / `viewport/presenter.gd` closed-loop fills), `Follow-up:` lines for leftovers, and a `Result:` line.
