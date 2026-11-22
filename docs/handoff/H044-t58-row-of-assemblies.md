### H044 — T58: copy an assembly into a row (3x, /3)

Author: Claude (integrator) | Date: 2026-11-22 | Status: answered | For: Codex

References: T58, I47 (copying a whole assembly makes a new assembly; a row of them is refused today), I32 (a row
works like a component you enter), T12 / A22c (rows of boards, linked copies), I48; viewport/tools/move_tool.gd
(`_whole_assemblies`, the count amendment), worker/move.py (`groups`), worker/assembly.py (`copy_into_assembly`).

Touches: viewport/tools/move_tool.gd, viewport/selection.gd (what a row member stands for), worker/move.py,
worker/assembly.py, worker/scenario/70_assembly.py (replace the old refusal check), a new worker/scenario/NN_assembly_rows.py, a new viewport/tests/quick/assembly_row.gd (or steps
in quick/assembly.gd), the T58 row. Not viewport/presenter.gd, main.gd, keys.gd, push_tool.gd, worker/push.py,
worker/model.py, docs/protocol.md or ARCHITECTURE.md: H041 (the Circle tool) is changing them. If you need one
of them, say so in chat first; for docs/protocol.md and ARCHITECTURE.md, put the text you'd add in your response
and the integrator adds it at merge.

Additional Touches — Codex, 2026-11-22: viewport/CLAUDE.md (remove the old row-refusal description);
ARCHITECTURE.md, Selection operations and Native model and identity only,
to satisfy AGENTS.md's same-commit architecture rule; announced in chat, separate from H041's module table rows.

Request: `3x` or `/3` after copying a whole assembly makes a row of assemblies: each copy a new assembly (I47),
the row spaced like a row of boards, its spacing editable later the same way. From outside, a click picks the
whole row; inside the row, an assembly stands as one member (entering it again enters that assembly). Undo is one
step. Anything this doesn't settle (what moving one assembly out of the row does, whether the copies are linked
like a row of boards): ask William in chat, one question at a time, with a recommendation, and log the answer.
Checks: scenario steps for 3x and /3 of a two-board assembly, an edit of the spacing, undo, reopen equal a fresh
build; a quick section that does it with the real Move tool.

Response — Codex, 2026-11-22 (claimed; behaviour clarification pending):

- Claimed `codex/h044-assembly-rows` from main `4aec99f` in `/private/tmp/fretchup-h044`.
  H041 is already claimed; H044's implementation files do not overlap H041 or H043.
- Added `worker/scenario/70_assembly.py` to Touches above: it asserts that assembly rows are refused.
  The existing `viewport/tests/quick/assembly.gd` has the matching refusal check and is already in scope.
- Asked William whether the row's copies stay linked in shape (recommendation: yes, as existing board rows
  and single assembly copies). Awaiting his answer before implementing dependent behaviour.
- Still to settle, one question at a time: moving a copied assembly inside the entered row (recommendation:
  detach that whole assembly's position from the row, retaining shape links, following I32).
- No application code changed; Status remains open. Protocol/architecture wording will be supplied here
  for the integrator as the assignment requests.
- Baseline `tools/quicktest.sh`: runtime aborts in Godot/FreeCAD, three viewport windows and twelve feature
  checks did not finish; terminated the stalled serve test. Log-sort/ID/startup tests passed (12/29/25).
  Logs: `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-quick.mlFeHj9mXg`.

Response — Codex, 2026-11-22 (implementation complete):

- Branch: `codex/h044-assembly-rows`; final commit recorded below. Based on current main `b426d7f`.
- William confirmed linked shapes (I-new-1, which supersedes I47's temporary refusal) and moving a copied
  assembly inside its row detaches all its positions while keeping shape links (I-new-2). No questions remain.
- `3x` / `/3` amend the original copy op; each offset gets its own assembly. Source-major board IDs and old
  single-copy journals remain readable. Array holders keep their board origins and share Count/Step/Span
  through the first holder. Editing that master Step (fixed) or Span (distributed) changes the whole row.
- Existing board `assembly`/`row` metadata resolves row → assembly → board context; Esc returns to the row.
  Moving outside moves every board once; inside a row, moving a copied assembly detaches all its members.
  Shape edits still propagate, including after detachment. One undo removes the row. Mirrored assembly
  members retain native mirror chains of hidden linked sources, with array expressions on source placements
  and mirror planes; detaching clears both. Added native checks for reflected geometry, shared shape edits,
  spacing, whole-row movement, detachment, fresh builds and reopen, plus atomic invalid-ID rejection.
- Verification: `tools/quicktest.sh` passed: 165 viewport checks, all feature tests (259 scenario checks).
  Logs: `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-quick.AVMXaGcRdT`.
  `tools/fulltest.sh` passed: all six recorded suites unchanged, targeted suites and all feature tests pass.
  Logs: `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-full.RViv4aHKnq`.
  The initial UI failure was only an overly strict new assertion: exported boxes round /3's 66.666… to 66.67;
  fixed its tolerance to the export precision. The earlier runtime aborts were confined to sandboxed runs;
  the completed verification ran with approved host execution.
- Architecture: updated Selection operations and Native model and identity in the same code commit, as
  AGENTS.md and the commit hook require. Announced the ARCHITECTURE.md overlap in chat before editing;
  H041 owns module table rows, which are untouched. Also corrected viewport/CLAUDE.md's old refusal description (announced first; no other job lists it).
  No other job's application files were touched.
- Integrator: update `docs/protocol.md`'s move schema to `groups?: {old AssemblyId: new AssemblyId | new AssemblyId[]}`.
  A string represents one copy; an array contains exactly `count` distinct destination IDs, one per offset.
  Replace "assembly rows are currently refused" with "whole-assembly copies support fixed and distributed
  rows; each offset gets its own assembly; board IDs remain source-major". Bump the reference revision
  alongside H041's pending protocol changes. This document remains untouched here as assigned.
- Placeholders: I-new-1, I-new-2. No merge to main or push performed.
