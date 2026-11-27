# T161: How a fit names its target face

**Status:** Proposal for William (2026-11-27) · **No code changed yet.**

---

## 1. How a fit names its face today

A `fit` op (and `push_pull.edge_fit`) names the target face with a single integer `face`:

- **On plain rectangular stock** (`plane_fit.stock(target)` is present): `face` is `0..5`, meaning **Left, Right, Front, Back, Bottom, Top** in the target board's stock-local axes (`-X, +X, -Y, +Y, -Z, +Z`).
- **On non-rectangular or cut boards** (`stock(target)` is `None`): `plane_fit.planar_faces(target)` collects every `Part::GeomPlane` face of the target's `Tip.Shape` in definition-local space, merges coplanar faces, sorts them by `(normal, offset)`, and `face` is the **0-based index into that sorted list**.

Once `plane_fit.apply()` runs, it does **not** rely on that integer alone:
- It saves `SSTargetNormal` and `SSTargetPoint` on the `PlaneFit` feature in the **target's definition-local frame**.
- On every later recompute (`update()` → `_resolve_face()`), it ignores `SSFace` when `SSTargetNormal` is set, maps `SSTargetNormal`/`SSTargetPoint` back to world space, finds the matching face in `planar_faces(target)` (same normal within `dot > 0.9999`, closest plane offset), and rewrites `SSFace`.

---

## 2. When this can go wrong (and what tests prove it)

| Scenario | What happens today | Does `_resolve_face` cover it? | Test coverage |
|---|---|---|---|
| **A cut adds a face to the target** | If the target was plain stock (`0..5`) and gets a cut, `stock(target)` becomes `None` and `planar_faces` switches to the sorted `Part::GeomPlane` list. `SSFace` now means a different face. | **Mostly yes, with one gap.** `_resolve_face` re-finds the face by `SSTargetNormal` + `SSTargetPoint` and updates `SSFace`. **Gap:** if the original face is completely cut away and another parallel face exists (e.g., a pocket floor), `min(matches, ...)` silently jumps to that parallel face instead of detaching as unavailable (there is no distance threshold). | `worker/test_properties.py` (T62, lines 537–550) tests fitting to an *already-cut* board and moving it. **No test** adds a cut to a target *after* a fit is already attached. |
| **Faces reorder in `planar_faces`** | Adding/removing faces on a cut board shifts indices in the sorted `planar_faces` list. | **Yes** for live fits (`_resolve_face` ignores `SSFace` and matches by normal + point). **Fragile at pick time** only if the viewport's `bodies.json` snapshot is stale relative to the worker. | **None.** No test triggers a `planar_faces` index shift on a live target. |
| **A board is mirrored** | `op_mirror` (`worker/mirror.py`) creates a `Part::Mirroring` object (`TypeId == 'Part::Mirroring'`). `_def(target)` in `worker/plane_fit.py` only recognizes `App::Part` and `App::Link`. | **No.** Fitting *to* a mirrored board is rejected (`target_dfn is None`). Worse, **flipping** (`mirror` with `replace=True`) an existing target board replaces its `App::Part` with a `Part::Mirroring` under the same `BodyId`, so on the next recompute `_def(target)` returns `(None, None)` and the fit **detaches** (`Reference unavailable · last geometry retained`). Also, `0..5` (Left/Right) flips handedness under a mirror. | **None.** No test fits to a mirrored board or flips a fit's target board. |

---

## 3. Two options

### Option A: Keep `face` integer + local `(normal, point)` (with small fixes)
- **Why it mostly meets G08:** Although `face` in the op is an integer, it is **not** a FreeCAD internal `Face1`..`FaceN` topological number — it is either a semantic stock side (`0..5`: Left..Top) or an index into our own deterministic, geometry-sorted `planar_faces` list, and the worker immediately converts it into geometric `(SSTargetNormal, SSTargetPoint)` on the `PlaneFit` feature.
- **What still needs fixing:**
  1. Add a tolerance check in `_resolve_face` (e.g., if `abs((p[0] - want_pt).dot(want_n)) > TOL` when the target hasn't been resized/moved? Careful: when a target is resized, its face *moves* along its normal, which is why `_resolve_face` picks closest parallel face rather than exact offset!).
  2. Support `Part::Mirroring` in `plane_fit._def` / `planar_faces` if fits to mirrored/flipped boards should stay live.
- **Pros:** Zero protocol/file-format churn; human-readable `Left..Top` names on plain stock.
- **Cons:** `fit` op in the journal still stores an integer `face` whose meaning changes if the target's history changes before `apply()` (e.g., undo/redo or replaying an op list where an earlier op changed `planar_faces`).

### Option B: Name the target face by `{normal, point}` (a `FaceRef` without `body`, or `{body, normal, point}`) in the `fit` op
- **What changes:**
  - `fit` (and `new_board.fit` / `push_pull.edge_fit`) replaces `face: int` with `face: {normal: Vec3, point: Vec3}` (world mm, just like `FaceRef` in `push_pull`, `rect`, `line`, and `to_face`).
  - `push_tool.gd` already has `option.plane_point` and `option.plane_normal` in `_edge_inference`, so it sends them directly instead of `option.face`.
  - `worker/plane_fit.py` resolves `{normal, point}` directly against `planar_faces(target)` (using `dot > 0.9999` and closest offset), and stores `SSTargetNormal`/`SSTargetPoint` as today.
  - `bodies.json` no longer needs `planar_faces` just to assign an index for `fit` (though `push_tool.gd` can still use `planar_faces` or `triangles` for edge inference).
- **How old files upgrade:**
  - In `session.upgrade_op` (or on first open in `worker/plane_fit.py` since resolving `0..5` or `planar_faces[i]` to `(normal, point)` requires the target's geometry), pre-upgrade `fit` ops with integer `face` are resolved against the target board and rewritten to `{normal, point}` on first save (same pattern as H171 / A42).
- **Pros:** Every face reference in the entire protocol (`push_pull`, `rect`, `line`, `arc`, `to_face`, `fit`) uses the exact same geometric `{normal, point}` language (G08, G02). Immune to `planar_faces` index shifts on replay.
- **Cons:** Needs one job to update `fit`, `push_tool.gd`, `plane_fit.py`, `protocol.md`, and tests, plus an upgrade path for existing integer-`face` ops.

---

## 4. Recommendation

**Recommend Option B** (name `fit`'s target face by `{normal, point}`), **plus** adding tests for the three uncovered cases (cutting a target after fitting, `planar_faces` reordering, and mirroring/flipping a target board).

Why: `FaceRef` (`{normal, point}`) is already how every other op in Shop Sketch names a face. Keeping `face: int` on `fit` is the last place in the protocol where a face is named by an index that depends on a list order. Switching `fit` to `{normal, point}` unifies the protocol under G08 and can be done cleanly right alongside T159 (or right after).

---

## Questions for William

1. **Keep integer `face` (Option A) or switch `fit` to `{normal, point}` (Option B)?**
2. **Mirrored/flipped targets:** Should a fit to a board stay live when that target board is flipped (`mirror` with `replace=True`) or mirrored, or is detaching acceptable?
3. **Deleted/cut-away target face:** If a cut removes the exact face a board was fitted to, should the fit detach ("Reference unavailable") or jump to the nearest remaining parallel face (today's behaviour)?
