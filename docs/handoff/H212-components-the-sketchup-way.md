### H212 — Components and arrays the SketchUp way: one click takes the group, inside every copy is linked, the original is marked (I82)

Author: Claude (integrator, integrator-teak) | Date: 2026-11-28 | Status: open | For: codex | Item: T169

References: I82 (William, 2026-11-28: "Just do what you recommended before and what SketchUp does. Make unique is a
fine fallback."), I69 (double-click enters a linked component), I28 / Q29 (Make Unique keeps its place in an array),
T168 (parked: keeping the array when a copy inside moves; not this job), G03, G04, G13; H211's response (entering
William's row of copies). William's model: `models/model.FCStd` (b16 and five linked copies in an array; open a copy in
scratch/, never the original).

Today (read, not yet checked in the app; check each): from outside a click on a row copy selects the whole row
(`selection.gd` `unit_of`, I32) and Move moves it (`move_tool.gd` around line 327). Double-click enters the clicked
instance with siblings tinted (H211). Every board in a row is an `App::Link` to one hidden definition, so a shape edit
on any copy reaches all (worker/move.py `op_make_unique` copies the definition for one copy and keeps its array place).
`move_selection` takes a `detach` flag that calls `op_detach` for an array member. `selection.gd` keeps `body_row`
(board -> the row's source board) and hands an entered `row:` context to another member when the source leaves
(around line 58). Nothing marks the original today, as far as the integrator saw.

Touches: viewport/selection.gd, viewport/selection_view.gd, viewport/tools/move_tool.gd (inside-a-component moves only),
worker/move.py (`op_make_unique`, `move_selection`, `op_detach` only), a viewport quick-test section, a worker test or
scenario step.

Request:
1. Check each part of I82 in the app on a copy of William's model and say in the response which already worked:
   (a) outside, one click selects the whole array and Move moves it as one; (b) double-click enters it; (c) inside,
   a shape edit (Push/Pull a copy's end, a hole) on any copy changes all six, and the tinted siblings show it before
   FreeCAD answers (G13); (d) inside, moving one copy takes it out of the row and it stays linked (its shape still
   follows); (e) Make Unique (U) on one copy lets it change alone; (f) Make Unique on the original: a remaining copy
   becomes the row's source, and entering/marking follow it.
2. Make whatever failed work as I82 says.
3. Inside an entered component or row, mark the original faintly so you can tell it from the copies: a subtle
   outline or tint in the selection's style, not violet, red or amber (G07), drawn by `selection_view.gd`. Pick the
   simplest look that reads beside the sibling tint and list it as a question for William in the response.
4. After (d), the remaining copies stay an array if they still are one in FreeCAD; if the move breaks the array into
   separate linked copies, that is acceptable (T168 is the someday version): say which it does.

What can fail (P42):
- Moving a copy inside leaves it in the array's FreeCAD list, so the next array edit snaps it back. Check: move a copy
  inside, change the array count or spacing (or undo/redo and reopen), the moved copy stays where it was put.
- Make Unique on the original leaves the row with no source: entering or the mark then points at a missing board.
  Check: make the original unique, double-click a remaining copy, the mark is on the new source.
- One Undo must undo a whole action (a detach-and-move is one ⌘Z). Check: undo after (d) puts the copy back in the row.

Checks:
- A named check per part (a)-(f) with a fixture like William's (one board, 5x copies), and the three above.
- `tools/TEST_BEFORE_MERGING.sh` passes.
