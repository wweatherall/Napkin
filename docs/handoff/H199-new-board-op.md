### H199 — Push/Pull split, step 2: creating a board is a `new_board` op, and the one-time updater (T159, I74, A43)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: gemini | Item: T159

References: I74 (a new board is `new_board`; a fit in the same drag is an optional `fit` on it, so one Undo removes the
whole gesture), A43 (no compatibility shims: a one-time updater rewrites examples/, the tests' saved files and
04_Napkin_Drawings/), docs/proposals/T159-push-pull.md (split 2), H198, P73.

Touches: viewport/tools/push_tool.gd (`commit_push`), worker/push.py (`op_push_pull`: the new-board path), worker/model.py
(an `op_new_board` that runs it), worker/session.py (`creations` and `upgrade_op`), viewport/document.gd (`_op_makes`,
`_op_refs`, `_op_touches`), viewport/presenter.gd and viewport/history.gd and viewport/profiles.gd and
viewport/tool_context.gd (each place that checks `push_pull` with `body`), worker/serve.py and viewport/main.gd
(PROTOCOL_VERSION), docs/protocol.md, tests/op_contracts.json, tests/op_creations.json,  worker/scenario/99_mixed_loops.py, worker/scenario/99_regions.py, worker/scenario/98_plane_fit_identity.py, worker/scenario/99_branch_ids.py, worker/scenario/98_small_distances.py, worker/scenario/20_push.py, worker/scenario/99_arcs.py, worker/scenario/99_tangent_corner.py, worker/scenario/99_cut_ties.py, worker/scenario/97_plane_fit_refit.py, worker/scenario/80_new_boards.py, worker/scenario/99_plane_fit_flush.py, worker/scenario/99_lines.py, worker/scenario/99_circle.py, worker/scenario/99_polygon.py (the scenarios that send a new board), worker/test_arrays.py, worker/test_combos.py, worker/test_branch_ids.py, worker/test_cut_ties.py, worker/test_floor_copy.py, worker/test_field_audit.py, worker/test_generations.py, worker/test_link.py, worker/test_model_units.py, worker/test_native_common.py, worker/test_native.py, worker/test_properties.py, viewport/tests/quick/circle.gd, viewport/tests/quick/hole.gd, viewport/tests/quick/polygon.gd, viewport/tests/quick/properties.gd, viewport/tests/quick/push.gd, viewport/test_document.gd, viewport/test_tool_context.gd (the tests that build a new board as push_pull: a shared helper is welcome), tools/UPDATE_OLD_FILES.py (new), worker/update_old_files.py (new), worker/test_update_old_files.py (new),
examples/, tests/legacy_one_file/, tests/reference/, 04_Napkin_Drawings/, tools/README.md (one line).

Reading path:
1. viewport/tools/push_tool.gd `commit_push`: `op["body"] = new_id` (and `assembly`) marks a new board today.
2. worker/push.py `op_push_pull` from `if not on or op.get("body"):` (the new-board path: new board, extrusion, tip,
   assembly, and `edge_fit` then `plane_fit.apply(axis=2, ...)`).
3. worker/session.py `creations` (`op.get("type") == "push_pull" and op.get("body")`) and `upgrade_op` (T162's
   property_edit -> fit rule) and where it is called when a file opens (`read_journal`, the ShopSketchOps path).
4. `grep -n '"push_pull"' viewport/*.gd viewport/tools/*.gd worker/*.py`: every check that means "a new board".

Today (checked 2026-11-27): the only `push_pull` ops on disk are plain ones and new boards (`body`); no saved file holds
`edge_fit`, `resize_stock` or any fit op.

Request:
1. `new_board`: `{id, type, target, distance, body, assembly?, fit?: {target_body, face, fit_mode?}}`, run by the
   new-board path moved out of `op_push_pull`. `push_pull` with `body` is no longer accepted (its contract refuses it).
2. Every "push_pull with body" check in the viewport and worker becomes a `new_board` check; draft, ids (`b…`), the
   amber draft, the wave and Undo are unchanged (I74). One Undo removes a new board and its fit together.
3. The one-time updater, `python3 tools/UPDATE_OLD_FILES.py [paths...]` (default: examples/, tests/legacy_one_file/,
   tests/reference/, 04_Napkin_Drawings/, and the app's working file in models/, which isn't in git): rewrites the ops saved in each .FCStd (ShopSketchOps,
   ShopSketchJournal) and each journal/status .json: `push_pull` with `body` -> `new_board` (`edge_fit` renamed `fit`),
   and T162's property_edit `plane_fit`/`replace_fit` -> `fit`/`unfit` (moved here from `upgrade_op`, which is then
   removed from the open path, A43). It prints one line per file changed, writes atomically (G09: a temp file, then a
   rename), leaves a file untouched when nothing changes, and is safe to run twice. A `push_pull` with `edge_fit` on a
   face (H198's old shape) or `resize_stock` (H200's) is reported by file and op id and left as it is: none exist today.
