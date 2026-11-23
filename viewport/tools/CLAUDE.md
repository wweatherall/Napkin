# viewport/tools/: the tools

One object per tool (T4). Each owns its state; `main.gd` hands it the cursor, clicks, keys and typed values.

## Adding a tool: one new file
`tools/<name>_tool.gd`, extending `res://tools/tool.gd`, with a `TOOL` constant:
`const TOOL := {"id": "circle", "label": "Circle", "tip": "Circle (C)", "key": KEY_C, "order": 60}`
(`key`: `KEY_NONE` for none; `order`: its place left to right, the five today are 10–50; `"show_links": true` to
tint a linked board's copies while over it). `tool_registry.gd` finds it (from source and in the built app) and
main.gd makes the tool, its toolbar segment, its Tools menu item (`label (key)`) and its key; nothing shared
lists tools. A repeated id or key is reported (`push_error`, and `test_tools.gd`). Then extend the expected lists
in `test_tools.gd` and `tests/quick/registry.gd` (they pin what William sees), and add its quick-test section.
A key the tool handles only while active stays in its `key(e)`; other shortcuts stay in keys.gd.
The viewport guide (`../CLAUDE.md`) covers drafts, waves and the rules for drawing.

## The interface (`tool.gd`, the base every tool extends)
- `setup_context(ctx)` gives every tool `ctx` (`../tool_context.gd`, T88; the spec is
  `docs/specs/T88-tool-interface.md`): `ctx.pick` (inference: hit, snap, on_grid, point, axis, axis_dest,
  plane_dest, ray, project, cursor, grid), `ctx.model` (boards' triangles, profiles, saved lines, drawn regions, stock frames, cuts),
  `ctx.selection` (ids, context, unit_of, set_ids, enter, ...), `ctx.document` (next_id, op, append, remove, sync),
  `ctx.view` (preview, marker, guides, selection box, face highlight, register_profile, present_draft: a committed draft's pieces and its wave), `ctx.ui` (typed text,
  measurements, tooltip, rejection note, New board) and `ctx.paint` (`current_name`, `apply`; owned by `../appearance.gd`). Answers are copies; no adapter gives out
  Main, a node, a material or a cache map. Pure geometry is `Geo` (`../tool_geometry.gd`), preloaded in tool.gd.
- Legacy, until each tool moves (T88 steps 1–6): `uses_main()` is the temporary marker. While it returns true
  (Move, the last legacy tool, until step 6), main.gd also calls `setup(m)`, giving `m` (main.gd) and `infer` (inference.gd). A tool
  moved to the context overrides `uses_main()` to return false, uses only `ctx` and `Geo`, and leaves
  `STILL_ON_MAIN` in `../test_tools.gd` in the same commit. A new tool (Line, H046) starts on the context; Paint (H065) is the worked example of a move, Push/Pull (H079) of one that commits drafts.
  Snap only through inference (`ctx.pick`, or `infer` / `m.snap()` / `m.pick()` in a legacy tool): one snapping
  engine for every tool (I03b).
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
1. Build the op: an id from `m.doc.next_id("pp")` (`ctx.document.next_id` in a ToolContext tool; never a counter by hand: IDs carry 128 random bits so they never collide across history branches, T67), `type`, and targets by geometry (`{body, normal,
   point}`, never face numbers, A03); a new board takes a new `b` id.
2. `m.ops.append(op)`, draw the draft at once, start the wave (`m._begin_wave`, `m._attach_wave`), clear the
   tool's state and overlays, then `m.sync()`. FreeCAD confirms later; never wait for it.
3. The worker needs a matching `op_<type>` (worker/CLAUDE.md). Add a quick-test step in `tests/quick/<section>.gd` (a new section file is picked up by itself; list it in `tests/quick_runner.gd` QUICK_LANES only to pin its lane).
Tools talk to the worker only through `ops` and `m.sync()`. On the context the same steps are
`ctx.document.next_id("pp")`, `ctx.document.append(op)` (doesn't sync), `ctx.view.register_profile(op)` or the
draft and its wave (`ctx.view.present_draft(op, pieces, wave)`), then `ctx.document.sync()`.

## Tests of the interface
`../test_tool_context.gd` (headless, `Godot --headless --path viewport --script res://test_tool_context.gd`):
each capability's public members against an allowlist (the spec's surface; `view.mirror_preview` is listed as
arriving with Move), answers are snapshots, id sequences, append
without a sync, remove's signals, ray/project against the camera's own answers on a tilted view, the moved
geometry and Main's wrappers agreeing, and no main.gd reference in the context, geometry or inference code.
`../test_tools.gd` makes every tool with a context and pins which still use main.gd.

## The tools
- `select_tool.gd` (Space; context-only, H071): click selects (from outside, an assembly or array row whole), Shift-click adds or
  removes, empty space clears; drag right selects enclosed units, left selects crossing units, Shift adds. Double-click enters an assembly or array (T20), Esc cancels a box before leaving. Delete acts on the reusable selection (T34).
- `paint_tool.gd` (no key yet, Q14; context-only, H065): paints the Wood menu's wood; a linked board paints its family. T turns grain.
- `rect_tool.gd` (R): click a face or the ground, then click or type `width, height` (or press-and-drag, I43). Its
  second corner ignores snaps that would leave a side at zero (I44).
- `line_tool.gd` (L, T82): context-only click-click chains and single press-drag-release segments; typed lengths follow the cursor. Esc ends a chain, clicking its start closes a polygon profile. Each segment is a saved `line` op, with world-mm endpoint and plane; explicit snap flags distinguish edge snaps from free endpoints; the closing op also holds the ordered outline. Presenter registers drawings through `ctx.view.register_line`; polygon profiles share `target.rect` Push/Pull. `regions.gd` finds the cell under Push/Pull from the source face and coplanar saved lines, including holes; the op carries `target.region` with its outline and holes. Unsplit profiles retain their exact native path. Curved boundary cells are refined against native arcs by FreeCAD.
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
