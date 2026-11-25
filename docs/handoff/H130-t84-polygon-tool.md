### H130 — T84 step 2: Polygon tool (toolbar button without hotkey, exact FreeCAD sketch polygon)

Author: Gemini (integrator, gemini-cedar-1124-2201) | Date: 2026-11-24 | Status: queued (after H129) | For: either

References: T84, T81, I49, I64, Q33, A35.

Touches: viewport/tools/polygon_tool.gd (new), viewport/measure_box.gd, viewport/presenter.gd, viewport/main.gd (`PROTOCOL_VERSION`), worker/polygon.py (new), worker/model.py, worker/push.py, worker/serve.py (`PROTOCOL_VERSION`), viewport/tests/quick/registry.gd, viewport/tests/quick/polygon.gd (new), worker/scenario/99_polygon.py (new).

Reading path:
1. `viewport/tools/circle_tool.gd` — exact centre-and-radius profile tool pattern to mirror.
2. `viewport/measure_box.gd` (lines 265–305) — where `tool in ["rect", "circle", ...]` routes typed input.
3. `viewport/presenter.gd` (`register_rect`, `circle_geometry`, lines 438–535) — profile draft tessellation and registration.
4. `worker/circle.py` and `worker/model.py` (`HANDLERS`) — exact FreeCAD `Sketcher::SketchObject` profile creation and `RectId`/`OnBody` convention.
5. `worker/push.py` — how `target.rect` extrudes/cuts a sketch profile (`Circle` / `Polygon`).

Today (verified 2026-11-24 on `main`, pre-H129):
- `viewport/tools/circle_tool.gd` defines `TOOL := {"id": "circle", "label": "Circle", "tip": "Circle (C)", "key": KEY_C, "order": 35, "show_links": true}` and emits `{"id": rid, "type": "circle", "plane": plane, "radius": radius}`.
- `viewport/measure_box.gd` (line 275) routes typed input for `tool in ["rect", "circle", "line", "arc", "push", "move"]`.
- `worker/circle.py` creates a constrained `Sketcher::SketchObject` (`Circle`) with `RectId=rid, OnBody=on` in the `Rectangles` group so Push/Pull extrudes or cuts it via the existing `target.rect` path.
- `PROTOCOL_VERSION` will be `14` after H129 merges; adding `"polygon"` op bumps it by +1 (to `15`) on both sides (A35).

Request:
1. **Polygon tool (`viewport/tools/polygon_tool.gd`)**:
   - `TOOL := {"id": "polygon", "label": "Polygon", "tip": "Polygon", "key": KEY_NONE, "order": 36, "show_links": true}` (toolbar button next to Circle, no hotkey per I64/Q33).
   - Default `sides := 6` (valid integer range `3..64`).
   - Gesture: click centre on ground or a face (same snap & `edit_blocked` checks as `circle_tool.gd`), move to set circumradius (and optionally orientation), click (or press-drag-release) to finish.
   - Typed input (wire `"polygon"` in `viewport/measure_box.gd` too):
     - Typing `Ns` (e.g. `8s`, `3s`, `12s`) + Enter before or during a gesture sets `sides = N` (ignoring values `< 3` or `> 64`), updating the live preview and hint/VCB.
     - Typing a positive length + Enter during a gesture commits with that radius.
   - Emit op: `{"id": rid, "type": "polygon", "plane": plane, "radius": radius, "sides": sides}` (with optional `"center": [0, 0]` default).
2. **Viewport draft (`viewport/presenter.gd`)**:
   - Handle `op["type"] == "polygon"` alongside `"circle"` in `register_rect()` (and draft rebuild/lookup paths), tessellating an exact `sides`-gon (`polygon_geometry(center, normal, radius, sides)`) with fill triangles and outline edges.
3. **FreeCAD exact sketch regular polygon (`worker/polygon.py`, `worker/model.py`, `worker/push.py`)**:
   - Create `worker/polygon.py` (`PolygonActions`, mixed into `Model` like `CircleActions`), implementing `op_polygon(self, op)`:
     - Validate `radius >= TOL` and `isinstance(sides, int)` with `3 <= sides <= 64` (raise `OpError` otherwise).
     - Build an exact constrained regular polygon in a `Sketcher::SketchObject` (`Polygon`) using `ProfileLib.RegularPolygon.makeRegularPolygon(sketch, sides, V(0, 0, 0), V(radius, 0, 0), False)` (or equivalent constrained `Part.LineSegment` + construction circle + `Coincident`/`Equal`/`PointOnObject`/`Radius` constraints if `ProfileLib` is unavailable in headless FreeCAD), placed with `App.Placement(center, rotation_from(x, y, n))`, with `RectId=rid, OnBody=on` in `Rectangles`.
   - Register `"polygon": "op_polygon"` in `Model.HANDLERS` (`worker/model.py`).
   - Verify Push/Pull (`worker/push.py`) extrudes a ground polygon into a solid prism and cuts a face-drawn polygon into a board cleanly (matching `circle`).
   - Bump `PROTOCOL_VERSION` by +1 in both `worker/serve.py` and `viewport/main.gd` (A35).

Checks:
- `worker/scenario/99_polygon.py`: create a 6-sided and an 8-sided polygon, verify exact sketch geometry and `sides` edges, extrude one into a board and cut one into a board, and verify invalid sides (`2`, `100`) or zero radius raise `OpError`.
- `viewport/tests/quick/polygon.gd` (registered in `viewport/tests/quick/registry.gd`): activate Polygon tool, verify default 6 sides and `KEY_NONE`, draw a 6-sided polygon and confirm in FreeCAD, type `8s` + Enter and draw an 8-sided polygon, and Push/Pull it into a board.
- Include `Architecture:` lines in your response noting the new `polygon` op, `worker/polygon.py`, `viewport/tools/polygon_tool.gd`, and `PROTOCOL_VERSION` bump (P28).
