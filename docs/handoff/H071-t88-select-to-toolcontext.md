### H071 — T88 step 2: Select moves to ToolContext

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: either

References: T88, docs/specs/T88-tool-interface.md (§ select_tool.gd, the delivery table's step 2), A34, H051
(ToolContext), H065 (Paint, step 1: the worked example; follow its pattern and test shape).

Touches: viewport/tools/select_tool.gd, viewport/tool_context.gd and viewport/test_tool_context.gd, viewport/presenter.gd
(the box Panel and unit triangles, if they move there), viewport/selection.gd (only if unit_tris belongs with it),
viewport/main.gd (only lifting `unit_tris` out and the box Panel; keep wrappers/aliases other code still reads),
viewport/test_tools.gd (STILL_ON_MAIN), viewport/tests/quick/selection.gd (only if the existing box/click checks don't
cover the move). Not ARCHITECTURE.md, docs/protocol.md or the folder guides: write what changes as "Architecture:"
lines and guide changes as "For the integrator:" lines.

Request: T88 step 2, as the spec says. select_tool.gd uses only `ctx` and `Geo` (`uses_main()` false; no `m.`):
reads through ctx.model / ctx.selection / ctx.pick, the selection box drawn through ctx.view (its Panel owned by
the presenter, not added by the tool), and `unit_tris`'s body lifted out of Main (a Main wrapper may stay for other
callers). `Select.box_ids` keeps its signature (other code calls it). No behaviour change: box direction
(window vs crossing), crossing triangles, points behind the camera, additive selection and Esc restoring the
previous selection, context, hidden and deleted boards all as today. Checks: test_tool_context.gd for whatever
capability grows (snapshots only, the allowlist kept), a context-only Select check like H065's Paint one, the
source check list gains select_tool.gd, the existing selection quick checks unchanged, test_tools.gd's registry.
Quick test, then the gate. End your response with a Result line; leftovers as Follow-up lines; anything for the
merge as For the integrator lines.
