### H129 — T84 step 1: Rotated Rectangle (R again toggles Rectangle and Rotated Rectangle)

Author: Gemini (integrator, gemini-cedar-1124-2201) | Date: 2026-11-24 | Status: open | For: either

References: T84, I49, I64, I60, I65, A35.

Touches: viewport/tools/rect_tool.gd, viewport/presenter.gd (`register_rect`), worker/push.py (`op_rect`), worker/serve.py (`PROTOCOL_VERSION`), viewport/main.gd (`PROTOCOL_VERSION`), worker/test_native.py, viewport/tests/quick/rect.gd.

Reading path:
1. `viewport/tools/arc_tool.gd` (`reset`, `tip`, `hint`, `key`, `vcb_label`) — the I60 mode-toggle pattern to match.
2. `viewport/tools/rect_tool.gd` (`click`, `release`, `typed`, `_amend_last_rect`, `_rect_drag`, `_preview_rect`, `commit_rect`) — current single-mode Rectangle tool.
3. `viewport/presenter.gd` (`register_rect`, lines 438–472) — viewport draft mesh construction from `rect` op.
4. `worker/push.py` (`op_rect`, lines 117–129) — FreeCAD `Part::Plane` creation from `rect` op.

Today (verified 2026-11-24 on `main`):
- `viewport/tools/rect_tool.gd` draws only axis-aligned rectangles using `Geo.plane_basis(n)` and emits `{"id": rid, "type": "rect", "plane": plane, "corner": [minf(0, du), minf(0, dv)], "size": [absf(du), absf(dv)]}`. After placing a rectangle, typing `width, height` amends it in place (`_amend_last_rect`, I65).
- `viewport/presenter.gd` `register_rect(op)` always computes `b = Geo.plane_basis(n)` for `rect` ops.
- `worker/push.py` `op_rect(self, op)` unpacks `origin, x, y, n, on = self.plane_from(op["plane"])` and calls `self.plane_feature(origin + x * u + y * v, x * w, y * h, rid)`.
- `PROTOCOL_VERSION` is `13` in both `worker/serve.py` and `viewport/main.gd`.

Request:
1. **Mode toggle (I64, matching Arc's I60 pattern)**:
   - Pressing `R` again while `rect` is active (no Ctrl/Meta/Alt, and `ctx.ui.typed_text().is_empty()` so unit letters while typing aren't stolen) toggles `rotated` between `false` (Rectangle, default) and `true` (Rotated Rectangle).
   - Toggling clears any in-progress gesture (and clears `last_oid`/`last_meta` so typing won't amend a prior rectangle), hides the marker, and refreshes hint, measurements, and tip.
   - `reset()` resets `rotated = false` when `ctx != null and not ctx.ui.tool_active("rect")` so switching away and back always starts in regular Rectangle.
   - `tip()` returns `"Rotated Rectangle"` when `rotated` else `"Rectangle"`.
   - `hint()` returns:
     - Regular: `"Rectangle: click a face or the ground, then click or type  width, height  + Enter; R for Rotated Rectangle"`
     - Rotated: `"Rotated Rectangle: click start, click end of first edge, then click width; R for Rectangle"`
2. **Rotated Rectangle 3-point gesture**:
   - Stage 1 (idle -> edge): first click picks `origin`, `n`, and `on` (same `ctx.pick.snap`, `edit_blocked`, and `on` resolution as regular Rectangle). Moving the pointer previews the first edge line from `origin` to the snapped point on the plane; `vcb_label()` is `"Length"` and `vcb_value()` formats the current first-edge length.
   - Stage 2 (edge -> width): second click (or typing a positive length + Enter while dragging the first edge) locks the first edge: unit `x` along `(end - origin)` projected onto the plane, `y = n.cross(x).normalized()`, and `du = length > 0`. Ignore a click whose distance is below `GEOMETRY_TOLERANCE_MM` (or fails `pointer_distance_ok`) so zero-length edges can't commit. Moving the pointer now previews the full rectangle with width `dv = v.dot(y)` along `y`; `vcb_label()` is `"Width"` and `vcb_value()` formats `absf(dv)`.
   - Stage 3 (commit): third click (when `absf(dv)` passes `pointer_distance_ok`) or typing a positive width + Enter (or `length, width` + Enter) commits the rotated rectangle.
   - After-the-fact typing (`_amend_last_rect`, I65): typing `length, width` right after placing a rotated rectangle amends it in place, keeping its `origin`, `n`, `x`, `y`, and `du`/`dv` signs.
   - Regular Rectangle mode (click-click, press-drag-release, after-the-fact amend) must remain unchanged.
3. **Op schema, viewport draft, and FreeCAD native `Part::Plane` (`PROTOCOL_VERSION` 13 → 14)**:
   - When committing a rotated rectangle, include `"x": Geo.arr3(x)` on the `rect` op (omit `"x"` for regular axis-aligned rectangles so existing ops/tests are untouched).
   - Bump `PROTOCOL_VERSION` from `13` to `14` in both `worker/serve.py` and `viewport/main.gd` (A35, since `rect` gains optional `"x"`).
   - `viewport/presenter.gd` (`register_rect`): if `op.has("x")`, derive `bx = Vector3(op["x"][0], op["x"][1], op["x"][2])`, project orthogonal to `n` and normalize, and set `by = n.cross(bx).normalized()` instead of `Geo.plane_basis(n)`.
   - `worker/push.py` (`op_rect`): if `op.get("x")` is present, construct `rx` from `op["x"]`, project orthogonal to `n`, raise `OpError("rect x axis is degenerate")` if its length is `< TOL`, normalize `x = rx`, set `y = n.cross(x)` (normalized), and pass `origin + x * u + y * v, x * w, y * h` to `self.plane_feature(...)`. Because `plane_feature` creates a native `Part::Plane`, extruded boards remain ordinary rectangular stock usable by Push/Pull, Properties, and plane fits.

Checks:
- `worker/test_native.py`: add tests verifying `op_rect` with `"x"` creates a rotated `Part::Plane` with the expected corner positions and axes, extruding it produces rectangular stock (`plane_fit.stock` succeeds), and a degenerate `"x"` (zero or parallel to `n`) raises `OpError`.
- `viewport/tests/quick/rect.gd`: add checks for `R` toggling between Rectangle and Rotated Rectangle (hint and tip update, switching tool resets to Rectangle), drawing a 3-click rotated rectangle on the ground (draft vertices rotated, op has `"x"`, confirmed in FreeCAD), typing first-edge length and perpendicular width, and after-the-fact `length, width` amend preserving the rotated axes. All existing `rect.gd` checks stay green.
- Include `Architecture:` lines in your response noting the optional `"x"` field on `rect` ops and `PROTOCOL_VERSION` 14 (P28).

**Response (Gemini, 2026-11-24):**
- Branch: `gemini/h129-t84-rotated-rectangle`
- Architecture: `rect` op gains optional `"x": [x, y, z]` unit first-edge vector (omitted for regular axis-aligned rectangles); `viewport/presenter.gd` (`register_rect`) and `worker/push.py` (`op_rect`) project `"x"` orthogonal to `n` and derive `y = n.cross(x)`.
- Architecture: bumped `PROTOCOL_VERSION` from `13` to `14` in `worker/serve.py` and `viewport/main.gd` for the `rect` `"x"` field (A35).
- Architecture: `viewport/tools/rect_tool.gd` now carries `rotated` mode state (`expects_pair()` / `accepts_pair()`) read by `viewport/measure_box.gd` (`apply()`).
