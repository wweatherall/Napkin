### H075 — T88 step 4: Rectangle moves to ToolContext

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: either

References: T88, docs/specs/T88-tool-interface.md (§ rect_tool.gd, the delivery table's step 4), P21, A34, H051
(ToolContext), H065 (Paint), H071 (Select) and H072 (Circle): the worked examples; follow Circle's pattern and test
shape (it shares the profile interface: register_profile, the "profile" preview style, ctx.model.profile).

Touches: viewport/tools/rect_tool.gd, viewport/tool_context.gd and viewport/test_tool_context.gd,
viewport/tool_geometry.gd (only if a pure body moves there), viewport/presenter.gd (only if register_rect's drawing
body moves there), viewport/main.gd (only lifting a body Rectangle needs out, or deleting a wrapper with no remaining
consumer; keep wrappers other code still reads), viewport/test_tools.gd (STILL_ON_MAIN), viewport/tests/quick/rect.gd
(only if the existing checks don't cover the move). Not ARCHITECTURE.md, docs/protocol.md or the folder guides: write
what changes as "Architecture:" lines and guide changes as "For the integrator:" lines.

Request: T88 step 4, as the spec says. rect_tool.gd uses only `ctx` and `Geo` (`uses_main()` false; no `m.`, no
`Main.`): picking and snapping through ctx.pick (ray for the camera), the corners through Geo.rect_points (not
Main._rect_pts), the preview through ctx.view.preview in the "profile" style, the op through ctx.document (next_id /
append / sync, no counters or ops by hand) and ctx.view.register_profile, measurements through ctx.ui, edit_blocked
through ctx.selection, a profile's board through ctx.model.profile. As the spec says, delete only wrappers with no
remaining consumer. No behaviour change: the rectangle gesture, the zero-side snap fallback, tilted planes, typed
fractional and sub-millimetre dimensions, the exact sizes FreeCAD gets and the draft's prediction of them (P21) all as
today. Checks: test_tool_context.gd for whatever capability grows (snapshots only, the allowlist kept), a context-only
Rectangle check like H072's Circle ones (the zero-side fallback, a tilted plane and a typed fractional size among
them), the source check list gains rect_tool.gd and line_tool.gd (H072's follow-up: Line uses only ctx but isn't
listed; clear that line in docs/follow-ups.md), the existing rectangle quick checks and length comparison tests
unchanged, test_tools.gd's registry. Quick test, then the gate. If only the known H069 flakes stop `job.py done`, say
so in the response and `job.py wait`; the integrator's gate decides. End your response with a Result line; leftovers
as Follow-up lines; anything for the merge as For the integrator lines.
