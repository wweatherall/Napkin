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
- Press and drag, or click and click (I43): a tool that starts on a press calls `press_started(screen)`, then
  `press_moved(screen)` on every move, and in `release` asks `press_released()`: `drag` true = end the action
  now, false = it was a click and the next click ends it. The thresholds are tool.gd's (tunables DRAG_PX, HOLD_MS).
- Distance policies (T33) are separate constants in `tool.gd`: `ACCIDENTAL_DRAG_MM` (0.5 mm) filters
  unsnapped pointer commits; typed values and geometry point/face snaps bypass it. `GEOMETRY_TOLERANCE_MM`
  matches the worker's existing 0.001 mm model tolerance. `DISTANCE_DISPLAY_FORMAT` / `DIMENSIONS_DISPLAY_FORMAT`
  preserve whole-mm text only: typed/snapped dimensions are sent without display or three-decimal rounding.
- `typed()` gets lengths already worked out, in mm (`"150.000000000000"`, Rectangle `"w,h"`): main.gd evaluates
  what was typed (units.gd, or FreeCAD for what it declines). Move also gets its count syntax raw (`3x`, `/3`).

## Making an action
1. Build the op: an id from `m.counters` (e.g. `"pp%d"`), `type`, and targets by geometry (`{body, normal,
   point}`, never face numbers, A03); a new board takes a new `b` id.
2. `m.ops.append(op)`, draw the draft at once, start the wave (`m._begin_wave`, `m._attach_wave`), clear the
   tool's state and overlays, then `m.sync()`. FreeCAD confirms later; never wait for it.
3. The worker needs a matching `op_<type>` (worker/CLAUDE.md). Add a quick-test step in `tests/quick/<section>.gd` (a new section file is picked up by itself; list it in `tests/quick_runner.gd` QUICK_LANES only to pin its lane).
Tools talk to the worker only through `ops` and `m.sync()`.

## The tools
- `select_tool.gd` (Space): click selects (from outside, an assembly or array row whole), Shift-click adds or
  removes, empty space clears; drag right selects enclosed units, left selects crossing units, Shift adds. Double-click enters an assembly or array (T20), Esc cancels a box before leaving. Delete acts on the reusable selection (T34).
- `paint_tool.gd` (no key yet, Q14): paints the Wood menu's wood; a linked board paints its family. T turns grain.
- `rect_tool.gd` (R): click a face or the ground, then click or type `width, height` (or press-and-drag, I43). Its
  second corner ignores snaps that would leave a side at zero (I44).
- `circle_tool.gd` (C, T81): click a face or the ground for the centre, then click or type a radius (or
  press-and-drag, I43). Uses Rectangle's snapping and distance policies; the measurements box accepts the same
  length syntax. Makes a `circle` op with an exact radius. Loose profiles share the existing `rects` presentation,
  `r` IDs and `target.rect` Push/Pull path; FreeCAD stores an exact fully constrained sketch circle.
- `push_tool.gd` (P): click a face, rectangle or circle, move, click or type a distance (minus = cut), or press-and-drag
  (I43). Snaps to faces behind (I23, I45; to the back face = a through-cut, `"through": true`, I24); on a face it
  joins that board, B for a new board (I04b). Circle profiles use point/back-face depth snaps;
  rectangular-stock plane-fit end conditions remain limited to rectangular profiles.
- `move_tool.gd` (M), SketchUp style: grabbing a selected board transforms the whole selection (T34; move/copy/mirror
  are each one op); otherwise grab a point on a board (or a hole's wall: the hole), move, click or type a distance,
  or press-and-drag (I43). Ctrl/Option toggles copy; Shift toggles mirror (I12c); arrows cycle axis lock → plane
  lock → free.
  After a copy: `5x` / `*5` for an array, `/5` to spread copies; a plain number right after a move changes its
  distance (`_amend_last_move`). Mirroring can use any face's plane (T27).
