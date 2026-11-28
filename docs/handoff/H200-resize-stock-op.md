### H200 — Push/Pull split, step 3: resizing plain stock is a `resize_stock` op (T159, I74)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: queued (after H199) | For: gemini | Item: T159 | Completes: T159

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
