### H-new-1 — The first `/code-review ultra` (main against ultra-base): ten findings, three fixed

Author: Claude (worker, session 01SF8AMM) | Date: 2026-11-22 | Status: open | For: the integrator

References: A36, T64, T65, G09 (outside saves); A32 (save generations); A23 (sync); H059 (reserved IDs); I51 and
the region push (H046/T82); P22 (small fixes); the 2026-11-22 integrator follow-up in docs/follow-ups.md (the
ultra review William was going to send off: he ran it himself, `/ultrareview ultra-base`, 110 files, +6592 −1169).

Touches: nothing yet. Each finding below that isn't fixed is a job for you to write (or a question for William).

Fixed on `small-fixes` (bd88639, quick test passed, worker/test_outside_save.py 29/29; both new checks fail
without the fixes): findings 1, 3 and 10. They're listed for William at the end of this session. This entry is
committed on the same branch, so merging `small-fixes` brings it in.

The other six findings are about reload or ID behaviour, so they aren't small fixes. For each one I read the code
the reviewer names and it does what they say. I haven't reproduced any of them in a run.

Finding or request:

1. **Fixed.** worker/serve.py save_pending ran `outside()` / `keep_both()` before its per-model `try`, and
   `watch()` had no `try`. A held model whose file was deleted took the worker down for every window once its
   window closed (copy2 FileNotFoundError out of serve()). Now that's a `save_failed`, and watch() logs and
   carries on.
2. **Open: a failed reload leaves the model held for good.** serve.py `reload`: `info = s.reload_outside()`
   runs before `held.pop(path)`. If it raises (FreeCAD's file won't open, board_marks throws), the path stays
   held. Meanwhile document.gd on_reload_reply clears `outside` on the error and carries on syncing. The timer
   skips held models, and hold() only tells the window once, so autosave is silently off until flush, bye or
   quit. Also, `reload_outside` closes `self.doc` before `_load_file()`, so a failed load leaves the session on
   a closed document. Recommended: on a failed reload, keep the window in its waiting/ask state (don't clear
   `outside`), so the user can still choose. In session.py, open the new document before closing the old one,
   so a failure leaves the old one live. Touches session.py, serve.py, document.gd.
3. **Fixed.** reload_outside returned `"rev": frev`, which overwrote open_reply's session rev in the reload
   reply. For a plain FreeCAD file that had no ShopSketchRev yet, that was null, and `int(null)` failed in
   on_reload_reply. Now the reply's rev is the session's, as serve.py's protocol note already said.
4. **Open, William's call: "Keep Shop Sketch's" can be overridden by a reload that's already out.**
   main.gd `_outside_choice` checks only `doc.outside.is_empty()`. If the delayed sync answers while the dialog
   is open, on_sync_reply sends the reload. A later "Keep Shop Sketch's" then loses to it: FreeCAD's version is
   adopted, the window's actions go to the journal, and the status says "took FreeCAD's save". (Only the
   non-blocking ConfirmationDialog path can do this, i.e. without FEATURE_NATIVE_DIALOG.) Recommended: while the
   dialog is open, on_sync_reply doesn't send the reload, so the user's answer decides. Ask William, since this
   is A36's flow.
5. **Open: the window stalls if the worker dies mid-reload.** document.gd on_link_up (the `outside` branch)
   sets dirty and `outside_seq = -1` but sends nothing. The OUTSIDE_SAVE_WAIT timer was never started (an idle
   window sends the reload straight away), so nothing asks. The next edit's sync builds on FreeCAD's file, which
   A36 means to prevent. Recommended: on link up with `outside` pending, send the reload again, or emit
   `outside_waiting` so the timer and the dialog run. Related to the H063 follow-up (a crash during an
   outside-save wait).
6. **Open: an older FreeCAD copy can lose every action.** session.py save keeps `rev_ops` for the last 50
   revisions only (`sorted(self.rev_ops)[:-50]`), and every autosave uses one. `_open_existing` resets it to the
   current rev, so a reopen or worker restart forgets the rest. The `.prev` journal covers one revision. Past
   that, `_file_ops` returns [] and the reload drops every action, including the rects and lines FreeCAD's file
   holds natively, so they vanish from the view. Recommended: when the revision isn't known, keep the ops
   (or ask) instead of dropping all of them. Keeping the window's ops whose IDs exist in the file
   (SSLineId / board names) would be the cheap route. A38's floor copy (H087) is nearby: check before writing
   this job.
7. **Open, narrow: a rejected op can come back after a reload.** session.py:638 stores `list(self.applied)`,
   failed ops included. `_open_existing` and the `.prev` branch keep only ok ops. A reload from such a revision
   puts the failed op back below `undo_floor`. The window then removes it, and every sync after that fails
   with "can't take back ops before N" until the model is reopened. Recommended (a few lines, but it changes what
   a reload restores, so I left it to you): store only ok ops in `rev_ops`, as the other two paths do, with a
   check in test_outside_save.py.
8. **Open: Redo can block all syncing.** document.gd next_id adds a new ID to `reserved_ids` before any sync
   carries its op. Draw something while a sync is in flight, Undo before it answers, then Redo. The worker has
   the ID reserved with no owner, and IdRegistry.accept (session.py:76) refuses it ("ID already reserved") on
   every sync while that op is in the list. Recommended: let the first op that creates an unowned reservation
   claim it. That touches the H059 follow-up (reserving every string) too, so maybe one job for both.
9. **Open: pushing one cell hides the rest of the shape.** document.gd consumed_rects counts any push_pull
   with `target.rect`, region pushes included, and presenter.gd present_draft drops `op.target.rect`'s draft.
   Push one cell of a free rectangle or circle that a Line splits, and the other cells vanish from the view and
   can't be picked, though FreeCAD still has them. Recommended: a push whose target has a `region` neither
   consumes nor drops its source profile, in both places, with a quick-test step. Viewport only.
10. **Fixed.** push.py built a region-only target's face twice (one OCC common plus one cut per hole each
    time). Now once.

For the integrator: merge `small-fixes` (bd88639 and this entry's commit) when the gate passes, as P22 says.
For the integrator: write jobs for findings 2, 5, 6, 8 and 9; ask William about 4 (A36's dialog) and whether 7 is a small fix.
Follow-up: the ultra review found ten bugs in a 6.6k-line diff. The 2026-11-22 follow-up about running one can be cleared once you've read this.

Response — Author, YYYY-MM-DD: ...

Resolution: ...
