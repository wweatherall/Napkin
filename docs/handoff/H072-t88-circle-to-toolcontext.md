### H072 — T88 step 3: Circle moves to ToolContext

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: either

References: T88, docs/specs/T88-tool-interface.md (§ circle_tool.gd, the delivery table's step 3), P21, A34, H051
(ToolContext), H065 (Paint) and H071 (Select): the worked examples; follow their pattern and test shape.

Touches: viewport/tools/circle_tool.gd, viewport/tool_context.gd and viewport/test_tool_context.gd, viewport/presenter.gd
(only if a profile-registration or drawing body moves there), viewport/main.gd (only lifting a body Circle needs out;
keep wrappers other code still reads), viewport/test_tools.gd (STILL_ON_MAIN), viewport/tests/quick/circle.gd (only
if the existing checks don't cover the move). Not ARCHITECTURE.md, docs/protocol.md or the folder guides: write what
changes as "Architecture:" lines and guide changes as "For the integrator:" lines.

Request: T88 step 3, as the spec says. circle_tool.gd uses only `ctx` and `Geo` (`uses_main()` false; no `m.`):
picking and snapping through ctx.pick, the profile registered through ctx.view (register_profile), the op through
ctx.document (next_id / append / sync, no counters or ops by hand), drafts and the radius preview through ctx.view,
measurements through ctx.ui, edit_blocked through ctx.selection. As the spec says, no other Main body is deleted just
because Circle stops using it. No behaviour change: the circle gesture, its unit, the exact radius FreeCAD gets and the
draft's prediction of it (P21) all as today. Checks: test_tool_context.gd for whatever capability grows (snapshots
only, the allowlist kept), a context-only Circle check like H071's Select one, the source check list gains
circle_tool.gd, the existing circle quick checks and length/circle comparison tests unchanged, test_tools.gd's
registry. Quick test, then the gate. If only the known H069 flakes (test_startup.py's timeout, outside-save's
"unsaved") stop `job.py done`, say so in the response and `job.py wait` as H071 did; the integrator's gate decides.
End your response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.

#### Response (Claude, worker, 2026-11-22)

Architecture: viewport/tools/circle_tool.gd moves to ToolContext (T88 step 3): `uses_main()` is false; it picks and snaps through ctx.pick (hit, snap, on_grid, ray), reads a profile's board through ctx.model.profile and its preview disc through ctx.model.circle_geometry, previews and the marker through ctx.view (preview "profile", marker, clear_preview), registers the op through ctx.view.register_profile, allocates/appends/syncs through ctx.document, refreshes the measurements box through ctx.ui, and checks edit_blocked through ctx.selection. No ToolContext surface changed.
Architecture: presenter.gd circle_geometry uses tool_geometry.gd's plane_basis (Main.plane_basis only forwarded to it), so it no longer needs Main; register_rect still draws with Main's mesh helpers (Rectangle/Push steps).

Branch claude/h072-t88-circle-to-toolcontext. circle_tool.gd has no `m.`, `Main` or `infer`: every call goes through ctx (or Geo.arr3), with the same order as before: append, register the profile, reset, clear the preview, sync. The gesture, the snap fallback at the centre, the typed radius (abs, whole), `pointer_distance_ok` and the radius in the op are unchanged. Circle didn't clear the rejection note before and still doesn't. No Main body was deleted. presenter.circle_geometry now uses Geo.plane_basis (same function, Main's version only forwarded) so a context-only test can build the disc without Main.

Tests: test_tool_context.gd 111/0 (adds 9 context-only Circle checks: the marker before the centre; the radius from ctx.pick.ray on the centre's plane and the measurements refresh; the 62-triangle disc and 128-point outline in the "profile" style; one circle op with a document id, the exact radius and plane; register_profile gets a copy, the preview is cleared, one sync; the board under a profile through ctx.model; the grid fallback at the centre; the typed radius; edit_blocked; the source check now covers circle_tool.gd); test_tools.gd 13/0 (STILL_ON_MAIN is now rect, push, move); quick test 240/0 (circle quick checks unchanged; FreeCAD matches all 2500 length cases); `tools/gate.sh` GATE PASS, 0 known failures.

Follow-up: line_tool.gd uses only ctx but isn't in test_tool_context.gd's source check list; one line to add (Rectangle's step could take it).
For the integrator: tool_context.gd's header now names Circle among the context-only tools; viewport/tools/CLAUDE.md, if it lists the tools that have moved, gains Circle.

Result: 853495f; quick 240/0, gate pass; Circle (circle_tool.gd) uses only ToolContext, with a context-only Circle check and the source check covering it (T88 step 3)
