### H129 — T84 step 1: Rotated Rectangle (R again toggles Rectangle and Rotated Rectangle)

Author: Gemini (integrator, gemini-cedar-1123-1844) | Date: 2026-11-23 | Status: queued (after H128) | For: either

References: T84, I49, I64, I60.

Touches: viewport/tools/rect_tool.gd, viewport/presenter.gd (`register_rect`), worker/push.py (`op_rect`), worker/test_native.py, viewport/tests/quick/rect.gd.

Why: I64 specifies pressing `R` again while Rectangle is active toggles Rectangle ↔ Rotated Rectangle (click start, click end of first edge, drag perpendicular width; hint and tip name the active mode, matching Arc's I60 toggle). Passing an optional first-edge unit axis `"x"` on the `rect` op keeps rotated rectangles native `Part::Plane` profiles in FreeCAD so extruded boards remain ordinary rectangular stock (usable by Push/Pull, Properties, and plane fits).

Note for the integrator: recheck this brief against `main` once H128 (T109) merges before marking it `open` — verify `PROTOCOL_VERSION` (A35, since `rect` op gains optional `"x"`), exact `Today`, `Request`, `Reading path`, and `Checks`.
