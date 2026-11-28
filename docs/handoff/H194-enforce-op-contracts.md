### H194 — The worker checks each op against its contract before running it (ops with a contract only)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: gemini

References: William, 2026-11-27 ("close the gap: nothing enforcing the contract"; the integrator's answer: enforce op
by op, for ops that have a contract, not waiting for all of them), H189-H192 (the contracts), H183 (`about`), H184
(failed runs skip the field audit), docs/protocol.md (OpStatus), P73.

Touches: worker/op_contracts.py (a `validate(op)` function), worker/model.py (`Model.apply` only: call it before the
handler), worker/test_op_contracts.py, docs/protocol.md (one sentence in the Operation payloads section),
docs/op-contracts.md.

Reading path:
1. worker/model.py `Model.apply`: where an op reaches its handler, and the field audit around it (H184).
2. worker/session.py: where saved ops are upgraded when a file opens (migrations) before they are applied; a check
   must see the upgraded op, never the saved one.
3. worker/op_contracts.py and tests/op_contracts.json (after H192): the contracts and their `kind` / `min` values.

Today (checked 2026-11-27): a contract is checked only by tests. A malformed op reaches its handler and fails there,
with whatever error that raises (for a missing field, often `KeyError: 'radius'`, a Python name, not a message).

Request:
1. `validate(op)` returns the first problem or nothing, for an op whose type has a contract; for other types it
   returns nothing (they run as today). Problems, in this order, with exactly this wording (the op's type first):
   - `circle: missing radius` (a required field absent);
   - `circle: unknown field rad` (a field not in the contract, other than `id` and `type`);
   - `circle: radius must be a number` (a `kind` the value isn't: number, string, list, object; `Plane` and other
     named kinds count as object, `[number, number]` as a list of two numbers);
   - `circle: radius must be at least 0.001` (below `min`).
2. `Model.apply` calls it before the handler and raises `OpError(problem, about=[op id])` when there is one, so it
   reaches the window as a normal rejection (OpStatus `failed`, `message`, `about`) and the field audit records the
   run as failed.
3. **Nothing the app or a saved file sends today is refused**: the full test, every examples/ model and every
   tests/ scenario replay pass unchanged. If one is refused, that is a contract that is wrong or an op the app builds
   wrongly: fix the contract if the handler accepts the op; otherwise stop and ask William (`job.py wait`), because
   the fix changes what the app sends.
4. Tests: each of the four problems for a contracted op, an uncontracted op type untouched, and a saved op of an old
   format upgraded first and then passing.
5. docs/protocol.md: one sentence: ops with a contract are checked against it first, and the four messages.
   docs/op-contracts.md: the runtime gap closed for contracted ops.

Not in this job: contracts for more ops, checking `creates` / `refers_to` at runtime (FreeCAD stays the authority on
what an op made), or changing any handler's own messages.

What can fail:
- An older saved file whose ops carry a field no longer read (kept for compatibility) being refused on open: the
  check runs after the upgrade, and step 3 replays every saved example. Check: a test opening an old-format file.
- A rejection the window groups wrongly: the problem carries `about` with the op's own id. Check: the quick tests'
  rejection scenarios pass unchanged.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope); quick 401/401; the full field audit passes.

Result:
- Added `validate(op)` in `worker/op_contracts.py` (using raw `dict.*` lookups so `AuditedDict` read tracking is untouched) checking required fields, unknown fields, `kind` (`number`, `integer`, `bool`, `string`, `[string]`, `[number, number]`, `[number, number, number]`, `[[number, number, number]]`, and `Plane`/object), and `min`/`max` bounds for contracted ops while returning `None` for uncontracted ops.
- Wired `op_contracts.validate(op)` into `Model.apply` in `worker/model.py` before handler dispatch (inside the `SERVE_FIELD_AUDIT` `try:` block so validation rejections record `failed=True`), raising `OpError(problem, about=[op["id"]])`.
- Extended `worker/test_op_contracts.py` (147/147 passed) to cover all four validation errors, check ordering, `about`, uncontracted ops, and legacy `property_edit` (`mode="replace_fit"`) upgraded via `upgrade_op` before `Model.apply`.
- Updated `docs/protocol.md` and `docs/op-contracts.md`.
- `tools/TEST_BEFORE_MERGING.sh` passed (`GATE PASS: full test passes; QUICK 401 passed, 0 failed in 32.2 s ; 0 known failure(s); 110 s total`, including field audit).
