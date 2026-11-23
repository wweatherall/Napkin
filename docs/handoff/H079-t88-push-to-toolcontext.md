### H079 — T88 step 5: Push/Pull moves to ToolContext

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: either

References: T88, docs/specs/T88-tool-interface.md (§ push_tool.gd, § view.present_draft, the delivery table's step
5), P21, A22, A34, W01-W09 (the confirmation wave), H051 (ToolContext), H072 (Circle) and H075 (Rectangle): the
worked examples of a move.

Touches: viewport/tools/push_tool.gd, viewport/tool_context.gd and viewport/test_tool_context.gd,
viewport/presenter.gd (present_draft's body, the face highlight's lifetime, wave attachment, the Push test
recorder/filter), viewport/main.gd (lifting the bodies Push/Pull needs out; keep wrappers other code, Move and the
tests, still reads), viewport/tool_geometry.gd (only if a pure body moves there), viewport/test_tools.gd
(STILL_ON_MAIN), viewport/tests/quick/push.gd (only if the existing checks don't cover the move). Not
ARCHITECTURE.md, docs/protocol.md or the folder guides: write what changes as "Architecture:" lines and guide
changes as "For the integrator:" lines.

Request: T88 step 5, as the spec says. push_tool.gd uses only `ctx` and `Geo` (`uses_main()` false; no `m.`, no
`Main.`). view.present_draft arrives as the spec defines it (committed draft nodes and collisions, prediction
caches installed together, the pushed profile consumed, replaced confirmed bodies hidden, the wave started or
attached); the face highlight's lifetime and the Push test hook (draft_bboxes / force_reject_next) move out of
Main and the tool's writes, to the presenter's test recorder or an injected Push-only filter. Main's draft bounds
and rendering aliases stay while Move or the tests still need them. No behaviour change: new / join / cut /
through, exact circles, plane-fit modes and face cycling, rejection and dependent rollback, immediate picking of a
draft, and the draft's prediction of FreeCAD's answer (P21) all as today. Checks: test_tool_context.gd for each
capability that grows (snapshots only, the allowlist kept; present_draft checked with stand-ins), context-only
Push/Pull checks like H075's (a new board, a join, a cut, a rejection rolled back), the source check list gains
push_tool.gd, the existing push quick checks and the recorded suites unchanged (tools/fulltest.sh compares them),
test_tools.gd's registry. Quick test, then the gate. This is the largest move so far: if it grows past one
reviewable branch, stop at a working point (present_draft and its checks first), say so, and `job.py wait`. End
your response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.

### Response — Codex, 2026-11-22

Branch `codex/h079-t88-push-to-toolcontext`, implementation `a52d692`. The headless tests exercised picking a predicted board, preview consumption, joins, through-cuts, rejected draft cleanup and both wave attachment paths. The gate matched all six recorded suites. The rejection suite removed both dependent edits and kept the independent board. No decision IDs added or open questions.

Architecture: Push/Pull uses ToolContext for picking, model snapshots, selection, ops, previews and UI. The tool supplies predicted pieces and the wave origin, geometry, bodies and attachment choice. Move is the last tool with legacy Main setup.
Architecture: The presenter owns committed draft roots, collisions, prediction caches, profile consumption, replacement visibility, wave attachments and face highlights. Mesh, collision, line and marker helpers now live there. Main forwards the rendering and test names used by Move and the suites. A test-only pre-append filter changes the submitted Push target while presentation uses the original profile.

For the integrator: Update the viewport and tools guides to list Move as the last legacy tool. Document `model.drawn_region`, `view.present_draft(op, pieces, wave)` and presenter ownership of the rendering helpers and Push/Pull face highlight.

Result: a52d692; ToolContext 135/135, registry 13/13, quick 240/240, gate passed; Push/Pull uses ToolContext and the presenter installs committed drafts and their waves.
