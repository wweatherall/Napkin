### H184 — The field audit checks each run of an op, not all runs of its type lumped together

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: queued (after H185) | For: gemini

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
