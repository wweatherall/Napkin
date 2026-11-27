### H150 — T147 step 1: a plane fit keeps its target face when boards are cut, flipped or chained

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: answered | For: either

References: T147, T145 (William's ultra review of Gemini's stretch, findings 1-5 and 10), A03, I26b, I40, T54
(`worker/scenario/97_plane_fit_refit.py`), H127 (face ties on non-rectangular shapes).

Touches: worker/plane_fit.py (`apply`, `update`, `planar_faces`, `face_plane`, `snapshot`, `_active_tips`, `_family_bodies`, `_driving_body`, `refit_changed`, `_inputs`, `refit_inputs`, new helpers), viewport/tools/push_tool.gd (`_target_face_plane`, `_edge_inference`), viewport/property_panel.gd (the fit face list and its result line), worker/scenario/98_plane_fit_identity.py (new), viewport/tests/quick/properties.gd.

Reading path:
1. `worker/plane_fit.py` `apply`: the op's `face` (an int) goes straight into `tip.SSFace`, and the cycle check walks
   `cur_dfn.Tip` only while that Tip is the PlaneFit itself (`hasattr(cur_tip, 'SSStock')`).
2. `planar_faces`: plain rectangular stock (`stock()` not None) gives the 6 standard faces, with the fitted end put in
   at `fitted_face()`'s place. Anything else (a cut board, a circle or polygon, a sketch) gives its planar faces
   deduplicated and **sorted by (normal, offset)**: a cut adds faces, which changes the order, and cutting plain stock
   switches it from the 6-face numbering to the sorted one. The fitted-end swap doesn't happen on that path.
3. `face_plane(target, tip.SSFace)` in `update` and `_inputs`: that number is read again on every refit.
4. `snapshot`: sends `planar_faces` and `fitted_end.face = fitted_face()` (the 0-5 numbering) for every fitted board,
   rectangular or not. `viewport/tools/push_tool.gd` `_target_face_plane` checks `fitted_end.face == face` first, so on
   a non-rectangular fitted target, face N of the list can show the fitted end's plane while the worker reads entry N.
5. `_active_tips(model, bodies, promote=True)` (called from `refit_changed`): when `_family_bodies` finds no live body
   for the definition, it clears `SSTargetId` (and `SSSourceBodyId`) for good. `bodies()` (worker/model.py) keeps only
   `SSRole == "body"`, so a board flipped in place (worker/mirror.py `op_mirror` with `replace`: the original becomes
   `SSRole = "source"`) or deleted while a mirror still builds from it (`SSRole = "deleted"`, deletion.py) loses its
   fit for good: only undoing the flip or delete itself brings it back (the clear is inside that op's transaction).
6. `refit_changed`: updates in target-first order, but reads each target's faces from its **Tip's** Shape. When the
   target is itself fitted and then cut, `update` has just written the PlaneFit's Shape, but the Cut above it isn't
   recomputed until model.py `apply`'s batch `doc.recompute()`, so the next board in the chain fits to the old shape.
   With no ready item, `refit_changed` `break`s silently ("Defensive cycle guard").

Today (checked 2026-11-26 on main 3d0e9d4): all six of these happen as described above. A03 says faces are referenced
by geometry, never by face numbers; a fit's face is the one place that keeps a number across edits.

Request:
1. **A fit names its target face by geometry (A03; findings 1, 5).** The op keeps its `face` int (no protocol change:
   the viewport picks it from the same snapshot the worker numbers). At `apply`, resolve it once to the face's plane in
   the **target definition's local frame** (outward normal and a point on it) and store that on the tip (two new
   properties, added where `apply` creates the PlaneFit, like `SSReverse`). Every later read (`update`, `_inputs`,
   `snapshot`'s result line) finds the target's current planar face by that geometry: same outward normal (dot >
   0.9999), and of those the one whose plane is nearest the stored point. That way a cut that only adds faces, or one
   that moves the face (a rebate on that end), keeps the fit on the same face. Keep `SSFace` up to date with the
   resolved index after each refit (the Properties panel and the tooltip read it), so nothing else needs the number to
   stay put. A file made before this change (no stored plane) resolves `SSFace` once on its first refit and stores the
   plane: say in your response whether that write happens inside an undo transaction (worker/CLAUDE.md: properties go
   on objects when they're created; adding them inside a transaction isn't reliably undone) and how you handled it.
   No face with that normal left: detach as `update` does today ("Reference unavailable · last geometry retained").
2. **One numbering for the fitted end (finding 5).** For a non-rectangular fitted target, `planar_faces` and the
   snapshot's `fitted_end.face` must agree: either `fitted_end.face` is the index of the fitted end in `planar_faces`
   (recommended: the list then already holds it), or the viewport stops special-casing it for non-rectangular targets.
   `push_tool.gd` `_target_face_plane` and the Properties panel must then show the same plane the worker will use for
   that index.
3. **Flipping or deleting doesn't detach (finding 2).** A fit is cleared only by an explicit detach (pushing the tied
   end, typing a length: I26b, I40) or when its target is gone. A fitted board whose definition no live body uses but a
   mirror or flip still builds from (`SSRole` `source` or `deleted`) keeps its `SSTargetId` and keeps following its
   target, so the flipped or mirrored board follows too. The promote path may still clear a fit whose definition
   nothing at all uses any more.
