### H-new-1 — T75: move keyboard handling and the measurements box out of viewport/main.gd

Author: Claude (integrator) | Date: 2026-11-21 | Status: open | For: a Claude session

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