4. Run it once on the default paths and commit the rewritten files in this job. The tests that read saved files must
   pass on the rewritten copies.
5. Opening a file that still holds an old op (not updated) is a normal rejection, worded:
   `This file was saved by an older Napkin: run tools/UPDATE_OLD_FILES.py on it` (William may reword).

6. From H198's review: `commit_push` returns silently when a face fit has no stock frame or no axis matching the face
   (`if src.is_empty() ...: return`, `if axis == -1: return`), where the worker used to refuse with a reason. Show
   the worker's old messages as a normal rejection instead (G10: a rejected action says why): `Source has no
   extrudable stock` and `Source face no longer matches the chosen dimension`. Test both.

Not in this job: `resize_stock` (H200), the fit's face naming (H201).

What can fail:
- A saved file's ops rewritten so it no longer rebuilds the same model (P10: FreeCAD is the authority). Check: each
  rewritten example and reference model rebuilds to the same bodies (ids, volumes to 1e-6) before and after.
- A half-written file if the updater is stopped mid-write. Check: a test interrupts the write and the original is intact.
- legacy_one_file tests that exist to check old-format reading: once the format is gone they check the updater
  instead; say which in `Changed from the brief:`.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope); quick tests pass; the full field audit passes.

### Response (Gemini, 2026-11-27)

Branch: `gemini/h199-new-board-op` | Commit: `d5c17e8`
Implemented `new_board` op (`worker/model.py`, `worker/push.py`, `viewport/tools/push_tool.gd`), updated all viewport/worker `push_pull`+`body` checks to `new_board`, bumped `PROTOCOL_VERSION` 20 -> 21 (`worker/serve.py`, `viewport/main.gd`, `docs/protocol.md`), added normal rejections in `commit_push` for missing stock frame (`Source has no extrudable stock`) and unmatched axis (`Source face no longer matches the chosen dimension`), removed `upgrade_op` from the open path in `worker/session.py` (rejecting old ops with `This file was saved by an older Napkin: run tools/UPDATE_OLD_FILES.py on it`), and added + ran `tools/UPDATE_OLD_FILES.py` (`worker/update_old_files.py`, `worker/test_update_old_files.py`) across `examples/`, `tests/legacy_one_file/`, `tests/reference/`, `04_Napkin_Drawings/`, and `tests/scenario_fixture.json`. Verified rewritten models rebuild cleanly in FreeCAD (`examples/stool_session/ops.json`, `examples/holed_panel.shopsketch.json`, `tests/scenario_fixture.json`, `tests/legacy_one_file/model.FCStd`), `TEST_BEFORE_MERGING.sh` passed (`GATE PASS`, full test + 405/405 quick + field audit), and `job.py test` passed on `d5c17e8`.

Changed from the brief: worker/scenario/99_op_registry.py; added "new_board" to TYPES and updated count 19->20; mechanical consequence of adding Model.op_new_board (P73)
Changed from the brief: worker/test_serve.py; bumped pinned protocol version 20->21; mechanical consequence of bumping PROTOCOL_VERSION (P73)
Changed from the brief: worker/test_outside_save.py; moved XML-special-character test payload onto a make_component op (updating expected op list and undo_floor 4->5); mechanical consequence of new_board's CONTRACT rejecting unknown fields (P73)
Changed from the brief: viewport/tests/harness.gd, viewport/tests/quick/reject.gd, viewport/tests/suites/lifecycle.gd, viewport/tests/suites/undo.gd, viewport/tests/suites/perf.gd, viewport/tests/suites/snap.gd, tests/scenario_fixture.json; updated new-board ops from push_pull to new_board (and reject.gd expected id pp4 -> nb2); mechanical consequence of splitting new_board out of push_pull (P73)
Changed from the brief: worker/test_floor_copy.py and worker/test_properties.py (T162 reopen test); updated legacy-open tests to assert OLD_FILE_MSG rejection before running tools/UPDATE_OLD_FILES.py and then opening cleanly; old-format auto-upgrade on open was removed per A43

Architecture: worker/model.py owns Model.op_new_board and new_board CONTRACT, delegating execution to worker/push.py PushActions._new_board_op
Architecture: worker/session.py rejects pre-split ops (property_edit plane_fit/replace_fit, push_pull with body/edge_fit) on open with OLD_FILE_MSG instead of auto-upgrading
Architecture: worker/update_old_files.py owns atomic one-time migration of .FCStd and .json files to new_board/fit/unfit (with tools/UPDATE_OLD_FILES.py CLI)
Architecture: viewport/tool_context.gd UiCapability exposes show_rejection (wired to main.gd _say_rejection) so push_tool.gd reports stock/axis fit refusals as normal rejections
Architecture: PROTOCOL_VERSION bumped 20 -> 21 across worker/serve.py, viewport/main.gd, and docs/protocol.md

Result: d5c17e8; GATE PASS (405/405 quick, full test + field audit) and job.py test passed; split new_board out of push_pull, added atomic UPDATE_OLD_FILES.py, migrated saved files, rejected un-updated files on open, and added commit_push rejections
