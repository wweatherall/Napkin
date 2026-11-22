### H051 — T88 step 0: the tools' interface, foundation

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: Claude

References: T88, docs/specs/T88-tool-interface.md (the spec, Codex, H047; William approved it 2026-11-22), A33b,
A34 (a new tool is one file; no hard-coded tool lists in Main), viewport/tools/CLAUDE.md (the tool interface).

Touches: viewport/tool_context.gd (new), viewport/tool_geometry.gd (new), viewport/tools/tool.gd (setup only),
viewport/main.gd (wiring and the static wrappers that forward to tool_geometry.gd), viewport/inference.gd (explicit
inputs), viewport/presenter.gd (the rendering constants only), viewport/tool_registry.gd and its test, a new
headless viewport/test_tool_context.gd (don't add it to tools/featuretest.sh: H049 owns that file; give the
line in your response and the integrator adds it at merge), ARCHITECTURE.md (the viewport modules
section), viewport/tools/CLAUDE.md. Not any tool other than tool.gd's setup: each tool moves in its own later job.
Not tools/quicktest.sh, gate.sh, fulltest.sh (H049, Codex).

Request: build the spec's step 0 ("Tests and incremental delivery", row 0; "Proposed surface"; "Static geometry"):
ToolContext with its capability adapters (pick, model, selection, document, view, ui, paint), each holding its owner
privately and returning snapshots; the pure static functions moved to tool_geometry.gd with Main keeping wrappers;
explicit inference inputs; a context-only setup path beside the legacy setup(Main), with the temporary marker the
registry test checks (no list of migrated tool IDs in Main). No tool moves to it yet, and nothing you'd see changes.
Checks: test_tool_context.gd covers the public member allowlist against the spec's surface, snapshot isolation, ID
sequences, append without early sync, remove signalling; the registry test instantiates tools with a context;
the exported pack still finds every tool; quick test, then the gate. Recorded references stay as they are.
Where the spec leaves a choice open, take the narrower interface and say so in your response. Later stages, for
the integrator: 1 Paint, 2 Select, 3 Circle, 4 Rectangle (beside H046 Line, on files it doesn't touch), then 5
Push/Pull and 6 Move after Line lands, 7 cleanup.
