# T159: Splitting `push_pull`'s jobs into separate ops

**Status:** Proposal for William (2026-11-27) · **No code changed yet.**

Today one `push_pull` op handles six distinct jobs depending on which optional fields are set. Splitting the unrelated jobs into their own op types (the way `fit` and `unfit` were split out of `property_edit` in H171) will make the protocol, worker, viewport bookkeeping, and tests much simpler without changing any user gesture.

---

## 1. What `push_pull` does today

| Job | Fields that select it | Gesture (`push_tool.gd`) | Worker code path (`worker/push.py`) |
|---|---|---|---|
| **1. New board** | `target: {rect}` or `{region}` (or `{rect/face, region}`), `distance`, `body` (or free profile), optional `assembly` | Push/Pull on a free profile/loop, or on-face with **New Board** on (`d > 0`) | `op_push_pull` lines 237–272: `new_board` → `extrusion` → `set_tip` → optional `assembly` |
| **2. New board + fit** | Same as #1 plus `edge_fit: {target_body, face, fit_mode?}` | Same as #1, dragged to an edge/point on another board (`_edge_inference`) | Same as #1, then calls `plane_fit.apply(axis=2, ...)` (lines 269–271) |
| **3. Fit an existing face** | `target: {face: FaceRef}`, nonzero `distance` (unused), `edge_fit: {target_body, face, fit_mode?}` | Push/Pull on an unfitted board's face dragged to an edge/point on another board | `op_push_pull` lines 155–167: resolves `axis` & `reverse`, calls `plane_fit.apply(...)`; never extrudes |
| **4. Detach & push a fitted end** | `target: {face: FaceRef}`, `distance` (no `edge_fit`, no `resize_stock`) | Push/Pull on the fitted end face of a fitted board | `op_push_pull` lines 168–175: `push_fitted_end(...)` restores stock + resizes (Butt/Fully reach) or clears tie and falls through (Slice) |
| **5. Resize plain stock** | `target: {face: FaceRef}`, `distance`, `resize_stock: true` | Push/Pull on any face of an unfitted rectangular board | `op_push_pull` lines 178–182: `plane_fit.resize_face(...)` edits `Length`/`Width`/`LengthFwd` directly (no boolean) |
| **6. Edit a board in place** (pad, blind cut, through cut, floor-tied cut) | `target: {face}` (non-rect/cut/Slice-detached), `{rect}`, or `{face/rect, region}`, `distance` (`+` pad / `-` cut), optional `through: true` or `to_face: {normal, point}` | Push/Pull a profile/region/non-rect face on a board; pointer snap to back face sets `through`; snap to pocket floor sets `to_face` | `op_push_pull` lines 176–177 (`_detach_floor_cuts`), 216–235 (`native_region`), 274–313 (`edit_frame` → `extrusion` → `through_all` / `tie_to_floor` → `boolean`) |

Because all six share one type, `op_push_pull` has to guard against invalid combinations at runtime (`to_face is only for a cut into a board`), `edge_fit` on a face sends a dummy `distance` that is checked for nonzero and then ignored, and `viewport/document.gd` + `worker/session.py` have special-case `if op.has("body")` / `if op.has("edge_fit")` checks everywhere.

---

## 2. Proposed split

### Split out (3 changes)

