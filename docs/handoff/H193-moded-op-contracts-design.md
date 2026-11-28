### H193 — Design: contracts for the ops with modes (move, push_pull, property_edit, fit), a proposal for William

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: gemini

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

---

### Response (Gemini, gemini-larch-1127-202212, 2026-11-27)

- **Branch & commit:** `gemini/h193-moded-op-contracts-design` at `c56bdab` (merged `main` at `c5b08c1` to pick up I74/I75 and resolve the P74 decision-log check).
- **What changed:**
  - Wrote [docs/proposals/op-contracts-with-modes.md](docs/proposals/op-contracts-with-modes.md) (147 lines, under the 200-line limit) comparing three ways to write contracts for ops with modes:
    - **Option A:** Declarative `variants` list with `when` selectors.
    - **Option B:** Flat `fields` with per-field `when` / `excludes`.
    - **Option C (recommended):** Named `variants` dict in `tests/op_contracts.json` + a small pure `*_variant(op)` Python classifier beside the handler.
  - Wrote out `move` (checked against `worker/move.py:180-299,363-372` and `worker/field_audit.py:20-26`) and post-I74 `push_pull` (checked against `worker/push.py:159-168,182-191,197-249,312-326`, noting pre-I74 `fit_face`/`resize_stock`/`new_board` variants only until I74 lands) in full for all three options, plus `property_edit` (`worker/model.py:348-349`, `worker/object_properties.py:168-229`), `fit` (`worker/model.py:336-339`, `worker/plane_fit.py:603-653`, and I75 `{normal, point}` face), and `mirror`.
  - Documented the changes each option requires for `test_op_contracts.py`, `test_document.gd` (`_op_makes`/`_op_refs`), `protocol_map.py`, tool/draft checks, and H194's `validate(op)`.
  - Added one link line in [docs/op-contracts.md](docs/op-contracts.md) pointing to `docs/proposals/op-contracts-with-modes.md`.
  - No code changes.
- **Open questions for William:**
  1. Pick a contract shape for ops with modes: Option C (recommended), Option A, or Option B?
  2. Keep `targets` marked `viewport_only: True` on `move`'s `cut` variant, or have `move_tool.gd` stop sending `targets: []` on `cut` moves?
  3. Include `mirror` (`replace` mode) in the follow-up job that writes the contracts for `move`, `push_pull`, `property_edit`, and `fit`?
- **Verified:** `python3 tools/job.py test` passed on `c56bdab` (quick 401/401, all feature suites including `OP CONTRACTS TESTS: 120 passed, 0 failed`, `PROTOCOL MAP TESTS: 17 passed, 0 failed`, `LOG TESTS: 70 passed, 0 failed`, `LOG SORT TESTS: 36 passed, 0 failed`).

Result: c56bdab; quick 401/401 & all feature suites passed; added docs/proposals/op-contracts-with-modes.md and linked it from docs/op-contracts.md
