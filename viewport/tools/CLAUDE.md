# viewport/tools/: the tools

One object per tool (T4). Each owns its state; `main.gd` hands it the cursor, clicks, keys and typed values.
The viewport guide (`../CLAUDE.md`) covers drafts, waves and the rules for drawing.

## The interface (`tool.gd`, the base every tool extends)
- `setup(m)` gives the tool `m` (main.gd) and `infer` (inference.gd). Snap only through `infer` / `m.snap()` /
  `m.pick()`: one snapping engine for every tool (I03b).
- `mouse_moved`, `click`, `double_click`, `release` (a press-and-drag ends here), `key(e)` (keys the tool handles
  itself; return true when handled), `typed(txt)` (a value from the measurements box, after Return), `reset()`
  (switching tools, Esc). Status: `hint()`, `tip()` (by the cursor), `vcb_label()`, `vcb_value()`.
- `busy()`: in the middle of an operation, so typed characters go to the measurements box; `accepts(ch)`: which
  characters it takes (digits and arithmetic; letters, spaces and quotes once something is typed, for units).
- While typing, Shift stays with the text (for `"` and `'`); other tool keys (arrow-key locks) still reach `key()`.
- `typed()` gets lengths already worked out, in mm (`"150.000000000000"`, Rectangle `"w,h"`): main.gd evaluates
  what was typed (units.gd, or FreeCAD for what it declines). Move also gets its count syntax raw (`3x`, `/3`).

## Making an action
1. Build the op: an id from `m.counters` (e.g. `"pp%d"`), `type`, and targets by geometry (`{body, normal,
   point}`, never face numbers, A03); a new board takes a new `b` id.
2. `m.ops.append(op)`, draw the draft at once, start the wave (`m._begin_wave`, `m._attach_wave`), clear the
   tool's state and overlays, then `m.sync()`. FreeCAD confirms later; never wait for it.
3. The worker needs a matching `op_<type>` (worker/CLAUDE.md). Add a quick-test step in `tests/quick/<section>.gd` (register a new section in `tests/quick_runner.gd` QUICK_LANES).
Tools talk to the worker only through `ops` and `m.sync()`.

## The tools
- `select_tool.gd` (Space): click selects (from outside, an assembly or array row whole), Shift-click adds or
  removes, empty space clears; double-click enters an assembly or array (T20), Esc leaves.
- `paint_tool.gd` (no key yet, Q14): paints the Wood menu's wood; a linked board paints its family. T turns grain.
- `rect_tool.gd` (R): click a face or the ground, then click or type `width, height`. Started with a click it ends
  with a click; started with a press-and-drag it ends on release (a wobbly click still counts as a click, I29).
- `push_tool.gd` (P): click a face or rectangle, move, click or type a distance (minus = cut). Snaps to faces
  behind (to the back face = a through-cut, `"through": true`, I24); on a face it joins that board, B for a new
  board (I04b).
- `move_tool.gd` (M), SketchUp style: grab a point on a board (or a hole's wall: the hole), move, click or type a
  distance. Ctrl/Option toggles copy; Shift toggles mirror (I12c); arrows cycle axis lock → plane lock → free.
  After a copy: `5x` / `*5` for an array, `/5` to spread copies; a plain number right after a move changes its
  distance (`_amend_last_move`). Mirroring can use any face's plane (T27).
