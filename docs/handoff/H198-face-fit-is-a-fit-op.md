### H198 — Push/Pull split, step 1: fitting a face to another board's edge sends a `fit` op (T159, I74)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: queued (after H194) | For: gemini | Item: T159

References: I74 (William, 2026-11-27: push_pull's jobs split into their own ops), A43 (breaking changes allowed: a
one-time updater, no shims), docs/proposals/T159-push-pull.md (job #3, split 1), H171 (how `fit` was split out of
`property_edit`), H194 (contracts checked at runtime), P73.

Touches: viewport/tools/push_tool.gd (`commit_push`), worker/push.py (`op_push_pull`: the `edge_fit`-on-a-face
branch), viewport/document.gd (`_op_refs`), worker/serve.py and viewport/main.gd (PROTOCOL_VERSION 19 -> 20, or one
past main's when you start), docs/protocol.md (push_pull and fit rows), tests/op_contracts.json (push_pull's
`edge_fit` only where a face is the target), worker/test_properties.py, viewport/tests/quick/properties.gd.

Reading path:
1. viewport/tools/push_tool.gd `commit_push` (from `func commit_push`): today a face push that ends on another board's
   edge sends `push_pull` with `target: {face}`, a `distance` that is checked for nonzero and then ignored, and
   `edge_fit: {target_body, face, fit_mode}`.
2. worker/push.py `op_push_pull`, the `if fit and "face" in tgt and "region" not in tgt:` branch: it works out `axis`
   from `plane_fit.source_frame` and the face's normal, and `reverse`, then calls `plane_fit.apply` with
   `body, target_body, axis, face, fit_mode, reverse`. Those six are exactly the `fit` op's fields (worker/model.py
   `op_fit`).
3. The viewport's `ctx.model.stock_frame(body)` (used a few lines below in `commit_push`): the same frame, so the tool
   can work out `axis` and `reverse` itself.

Today (checked 2026-11-27): no saved file (examples/, tests/legacy_one_file, tests/reference, models/) holds an
`edge_fit` op, so nothing on disk needs converting for this step.

Request:
1. In `commit_push`, when `edge_fit` is set and the target is a face (no `rect`, no `region`), send
   `{"type": "fit", "body", "target_body", "axis", "face", "fit_mode", "reverse"}` instead of `push_pull`, with axis
   and reverse worked out as the worker's branch does today (so the result is the same board). A new board fitted in
   the same drag (`rect` or `region` with `edge_fit`) stays as it is: step 2 (H199) moves it into `new_board`.
2. Remove that branch from `op_push_pull`; a `push_pull` with `edge_fit` on a face target is now refused by its
   contract (H194) like any unknown field. Remove the matching `edge_fit` case from `document.gd`'s `_op_refs` only
   where it served this path (a `fit` op already names its `target_body`).
3. Draft, Tab/Option cycling, the confirmation wave and Undo look and behave exactly as before (I74: nothing you do
   with the mouse or keys changes). Check: the quick tests for fits pass unchanged except where they assert the op's
   type, which now says `fit`.
4. Bump PROTOCOL_VERSION in both places; docs/protocol.md: push_pull's row loses the face-fit case; the fit row says
   Push/Pull sends it.

Not in this job: `new_board`, `resize_stock`, the fit's face naming (H201), the updater (H199).

What can fail:
- The draft of a face fit vanishes or doubles because the presenter or history keys on `push_pull` (presenter.gd
  and history.gd check `op.type == "push_pull"`). Check: a quick test pushes a face to an edge and sees one draft,
  one wave and one Undo step.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope); the full field audit passes.
