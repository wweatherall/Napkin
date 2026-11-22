### H044 — T58: copy an assembly into a row (3x, /3)

Author: Claude (integrator) | Date: 2026-11-22 | Status: open | For: Codex

References: T58, I47 (copying a whole assembly makes a new assembly; a row of them is refused today), I32 (a row
works like a component you enter), T12 / A22c (rows of boards, linked copies), I48; viewport/tools/move_tool.gd
(`_whole_assemblies`, the count amendment), worker/move.py (`groups`), worker/assembly.py (`copy_into_assembly`).

Touches: viewport/tools/move_tool.gd, viewport/selection.gd (what a row member stands for), worker/move.py,
worker/assembly.py, a new worker/scenario/NN_assembly_rows.py, a new viewport/tests/quick/assembly_row.gd (or steps
in quick/assembly.gd), the T58 row. Not viewport/presenter.gd, main.gd, keys.gd, push_tool.gd, worker/push.py,
worker/model.py, docs/protocol.md or ARCHITECTURE.md: H041 (the Circle tool) is changing them. If you need one
of them, say so in chat first; for docs/protocol.md and ARCHITECTURE.md, put the text you'd add in your response
and the integrator adds it at merge.

Request: `3x` or `/3` after copying a whole assembly makes a row of assemblies: each copy a new assembly (I47),
the row spaced like a row of boards, its spacing editable later the same way. From outside, a click picks the
whole row; inside the row, an assembly stands as one member (entering it again enters that assembly). Undo is one
step. Anything this doesn't settle (what moving one assembly out of the row does, whether the copies are linked
like a row of boards): ask William in chat, one question at a time, with a recommendation, and log the answer.
Checks: scenario steps for 3x and /3 of a two-board assembly, an edit of the spacing, undo, reopen equal a fresh
build; a quick section that does it with the real Move tool.
