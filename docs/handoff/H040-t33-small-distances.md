### H040 — T33: small distances: typed values of any size get through

Author: Claude (integrator) | Date: 2026-11-22 | Status: open | For: Codex

References: T33 (your D05), I35 (typed lengths); viewport/tools/move_tool.gd (`vec.length() < 0.5` at ~422, and
~102), rect_tool.gd (~49, ~101), push_tool.gd; the worker's push/move handlers if they refuse tiny values too.

Touches: viewport/tools/move_tool.gd, rect_tool.gd, push_tool.gd, viewport/tools/CLAUDE.md (if the tool interface
says anything about it), a new quick section viewport/tests/quick/small.gd (found by name), a new
worker/scenario/NN_small_distances.py, worker/push.py and worker/move.py only if the worker refuses them, the T33
row. Not viewport/tests/suites/* or harness.gd (H039 owns them), not viewport/main.gd.

Request: today pushes and moves under 0.5 mm are dropped. Keep that for drags (a drag that small is an accident),
but a typed value of any size (0.2 mm, 1/64") goes through, as does a snap to a point that close. Keep three
things separate in the code, each named: the accidental-drag threshold, FreeCAD's geometry tolerance, and display
rounding. If the drag threshold should become a Tunable, or anything else needs William, ask in chat first.
Checks: a typed 0.2 mm push and move land in FreeCAD at 0.2 mm; a 0.3 mm drag is still ignored; undo is one step.
