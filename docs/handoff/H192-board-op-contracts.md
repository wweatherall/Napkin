### H192 — Contracts for the single-mode board ops (paint, grain, hide, delete, link, assembly, mirror, unfit)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: gemini

References: William, 2026-11-27 ("carry on with the contracts"), H189, H191 (the contracts' shape and the generic
checks), docs/op-contracts.md, P73.

Touches: worker/paint.py (`op_set_material`, `op_turn_grain`), worker/visibility.py (`op_hide`),
worker/deletion.py (`op_delete`), worker/move.py (`op_make_component`, `op_detach`, `op_make_unique` only: a
`CONTRACT` each), worker/assembly.py (`op_make_assembly`), worker/mirror.py (`op_mirror`), worker/model.py
(`op_unfit` only), tests/op_contracts.json (regenerated), worker/test_op_contracts.py,
viewport/test_tool_context.gd and viewport/test_selection.gd (the tool check, where the op is built),
docs/protocol.md (those ops' rows, only where the check shows they disagree), docs/op-contracts.md.

Reading path:
1. docs/op-contracts.md (as H191 left it) and two of H191's contracts.
2. Each handler above: the fields it reads, limits, rejections; `creations`, `_op_makes`, `_op_refs` for each.
3. Where the app builds each op: `grep -rn '"type": "<op>"' viewport` (selection.gd, appearance.gd, menus, tools);
   viewport/test_selection.gd and test_tool_context.gd for builders already driven in tests.

Today (checked 2026-11-27): after H191, five profile ops have contracts. These ten ops each take one fixed set of
fields (no modes), so they fit the same shape. A module holding several handlers needs one contract per op: make
`CONTRACT` a list there (or add `CONTRACTS`), and op_contracts.py collects both.

Request:
1. A contract for each of the ten ops, from what its handler really does. One whose fields depend on another field
   (a mode) doesn't fit: leave it out and say why in the report (H193 designs for those).
2. The tool check for each op whose builder a test already drives or can drive without the app; for the rest, name
   the builder in the contract (`tool`) and list it in the report as unchecked.
3. The checks from H191 run over the new contracts unchanged (they read every contract); the draft check applies only
   to ops that draw a draft (none of these: say so).
4. docs/op-contracts.md updated: which ops have contracts, which builders are checked, and the ops left out with why.

Not in this job: move, push_pull, property_edit, fit (H193), runtime validation (H194), changing a handler or builder.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope); quick 401/401.
- `python3 worker/op_contracts.py --check` and `python3 tools/protocol_map.py --check` pass.

Response (Gemini, gemini-elm-1127-200128, 2026-11-27):
- Added `CONTRACT` / `CONTRACTS` for 9 single-mode board ops: `set_material` and `turn_grain` (`worker/paint.py`), `hide` (`worker/visibility.py`), `delete` (`worker/deletion.py`), `make_component`, `detach`, and `make_unique` (`worker/move.py`), `make_assembly` (`worker/assembly.py`), and `unfit` (`worker/model.py`).
- Left `mirror` (`worker/mirror.py:op_mirror`) out: `group` (and `new_ids` / `creates`) depend on `replace` (`replace=False` copy mode reads `group` and creates `new_ids`/`group`; `replace=True` flip-in-place mode short-circuits `group` unread and reuses target `BodyId`s), so it belongs in H193.
- Updated `worker/op_contracts.py` to collect `CONTRACTS` / list `CONTRACT` and include `worker/model.py` (for `op_unfit`), and regenerated `tests/op_contracts.json` (14 ops total).
- Updated `docs/protocol.md` to split the combined `detach` / `make_unique` row into separate rows so `tools/protocol_map.py --check` matches each op.
- Extended `worker/test_op_contracts.py` (board/array/component/fit fixtures, `string`/`[string]` kinds, list-valued `creates` flattening) and `viewport/test_document.gd` (`_build_op_from_contract` kinds and list-valued `creates`/`refers_to` flattening).
- Added tool checks in `viewport/test_selection.gd` (`hide`, `make_assembly`, `make_unique`, `detach`, `delete`) and `viewport/test_tool_context.gd` (`Appearance` `set_material`, `turn_grain`). Unchecked / absent: `unfit` (`viewport/property_panel.gd`, UI `PanelContainer`) and `make_component` (`tool: ""`, internal `as_component` helper only). None of the 9 board ops draw a draft (draft check remains profile-ops-only).
- Updated `docs/op-contracts.md` with the 14 covered ops, checked/unchecked builders, and ops left out.
- Changed from the brief:
  - `worker/op_contracts.py`: updated to collect `CONTRACTS` / list `CONTRACT` and read `worker/model.py` (requested in Today section; not listed in Touches).
  - `viewport/test_document.gd`: mechanical P73 update so H189's generic `tests/op_contracts.json` check handles `string`/`[string]`/`integer`/`bool` fields and list-valued `creates`/`refers_to` (`targets`).

Result: `tools/TEST_BEFORE_MERGING.sh` (full scope): GATE PASS, QUICK 401 passed, 0 failed, 0 known failures (89 s); `python3 worker/op_contracts.py --check` and `python3 tools/protocol_map.py --check` pass.
