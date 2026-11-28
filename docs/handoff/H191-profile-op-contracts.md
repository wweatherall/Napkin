### H191 — Contracts for every profile op (rect, polygon, line, arc), and the tool and draft checks Circle's pilot lacked

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: gemini

References: William, 2026-11-27 ("carry on with the contracts; close those gaps between the drawing tool and the
draft drawing"), H189 (the Circle pilot: `CONTRACT`, worker/op_contracts.py, tests/op_contracts.json,
docs/op-contracts.md and its gaps), H182, H184, P73.

Touches: worker/push.py (a `CONTRACT` for `rect` beside `op_rect`; the handler unchanged), worker/polygon.py,
worker/line.py, worker/arc.py (a `CONTRACT` each, handlers unchanged), tests/op_contracts.json (regenerated),
worker/test_op_contracts.py, viewport/test_tool_context.gd (the contract checks for tools and drafts), docs/protocol.md
(the `rect`, `polygon`, `line`, `arc` rows, only where the check shows they disagree), docs/op-contracts.md.

Reading path:
1. docs/op-contracts.md and worker/circle.py's `CONTRACT`: the shape and what each part is checked by.
2. Each handler (`op_rect`, `op_polygon`, `op_line`, `op_arc`): every field it reads, its limits and what it rejects;
   worker/session.py `creations` and viewport/document.gd `_op_makes` / `_op_refs` for what each creates and refers to.
3. viewport/test_tool_context.gd ~480-520: how Circle's tool is driven without the app and its committed op read back
   from `doc.ops`; the other profile tools' blocks in the same file.
4. viewport/profiles.gd `register_rect` / `register_line`: how a profile op's draft is drawn from its fields.

Today (checked 2026-11-27): only Circle has a contract. The pilot's two gaps: nothing checks that a drawing tool builds
an op its contract allows, and nothing checks that the draft drawing handles every op shape its contract allows.

Request:
1. A `CONTRACT` for `rect`, `polygon`, `line` and `arc`, the same shape as Circle's, written from what each handler
   really reads, limits and rejects (if a handler reads a field only in some cases, write it as optional and say so in
   the report). `python3 worker/op_contracts.py` regenerates tests/op_contracts.json with all five.
2. worker/test_op_contracts.py checks every contract in the file, not just Circle (required-only op, full op, missing
   required field, below `min`, `creates`), so a sixth contract is checked without editing the test.
3. **The tool gap**: in viewport/test_tool_context.gd, for each of the five profile tools, the op it commits has every
   required field of its contract and no field outside it (read the contracts from tests/op_contracts.json).
4. **The draft gap**: for each of the five contracts, `register_rect` / `register_line` (whichever draws that type)
   draws a draft from a required-only op and from an op with every field, without an error, so the draft drawing
   accepts every shape the contract allows.
5. Mutation check, one per new check: a contract field the tool doesn't send (required), a field the tool sends that
   the contract lacks, a required field the draft drawing can't do without, removed from the contract. Report which
   check caught each.
6. docs/op-contracts.md: the table and gaps updated for the five profile ops (the tool and draft rows now checked).

Not in this job: other ops (H192), validating ops at runtime (H194), changing a handler, tool or draft, or the
contract's shape beyond what these ops need.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope); quick 401/401.
- `python3 worker/op_contracts.py --check` and `python3 tools/protocol_map.py --check` pass.

Response (Gemini, gemini-maple-1127-195450):
- Added `CONTRACT` dicts to `worker/push.py` (`rect`), `worker/polygon.py` (`polygon`), `worker/line.py` (`line`), and `worker/arc.py` (`arc`), and regenerated `tests/op_contracts.json` via `python3 worker/op_contracts.py`.
- `line` and `arc` mark `snap_start` and `snap_end` as `"viewport_only": True` (sent by `line_tool.gd` / `arc_tool.gd`, read by `register_line`, documented in `docs/protocol.md`, unread by `op_line` / `op_arc`).
- Extended `worker/test_op_contracts.py` to support `integer`, `bool`, `[number, number, number]`, `[[number, number, number]]`, `max` bounds, and `viewport_only` fields across all contracts (52/52 passed).
- Added `_test_profile_contracts()` in `viewport/test_tool_context.gd` checking all five profile tools (`circle`, `rect`, `polygon`, `line`, `arc`) against `tests/op_contracts.json` and checking `register_rect` / `register_line` on both required-only and full ops for all five contracts (165/165 passed).
- Fixed `docs/protocol.md` `line` and `arc` rows (`snap_start?: boolean`, `snap_end?: boolean`) so `tools/protocol_map.py --check` parses all optional fields, and updated `docs/op-contracts.md` table and gaps.
- Mutation checks (all 3 caught and reverted):
  1. Required field tool does not send (`circle.bogus_req` added): caught by `H191: circle tool commits op matching contract (missing=["bogus_req"] extra=[])`.
  2. Field tool sends that contract lacks (`circle.radius` removed): caught by `H191: circle tool commits op matching contract (missing=[] extra=["radius"])` (and `register_rect draws required/full circle op`).
  3. Required field draft needs removed (`rect.size` removed): caught by `H191: register_rect draws required rect op` / `register_rect draws full rect op` (`Invalid access to property or key 'size'`, plus `rect tool commits op matching contract`).

Result: `python3 worker/op_contracts.py --check` passed; `python3 tools/protocol_map.py --check` passed; `tools/TEST_BEFORE_MERGING.sh` passed (`GATE PASS: full test passes; QUICK 401 passed, 0 failed in 28.9 s ; 0 known failure(s); 88 s total`).
