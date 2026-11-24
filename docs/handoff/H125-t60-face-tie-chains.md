### H125 — T60: chains of face ties (a board tied to a board that is itself tied)

Author: Gemini (integrator, gemini-cedar-1123-1844) | Date: 2026-11-23 | Status: open | For: either

References: T60, T14, I26b, I40, I41, A35.

Touches: worker/plane_fit.py, worker/serve.py (`PROTOCOL_VERSION`), worker/test_properties.py, viewport/main.gd (`PROTOCOL_VERSION`), viewport/property_panel.gd (`pick_reference`, `_preview`), viewport/tools/push_tool.gd (`_edge_inference`, `_choose_face`), viewport/tests/quick/properties.gd. Not worker/push.py or worker/model.py (if a chain update needs a touch there, ask with `job.py wait --scope`).

Why: I26b / I40 specify that face-tie changes ripple through chains (A ← B ← C: moving or resizing A moves B's fitted end, which moves C's fitted end), while rejecting cycles and keeping the last valid shape when an upstream board is deleted or moved past a start end. Today T53 forbids picking a fitted board as a target on both the worker and viewport sides.

Today (checked 2026-11-23):
- `worker/plane_fit.py`:
  - `apply()` (~158) refuses a fitted target: `hasattr(target.Tip, 'SSStock')` raises `ValueError('Pick a face on a different rectangular board')`.
  - `update()` (~130) detaches when `hasattr(target.Tip, 'SSStock')` is true (`Reference unavailable · last geometry retained`).
  - `geometry(source, target, axis, face, mode, reverse=False)` (~39–62) computes the target plane strictly from `stock(target)`'s unfitted box sizes, never from `fitted_end(target)` (which gives the world `(outward_normal, point)` of a fitted board's fitted end — including sloped Slice ends!).
  - `snapshot(board)` (~28–36) exports `stock(board)`'s unfitted `origin`, `axes`, `sizes` plus `fitted`, `reverse`, `linked_axis`, `result` (read by both `worker/session.py` for `bodies.json` `stock_frame` and `worker/object_properties.py` `inspect()`). It does not yet export the fitted end's actual face/normal/point.
  - `_inputs()` (~71–86) compares `stock(target)` without `fitted_end(target)` / `SSFitCorners`, and `refit_changed()` (~98–122) iterates `pending` without guaranteeing that an upstream fitted board updates before its downstream dependent when both are in `pending`.
- `viewport/property_panel.gd`: `pick_reference()` (~263) rejects `data.boards[target].fitted`, and candidate planes / `_preview()` compute target planes only from `b.origin` / `b.axes` / `b.sizes`.
- `viewport/tools/push_tool.gd`: `_edge_inference()` (~220) returns early if `target.fitted` is true, and computes candidate target planes only from `target.origin` / `target.axes` / `target.sizes`.
- `PROTOCOL_VERSION` is 12 in `worker/serve.py` and `viewport/main.gd`.

Request:
1. **Worker (`worker/plane_fit.py`)**:
   - Allow fitting a board to a rectangular board that is itself fitted (removing the `hasattr(target.Tip, 'SSStock')` refusal in `apply()` and `update()`).
   - **Cycle rejection**: in `apply()`, walk `target -> target.Tip.SSTargetId -> ...` (stopping on empty/missing/visited); if `board.BodyId` is reached, raise `ValueError('This fit would create a cycle')` so circular chains (`A -> B -> A`, `A -> B -> C -> A`) are cleanly rejected before mutating anything.
   - **Target plane on a fitted target**: add a helper that resolves `(point, outward_normal)` for `(target, face)`:
     - When `target` is fitted (`hasattr(target.Tip, 'SSStock')`) AND `face` is `target`'s fitted end face (`2 * target.Tip.SSAxis + (0 if getattr(target.Tip, 'SSReverse', False) else 1)`), use `fitted_end(target)` (the actual world outward normal and point, which works for Butt, Fully reach, *and* sloped Slice ends!).
     - Otherwise (any of the other 5 faces, or an unfitted target), use `stock(target)`'s plane as today.
     - Keep `geometry()` accepting either stock-based or fitted target planes cleanly (and compute the `SSFitResult` face-frame angles from that actual outward normal so sloped fitted targets report accurate angles).
   - **Deterministic chain propagation**:
     - Include `fitted_end(target)` (or `tuple(target.Tip.SSFitCorners)` when fitted) in `_inputs()` so moving an upstream board marks downstream boards' inputs changed.
     - In `refit_changed()`, ensure topological order: never update a tip while its `SSTargetId` is also still in `pending` (unless a defensive cycle guard triggers, in which case break cleanly). Updating upstream boards before downstream boards guarantees `A -> B -> C` settles in a single pass with `C` seeing `B`'s new `SSFitCorners`.
     - If an upstream move makes any link in the chain invalid (e.g. target plane moves behind start end), `update()` raises `ValueError` and the transaction rolls back cleanly (I26b / I40).
     - If an intermediate board `B` in `A <- B <- C` is deleted, `C`'s `update()` detaches `C` with `'Reference unavailable · last geometry retained'` and preserves `C`'s last geometry.
   - **Snapshot & protocol (A35)**:
     - In `snapshot(board)`, when `board` is fitted and `fitted_end(board)` is not `None`, include `"fitted_end": {"face": 2 * tip.SSAxis + (0 if getattr(tip, 'SSReverse', False) else 1), "normal": list(n), "point": list(pt)}` (else omit or `None`).
     - Bump `PROTOCOL_VERSION` from 12 to 13 in both `worker/serve.py` and `viewport/main.gd` (because `bodies.json` `stock_frame` and `inspect` gain `fitted_end`).
