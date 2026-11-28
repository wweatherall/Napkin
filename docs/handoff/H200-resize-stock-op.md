### H200 — Push/Pull split, step 3: resizing plain stock is a `resize_stock` op (T159, I74)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: gemini | Item: T159 | Completes: T159

References: I74, A43, docs/proposals/T159-push-pull.md (split 3), H198, H199 (the updater), P73.

Touches: viewport/tools/push_tool.gd (`commit_push`), worker/push.py (`op_push_pull`: the `resize_stock` branch),
worker/model.py (an `op_resize_stock`), worker/serve.py and viewport/main.gd (PROTOCOL_VERSION), docs/protocol.md,
tests/op_contracts.json, worker/update_old_files.py (new in H199) and worker/test_update_old_files.py (new in H199) (the `resize_stock` rule),
worker/test_cut_ties.py and viewport/tests/quick/line.gd (where they build that op), viewport/tools/push_tool.gd's header comment.

Reading path:
1. viewport/tools/push_tool.gd `commit_push`: `op["resize_stock"] = true` when the target is a face of an unfitted,
   rectangular board (`stock_frame`).
2. worker/push.py `op_push_pull`: `if op.get("resize_stock") and "face" in tgt and "region" not in tgt:` calls
   `plane_fit.resize_face` and, when that returns false, falls through to the boolean path.

Request:
1. `resize_stock`: `{id, type, target: {face: FaceRef}, distance}`, run by that branch moved out of `op_push_pull`.
   When `resize_face` can't resize (it returns false today and the op falls through to a pad/cut), say what it does
   now in `Changed from the brief:` and keep the result the same: either `op_resize_stock` falls back to the same
   pad/cut, or the tool sends `push_pull` in that case; pick the one that keeps one op per gesture.
2. The updater gets the `push_pull` + `resize_stock: true` -> `resize_stock` rule (none on disk today; tested on a made-up op).
3. PROTOCOL_VERSION bump; protocol.md rows. Nothing you do with the mouse or keys changes (I74).

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope); the full field audit passes.

Response — Gemini (gemini-larch-1127-232508), 2026-11-27:
Split `resize_stock` out of `push_pull` into its own `resize_stock` op (`{id, type, target: {face: FaceRef}, distance}`):
- `worker/model.py` & `worker/push.py`: added `resize_stock` to `CONTRACTS`, `Model.op_resize_stock`, and `PushActions._resize_stock_op` (extracted shared `_push_boolean` helper so `op_push_pull` and `_resize_stock_op` share the boolean pad/cut path without duplication); `op_push_pull` now refuses `resize_stock` with `OpError("use resize_stock to resize stock")` and `to_face` no longer checks `resize_stock`.
- `viewport/tools/push_tool.gd`: `commit_push` now emits `type: "resize_stock"` with `rs` IDs for unfitted rectangular stock face pushes; updated header comment.
- `worker/serve.py`, `viewport/main.gd`, `docs/protocol.md`: bumped `PROTOCOL_VERSION` 22 -> 23 and documented `resize_stock` (plus `hello` example).
- `tests/op_contracts.json`: regenerated via `python3 worker/op_contracts.py` (`op_contracts.py --check` passes).
- `worker/update_old_files.py` & `worker/test_update_old_files.py`: added `push_pull` with `resize_stock: true` on a face -> `resize_stock` rule (13/13 updater tests pass).
- `worker/test_cut_ties.py` & `viewport/tests/quick/line.gd`: updated `to_face` rejection test for `resize_stock` (`unknown field to_face`) and tightened `line.gd` check to assert `type == "push_pull"`.

Changed from the brief: `worker/push.py` (`PushActions._resize_stock_op`): when `plane_fit.resize_face` returns `False` (for example, an expression-driven stock dimension), `op_resize_stock` falls back to `_push_boolean(op)` (the same boolean pad/cut path `op_push_pull` used previously), keeping one op per gesture.
Changed from the brief: `viewport/document.gd`: added `"rs": 0` to `counters` and included `"resize_stock"` in `_op_touches`; mechanical consequence of `push_tool.gd` allocating `rs` IDs and `resize_stock` editing a board in place (P73).
Changed from the brief: `viewport/presenter.gd` & `viewport/tool_context.gd`: included `"resize_stock"` in `waves.begin_wave` and `_push_filter` op type lists; mechanical consequence of splitting `resize_stock` out of `push_pull` (P73).
Changed from the brief: `viewport/tests/quick/press.gd`: updated unfitted plank face push assertion from `"push_pull"` to `"resize_stock"`; mechanical consequence of `push_tool.gd` emitting `resize_stock` (P73).
Changed from the brief: `worker/session.py`: added `op.get("resize_stock")` to `is_legacy_op` so un-updated files with `push_pull` + `resize_stock` are rejected with `OLD_FILE_MSG`; mechanical consequence of retiring `resize_stock` from `push_pull` (P73).
Changed from the brief: `worker/test_serve.py`: bumped pinned `PROTOCOL_VERSION` 22 -> 23; mechanical consequence of bumping `PROTOCOL_VERSION` (P73).
Changed from the brief: `worker/test_properties.py`, `worker/test_op_contracts.py`, `worker/scenario/99_op_registry.py`, `worker/scenario/99_regions.py`: updated `repull` to `type="resize_stock"`, added `resize_stock` fixture and `push_pull`+`resize_stock` refusal check in `test_op_contracts.py`, added `"resize_stock"` to `TYPES` (21 ops) in `99_op_registry.py`, and removed `resize_stock=True` from `99_regions.py`'s region `push_pull` op; mechanical consequences of splitting `resize_stock` out of `push_pull` (P73).

Architecture: `worker/model.py` owns `Model.op_resize_stock` and the `resize_stock` `CONTRACTS` entry, delegating execution to `worker/push.py` `PushActions._resize_stock_op` (which falls back to `_push_boolean` if `plane_fit.resize_face` returns `False`).
Architecture: `PROTOCOL_VERSION` bumped 22 -> 23 across `worker/serve.py`, `viewport/main.gd`, and `docs/protocol.md`, with `viewport/document.gd` allocating `rs` IDs.

Result: `tools/TEST_BEFORE_MERGING.sh` passed (`GATE PASS: full test passes; QUICK 405 passed, 0 failed in 33.5 s ; 0 known failure(s); 97 s total`, including full field audit, 170/170 op contracts, 17/17 protocol map, 714/714 scenario, 13/13 update_old_files, 22/22 cut_ties, 99/99 properties, 34/34 serve).
