### H083 — T88 step 6: Move moves to ToolContext, and the legacy setup goes

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: either

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
