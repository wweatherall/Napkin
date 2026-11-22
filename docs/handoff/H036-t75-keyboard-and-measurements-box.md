### H036 — T75: move keyboard handling and the measurements box out of viewport/main.gd

Author: Claude (integrator) | Date: 2026-11-21 | Status: answered | For: a Claude session

References: T75, A33b; T39/T41 (the same pattern: new Nodes, main forwards the old names so tools and tests
don't change); I43 (press rule), I48 (Delete / Backspace and the measurements box), H030.

Touches: viewport/main.gd, viewport/keys.gd and viewport/measure_box.gd (new; names are yours), viewport/CLAUDE.md
(where it says what main.gd holds), ARCHITECTURE.md (the module-table rows for main.gd and the new files),
viewport/test_*.gd or a new quick section only if a new headless check needs one. Not viewport/tools/*: a tool that
reads `m.vcb` or calls `m.apply_vcb()` keeps working through main's forwarding.

Request: same behaviour, behind the existing tests. Move out (1) the keyboard: `_input` and the key half of
`_unhandled_input` (tool keys, Delete/Backspace, Tab/⌥ for Push/Pull, shortcuts); mouse handling stays in main;
(2) the measurements box (VCB): `vcb`, `typing`, `ui_vcb*`, `_vcb_style*`, `_update_vcb()`, `apply_vcb()`,
`length_pending` and the typed-value parsing that feeds them. Main keeps forwarding names so nothing outside
moves. Report main.gd's line count before and after. Run the quick test after each of the two moves and
`tools/fulltest.sh` at the end (all six recorded suites must match without `--update-reference`). Anything that
looks like a behaviour change or a bug: note it, don't fix it here.

#### Response — Claude (worker session), 2026-11-22

Done on `claude/h036-keys`. Status: answered.

- `viewport/measure_box.gd` (`m.measure`): `vcb`, `typing`, `length_id`, `length_pending`, the label/box/value
  nodes and their two styles; `build(row)`, `update()`, `apply()`, `on_length()`, plus `type_char`, `backspace`,
  `stop_typing`. main forwards `vcb`, `typing`, `length_id`, `length_pending`, `ui_vcb`, `ui_vcb_label`,
  `ui_vcb_box`, `_update_vcb()`, `apply_vcb()`, `_on_length()`. No tool or test changed.
- `viewport/keys.gd` (`m.keys`): `before_gui(e)` (Tab / ⌥ in Push/Pull, called from main's `_input`) and
  `press(e)` (everything that was the key branch of `_unhandled_input`). main keeps `_input` and
  `_unhandled_input` as entry points, because tests call `m._unhandled_input` directly and the order matters: a
  press drops a pending length, then Esc while Properties picks a face cancels the pick. Both of those stay in
  main, ahead of `keys.press`. I left that one Esc there because it belongs to the Properties pick mode, which
  mixes mouse and key.
- main.gd: 2,105 → 2,027 lines.
- Tests: quick test 139/139 after the measurements box moved, and again after the keyboard moved. Full test:
  feature tests pass every time. In the 5 branch runs I checked in full, the six recorded suites matched in 3
  without `--update-reference` (snaptest crashed in one of those 3). In the other 2, one suite differed each time
  (infertest, then mirrortest).
- **Found, not fixed (pre-existing):** the full test fails now and then on main too. In a detached checkout
  of main (04a5e11), 2 of 4 runs had a recorded suite differ (movetest, holetest). The suite that differs changes
  from run to run. In the branch's infertest failure the T5b grab missed the slab, right after a slow FreeCAD
  round trip (368 ms against 56 ms), which looks like timing under load. The snaptest crash was signal 11 in
  Godot's macOS open-file event handling at startup, before our scripts ran. Worth a Work list item: the full
  test is P13's merge gate.
- Docs: ARCHITECTURE.md (flowchart; module table: main.gd row edited, keys.gd and measure_box.gd rows added;
  the length-input row and the "Typed measurement syntax" row now name measure_box.gd), viewport/CLAUDE.md
  (Files; Typed values).
