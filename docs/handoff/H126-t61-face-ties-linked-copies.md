### H126 — T61: face ties on linked copies (component definitions and instances)

Author: Gemini (integrator, gemini-cedar-1124-0100) | Date: 2026-11-24 | Status: open | For: either

References: T61, T14, T60 (H125), I26b, I28, I40, I41, A22c.

Touches: worker/plane_fit.py, worker/push.py (`op_push_pull` face-fit, `push_fitted_end`, and `resize_stock` branches), worker/move.py (`op_make_unique`), worker/test_properties.py, viewport/property_panel.gd (`pick_reference`, `_preview`), viewport/tools/push_tool.gd (`_edge_inference`, `_choose_face`), viewport/tests/quick/properties.gd. Not `viewport/tools/push_tool.gd` (`_push_hover`, `_push_drag`, `_preview_push`, `coplanar_region` — held by H139, P45).

Why: I26b and A22c say linked copies (Option-copy / arrays / component instances) share one component definition, so face ties on a linked copy belong to the shared definition: fitting one instance or moving the target updates all instances of that component together, fitting *to* a linked copy's face works like any rectangular board, and Make unique (I28) detaches the unique copy's tie cleanly without disturbing its former siblings.

Today (checked 2026-11-24, after H125 merged):
- `worker/move.py` (`op_make_component`, `as_component`, `copy_body`, ~15–75): when a board is copied, its `App::Part` becomes `SSRole = "definition"` inside `ComponentDefinitions` (`Visibility = False`) and both the original and every copy become `App::Link` objects (`SSRole = "body"`, `BodyId = bid`, `LinkedObject = dfn`, `Placement = instance placement`).
- `worker/plane_fit.py`:
  - `stock(board, feature=None)` (~10–25) checks `if getattr(board, 'TypeId', '') != 'App::Part': return` — so every linked copy (`App::Link`) returns `None`! Neither Push/Pull nor Properties can fit a linked copy or target a linked copy's face.
  - `fitted_face(board)` (~28), `fitted_end(board)` (~250), `snapshot(board)` (~55) all read `board.Tip` and `board.Placement` directly (an `App::Link` has no `.Tip` — its features live on `board.LinkedObject.Tip`, while its world placement is `board.Placement`).
  - `apply(model, op)` (~199) attaches `PlaneFit` onto `board.Tip` and checks cycles by `BodyId` only (not by shared component definition).
  - `refit_inputs(model)` (~125) and `refit_changed(model, before)` (~134) find tips via `owner = tip.getParentGeoFeatureGroup()` and require `owner.BodyId`, which skips component definitions (`SSRole = "definition"`, where live bodies are `App::Link` instances pointing to `owner`).
  - `replace(model, op)` (~235), `push_fitted_end(...)` (~265), `resize_face(...)` (~215), and `_restore(...)` (~285) assume `board` is an `App::Part` with `board.Tip` and return `[board.BodyId]`.
- `worker/move.py` (`op_make_unique`, ~284–313): clones `dfn` via `copyObject(dfn, True)` without detaching an inherited `PlaneFit` tip (`SSTargetId` stays live on the unique board!).
- `worker/push.py` (`op_push_pull`, ~141–167): calls `plane_fit.stock`, `plane_fit.apply`, `plane_fit.fitted_end`, `plane_fit.push_fitted_end`, and `plane_fit.resize_face`.

Request:
1. **Worker (`worker/plane_fit.py`)**:
   - Add a small helper (e.g. `_def(board)`) that returns `(dfn, placement)` for both plain `App::Part` bodies (`(board, board.Placement)`) and `App::Link` instances (`(board.LinkedObject, board.Placement)` when `board.LinkedObject` is an `App::Part`), returning `(None, None)` for anything else (mirrors remain unsupported here; T62 handles non-rectangular shapes).
   - Update `stock(board, feature=None)`, `fitted_face(board)`, `fitted_end(board)`, `face_plane(target, face)`, and `snapshot(board)` to work identically on both `App::Part` bodies and `App::Link` instances (reading `dfn.Tip` / `SSStock` / `SSFitCorners`, transforming by `board.Placement`, and using `board.Label`).
   - Add a helper `_family_bodies(model, dfn)` returning all live body `BodyId`s whose definition is `dfn` (for plain `App::Part`, `[dfn.BodyId]`; for a component definition, every live `App::Link` body whose `LinkedObject == dfn`).
   - **Fitting a linked copy (`apply`, `update`, `refit_inputs`, `refit_changed`)**:
     - Store the `PlaneFit` tip on `dfn` (the shared definition, via `model.set_tip(dfn, tip)`) and add property `SSSourceBodyId` (`App::PropertyString`) recording the driving instance `board.BodyId` (empty for plain `App::Part`).
     - Solve `geometry()` in the driving instance's world frame (`source_obj = bodies.get(tip.SSSourceBodyId)` or fallback to first live instance of `dfn`), write `SSFitCorners` in `source_obj.Placement.inverse()` (definition-local coordinates), so every sibling `App::Link` automatically renders the updated shared `dfn.Tip` solid!
     - **Cycle & self-family rejection in `apply()`**: reject fitting a board to itself OR to another instance of its own shared definition (`_def(board)[0] == _def(target)[0]`, raising `'Pick a face on a different rectangular board'`), and walk `SSTargetId` chains across definitions (checking `_def(cur)[0]` against visited definitions, raising `'This fit would create a cycle'`) so `A_instance1 -> B -> A_instance2` is also caught as a cycle before mutating anything.
     - In `refit_inputs()` and `refit_changed()`: include `PlaneFit` tips whose parent group is either a live `App::Part` body OR a component definition with at least one live `App::Link` instance. For a definition tip, resolve its driving instance (`SSSourceBodyId`, or if that instance was deleted, promote/use a surviving instance or detach cleanly if none remain), run topological waves by definition/body dependencies, and append **all** `_family_bodies(model, dfn)` to `affected` and `changed` so every sibling re-exports and triggers downstream chains!
   - **Detaching, replacing & resizing (`replace`, `push_fitted_end`, `resize_face`, `_restore`)**:
     - Resolve `dfn` via `_def(board)` so typing a new length in Properties (`replace_fit`), pushing a tied end (`push_fitted_end`), or numeric stock-face resizing (`resize_stock`) works on any linked instance and returns `_family_bodies(model, dfn)`.
     - In `worker/push.py` (`op_push_pull` lines 155–167), return the changed BodyId list from `push_fitted_end` / `resize_face` (or `_family_bodies`) rather than only `[board.BodyId]`.
