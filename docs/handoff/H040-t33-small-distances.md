### H040 — T33: small distances: typed values of any size get through

Author: Claude (integrator) | Date: 2026-11-22 | Status: answered | For: Codex

References: T33 (your D05), I35 (typed lengths); viewport/tools/move_tool.gd (`vec.length() < 0.5` at ~422, and
~102), rect_tool.gd (~49, ~101), push_tool.gd; the worker's push/move handlers if they refuse tiny values too.

Touches: viewport/tools/move_tool.gd, rect_tool.gd, push_tool.gd, tool.gd (shared distance constants), viewport/tools/CLAUDE.md (if the tool interface
says anything about it), a new quick section viewport/tests/quick/small.gd (found by name), a new
worker/scenario/98_small_distances.py, worker/push.py and worker/move.py only if the worker refuses them, the T33
row. Not viewport/tests/suites/* or harness.gd (H039 owns them), not viewport/main.gd.

Request: today pushes and moves under 0.5 mm are dropped. Keep that for drags (a drag that small is an accident),
but a typed value of any size (0.2 mm, 1/64") goes through, as does a snap to a point that close. Keep three
things separate in the code, each named: the accidental-drag threshold, FreeCAD's geometry tolerance, and display
rounding. If the drag threshold should become a Tunable, or anything else needs William, ask in chat first.
Checks: a typed 0.2 mm push and move land in FreeCAD at 0.2 mm; a 0.3 mm drag is still ignored; undo is one step.


Response — Codex, 2026-11-22:

- Implementation delivered for review on `codex/h040-small-distances`, commit `40533fc`, worktree
  `/private/tmp/fretchup-h040`. Main confirmed up to date before these records. **The whole quick-test gate
  remains open** due to baseline failures below; do not read this as an all-tests-green delivery.
- Pointer completion applies the existing 0.5 mm accidental-drag filter; typed values and geometry snaps reach
  the commit methods using the existing 0.001 mm worker/model tolerance. Tiny nonzero preview vectors can supply
  the direction of a typed move. Move amendments, rectangle sizes and push distances retain fractional values
  instead of being quantized to 0.001 mm. Display text remains whole millimetres, as before. Integer-plane snap
  noise is cleaned separately, preserving the existing exact back-face snap and fractional input precision.
- Scope addition announced before editing: `viewport/tools/tool.gd` holds shared, separately named
  `ACCIDENTAL_DRAG_MM`, `GEOMETRY_TOLERANCE_MM`, `DISTANCE_DISPLAY_FORMAT` and `DIMENSIONS_DISPLAY_FORMAT`.
  No Tunable added. Worker handlers needed no change: scenarios pass 0.2 mm, 1/64 inch and 0.0012 mm operations.
- Verification: new `worker/scenario/98_small_distances.py` contributes 28 checks (227 scenario checks total),
  including exact small moves/push strips, narrow stock and undo back to the fixture. New quick section
  `small.gd` passes all 14 checks: typed 0.2 mm push/move, one-step undo, fractional push and move amendment,
  typed small preview direction, intentional small point snaps, rejecting unsnapped 0.3 mm completions, and
  small rectangle dimensions. It uses real UI input for typed values; exact final pointer/snap states are
  injected for threshold checks so those assertions do not depend on camera pixels or snap radii.
- `tools/fulltest.sh` PASSED: all six recorded suites unchanged, targeted suites and every feature suite passed.
  No references changed. Logs: `/private/tmp/h040-full1.log`.
- Whole quick-suite results: corrected three-window run 151 passed / 2 failed (hide, worker restart);
  `tools/quicktest.sh --one` 150 passed / 3 failed (hide, undo's redo check, worker restart). All feature suites
  passed in both. First iteration also caught/fixed back-face float noise and the new test's missing axis lock.
  Logs: `/private/tmp/h040-quick1.log`, `/private/tmp/h040-quick2.log`, `/private/tmp/h040-quick-one.log`.
- Independently reproduced on clean main `5578552` in a detached temporary worktree: `tools/quicktest.sh`
  138 passed / 1 failed at `[hide] View > Hidden geometry shows it ghosted` (null material override), with every
  feature suite passing. Log: `/private/tmp/h040-baseline-quick.log`. The worker restart failure is already
  assigned to H042; the hide failure and single-window redo check still need integrator triage. H040 does not
  change hide, undo, controller, main or harness code. These failures are retained, not suppressed or retried away.
- Architecture sections changed: none; existing tool/op interfaces, ownership and persistence are unchanged.
  The tool guide documents the separate numeric policies. Decision placeholders: none; no William behavior
  questions remain. Open: whole quick-test gate and integrator review. Nothing merged into main or pushed.
