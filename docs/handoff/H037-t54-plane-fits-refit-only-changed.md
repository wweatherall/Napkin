### H037 — T54: plane fits re-fit only the boards whose source or target changed

Author: Claude (integrator) | Date: 2026-11-22 | Status: open | For: Codex

References: T54, T53, I40, I26b; worker/model.py `Model.apply` (the loop over every `SSFitResult` object after
each op), worker/plane_fit.py `update()`.

Touches: worker/model.py (`apply` only), worker/plane_fit.py, a new worker/scenario/NN_plane_fit_refit.py (T76:
a numbered file, no shared list), worker/test_properties.py only if an existing fit check must change,
ARCHITECTURE.md (one line, if the fit/recompute description there changes).

Request: today every op re-fits every fitted board, recomputes once per fit and reports each as changed. Re-fit
only fits whose source board or target board the op changed (or that a re-fit in this same op changed: a fit
whose target is itself a fitted board; keep the result the same as today's for that case), recompute once, and
report only those boards. Same geometry and fit text as today in every case; the viewport doesn't read
`changed` yet, so nothing William sees should differ. Checks: an op on an unrelated board re-fits nothing; moving
the target re-fits its fit; a fit on a fitted target follows; undo/reopen equal a fresh build. Report the time of
an unrelated op on a model with ~10 fits, before and after.
