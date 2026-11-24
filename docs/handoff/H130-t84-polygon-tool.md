### H130 — T84 step 2: Polygon tool (toolbar button without hotkey, exact FreeCAD sketch polygon)

Author: Gemini (integrator, gemini-cedar-1123-1844) | Date: 2026-11-23 | Status: queued (after H129) | For: either

References: T84, I49, I64, Q33.

Touches: viewport/tools/polygon_tool.gd (new), worker/polygon.py (new), worker/model.py, worker/push.py, worker/serve.py (`PROTOCOL_VERSION`), viewport/main.gd (`PROTOCOL_VERSION`), viewport/presenter.gd, viewport/tests/quick/registry.gd, viewport/tests/quick/polygon.gd (new), worker/scenario/99_polygon.py (new).

Why: I64 specifies a dedicated Polygon toolbar button with no keyboard shortcut for now (`KEY_NONE`, Q33), default 6 sides (typed `Ns` like `8s`), drawn from centre and radius, saved as an exact FreeCAD sketch regular polygon (like Circle in `worker/circle.py`), pushable into a board or a cut like a rectangle or circle.

Note for the integrator: recheck this brief against `main` once H129 (T84 step 1) merges before marking it `open` — add exact `Today`, `Request`, `Reading path`, `PROTOCOL_VERSION` bump, and `Checks`.