4. **Chains read the target's current shape (finding 3).** Before reading a target's faces in `refit_changed`, if that
   target was updated earlier in the same pass, recompute its feature chain from the PlaneFit up to its Tip (object
   `recompute()`s, not `doc.recompute()`: `97_plane_fit_refit.py` counts document recomputes and must keep passing).
5. **No cycles through cut boards (finding 4).** The cycle check in `apply` follows a board's fit whatever sits on top
   of it: find the definition's PlaneFit by walking down from its Tip (`_underlying_extrusion`'s walk, or a helper
   beside it), not only when the Tip is the PlaneFit. A fit that would close a loop is refused with the existing
   message `This fit would create a cycle`. `refit_changed`'s guard stays, but if it ever stops with items left it marks
   their `SSFitResult` `Reference unavailable · last geometry retained` instead of returning silently.
6. **No needless recomputing (finding 10).** `_inputs` for a non-rectangular target currently rebuilds every planar
   face of the target on every sync. Make the comparison cheap for boards whose shape hasn't changed (for example key it
   on the target Tip's shape identity or a hash FreeCAD already gives, `shape_key` in export.py), as long as a change of
   that shape still triggers the refit.

What can fail (P42: this changes what a saved file holds):
- An old file reopened: fits without the stored plane must still refit to the face they showed before (step 1's
  migration), and saving then reopening must give the same result.
- Undo past the migration, or a rebuild from the journal past 20 steps (T10): the fit must come back on the same face.
- A cut that removes the fitted face completely: detach with the existing message, keep the shape (no exception).
- A component (App::Link) target and a shared definition: the stored plane is in the definition's frame, so every
  instance resolves it the same way.

Checks: a new `worker/scenario/98_plane_fit_identity.py` (`requires = ("97_plane_fit_refit.py",)` only if you reuse its
ops), each check failing without its fix:
- "a fit stays on its face when the target is cut" (cut plain stock that a board is fitted to; the fitted end still lies
  on the original face's plane);
- "a fit stays on its face when a cut target gains faces" (non-rectangular target, a second cut adds planar faces);
- "a fitted end on a non-rectangular target has one face number" (snapshot `fitted_end.face` indexes `planar_faces` to
  the same plane);
- "flipping a fitted board keeps it following its target" (flip, then move the target: the flipped board follows);
- "deleting a fitted board a mirror still reads keeps the mirror following";
- "a chain through a fitted-then-cut board reaches the target's new position" (C fitted to B, B fitted to A then cut,
  move A: C ends on B's new face);
- "a circular fit through a cut board is refused" (`This fit would create a cycle`, the op rejected, A keeps its solid);
- "an old file's fit migrates to its face once" (build with the stored plane removed, reopen, refit).
`97_plane_fit_refit.py` passes unchanged. In `viewport/tests/quick/properties.gd`, a step that picks a non-rectangular
target's fitted end in the panel and checks the result line names the same face FreeCAD reports.

**Response (Gemini, `gemini-cherry-1126-1855`, 2026-11-26):**
- Branch: `gemini/h150-t147-plane-fit-face-identity`, commit: `d73166f`.
- Verified: `tools/quicktest.sh` via `python3 tools/job.py test` on `d73166f` — all feature suites passed (`SCENARIO TESTS: 709 passed, 0 failed`, including `97_plane_fit_refit.py` unchanged and new `98_plane_fit_identity.py`) and `viewport: QUICK 399 passed, 0 failed`.
- Legacy fit migration (`SSTargetNormal` / `SSTargetPoint` added when missing on first refit): the write happens inside the `Model.apply` undo transaction during `update`; `_resolve_face` treats a missing or zero-length `SSTargetNormal` as unset, so undoing past migration cleanly re-resolves from `SSFace`.
- IDs added: none. Open questions: none.

Architecture: PlaneFit tip stores target face geometry in the target definition's local frame (`SSTargetNormal`, `SSTargetPoint`); `snapshot` reports `fitted_end.face` as the index in `planar_faces` for non-rectangular targets.
Result: d73166f; quicktest passed (709 scenario, 399 viewport quick); plane fits track target face geometry across cuts, flips, deletes and chains
