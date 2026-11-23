### H052 — T66: lengths shown in the model's units

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: gemini

References: T66, I57, I62 (the Units menu, rounding, ~, saved per model), I59 (bare numbers typed are in the model's
units), I35 and T32 (typing lengths), P21 (viewport vs FreeCAD answers: tests/length_cases.json), Q22.

Touches: viewport/units.gd and viewport/test_units.gd (formatting), viewport/measure_box.gd (display, default_unit),
every viewport/tools/*_tool.gd's vcb_value (a length, not a string in mm), viewport/main.gd (the Units menu only),
worker/session.py (the units in the .FCStd's Meta, beside ShopSketchRev) and worker/serve.py (open / set_units),
both PROTOCOL_VERSIONs (worker/serve.py, viewport/main.gd: a message changes), worker/test_*.py for the units' save
checks, a new quick section. Not ARCHITECTURE.md or docs/protocol.md: write what changes there as "Architecture:"
lines (the open / reload replies' new field, the new message). T88's tool moves are in (H083): every tool is
context-only, so a tool's vcb_value reaches units only through what ToolContext gives it (add to `ctx.ui` if needed,
on the allowlist in test_tool_context.gd).

Request: build I57 and I59. Feet and inches 8' 3 1/4", inches as fractions 99 1/4", as decimals 99.25", metric m /
cm / mm, each with its rounding; default fractional inches at 1/16"; ~ in front of a length rounding changed; the
choice saved in the model, a new model starting with the last units used (user://settings.cfg); a bare typed number
in the model's units. Display only: ops stay in exact mm. Checks: unit tests for every format and rounding (and the
~), a round-trip check that what the box shows parses back to the same rounded length through units.gd and
FreeCAD's length_input (P21), a worker test that the units survive save and reopen, a quick section that switches
units and reads the box.

Today (checked 2026-11-22, after H083): the oplog a window sends always says `"units": "mm"` (document.gd
`oplog()`), and serve.py `run_sync` refuses anything else: that is the ops' unit and stays mm (display only, I57);
the display units are a separate field. The model's revision is kept on the Session (`self.rev`) and written into
`doc.Meta["ShopSketchRev"]` at each save (session.py `save`); it is read back from Meta only when a file is opened
(`_open_existing`) or reloaded (`reload_outside`). The live document is replaced in three places: `_new_doc` (a
rebuild from empty, `_rebuild` with no undo floor), `_load_file` (open, an outside save reloaded, a rebuild from
the floor copy, A38). The measure box asks the worker to evaluate a typed length with `"default_unit": "mm"`
(measure_box.gd).

What can fail (P42: the units are saved in the model and come back on open and reload):
- A rebuild replaces the document (`_rebuild`: `_new_doc` makes an empty one, the floor copy's Meta is from when
  FreeCAD's edit was taken in): the units must not be lost or go back. Keep them on the Session, as `rev` is, and
  write them into Meta at every save. Check: set inches, make more than 20 actions and undo past them (a rebuild),
  save, reopen: inches.
- Changing the units with no action after it: the change is saved (it doesn't wait for the next action), and a
  window closed straight after keeps it. Check: set_units, flush, reopen: the new units.
- A file from before this job (no units in its Meta), and a Meta value that isn't one of the formats (edited
  by hand, a newer version): it opens, in the last units used (I62: as a new model does; a default from Preferences, T111, comes later) and is saved with them; a value it can't read never stops the open.
  Checks: an old fixture file; one with `ShopSketchUnits` set to `"furlongs"`.
- FreeCAD saves the file (the outside save, A36): reload takes the units in FreeCAD's file (FreeCAD keeps Meta);
  "Keep Shop Sketch's" keeps the window's. Check: both, in worker/test_outside_save.py's style.
- The worker gone while the units change (the reply never comes): the window shows the new units at once (display
  only, never waits on FreeCAD) and sends them again once the link is back, after the open. Check: a quick or
  document test that drops the link between the menu choice and the reply.
- A new model: the open reply has no units; the window sends the last units used (user://settings.cfg) and they
  are saved with the model. The worker's reply to that open must not overwrite a choice the user made meanwhile.
  Check: a new model opens in the last units used.
- Undo doesn't change the units (they aren't an action): check undo after a units change leaves them.
- A typed bare number goes out with the model's unit as `default_unit` (I59), and the viewport's own answer
  (units.gd) agrees with FreeCAD's for it (P21: add cases to tests/length_cases.json for a bare number in inches).

Reading path: document.gd `oplog` and `sync` → serve.py `run_sync`, the `open` / `reload` / `keep_mine` handlers
and `open_reply` → session.py `_open_existing`, `save` (the Meta write), `_rebuild`, `_new_doc`, `_load_file`,
`reload_outside` → measure_box.gd (where a typed length is worked out) → units.gd. Who owns what: the Session owns
the saved units (as it owns rev); the window owns what's shown and sends the choice; tools only ask ToolContext
to format a length.

#### Response (Gemini, 2026-11-22)

Branch: `gemini/h052-t66-units` | Commit: `<pending>`

Implemented T66 (I57, I59, I62):
- `viewport/units.gd`: canonical `<format>:<rounding>` specs for all six formats (`ft-in`, `in-frac`, `in-dec`, `m`, `cm`, `mm`) with their rounding choices (`1/8`–`1/64"`, `0.1`–`0.001"`, `1`–`0.01 mm`, `1`–`0.01 cm`, `0.1`–`0.001 m`), default `in-frac:1/16`, `~` prefix whenever rounding changes the length beyond `ROUND_TOL_MM` (0.0005 mm, absorbing float32 noise while catching any >=0.001 mm rounding), `default_unit_of`, and format/precision helpers.
- `viewport/measure_box.gd`: owns the window's display units, last-used persistence in `user://settings.cfg` (`[units] last`, disabled in `test_mode` unless a test sets `settings_path`), immediate UI updates, `set_units` send/reply/reconnect/open-race/reload handling, `default_unit` for both local `Units.evaluate_*` and worker `length` requests (I59), and removes the hardcoded `" mm"` suffix from `ui_value`.
- `viewport/tool_context.gd` & `viewport/tools/*_tool.gd`: added `ctx.ui.format_length(mm)` (allowlisted in `viewport/test_tool_context.gd`); `rect_tool.gd`, `circle_tool.gd`, `line_tool.gd`, `push_tool.gd`, and `move_tool.gd` format `vcb_value()` (and Move's `tip()`) through `ctx.ui.format_length`.
- `viewport/main.gd`: added the top-level `Units` menu (`_units_menu_rid`, format + active format's rounding choices with radio checks), wired `measure` into `_on_open`, `_on_reloaded`, `_on_worker` (`set_units`), `_on_link_up`, `_outside_choice`, and `_reset_model_state`, and bumped `PROTOCOL_VERSION` 8 → 9.
- `worker/session.py` & `worker/serve.py`: `Session.units` (validated against `UNIT_SPECS`, unreadable/absent reads as `None` per I62), persisted in `doc.Meta["ShopSketchUnits"]` on every `Session.save` (with rollback on failed save), preserved across `_rebuild` (both empty and floor-copy), updated from FreeCAD's file on `reload_outside`, exposed on `open` / `reload` replies as optional `"units"`, and updated via `cmd: "set_units"` (which queues a save without an undoable op); bumped `PROTOCOL_VERSION` 8 → 9.
- Tests: `viewport/test_units.gd` (132 passed: every format/rounding/`~`, round-trip via `parse_length` & `evaluate_length`, FreeCAD `tests/length_cases.json` agreement with 21 new `default_unit` cases in `in`/`cm`/`m`, and `MeasureBox` lifecycle including link-drop reconnect, open race, reload, settings.cfg, and `default_unit`), `worker/test_model_units.py` (22 passed: `set_units` + `flush` + reopen, >20-op rebuild and floor-copy rebuild, undo invariance, pre-T66 and `"furlongs"` files, outside-save `reload` vs `keep_mine`, and FreeCAD `length_input` round-trip), `worker/test_length_input.py` (23 passed across all 2,521 table cases), `viewport/test_tool_context.gd` (147 passed), and `viewport/tests/quick/units.gd` (254/254 quick checks passing).

IDs added: none (builds I57, I59, I62).
Open questions: none.

Architecture: Protocol version bumped 8 → 9 (worker/serve.py, viewport/main.gd).
Architecture: open and reload replies carry optional units: string (canonical '<format>:<rounding>' from doc.Meta['ShopSketchUnits'], omitted when unset or unreadable, I57/I62).
Architecture: New worker command set_units ({cmd:'set_units', model, units, seq} → {ok, cmd:'set_units', model, units, rev, seq}) updates Session.units without an undoable op and queues an autosave.
Architecture: .FCStd Meta stores ShopSketchUnits beside ShopSketchRev on every Session.save; Session owns saved units across rebuilds (_new_doc and floor-copy _load_file), and reload_outside reads Meta from FreeCAD's file.
Architecture: ToolContext.ui gains format_length(mm) (allowlisted in viewport/test_tool_context.gd); viewport/measure_box.gd owns display units, last-used user://settings.cfg persistence, set_units sync/reconnect, and default_unit for typed lengths; tools format vcb_value (and Move's tip) only through ctx.ui.format_length.
Follow-up: tools/length_cases.py does not yet generate the default_unit cases appended to tests/length_cases.json; add a default_unit list to tools/length_cases.py next time it is regenerated.
Follow-up: tools/featuretest.sh keys each test's log by basename after test_, so a worker/test_<name>.py and viewport/test_<name>.gd with the same <name> overwrite each other's log (avoided here by naming worker/test_model_units.py); prefixing logs by folder in featuretest.sh would prevent silent collisions.
For the integrator: Update docs/protocol.md (PROTOCOL_VERSION 9, open/reload units field, set_units command, .FCStd Meta ShopSketchUnits) and ARCHITECTURE.md (Session.units, MeasureBox units ownership, ToolContext.ui.format_length) from the Architecture lines above, and record the T66 Work list result.
Result: <pending>; quicktest 254/254 + feature tests all green (units 132/132, model_units 22/22, tool_context 147/147, length_input 23/23); T66 display units (I57, I59, I62), Units menu, Meta persistence, set_units protocol v9, bare-number default_unit.

