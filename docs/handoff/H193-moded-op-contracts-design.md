### H193 — Design: contracts for the ops with modes (move, push_pull, property_edit, fit), a proposal for William

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: open | For: gemini

References: William, 2026-11-27 ("carry on with the contracts"; behaviour and design choices are his, P01), H189's
report section 5 (what Move and Push/Pull would need), H191/H192 (the contracts so far, and any op H192 left out),
H179 (the model for a proposal job: docs/proposals/T159-push-pull.md, T161), T159 (Push/Pull's meanings: waiting on
William), P73.

Touches: docs/proposals/op-contracts-with-modes.md (new), docs/op-contracts.md (one line pointing to the proposal).

Reading path:
1. docs/op-contracts.md (as H192 left it) and the contracts in tests/op_contracts.json.
2. worker/move.py `op_move` (its three paths: cut, selection, plain/copy/array), worker/push.py `op_push_pull` (the
   `target` variants and the mode flags with their exclusions), worker/model.py `op_property_edit` (its `mode`s) and
   `op_fit`; for each, `creations`, `_op_makes`, `_op_refs` and field_audit.py's `UNREAD_WHEN`.
3. docs/proposals/T159-push-pull.md and I74 (William decided it 2026-11-27): push_pull splits into `fit`,
   `new_board` (with an optional `fit`) and `resize_stock`, pad/cut/fitted-end stay `push_pull`; I75: a fit names its
   target face by {normal, point}. Write push_pull's and fit's options for the ops as they will be after the split,
   and say what today's push_pull would need only until then.

Today (checked 2026-11-27): the contract shape has one fixed field list per op. These four ops change which fields
apply by mode (`cut` present, `target` variant, `mode` value), and several fields exclude others.

Request:
1. **docs/proposals/op-contracts-with-modes.md** (under 200 lines): two or three ways to write a contract for an op
   with modes (for example: a list of variants each with its own fields; `when` conditions on fields; a small
   function beside the handler that says which variant an op is), each shown written out for **move** and
   **push_pull** in full, with what the existing checks (fields read, creates, refers to, protocol row, tool, draft)
   would need to change for it, and how H194's runtime check would use it. A recommendation, and what to ask William.
2. Each option is checked against the code: every field, exclusion and error message it claims comes from the
   handler (cite the line).
3. No code changes.

Not in this job: writing the contracts (after William picks), T159's decision, runtime validation.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (docs scope).