1. **Face-to-edge fit → existing `fit` op** (replaces job #3)
   - **Type & fields:** `fit` (already exists: `body`, `target_body`, `axis`, `face`, `fit_mode`, `reverse?`).
   - **What changes:** `push_tool.gd` computes `axis` and `reverse` from `stock_frame` (the same 4 lines `op_push_pull` runs today) and emits `type: "fit"` directly. No dummy `distance`, no `edge_fit` on `push_pull` for existing faces.
   - **What William notices:** Nothing — same edge inference, Tab/Option keys, draft, and undo.
   - **What gets simpler:** Removes `op_push_pull` lines 155–167 and the `edge_fit` branch in `document.gd:_op_refs`.

2. **New board → `new_board`** (replaces jobs #1 and #2)
   - **Type & fields:** `new_board`: `target` (`{rect}`, `{region}`, `{rect, region}`, or `{face, region}`), `distance` (`number`), `body` (`string`), optional `assembly` (`string`), optional `fit: {target_body, face, fit_mode?}` (keeping new-board + fit as one undo step, since `document.gd` undoes one op at a time).
   - **What William notices:** Nothing — same Push/Pull gesture, same `b` IDs, same amber draft and confirmation wave.
   - **What gets simpler:** `session.py:creations` checks `type == "new_board"` instead of `push_pull` + `body`; `document.gd:_op_makes` and `_op_touches` drop `op.has("body")` branching; `op_push_pull` drops lines 237–272; `to_face`/`through`/`resize_stock` are impossible by construction on `new_board`.

3. **Plain stock resize → `resize_stock`** (replaces job #5)
   - **Type & fields:** `resize_stock`: `target: {face: FaceRef}`, `distance` (`number`).
   - **What William notices:** Nothing — same face push/pull and draft preview.
   - **What gets simpler:** Removes the `resize_stock` flag from `push_pull` and makes direct dimension edits distinct from boolean pad/cut in journals and tests. (If `resize_face` ever refuses an expression-driven stock face, it fails cleanly or falls back inside its own small handler.)

### Keep in `push_pull`

- **Job #6 (pad / blind cut / through cut / floor-tied cut on an existing board)** stays `push_pull` (`target`, `distance`, optional `through`, optional `to_face`).
  - *Why not split `cut` from `pad`?* In SketchUp and `push_tool.gd`, pushing a profile or face on a board is one continuous drag across `distance = 0`, and `worker/push.py` uses the exact same `edit_frame` → `extrusion` → `boolean` path for both signs. Splitting `cut` from `pad` would duplicate that shared path without simplifying it.
- **Job #4 (pushing a fitted end to detach it)** stays on `push_pull` (when `target` is `{face}` on a fitted board): `push_fitted_end` either restores stock + resizes (Butt/Fully reach) or detaches and falls through to a boolean pad/cut (Slice).

### Upgrading old files (following H171 / A42)

- Bump `PROTOCOL_VERSION` (once per split or together).
- Extend `session.upgrade_op(op)` in `worker/session.py` (which already runs on `ops`, `dropped`, and `Meta.ShopSketchOps` when opening any `.FCStd`):
  - `push_pull` with `edge_fit` on `{face}` (no `region`, no `body`) → `fit` (or upgraded when the model opens if `axis`/`reverse` need `stock_frame`, or `fit` accepts `face_ref`? Note: `upgrade_op` is pure dict-to-dict without the FreeCAD doc, so either `upgrade_op` only converts `new_board` / `resize_stock` cleanly and keeps a small legacy shim for old `edge_fit`-on-face, OR `fit` accepts an optional `normal` fallback.Worth flagging in the questions!).
  - `push_pull` with `body` (or free `rect`/`region` with no `OnBody`) → `new_board` (renaming `edge_fit` → `fit` if present).
  - `push_pull` with `resize_stock: true` → `resize_stock` (dropping `resize_stock`).
- First save writes the upgraded ops, just like H171.

---

## 3. Recommendation & order of jobs

**Recommend doing all three splits** in three small, independent jobs (each with its own `upgrade_op` rule, protocol bump, and tests):

1. **Job 1 — `fit` for face-to-edge fits:** Smallest change; `fit` op already exists from H171.
2. **Job 2 — `new_board`:** Separates board creation (`body`, `assembly`) from in-place board edits; simplifies `session.py`, `document.gd`, `presenter.gd`, and `push.py`.
3. **Job 3 — `resize_stock`:** Separates parametric stock resizing from boolean pad/cut.

---

## Questions for William

1. **Approve the 3-way split** (`fit` for face-to-edge fits, `new_board` for creating a board, `resize_stock` for resizing stock, keeping pad/cut/detach in `push_pull`)?
2. **Name check:** Are `new_board` and `resize_stock` the names you want in the op log / protocol?
3. **New board + edge fit in one gesture:** Keep `fit?: {...}` as an optional field on `new_board` so Undo undoes both creation and fit together in one step?
4. **Old files with `push_pull.edge_fit` on a face:** Since `session.upgrade_op` runs before FreeCAD builds the board's `stock_frame`, should `fit` accept an optional `normal` when upgrading old journals, or keep a 5-line legacy shim in `op_push_pull` for pre-split files?