2. **Make unique (`worker/move.py` `op_make_unique`)**:
   - When `copy.Tip` is a `PlaneFit` (`hasattr(copy.Tip, 'SSStock')`), detach the unique copy cleanly (`copy.Tip.SSTargetId = ''`; `copy.Tip.SSFitResult = 'Detached · shape kept'`; clear `SSSourceBodyId` if present) so the unique board keeps its exact current geometry (including sloped Slice ends) while no longer following the target, and its former linked siblings keep their live tie intact!
   - If the instance made unique was the driving `SSSourceBodyId` of the remaining family's `PlaneFit`, reassign `dfn.Tip.SSSourceBodyId` to a surviving sibling instance so the remaining family keeps following the target cleanly!
3. **Viewport (`viewport/property_panel.gd`, `viewport/tools/push_tool.gd`)**:
   - Verify linked copies now receive `stock_frame` (including `fitted_end` when fitted) in `bodies.json` and `inspect_properties`, so Push/Pull edge-inference and Properties `Pick face…` / direct-link work on linked copies as both source and target (and guard against picking a sibling of the same component family if `family` matches — or let the worker's error message reject cleanly; note which you did).

Cases that must still work:
- All existing plain-board and T60 chain plane-fit checks in `worker/test_properties.py`, `worker/scenario/97_plane_fit_refit.py`, and `viewport/tests/quick/properties.gd`.
- Full gate (`tools/gate.sh`) with no change to `tests/reference/`.

Checks (new, named):
- In `worker/test_properties.py`:
  1. Fit one linked copy `b1` (of linked pair `b1`, `b2`) to target `t1`: both `b1` and `b2` update to the fitted length (including Slice mode), moving `t1` updates both `b1` and `b2`, undo restores both, and save + reopen preserves the shared tie.
  2. Fit another board `c1` to a linked copy's face (and to a linked copy's fitted end in a chain `t1 <- (b1, b2) <- c1`): moving `t1` ripples through the linked family to `c1`.
  3. Fitting a linked copy to its own sibling (`b1 -> b2`) or in a cross-sibling cycle (`b1 -> c1 -> b2`) is rejected without mutating anything.
  4. Make unique on `b2` (non-driving) detaches `b2` (keeping its geometry) while `b1` keeps following `t1`; make unique on `b1` (driving instance, when `b2` & `b3` remain) hands driving duty to a surviving sibling so `b2` & `b3` keep following `t1`.
  5. Pushing a linked copy's tied end (`push_fitted_end`) or typing a replacement length (`replace_fit`) detaches and updates all siblings in the family.
- In `viewport/tests/quick/properties.gd`:
  1. Option-copy a board to make a linked pair, link one copy to a target face via Push/Pull or Properties, move the target, and verify both linked copies update on screen.

Reading path: `worker/plane_fit.py` (`stock`, `snapshot`, `face_plane`, `refit_inputs`, `refit_changed`, `update`, `apply`, `replace`, `push_fitted_end`, `resize_face`, `_restore`) → `worker/move.py` (`op_make_component`, `copy_body`, `op_make_unique`) → `worker/push.py` (`op_push_pull`, lines 140–170) → `worker/model.py` (`definition`, `apply`) → `worker/test_properties.py` → `viewport/tests/quick/properties.gd`.

Run `tools/featuretest.sh` while building, quick test after viewport changes, then `python3 tools/job.py test`. End your response with `Architecture:` lines (for `worker/plane_fit.py`, `worker/move.py`, `worker/push.py`), `Follow-up:` lines for leftovers, and a `Result:` line.
