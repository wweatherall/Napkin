### H065 — T88 step 1: Paint moves to ToolContext

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: queued (after H059) | For: either

References: T88, docs/specs/T88-tool-interface.md (§ paint_tool.gd, § Paint: ctx.paint, the delivery table's step 1),
A34 (tool registry), H051 (ToolContext, merged 9581352), H046 (Line, the first context-only tool: follow its
pattern), T99 (Paint's key: not this job, keep B / today's key as is).

Touches: viewport/tools/paint_tool.gd, viewport/appearance.gd (new), viewport/tool_context.gd (the paint capability)
and viewport/test_tool_context.gd, viewport/main.gd (only removing the paint command and library state it hands to
appearance.gd, keeping compatibility aliases where other code still reads them), viewport/test_tools.gd, a
quick-test step if the existing paint checks don't cover the move (viewport/tests/quick/paint.gd, new or existing).
Not ARCHITECTURE.md or docs/protocol.md (P28): write what changes as "Architecture:" lines.

Request: T88 step 1, as the spec says. paint_tool.gd uses only `ctx` (`uses_main()` false; no `m.`), and
appearance.gd owns the wood library, the paint selection, `current_name()` and `apply(targets)` (the lifted
`main.gd:paint`, through document.next_id/append/sync, status through a signal to Main's `_say_status`). Menus keep
their layout in Main and ask appearance to select a wood; selecting still activates Paint. `_turn_grain` stays a
keyboard/menu action. No behaviour change: the same status text, the same empty/invalid target checks, the same
paint/family/assembly and wood/grain results. Checks: test_tool_context.gd for the paint capability (no library map
or material resources escape), the existing paint quick checks unchanged, test_tools.gd's registry. Paint is the first worked example for the other tool moves (Codex's suggestion, 2026-11-22): in your response,
say whether ctx told you enough to change painting and its hover highlight without reading main.gd, and what was
missing. Quick test, then
the gate. End your response with a Result line; leftovers as Follow-up lines; anything for the merge as For the
integrator lines.
