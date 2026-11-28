### H189 — An op contract, piloted on Circle: what it takes, refers to and creates, written once beside its handler and checked everywhere else

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: open | For: gemini

References: William, 2026-11-27 (ChatGPT's architecture review: "adding an operation should require understanding
the operation itself, not every system through which it passes"; the integrator's answer: pilot on Circle only,
built on the existing generators, no second copy of the rules), H182 (tests/op_creations.json: both sides read one
table), H183 (`about`), H184 (field audit per run), H169's follow-up (operation payload generation), P73.

Touches: worker/circle.py (a `CONTRACT` beside `op_circle`; the handler itself unchanged), worker/op_contracts.py
(new), worker/test_op_contracts.py (new), tools/protocol_map.py (a contract check on the `circle` row),
tools/test_protocol_map.py, tests/op_contracts.json (new), generated, viewport/test_document.gd (one check block),
docs/protocol.md (the `circle` row only, if the check shows it disagrees), docs/op-contracts.md (new), the pilot's
report.

Reading path:
1. worker/circle.py `op_circle`: what it reads (`id`, `plane`, `radius`, `center`) and rejects.
2. docs/protocol.md's `## Operation payloads` table, the `circle` row (hand-written today), and
   tools/protocol_map.py: how it checks the message table against the code (`--check`).
3. worker/session.py `creations` and viewport/document.gd `_op_makes` / `_op_refs` (H182): what an op creates and
   refers to, on each side; tests/op_creations.json and the two tests that read it.
4. worker/field_audit.py (H184): which fields a run read.
5. Where else Circle's meaning lives (read, don't change): viewport/tools/circle_tool.gd (builds the op),
   viewport/presenter.gd `register_rect` / `circle_geometry` (draws its draft), worker/scenario/99_op_registry.py.

Today (checked 2026-11-27): what a circle op means is written in at least five places: the handler (fields and
limits), protocol.md's row (fields and limits again, by hand), `creations` and `_op_makes` (what it creates),
`_op_refs` (`plane.on.body`), and the tool and presenter (how it is built and drawn). Only H182's table checks two
of them against each other.

Request:
1. **The contract**, a plain dict `CONTRACT` in worker/circle.py beside `op_circle`:
   `{"type": "circle", "fields": {"plane": {"required": True, "kind": "Plane"}, "radius": {"required": True,
   "kind": "number", "min": 0.001}, "center": {"required": False, "kind": "[number, number]", "default": [0, 0]}},
   "refers_to": ["plane.on.body"], "creates": ["id"], "tool": "viewport/tools/circle_tool.gd"}` (adjust only to what
   the handler really does: say what you changed and why). worker/op_contracts.py collects every handler module's
   `CONTRACT` (as Model's handlers are discovered) and writes tests/op_contracts.json (`python3 worker/op_contracts.py`;
   `--check` exits 1 if the file is stale).
2. **Checks against the contract**, each failing if the contract and the code disagree:
   - worker/test_op_contracts.py: an op built from the contract's required fields (and one with every field) runs
     through `op_circle` under field_audit's `AuditedDict`: every field is read, none outside `fields` is; an op
     missing a required field is rejected; a radius below `min` is rejected.
   - The same test: `creations` of a contract-built op yields exactly the `creates` ids.
   - viewport/test_document.gd: for each contract in tests/op_contracts.json, `_op_makes` of a built op matches
     `creates`, and `_op_refs` matches `refers_to` (read the paths from the op).
   - tools/protocol_map.py `--check`: for an op with a contract, its protocol.md row names exactly the contract's
     fields, required ones without `?`, optional ones with `?`.
3. **Mutation check** (the review asked for it): make each of these defects in turn, run the checks, and put it back:
   rename `radius` in the contract; drop `refers_to`; add a field the handler doesn't read; change `min`; take
   `center` out of the protocol row. Report which check caught each one. A defect no check catches goes in the report
   as a gap, not hidden.
4. **docs/op-contracts.md**, the pilot's report for William's decision: the contract's shape; every place Circle's
   meaning lived before and which of them the contract now checks; what adding a field to Circle takes now, as a list
   of files (before and after); the mutation results; and what a Move or Push/Pull contract would need that Circle
   didn't (one paragraph each, from reading their handlers). Under 150 lines.

Not in this job: contracts for any other op, validating ops against contracts at runtime (a behaviour change:
William's call after the pilot), changing the handler, the tool or the presenter, or generating protocol.md's row
(the check is enough for the pilot).

What can fail:
- The contract becoming a third copy nobody checks: every part of it is used by a check in Request 2. Check: the
  mutation results in Request 3.
- The GDScript check reading a stale tests/op_contracts.json: `op_contracts.py --check` runs in the feature tests
  (worker/test_op_contracts.py calls it), so a stale file fails the gate.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope); quick 401/401.
- `python3 worker/op_contracts.py --check` and `python3 tools/protocol_map.py --check` pass.
