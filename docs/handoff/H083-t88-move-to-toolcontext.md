### H083 — T88 step 6: Move moves to ToolContext, and the legacy setup goes

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: either

References: T88, docs/specs/T88-tool-interface.md (§ move_tool.gd, § view.mirror_preview and present_draft, the
delivery table's step 6), P21, A34, W01-W09 (the confirmation wave), H051 (ToolContext), H079 (Push/Pull: the
worked example of a tool that commits drafts through `view.present_draft`).

Touches: viewport/tools/move_tool.gd, viewport/tools/tool.gd (the legacy `setup`, `m`, `infer`, `uses_main()` and
the Main preload go), viewport/tool_context.gd and viewport/test_tool_context.gd, viewport/presenter.gd
(`mirror_preview`, the guides body, anything Move's drafts need from present_draft), viewport/main.gd (lifting the
guides body out; `_make_tools` stops calling `setup`; keep the aliases other code and the tests still read:
`move_state`, `draft_bboxes`, `_lines`, `_tri_mesh`, the tools' `last_oid` / `memo` resets), viewport/tool_geometry.gd
(only if a pure body moves there), viewport/test_tools.gd (STILL_ON_MAIN and the marker go),
viewport/tests/quick/move.gd (only if the existing checks don't cover the move). Not ARCHITECTURE.md,
docs/protocol.md or the folder guides: write what changes as "Architecture:" lines and guide changes as "For the
integrator:" lines.

How Move reaches Main today (move_tool.gd, about 200 references): the caches (`m.body_tris`, `body_verts`,
`body_edges`), the overlays (`m.overlay`, `overlay_lines`, `marker`, `guides`, `_draw_guides`), the mesh helpers
(`_tri_mesh`, `_lines`, `_add_collision`, `_show_marker`), the draft roots and waves (`drafts_root`, `drafts`,
`bodies_root`, `_begin_wave`, `_attach_wave`, `_base_of`), the materials (`mat_draft`, `mat_cut`, `mat_cut_hl`,
`mat_hover`, `mat_plane`), the op list (`m.doc.next_id`, `m.ops.append`, the `m.ops` scan in `_amend_last_move`,
`m.remove_op`, `m.sync`), selection (`m.selection`, `body_assembly`, `context`, `unit_of`, `unit_tris`,
`m.sel.members_of`), picking (`m.pick`, `m.snap`, `m._cursor_pos`, `m.grid_snap`, `infer.axis`, `axis_dest`,
`plane_dest`, `point`), the UI (`_update_vcb`, `_update_tip`, `reject_note`), the test hooks (`m.test_mode`,
`m.draft_bboxes`) and statics on `Main.` (`arr3`, `feature_edges`, `unique_verts`, `reflect_point`, `reflect_tris`,
`_mirror_tris`, `_axis_vec`, `plane_basis`, `clean_normal`, `GRID`, `DEFAULT_BASE`, `AXIS_COLORS`, `SNAP_COLORS`).
ToolContext already answers most of these: `pick.hit/snap/point/axis/axis_dest/plane_dest/cursor/grid_enabled/
grid_step`, `model.triangles/unit_triangles/cut_at/cut_triangles/has_body`, `selection.ids/context/assembly_of/
members_of/unit_of`, `document.next_id/op/append/remove(id, resync)/sync`, `view.preview` (styles include
`cut_highlight`), `marker`, `guides`, `present_draft`, `ui.refresh_measurements/refresh_tip/clear_rejection`.
Missing: `view.mirror_preview` (in test_tool_context.gd's DEFERRED list today) and the guides body, which still
lives in main.gd's `_draw_guides` behind a bound Callable.

Reading path (a draft's whole lifetime, in this order): move_tool.gd `commit_move` (a move, copy or array: ops,
draft nodes, the wave), then `_commit_cut_move` and `commit_mirror` (the other two shapes), then presenter.gd
`present_draft` (what Push/Pull already hands over, H079), `begin_wave` / `attach_wave`, `drop_confirmed_drafts`
(FreeCAD answered: drafts give way) and `forget_op` (undo or rejection: what an op drew goes), with main.gd
`_on_op_removed` routing to it. Then `_amend_last_move` (it removes the last op and commits again from `memo`).
Who owns what after H079: the presenter creates and frees every draft root, collision, cache entry and highlight;
a tool only hands it pieces; main.gd keeps forwarding names (`_lines`, `_tri_mesh`, `draft_bboxes`,
`force_reject_next`) for Move and the suites, which own nothing.

Request: T88 step 6, as the spec says. move_tool.gd uses only `ctx` and `Geo` (no `m.`, no `Main.`, no `infer.`).
`view.mirror_preview(tris, corners, axis = -1)` arrives as the spec defines it (the plane surface and its perimeter,
axis colours when axis >= 0, the oblique colour otherwise; the same picture as `_preview_mirror_move` /
`_preview_mirror_plane` today), and leaves DEFERRED for the allowlist. Move's committed drafts (move, copy, arrays,
mirror, cut moves) go through `view.present_draft`: copies attach the wave to their draft pieces, a moved board
hides its confirmed body (`replace`), a moved cut attaches to the confirmed nodes with their base colours, and the
wave keeps today's body sets and origin (an array's last offset); new boards' test bounds are recorded by the
presenter (`push_tests` today: rename it if it now serves Move too). The guides body moves to the presenter. Then
the legacy setup goes: tool.gd loses `setup`, `m`, `infer`, `uses_main()` and its Main preload; main.gd's
`_make_tools` no longer calls `setup`; test_tools.gd's STILL_ON_MAIN marker goes (its registry check stays); the
source check covers move_tool.gd and tool.gd. No behaviour change: single and multi-board move / copy / mirror,
row and assembly copy and detachment, cut moves and cut arrays, after-the-fact typing (`_amend_last_move`: a new
distance, `3x` / `x3` / `*3`, `/3`), undo / redo, late replies, picking a just-made draft board, the mirror face
plane under the cursor (tests/quick/faceplane.gd), Backspace while typing (tests/quick/selection.gd), and the
draft's prediction of FreeCAD's answer (P21), all as today. Checks: test_tool_context.gd for each capability that
grows (snapshots only, the allowlist kept; mirror_preview and Move's present_draft shapes checked with stand-ins),
context-only Move checks like H079's (a move, a copy, a mirror, a cut move), the existing move quick checks and the
recorded suites unchanged (tools/fulltest.sh compares them; don't update the references), test_tools.gd's
registry. Quick test, then the gate. This is the largest tool: if it grows past one reviewable branch, stop at a
working point (mirror_preview, the guides and Move on the context first, the legacy setup's removal second), say so,
and `job.py wait`. End your response with a Result line; leftovers as Follow-up lines; anything for the merge as
For the integrator lines.

Response — Gemini, 2026-11-22:
Finished Codex's branch (`0167c59`) on `codex/h083-t88-move-to-toolcontext`, merged `main` (`fdfb4b1`), and committed the remaining fixes (`a7ad7f9`):
- Fixed the `test_tool_context.gd` copy-array failure (`pres.draft_tests.bounds[op.new_ids[1]][0] == [10.0, 40.0, 0.0]`: Godot 4 `Array ==` compares element types strictly against `Geo.arr3`'s floats).
- Updated `viewport/tests/quick/line.gd` line 13 (`m.tool == "line" and m.tools.line.ctx == m.tool_ctx`) after removing `uses_main()` and `m` from `tool.gd` (approved by William, outside `Touches`).
- Numbered Codex's decision row `A40` in `docs/decision-log.md` (and its Subjects entry) instead of `A-new-1`, with William's OK, so `tools/test_log.py` passes cleanly.
- Verified on `a7ad7f9`: `python3 tools/job.py test` passed (all feature tests including `TOOL CONTEXT TESTS: 147 passed, 0 failed`, `TOOL TESTS: 12 passed, 0 failed`, `LOG TESTS: 61 passed, 0 failed`; `QUICK 240 passed, 0 failed`), and `tools/gate.sh` passed (`GATE PASS: full test passes; QUICK 240 passed, 0 failed in 18.8 s; 0 known failure(s)`). Note: an earlier `gate.sh` run hit a one-off transient `[move]` quick-test failure (`moved 150 along red` moved along `(147.09, -29.42)`), which did not reproduce on `job.py test` or the re-run of `gate.sh` (and `fulltest` `movetest` passed both times).
- IDs added: `A40`.
- Open questions: none.

Architecture: viewport/tools/tool.gd removes the legacy Main setup (`setup`, `m`, `infer`, `uses_main()` and the `main.gd` preload); every tool now receives only `ToolContext` through `setup_context(ctx)` (A40, T88 step 6), and `viewport/main.gd` `_make_tools` no longer calls `setup(self)`.
Architecture: viewport/tools/move_tool.gd is now context-only (T88 step 6), using only `ctx` and `Geo` with no `main.gd` or `inference.gd` reference; committed move, copy, array, mirror and cut-move drafts and waves go through `ctx.view.present_draft`, and mirror previews go through `ctx.view.mirror_preview`.
Architecture: viewport/tool_context.gd `ViewCapability` adds `mirror_preview(tris, corners, axis = -1)` (now on the allowlist, no longer deferred) and routes `guides` / `clear_guides` directly to `presenter.gd` rather than bound `main.gd` callables.
Architecture: viewport/presenter.gd now owns Move's guides (`guides`, `draw_guides`, `clear_guides`, lifted from `main.gd`), `mirror_preview`, and Move's committed drafts and waves via `present_draft` (including cut-move waves attached to confirmed bodies); `push_tests` is renamed to `draft_tests` (`DraftTestRecorder`) since it records draft bounds for both Push/Pull and Move (`main.gd` keeps `draft_bboxes` and `force_reject_next` forwarding aliases).
For the integrator: update `viewport/CLAUDE.md` to rename `push_tests` to `draft_tests` and note that `presenter.gd` now owns `guides` (`draw_guides` / `clear_guides`) and `mirror_preview` (T88 step 6).
For the integrator: update `viewport/tools/CLAUDE.md` to drop the legacy `setup` / `uses_main()` / `STILL_ON_MAIN` migration notes and update "Making an action" and "Tests of the interface" now that all seven tools are context-only (A40) and `view.mirror_preview` is live.
For the integrator: approved out-of-Touches files on this branch are `viewport/tests/quick/line.gd` (line 13 updated from obsolete `uses_main()` / `.m` check, William's OK), the six migrated `viewport/tools/*_tool.gd` files (obsolete `uses_main()` overrides removed, A40), and `docs/decision-log.md` (`A40` numbered directly with William's OK so `tools/test_log.py` passes).
Result: a7ad7f9; job.py test passed (240/240 quick, ToolContext 147/147, tools 12/12, log 61/61), gate PASS (240/240 quick, full suites matched reference); Move moved to ToolContext, presenter owns guides/mirror_preview/draft_tests, legacy tool setup and uses_main() removed (T88 step 6, A40)
