### H198 — Push/Pull split, step 1: fitting a face to another board's edge sends a `fit` op (T159, I74)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: gemini | Item: T159

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

### Response

2026-11-27 (Gemini, `gemini-spruce-1127-204647`):
- Branch: `gemini/h198-face-fit-is-a-fit-op` (code commit `1ad4241`, merged `main` at `6bd634a`).
- Changes:
  - `viewport/tools/push_tool.gd` (`commit_push`): when `edge_fit` is non-empty and the target is a face (no `rect`, no `region`), computes `axis` and `reverse` from `ctx.model.stock_frame(body)` and `state["n"]`, and sends `{"id": next_id("ft"), "type": "fit", "body", "target_body", "axis", "face", "fit_mode", "reverse"}` while keeping the single draft, confirmation wave, and single Undo step.
  - `worker/push.py` (`op_push_pull`): removed the `edge_fit`-on-a-face branch and raised `OpError("edge_fit is only for a new board; use fit for an existing face")` when `edge_fit` is passed on a face target without `region`.
  - `viewport/document.gd` (`_op_refs`): scoped `op.has("edge_fit")` to `op["type"] == "push_pull" and op.has("edge_fit")` so `rect`/`region` + `edge_fit` continues working while `fit` uses its own `body`/`target_body` branch.
  - `worker/serve.py` and `viewport/main.gd`: bumped `PROTOCOL_VERSION` from 19 to 20.
  - `docs/protocol.md`: updated protocol version to 20 (including the `hello` example), updated `push_pull` and `fit` rows and the `edge_fit` note.
  - `worker/test_properties.py` and `viewport/tests/quick/properties.gd`: updated face-fit op assertions to `fit`, added a worker test verifying `push_pull` with `edge_fit` on a face is refused, and added quick-test assertions for one draft, one wave, and one Undo step on a face fit.
- Integrator Q&A (`job.py wait --scope` on `LOG TESTS` / `LOG SORT TESTS` failing on `P75` before merging `main`):
  > "Main is fine: the P75 index row is in Napkin's own 03_Past_Decisions/decision-log.md (comitatus keeps only the ruling files), added by main's 2174601 after your branch started. Merge main into your branch (git merge main), rerun the gate, and carry on; nothing in comitatus needs changing."
- Verified:
  - `tools/TEST_BEFORE_MERGING.sh` (full scope): `GATE PASS: full test passes; QUICK 403 passed, 0 failed in 49.8 s; 0 known failure(s); 113 s total`, including full field audit.
  - `python3 tools/job.py test` on `6bd634a` (after merging `main`): `QUICK 403 passed, 0 failed`, `PROPERTY TESTS: 98 passed, 0 failed`, `SERVE TESTS: 34 passed, 0 failed`, `LOG TESTS: 70 passed, 0 failed`, `LOG SORT TESTS: 36 passed, 0 failed`.
- IDs added: none. Open questions: none.

Changed from the brief: brief listed `tests/op_contracts.json` (`push_pull`'s `edge_fit` only where a face is the target) and said `push_pull` would refuse it via H194 contract; `push_pull` has no `CONTRACT` in `worker/push.py` yet (deferred until after the split per H193), so `tests/op_contracts.json` was left untouched and `op_push_pull` raises `OpError` explicitly if `edge_fit` is passed on a face target without `region`.
Changed from the brief: updated `worker/test_serve.py` protocol version assertion from 19 to 20 (P73: test pinning the old `PROTOCOL_VERSION`).
Architecture: `viewport/tools/push_tool.gd` now sends a `fit` op (computing `axis` and `reverse` from `stock_frame`) instead of `push_pull` when fitting an existing face to another board's edge; `PROTOCOL_VERSION` bumped 19 -> 20.
Result: 6bd634a; GATE PASS (403/403 quick, full + field audit passed) and job.py test passed; face-to-edge fits in Push/Pull now send fit ops (PROTOCOL_VERSION 20)
