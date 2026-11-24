### H139 — T125: Fix Pull/autosave lag (TechDraw-on-autosave stall, .FCBak/.saving clutter, and Push/Pull frame caching)

Author: Gemini (integrator, gemini-cedar-1124-0100) | Date: 2026-11-24 | Status: open | For: either

References: T125, G01, A24, A29, A32, A38.

Touches: worker/session.py (`_load_file`, `reload_outside`, `save`, `_write`), worker/serve.py (`run_sync`, `save_pending`), worker/test_generations.py, worker/test_serve.py, viewport/tools/push_tool.gd (`_push_hover`, `_push_drag`, `_preview_push`, `coplanar_region`), viewport/tests/quick/push.gd. Not `worker/serve.py` (`PROTOCOL_VERSION`) or `viewport/tools/push_tool.gd` (`_edge_inference`, `_choose_face`) — those are held by H125 (P45).

Why: William's real-world test file (`models/model.FCStd`, `worker.log`) exposed two concrete causes of Pull lag and file clutter:
1. **Worker autosave stalls (1.7 s per save on a 4-hole board, up to 54 s on an 8× array):** Once a model ever had a TechDraw page (from pressing Drawing `D` once), `Session._load_file()` (`worker/session.py:381`) latches `self.drawing = True` forever. Every 0.25 s autosave then reopens `model.saving.FCStd` in FreeCAD, builds a 4-view TechDraw projection (`Front`, `Top`, `Right`, `Iso`), runs `TechDraw.viewPartAsSvg()`, and calls `d2.save()` — blocking the single-threaded worker loop while subsequent pulls wait, creating FreeCAD `.FCBak` backup files (`model.saving.*.FCBak`), and leaving `Document.Label = 'model.FCStd.saving'`.
2. **Viewport Push/Pull per-frame work:** `_push_hover` recomputes O(N) `coplanar_region` + `drawn_region` on every mouse-move event even when still over the same face, and `_push_drag` rebuilds `_preview_push` (`Geo.prism` + `Geo.feature_edges` + `ArrayMesh`) on every mouse-move event even when the push distance / fit mode hasn't changed.