2. **Viewport (`viewport/property_panel.gd`, `viewport/tools/push_tool.gd`)**:
   - Allow picking/inferring a fitted board as the target (drop the `target.fitted` / `data.boards[target].fitted` guard; keep the `src.fitted` guard on pushing an already-fitted source face as today).
   - When evaluating candidate faces on a target that has `fitted_end`, replace the plane `(plane_point, outward_normal)` for `face == fitted_end.face` with `fitted_end.point` and `fitted_end.normal` (in both `push_tool.gd` `_edge_inference()` and `property_panel.gd` `pick_reference()` / `_preview()`), so hovering or clicking a fitted board's fitted end (even a sloped Slice end!) previews and commits to its real end plane.
   - Do not offer a fit onto a target that would create a cycle in `property_panel.gd`? Keep the worker's cycle check as the source of truth (so a cycle attempt gets the worker's rejection cleanly; if `property_panel.gd` checks or lets the worker reject, either is fine — note which you did).

Cases that must still work:
- All existing plane-fit, edge-fit, detach, undo/redo, and reopen checks in `worker/test_properties.py` and `viewport/tests/quick/properties.gd`.
- Full gate (`tools/gate.sh`) with no change to `tests/reference/`.

Checks (new, named):
- In `worker/test_properties.py`:
  1. 3-board chain `A <- B <- C` (where `C` is tied to `B`'s fitted end, and `B` is tied to `A`): moving `A` updates both `B` and `C` to exact expected volumes/bounds, regardless of op/object order; undo restores both; save + reopen preserves both ties and keeps following further moves of `A`.
  2. Chain through a sloped `Slice at plane` target (`B` sliced to a tilted `A`, `C` fitted to `B`'s sloped fitted end): `C` meets `B`'s actual sloped plane and follows when `A` moves.
  3. Direct (`A -> B -> A`) and 3-board (`A -> B -> C -> A`) cycles are rejected with an error and leave prior fits intact.
  4. Moving `A` past `B`'s start rejects the move and leaves `A`, `B`, and `C` at their last valid geometry.
  5. Deleting intermediate `B` detaches `C` with `'Reference unavailable · last geometry retained'` while keeping `C`'s last geometry.
- In `viewport/tests/quick/properties.gd`:
  1. Push/Pull edge-inference (or Properties link) onto a fitted board `B`'s fitted end creates a chain `A <- B <- C`, and moving `A` updates both `B` and `C` on screen.

Reading path: `worker/plane_fit.py` (`stock`, `snapshot`, `geometry`, `_inputs`, `refit_inputs`, `refit_changed`, `update`, `apply`, `fitted_end`) → `worker/model.py` (where `refit_inputs` / `refit_changed` run around every op) → `viewport/property_panel.gd` (`pick_reference`, `_preview`) → `viewport/tools/push_tool.gd` (`_edge_inference`, `_choose_face`) → `worker/test_properties.py` (lines 97–205) → `viewport/tests/quick/properties.gd`.

Run `tools/featuretest.sh` while building, quick test after viewport changes, then `python3 tools/job.py test`. End your response with `Architecture:` lines (for `worker/plane_fit.py`, `docs/protocol.md` version 13 + `stock_frame.fitted_end`, `push_tool.gd`, `property_panel.gd`), `Follow-up:` lines for leftovers, and a `Result:` line.
