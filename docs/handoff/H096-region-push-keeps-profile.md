### H096 — Pushing one cell of a split profile keeps the rest of the profile on screen (H092 finding 9)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: either

References: T82 / H046 (Line splits faces; a push takes the cell under the cursor, `target.region`), I51, H092
finding 9.

Touches: viewport/document.gd (`consumed_rects`), viewport/presenter.gd (`present_draft`, its one
`drop_draft` line), viewport/test_document.gd, viewport/tests/quick/line.gd. Not the worker (it already keeps the
profile: `op_push_pull` sets `pl = None` for a region and never extrudes or consumes the source profile).
Queued after H083, which touches presenter.gd and line.gd.

Today (checked 2026-11-22): document.gd `consumed_rects` counts every `push_pull` whose target has `rect`,
region pushes included, and presenter.gd `present_draft` calls `drop_draft(op.target.get("rect", ""))` for every
push_pull. Draw a free rectangle (or circle), split it with a Line, push one cell: the whole profile's draft goes,
so the other cells vanish from the view and can't be picked, though FreeCAD still has them. The same through
`rebuild_rect_drafts` and `drop_confirmed_drafts` (main.gd), which read `consumed_rects`.

Request: a push whose target has a `region` neither consumes nor drops its source profile: `consumed_rects`
skips it, and `present_draft` drops the draft only when the target has `rect` and no `region`. A push of the
whole profile (no region) consumes it as today.

Cases that must still work: the quick test's line_regions steps (one cell joins, undo, redo), every push of a
whole rectangle or circle (the profile goes once pushed), test_document.gd's "consumed rects" check.

Checks: test_document.gd: a `push_pull` with `target: {rect: "r1", region: {...}}` leaves `consumed_rects()`
empty; one with `target: {rect: "r1"}` gives `{"r1": true}`. viewport/tests/quick/line.gd: a free 200 × 200
rectangle split into two cells by one Line; push one cell 20: the new board is the cell (its volume), the
rectangle's draft is still there, and the Push/Pull hover over the other cell finds its region (as the
"previews only the quadrant under cursor" step does); pushing that second cell makes a second board; after an
undo of both and a redo of the first, the same.

Reading path: tools/push_tool.gd `commit_push` (the op it builds: `target.rect` plus `target.region`) →
presenter.gd `present_draft` → document.gd `consumed_rects` → main.gd `_consumed_rects`, `_rebuild_rect_drafts`,
`drop_confirmed_drafts` → presenter.gd `rebuild_rect_drafts`. Who owns what: document.gd says which profiles are
used up; the presenter draws what isn't.

Run the feature tests while building (`tools/featuretest.sh`), then `python3 tools/job.py test`. End your
response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.

#### Response — Gemini (`gemini-cedar-1123-0845`, 2026-11-23)

- Branch: `gemini/h096-region-push-keeps-profile` (fast-forwarded to `main` `08d6a41`)
- Commit: `0704f45`
- What changed:
  - `viewport/document.gd` (`consumed_rects`): skip `push_pull` ops whose `target` has `region` so a region push does not mark its source profile consumed.
  - `viewport/presenter.gd` (`present_draft` and `forget_op`): skip `drop_draft` on region `push_pull` in `present_draft`, and skip re-registering the profile draft on undo of a region `push_pull` in `forget_op` so the still-present draft node is not overwritten and leaked in `drafts_root`.
  - `viewport/main.gd` (`redo`): skip freeing/erasing `drafts[rid]` on redo of a region `push_pull` so the source profile draft stays on screen and pickable after redo.
  - `viewport/test_document.gd`: added checks that a region `push_pull` leaves `consumed_rects()` empty while a whole-profile `push_pull` still gives `{"r1": true}`.
  - `viewport/tests/quick/line.gd` (`line_split_profile`): added checks for a free 200 × 200 rectangle split into two cells by one Line — pushing cell 1 creates only that cell's board (400,000 mm³), keeps the profile draft intact, keeps Push/Pull hover over cell 2 finding its 20,000 mm² region, pushing cell 2 makes a second 400,000 mm³ board, undoing both keeps the original draft node intact without leaking, and redoing the first keeps the draft and remaining cell pickable.
- Scope permission (P45): asked William in chat (via `job.py wait`) whether I may also guard `target.region` in `viewport/main.gd` (`redo`, outside `Touches`) and `viewport/presenter.gd` (`forget_op`, outside `present_draft`). William answered: "yes".
- Verified: `tools/featuretest.sh` (all 36 feature suites passed, including `DOCUMENT TESTS: 137 passed, 0 failed`), `tools/quicktest.sh` (319 passed, 0 failed), and `python3 tools/job.py test` on clean commit `0704f45` (all 36 feature suites + `QUICK 319 passed, 0 failed in 22.7 s`).
- IDs added: none.
- Open questions: none.

Changed from the brief: Touches listed only `viewport/document.gd (consumed_rects)` and `viewport/presenter.gd (present_draft)` (not `viewport/main.gd` or `presenter.gd`'s `forget_op`); with William's approval ("yes"), also guarded `not op["target"].has("region")` in `viewport/main.gd` (`redo`) and `viewport/presenter.gd` (`forget_op`); without the `redo` guard redoing a region push dropped the profile draft and broke H096's redo check, and without the `forget_op` guard undoing a region push overwrote and leaked the existing draft node in `drafts_root`.
Follow-up: One `job.py test` run hit a one-off timing flake in unrelated `viewport/tests/quick/rect.gd` (`the second click finishes a 100 x 150` got `[2, [50.0, 70.0]]` under parallel test load); it passed cleanly on the immediately preceding and following runs.
Result: 0704f45; test_document.gd 137/137, all 36 feature suites passed, quick test 319/319 (job.py test); region pushes skip profile consumption and draft drop/recreate across document.gd, presenter.gd and main.gd redo, keeping remaining split-profile cells pickable through push, undo and redo.
