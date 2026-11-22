### H072 — T88 step 3: Circle moves to ToolContext

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: either

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
