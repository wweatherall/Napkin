### H184 — The field audit checks each run of an op, not all runs of its type lumped together

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: gemini

References: William, 2026-11-27 (ChatGPT's architecture review: "the field auditor combines observations across all
executions of an operation type: a parameter used in one execution but incorrectly ignored in another can escape
detection"), H178 (unread op fields), P44 (every rule says what it's for).

Touches: worker/field_audit.py, worker/test_field_audit.py.

Reading path:
1. worker/field_audit.py's docstring and `unread_fields` (~84): each record is one op run, `{"type", "sent", "read"}`;
   today `sent` and `read` are unioned per type before comparing.
2. tools/fulltest.sh ~42 and ~93-96: the full test writes one audit file per worker and runs the CLI on them all.

Today (checked 2026-11-27): a field counts as read for an op type if any run of that type read it. A push_pull that
sends `edge_fit` but takes a branch that never reads it passes, as long as some other push_pull read `edge_fit`.

Request:
1. `unread_fields` compares each record on its own: a field sent in a run and not read in that run is unread for that
   run. The report groups by op type and field, with the number of runs it went unread in and one example of the
   run's sent keys (so the reader can tell which kind of op it was).
2. Some fields are rightly unread in some runs (read only when another field is set). Run the full test, look at
   each type/field the per-run check flags, and read its handler:
   - rightly unread: add it to an `UNREAD_WHEN` table in field_audit.py, `{(type, field): "<when, and why it's
     fine>"}` (P44: each entry says what it's for), and the check passes it;
   - looks like a bug (sent, meant to matter, ignored): don't fix it; list it in your response as a follow-up, and
     put it in `UNREAD_WHEN` with a reason starting `"SUSPECTED BUG:"` so the gate passes and the entry stays visible.
3. test_field_audit.py: a case where one run reads a field and another run of the same type doesn't (flagged), and
   one where the field is in `UNREAD_WHEN` (passes).

Not in this job: fixing any handler, or changing which runs the full test makes.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope; the field audit stage included); quick 401/401.
- The response lists every `UNREAD_WHEN` entry with its reason, the suspected bugs first.

Response:
- Updated `worker/model.py` (`Model.apply`) and `worker/field_audit.py` (`append_record`) to record `"failed": true` when an op handler raises, and `"failed": false` otherwise.
- Updated `worker/field_audit.py` so `unread_fields(paths, allow=None)` checks each audit record individually, skips failed runs (a rejected op stops reading at its error, by design), and `format_report` groups by `(op_type, field)` with run count and an example of the run's sorted `sent` keys.
- Updated `UNREAD_WHEN` in `worker/field_audit.py` to `{(op_type, field): (when_key or None, reason)}`, dropped the three rejection-only entries (`push_pull.body`, `rect.corner`, `rect.size`), and scoped `("move", "targets")` to `when_key="cut"` (no suspected bugs found):
  - `("move", "targets")` (`when_key="cut"`): when `'cut'` is set, `op_move` dispatches to `move_cut` which reads `op['cut']` instead of `op['targets']` (`move_tool` sends `targets: []`).
- Updated `worker/test_field_audit.py` (30/30) to test the per-run shape, a field read in one run and unread in another run of the same type (flagged), `move.targets` with `cut` (passes) and without `cut` (flagged), failed runs with unread fields (passes) vs successful runs with unread fields (flagged), and `Model.apply` recording `failed=True` on handler error.
- Changed from the brief: `worker/model.py` (added to Touches by integrator review notes to record `failed` in `Model.apply` around the handler).
- Integrator scope note: initial gate hit a pre-existing `03_Past_Decisions/decision-log.md` failure on `main` (`90c9ede`); integrator confirmed `main` was updated (`19208f1`), merged `main` into the branch, and re-ran the full gate cleanly.

Result: `tools/TEST_BEFORE_MERGING.sh` passed (`GATE PASS: full test passes; QUICK 401 passed, 0 failed in 28.4 s ; 0 known failure(s); 79 s total`, `full: field audit passed in 0 s`); `worker/test_field_audit.py` 30/30.
