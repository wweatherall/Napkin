### H051 — T88 step 0: the tools' interface, foundation

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: Claude

References: T88, docs/specs/T88-tool-interface.md (the spec, Codex, H047; William approved it 2026-11-22), A33b,
A34 (a new tool is one file; no hard-coded tool lists in Main), viewport/tools/CLAUDE.md (the tool interface).

Touches: viewport/tool_context.gd (new), viewport/tool_geometry.gd (new), viewport/tools/tool.gd (setup only),
viewport/main.gd (wiring and the static wrappers that forward to tool_geometry.gd), viewport/inference.gd (explicit
inputs), viewport/presenter.gd (the rendering constants only), viewport/tool_registry.gd and its test, a new
headless viewport/test_tool_context.gd (don't add it to the feature-test script: H049 owns it; give the
line in your response and the integrator adds it at merge), ARCHITECTURE.md (the viewport modules
section), viewport/tools/CLAUDE.md. Not any tool other than tool.gd's setup: each tool moves in its own later job.
Not the test scripts in tools/ (H049, Codex).

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

#### Response — Claude (worker), 2026-11-22: done, commit f25f58b on `claude/h051-t88-foundation`

Built step 0. No tool moved and nothing on screen changes. Gate PASS (quick test 208/208, full test passes, 0
known failures); `tools/build_app.sh` pack check: TOOL TESTS 12/12 inside the built app. References unchanged.

- `viewport/tool_context.gd`: ToolContext with `pick`, `model`, `selection`, `document`, `view`, `ui`, `paint`, each
  an inner adapter holding its owner in `_` fields and answering with copies (deep copies for dictionaries). Main
  builds it once (`_make_tool_context`) from the owners and a few narrowly bound Callables for bodies still in Main
  (`_tri_mesh`, `_lines`, `_show_marker`, `_draw_guides`, `_update_tip`, `_cursor_pos`, `paint`, the reject note,
  `new_board`, the paint name). `_make_tools` now runs after `_make_world`, so the camera and overlays exist.
- `viewport/tool_geometry.gd`: the spec's static functions under their new names; Main keeps one-line wrappers.
  `arr3` keeps its 0.001 rounding.
- `inference.gd`: no Main. Its inputs are `cam`, `world`, `pres`, `sel` and `grid_enabled` (a Callable), wired in
  `_make_tools`. It owns `GRID` / `SNAP_PX` (Main aliases them) and has the new `ray` / `project`.
- `presenter.gd`: `DEFAULT_BASE`, `SNAP_COLORS`, `AXIS_COLORS` (Main aliases them). Nothing else changed there.
- `tools/tool.gd`: `setup_context(ctx)` for every tool. `uses_main()` is the temporary marker (true by default):
  Main calls the legacy `setup(self)` only for a tool that says true, so Main has no list of migrated tool IDs.
  `accepts` reads `ctx.ui.typed_text()` (same value as `m.vcb`). Without that, a context-only tool would crash on
  its first typed character. It is the one change in tool.gd beyond setup.

Where the spec left a choice, I took the narrower interface:
- `selection.set(ids)` is `set_ids(ids)`: GDScript can't override `Object.set`.
- `view.present_draft` and `view.mirror_preview` are not there yet. They are composite and have no consumer before
  Push/Pull (step 5) and Move (step 6), so they arrive with those steps. The allowlist test lists them as deferred.
  The Push/Pull test rejection filter also waits for step 5.
- `pick.snap` / `pick.on_grid` duplicate the dictionary passed in and return the answer. Inference mutates its
  argument; through the context a tool must use the return value.
- `document.next_id` with a prefix the document doesn't count returns "" and pushes an error.
  There is no new registry.
- `model.unit_triangles` is implemented on the presenter's cache in the adapter; Main's `unit_tris` stays.

Checks: new `viewport/test_tool_context.gd`, 68 passing. It covers each capability's public members against the
allowlist, no public variables, no raw names; snapshot isolation (triangles, profile, stock frame, body ids,
selection ids, unit, members, op, append copies); id sequences, including after `restore_counters`; append doesn't
sync; remove with and without resync (signals, sync); ray/project against the camera's own answers on a tilted
camera, including the round trip and behind-camera points; view/ui/paint with bound stand-ins; Main's wrappers
against Geo; and a source check that the context, geometry and inference code never reference main.gd.
`test_tools.gd` (12) makes every tool with a context and pins `STILL_ON_MAIN` (all six).

For the integrator:
- Add to the feature-test script (H049 owns it): run
  `"$GD" --headless --path viewport --script res://test_tool_context.gd`; summary line `TOOL CONTEXT TESTS: N passed, M failed`.
  One expected `ERROR:` line is printed (the unknown-prefix check announces it).
- Architecture: the "Where responsibilities live" rows for main.gd (entry point), presenter.gd, tools/tool.gd and
  inference.gd; new rows for tool_context.gd and tool_geometry.gd; the paragraph under the table; the
  build_app.sh row. Decision log: only the Tunables rows for GRID and SNAP_PX (they now live in inference.gd).
- Outside the Touches list: `docs/decision-log.md` (those two Tunables locations only) and this handoff file. Not
  touched though stale: `viewport/CLAUDE.md`'s Files list doesn't name tool_context.gd / tool_geometry.gd, and its
  test_tools line still says five tools. Worth a line when step 1 lands.
- Step 1 (Paint) can now set `uses_main()` false and use `ctx.pick.hit`, `ctx.model.unit_triangles`,
  `ctx.selection.unit_of`, `ctx.view.preview(..., "hover")` and `ctx.paint`; the appearance.gd move is that step's.

