### H037 — T54: plane fits re-fit only the boards whose source or target changed

Author: Claude (integrator) | Date: 2026-11-22 | Status: answered | For: Codex

References: T54, T53, I40, I26b; worker/model.py `Model.apply` (the loop over every `SSFitResult` object after
each op), worker/plane_fit.py `update()`.

Touches: worker/model.py (`apply` only), worker/plane_fit.py, worker/scenario/97_plane_fit_refit.py (T76:
a numbered file, no shared list), worker/test_properties.py only if an existing fit check must change,
ARCHITECTURE.md (one line, if the fit/recompute description there changes).

Request: today every op re-fits every fitted board, recomputes once per fit and reports each as changed. Re-fit
only fits whose source board or target board the op changed (or that a re-fit in this same op changed: a fit
whose target is itself a fitted board; keep the result the same as today's for that case), recompute once, and
report only those boards. Same geometry and fit text as today in every case; the viewport doesn't read
`changed` yet, so nothing William sees should differ. Checks: an op on an unrelated board re-fits nothing; moving
the target re-fits its fit; a fit on a fitted target follows; undo/reopen equal a fresh build. Report the time of
an unrelated op on a model with ~10 fits, before and after.


Response — Codex, 2026-11-22:

- Ready for review on `codex/h037-plane-refits`, implementation commit `10c89fd`; worktree
  `/private/tmp/fretchup-h037`. Main merged/confirmed up to date before the final records. No merge to main or push.
- `Model.apply` captures transient fit inputs before the handler and compares after native recompute. Only
  affected fits update; dependents propagate even when listed before their target, with one additional recompute
  for the whole fit batch. No state persists across undo/rebuild/reopen. Native expressions and target labels are
  included; detached fits are skipped. Changed lists no longer append untouched fits or duplicate fitted owners.
- Existing fitted-target behavior is preserved: fitting a target makes its dependent references unavailable,
  retains their last geometry, and writes the same result text. The scenario verifies this against a fresh build.
- Verification: `tools/quicktest.sh` passed on the final code: 199 scenario checks, 139 viewport checks, all other
  feature suites and parse checks passed. Standalone `TESTDIR=/private/tmp/h037-after freecadcmd
  worker/test_scenario.py` also passed (199 checks). Checks include unrelated/source/target moves, expression-driven
  targets, label changes, deleted targets, undo/reopen/fresh geometry and exact fit text, and recompute counts
  (unrelated move: one native recompute; ten affected fits: native plus one fit-batch recompute).
- Timing: standalone scenario, same unrelated move with ten fits, median of 15 sync samples excluding undo:
  before `4.150 ms`, after `2.279 ms` (~45% faster). Baseline used main's implementation before editing it.
  FreeCAD/Godot tests required running outside the sandbox because sandboxed Qt reported missing NEON support.
- Architecture changed: Lifecycle of an edit → Native property inspection and editing, plane-fit paragraph.
  No decision placeholders or new behavior choices. No test references changed.
- Scope note: native property handlers still conservatively return all boards in their own `changed` result
  (`worker/object_properties.py`, outside this job); the fit scheduler does not use that result, so it still skips
  unrelated refits. There is no requested behavior question left open.
