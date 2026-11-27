### H171 — Fits become their own ops (`fit`, `unfit`), and old files' fits are upgraded when opened

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: open | For: gemini

Item: T162

References: T162 (this item), William, 2026-11-27 ("Make a fit op job. Make it update old files. Fortunately we can
still make breaking changes at this point"), A35 (a changed message bumps PROTOCOL_VERSION on both sides), G09 (never
lose work), T161 (face numbering: not in this job), H169 (protocol_map.py checks protocol.md against the code).

Touches: worker/model.py (`op_property_edit`, `HANDLERS`, a new `op_fit` / `op_unfit`), worker/plane_fit.py (`apply`,
`replace`: called the same way, only their entry changes), worker/session.py (where ops are read from the journal and
from Meta `ShopSketchOps`: `read_journal`, `_open_existing` and the code at ~555), worker/serve.py
(`PROTOCOL_VERSION`), viewport/main.gd (`PROTOCOL_VERSION`, `_edit_property`), viewport/document.gd (`_op_refs`:
the list of IDs an op names), viewport/property_panel.gd (the three `edit_requested.emit` calls with
`plane_fit`/`replace_fit`), docs/protocol.md (the Operation payloads table), worker/test_properties.py,
worker/test_native.py, worker/scenario/97_plane_fit_refit.py, worker/scenario/98_plane_fit_identity.py,
worker/scenario/99_plane_fit_flush.py, viewport/tests/quick/properties.gd, worker/test_load.py, worker/test_floor_copy.py.

Reading path:
1. docs/protocol.md `## Operation payloads`: the three `property_edit` rows (value/expression, plane fit, replace fit).
2. worker/model.py `op_property_edit` (dispatches on `mode`) and `apply` (`plane_fit.refit_inputs`).
3. viewport/property_panel.gd lines ~282, 335, 362 (`edit_requested.emit({... "mode":"plane_fit" ...})`) and
   viewport/main.gd `_edit_property` (makes the op: `id` prefix `pr`, `type` `property_edit`).
4. viewport/document.gd `_op_refs` (line ~577: `property_edit` names only `body`).
5. worker/session.py: `read_journal`, `_open_existing`, the `ShopSketchOps` reader (~555), `canon`.

Today (checked 2026-11-27): fitting a board to a face, and taking a fit off, are `property_edit` ops with
`mode: "plane_fit"` / `"replace_fit"`, though they edit no property: they have their own fields and their own code
(`plane_fit.py`). Saved models hold such ops in their journal and in the .FCStd's Meta `ShopSketchOps`.
`_op_refs` lists only `body` for a property_edit, not a fit's `target_body`.

Request:
1. **Two new op types**, the same fields minus `mode`:
   - `fit`: `body`, `target_body`, `axis`, `face`, `fit_mode`, `reverse?` (today's plane_fit) -> `plane_fit.apply`.
   - `unfit`: `body`, `axis`, `value` (today's replace_fit: restores plain stock at that length) -> `plane_fit.replace`.
   `property_edit` keeps only `mode: "value" | "expression"`; a `property_edit` with any other mode is refused
   (`OpError`), so nothing old slips through un-upgraded.
2. **The window sends them.** property_panel.gd emits the fit fields without `mode` and says which kind;
   `_edit_property` makes a `fit` op (ID prefix `ft`) or an `unfit` op (prefix `uf`), else `property_edit` (`pr`) as
   today. `_op_refs` lists `body` and `target_body` for `fit`, `body` for `unfit`.
3. **Old files upgraded on open (G09: nothing lost).** One function, `upgrade_op(op)` in session.py, rewrites a
   `property_edit` with mode `plane_fit` to `fit` and with `replace_fit` to `unfit` (same `id`, same fields, `mode`
   removed), and leaves every other op alone. It runs on every op read from disk: the journal (including its
   `dropped` and floor entries), Meta `ShopSketchOps`, and the floor copy's ops. The first save after opening writes
   the upgraded ops, so a file is upgraded once. IDs never change, so undo, redo and references still line up.
4. **Protocol 17** on both sides (H170 takes 16). protocol.md: `fit` and `unfit` rows in the Operation payloads
   table, `property_edit` down to value/expression, and one line: "Files saved before protocol 17 have their fits
   upgraded when opened." `python3 tools/protocol_map.py --check` passes.

Not in this job: face numbering (T161), push_pull (T159), checking unknown fields (T160), any change to how a fit
behaves.

What can fail (P42: this changes what is saved and how old files load):
- An old model with fits doesn't reopen the same: open a saved model made before this change (the scenarios 97-99
  make them; or save one on main first, then open it on the branch) and check the bodies, the fit, undo across the
  fit, and redo come out the same. Check: worker/test_load.py, a fixture written by main's code.
- A fit in the journal's `dropped` list or the floor copy not upgraded: `upgrade_op` is called on each. Check: a
  test with one of each.
- An upgraded op whose canonical key changes makes sync think the history diverged and rebuild: the window gets
  the upgraded ops in the open reply, so its next sync matches. Check: a test that opens an old file and syncs the
  same ops back with no undo or rebuild (`how: "nothing"`).
- An old window (protocol 16) on a new worker: refused by the version check, as today.

Checks:
- worker/test_properties.py, worker/test_native.py, worker/test_load.py, worker/test_floor_copy.py, scenarios 97-99, the viewport
  properties quick tests: fits made, refit, taken off and reopened, as `fit`/`unfit`.
- `python3 tools/protocol_map.py --check`.
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope).

### Response

- **2026-11-27 (gemini, gemini-walnut-1127-0808):**
  Branch `gemini/h171-fit-op`. Split plane fits out of `property_edit` into `fit` (`ft`) and `unfit` (`uf`), added `upgrade_op` in `worker/session.py` for old journals/dropped entries/Meta `ShopSketchOps`, and bumped `PROTOCOL_VERSION` to 17.
  Architecture: `fit` and `unfit` are top-level ops (`Model.op_fit`, `Model.op_unfit`) with `ft`/`uf` IDs and `_op_refs` (`body`, `target_body` for `fit`; `body` for `unfit`), `property_edit` accepts only `mode` `"value" | "expression"`, `session.upgrade_op(op)` upgrades pre-protocol-17 fits on read, and `PROTOCOL_VERSION` is bumped 16 -> 17 in `worker/serve.py`, `viewport/main.gd`, and `docs/protocol.md`.