Today (checked 2026-11-24):
- `worker/session.py`:
  - `_load_file()` (~378–381) does `self.drawing = drawing or self.drawing` where `drawing = remove_drawing_pages(doc)` (~388). `reload_outside()` (~571) does the same (`staged.drawing = drawing or self.drawing`).
  - `save(outdir)` (~794–829) unconditionally calls `write_glb(self.model, ...)` (~801) on every save (even when only units/metadata changed and `model.glb` already exists) and calls `_write(g, outdir)`.
  - `_write(g, outdir)` (~831–861): if `self.drawing` is true, opens `tmp` (`model.saving.FCStd`), adds TechDraw page + views, writes `views.json`, and calls `d2.save()` (which triggers FreeCAD's backup `.FCBak` writer if enabled and leaves `Label` set to the `.saving` stem!). It never clears `self.drawing = False` afterwards.
  - Note: `worker/test_native.py` section Q (~530–544) explicitly sets `s.drawing = True`, calls `s.save(...)`, asserts `"TechDraw" in Document.xml`, then reopens `Session(qp)` and checks that TechDraw objects are stripped from the live doc.
- `worker/serve.py`:
  - `run_sync()` (~19–20) sets `if req.get("drawing"): session.drawing = True`.
- `viewport/tools/push_tool.gd`:
  - `_push_hover()` (~114–134) runs `coplanar_region()` and `drawn_region()` on every `mouse_moved` frame.
  - `_push_drag()` (~178–200) calls `_preview_push(state["dist"])` on every `mouse_moved` frame without checking if `dist` and `edge_fit` changed since the last preview.

Request:
1. **Worker (`worker/session.py`, `worker/serve.py`)**:
   - **One-shot drawing export (never latch on open or across autosaves):**
     - In `_load_file()` and `reload_outside()`, still call `remove_drawing_pages(doc)` so opening a file with a TechDraw page stays crash-safe (Test Q), but do **not** set `self.drawing = True` on open/reload (opening a file that was once exported must never turn every future autosave into a 1.7 s TechDraw render).
     - In `save()` / `_write()`: when `self.drawing` is `True` (explicitly requested by `req.get("drawing")` or test code like Test Q), write the TechDraw page + `views.json` on that save, and clear `self.drawing = False` once the save succeeds (keep `self.drawing = True` if `_write` raises so a retry still writes it!).
   - **Clean `.FCStd` label & no `.FCBak` clutter:**
     - Ensure `saveCopy(tmp)` / `d2.save()` never leaves `.FCBak` files beside `model.FCStd` (disable FreeCAD backup file creation in the worker via `App.ParamGet("User parameter:BaseApp/Preferences/Document").SetBool("CreateBackupFiles", False)` before saving, or clean up any `tmp` backup written during `d2.save()`).
     - Keep the saved document's `Label` as the real model stem (e.g. `os.path.splitext(os.path.basename(self.path))[0]`), never `model.saving` or `model.FCStd.saving`.
   - **Skip redundant `model.glb` rewrites when geometry/materials are unchanged:**
     - Track a lightweight signature of the model's exported geometry/materials (or mark a `glb_dirty` flag set when `sync()`/`_open_existing()`/`reload_outside()` changes geometry, cleared after `write_glb` succeeds). In `save(outdir)`, skip `write_glb` if `glb_dirty` is false AND `os.path.exists(glb_path)` — so pure metadata/units saves don't re-serialize a multi-MB GLB.
2. **Viewport (`viewport/tools/push_tool.gd`)**:
   - **Cache `_push_hover`:** remember the last hover key `(body, rect, quantized normal + plane offset, op_count/revision)` (invalidate on `reset()`, sync/model change, or when `hit` changes to a different body/rect/face plane) so moving the mouse across the same face does not re-run `coplanar_region` + `drawn_region` + `ctx.view.preview` on every frame.
   - **Avoid redundant `_preview_push` rebuilds during `_push_drag`:** track the last previewed `(dist, edge_fit)` in `state` (cleared on `reset()` / `click()` / `key()`); if neither changed since the previous mouse-move, skip rebuilding `Geo.prism` + `Geo.feature_edges` + `ctx.view.preview`.
   - Keep `coplanar_region` exact (same triangle set and flood-fill result; any micro-optimization must not alter results).

What can fail (P42 — each case gets a named check in `worker/test_generations.py` / `worker/test_serve.py`):
1. **Explicit Drawing export (`req.get("drawing") == True`):** writes `views.json` and embeds the TechDraw page in the saved `.FCStd` on that save, then resets `self.drawing = False` so the very next ordinary edit + autosave does **not** re-run TechDraw or rewrite `views.json`.
2. **Reopening a `.FCStd` that contains a TechDraw page:** strips TechDraw from the live doc (preserving `worker/test_native.py` section Q) and leaves `self.drawing == False`, so subsequent autosaves stay fast and leave no `.FCBak` files.
3. **Failed save during an explicit drawing export (e.g. read-only dir):** rolls back `rev` and `Meta` cleanly as today AND keeps `self.drawing == True` so the next successful save/retry still exports the drawing.
4. **Saved document `Label` and `.FCBak` cleanliness:** after both an ordinary autosave and an explicit drawing save, `Document.xml`'s `Label` is the model's real name (not `*.saving*`), and zero `*.FCBak` files exist in the model directory.
5. **GLB write skipping vs refresh:** saving after a pure `set_units` change does not rewrite `model.glb` if it already exists, whereas saving after a geometry/material edit (or when `model.glb` is missing) does write an up-to-date `model.glb`.
6. **Viewport hover/drag cache invalidation (`viewport/tests/quick/push.gd`):** after a push or undo modifies a board's face, hovering the updated face recomputes the new region (never serves stale cached triangles), and dragging across distinct distances updates the preview accurately.

Cases that must still work:
- `worker/test_native.py` (especially section Q!), `worker/test_generations.py`, `worker/test_outside_save.py`, `worker/test_floor_copy.py`, `worker/test_serve.py`, `viewport/tests/quick/push.gd`, `viewport/tests/quick/properties.gd`, and the full gate with no change to `tests/reference/`.

Reading path: `worker/session.py` (`_load_file`, `_open_document`, `reload_outside`, `save`, `_write`) → `worker/serve.py` (`run_sync`, `save_pending`) → `worker/test_native.py` (lines 530–545) → `worker/test_generations.py` → `viewport/tools/push_tool.gd` (`_push_hover`, `coplanar_region`, `_push_drag`, `_preview_push`).

Run `tools/featuretest.sh` and `tools/quicktest.sh` while building, then `python3 tools/job.py test`. End your response with `Architecture:` lines (if `Session.drawing` one-shot lifecycle changes `ARCHITECTURE.md`), `Follow-up:` lines for leftovers, and a `Result:` line.
