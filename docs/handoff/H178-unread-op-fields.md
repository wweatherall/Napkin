### H178 — The full test fails on an op field that's sent but never read (a misspelt field can't run as its default)

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: open | For: gemini

Item: T160
Completes: T160

References: T160 (William, 2026-11-27: "Ok"), comitatus principle C03 (simplify: a runtime record instead of parsing
two languages), P07 (feature tests check answers against FreeCAD with no window), G10 (a rejected action says why).

Touches: worker/model.py (`apply`), worker/field_audit.py (new), worker/test_field_audit.py (new), tools/fulltest.sh
(where it starts workers and where it reports), tools/quicktest.sh (only if the quick test starts workers the same
way; say which).

Reading path:
1. worker/model.py `apply` (dispatches an op to `op_<type>`; `HANDLERS`), and a few handlers reading their op
   (`op["x"]`, `op.get("x")`), including ones that pass the op to helpers (`plane_from`, `resolve_face`,
   `move_cut`, `plane_fit.apply`).
2. tools/fulltest.sh: how it starts workers (`SERVE_PORT=0 ... SERVE_STATUS_FILE=1`) and prints its verdict.

Today (checked 2026-11-27): an op field the worker doesn't read is silently ignored (protocol.md: "Unknown fields
are generally ignored"), so a window sending `distnace` instead of `distance` gets the default and no error.

Request:
1. **Record what's read.** With `SERVE_FIELD_AUDIT=<file>` in the environment, `apply` hands each handler its op
   wrapped in a dict that records every key read (`[]`, `get`, `in`, `items`/`keys`/`values` count as reading all,
   copies keep recording), and appends, per op type, the keys sent and the keys read to that file (one JSON line per
   op is fine). Without the variable, nothing changes and nothing is wrapped (no cost in the app).
2. **Report and fail.** worker/field_audit.py reads the file(s) and prints, per op type, any key that was sent but
   never read in the whole run (`id` and `type` are always read). tools/fulltest.sh sets the variable for its
   workers and fails the run when the report isn't empty, naming the op type and the key.
3. **Fix what it finds**, if anything: a key the window sends that nothing reads is either a bug (the worker
   should read it) or dead (the window should stop sending it). Don't change behaviour to make it pass: list each
   in your response with which it was, and for a real bug ask the integrator before fixing (`job.py wait --scope`).

Not in this job: checking fields the worker reads that the window never sends (defaults), the request-level
fields (H169 covers messages), any change to the protocol.

What can fail:
- A key read only on a rare path reported as unread: the report covers the whole full test; if a real field is
  only read in a branch no test reaches, that's a missing test: say so and add one rather than allow-listing it.
- The wrapper changing behaviour (a handler that checks `isinstance(op, dict)`, mutates the op, or JSON-dumps it):
  subclass dict, so all three behave as before. Check: the full test passes with and without the variable, same
  results (compare_suites).

Checks:
- worker/test_field_audit.py: the wrapper records `[]`, `get`, `in`; a sent-but-unread key is reported; without the
  variable `apply` gets the plain op.
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope), with the audit on in the full test.
