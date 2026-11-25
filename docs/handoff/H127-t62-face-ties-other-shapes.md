### H127 — T62: face ties on shapes other than plain rectangular boards

Author: Gemini (integrator, gemini-cedar-1124-2201) | Date: 2026-11-24 | Status: open | For: either

References: T62, T14, T60, T61, I26b, I40, I49.

Touches: worker/plane_fit.py, worker/push.py (`op_push_pull`), worker/test_properties.py, viewport/property_panel.gd, viewport/tools/push_tool.gd, viewport/tests/quick/properties.gd.

Reading path:
1. `worker/plane_fit.py` (`stock`, `face_plane`, `snapshot`, `geometry`, `apply`, `update`, `push_fitted_end`) — currently requires `Part::Extrusion` of `Part::Plane` for both source and target.
2. `worker/push.py` (`op_push_pull`, lines 131–180 and 240–260) — calls `plane_fit.stock` / `plane_fit.apply` when `edge_fit` is sent.
3. `viewport/tools/push_tool.gd` (`_edge_inference`, lines 240–335) — picks target board faces from `ctx.model.stock_frame(body)`.
4. `viewport/property_panel.gd` (`_target_face_plane`, `pick_reference`, `_preview`) — picks target faces from `data.boards`.

Today (verified 2026-11-24 on `main`, post-H126 and post-H141):
- `worker/plane_fit.py` `stock(board)` returns `None` unless the board's base is `Part::Extrusion` of `Part::Plane`.
- Because `stock()` returns `None` for extruded circles, extruded closed line/arc profiles, and boards that already have cuts/pockets (`Part::Cut`), neither Push/Pull's `edge_fit` nor Properties' "Pick face…" can tie a face *to* or *from* a non-rectangular or cut board.
- `worker/plane_fit.py` `face_plane(target, face)` and `snapshot(board)` rely strictly on `stock(target)`'s 6 box faces (`0..5`).

Request:
1. **Extend `worker/plane_fit.py` to support non-rectangular & cut boards**:
   - **As a target**: allow any board with planar faces (circles, closed line/arc extrusions, boards with cuts/pockets) to serve as a face-tie target. Add a helper (e.g. `planar_faces(board)` / generalize `face_plane(target, face)` and `snapshot(board)`) that still returns the 6 canonical stock faces (`0..5`) for plain rectangular stock, AND for non-rectangular or cut boards exposes planar faces (using `BoundBox` / planar `Face` normal + point, or a stable planar-face descriptor `(normal, point)` / face index) so `face_plane()` and `refit_inputs()` resolve the target plane live when the target board moves or resizes.
   - **As a source**: allow extruding or pushing the extrusion end of a non-rectangular profile (`Part::Extrusion` of a `Sketcher::SketchObject` circle or closed line/arc wire, as well as a rectangular board with cuts/pockets whose underlying `Part::Extrusion` is still reachable along its extrusion axis) to tie its extruded length (`LengthFwd`) to a target board's planar face (`Butt to plane`, `Slice at plane`, `Fully reach plane`), updating automatically via `refit_changed()` when the target moves, and detaching cleanly when pushed again (`push_fitted_end` / `replace`, I26b/I40).
   - Keep plain rectangular stock and linked copies (H126/T61) behaving identically.
2. **Viewport support (`viewport/tools/push_tool.gd` and `viewport/property_panel.gd`)**:
   - Allow Push/Pull edge-inference (`_edge_inference`) and Properties (`pick_reference`, `_preview`) to target planar faces on non-rectangular and cut boards (and tie the extrusion axis of a circular / line-arc / cut board to another board's planar face), while still rejecting self-targets, sibling targets sharing the same definition, and cycles.

Checks:
- `worker/test_properties.py`:
  - Tie a rectangular board's end to a planar face of a cut board and a circular board; moving the target updates the tied board live (`refit_changed`).
  - Tie a circular (or closed-line) extruded board's end to another board's face; moving the target updates the circular board's extrusion length live; pushing the tied end detaches it cleanly.
  - Existing plain-rectangular and linked-copy (H126) plane-fit tests all stay green.
- `viewport/tests/quick/properties.gd`:
  - Verify Properties "Pick face…" can tie a board to a cut or circular board's planar face and updates when the target moves.
  - All existing `properties.gd` checks stay green.
