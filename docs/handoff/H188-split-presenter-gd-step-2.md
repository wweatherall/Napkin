### H188 — presenter.gd step 2: drawn profiles (rectangles, circles, polygons, lines) move to their own file, behaviour unchanged

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: open | For: gemini

References: William, 2026-11-27 (architecture order: split main.gd and presenter.gd; step 2 for the next batch), H181
(presenter.gd step 1: the pattern, `pres.waves` / `pres.selection_view`), A33b, P50, P73, comitatus principle C03.

Touches: viewport/presenter.gd (its "rectangles drawn on faces and in space" section, ~lines 302-574), 
viewport/profiles.gd (new), viewport/CLAUDE.md (the presenter's lines). (H187 also touches viewport/CLAUDE.md: under the hopper
this job is cut from H187's branch.)

Reading path:
1. viewport/presenter.gd's header and its "operation wave (waves.gd) & selection/context (selection_view.gd)" section:
   how H181 made `pres.waves` / `pres.selection_view` and kept forwarders.
2. The rectangles section: `register_line`, `_refresh_loop_drafts`, `lines_on`, `drawn_region`, `register_rect`,
   `circle_geometry`, `polygon_geometry`, `drop_draft`, `rebuild_rect_drafts`, `forget_op`, `drop_confirmed_drafts`,
   and the state they use (`rects`, `drafts`, `loose_lines`, ...: some is declared near the top of the file).
3. Every caller of those names: `python3 tools/dependency_map.py callers viewport/presenter.gd:<name>`. Callers
   reach them as `m.pres.<name>`, through main's forwarders (`m.drafts`, `m._rebuild_rect_drafts`), and through
   tool_context.gd's presenter view (`circle_geometry`, `polygon_geometry`, `lines_on`, `drawn_region`), which
   test_tool_context.gd stubs by name.

Today (checked 2026-11-27): presenter.gd is 812 lines. The rectangles section (~270 lines) is what every drawing
tool's preview and every profile op's draft goes through: Circle, Polygon, Rectangle, Line and Arc jobs all touch it.

Request:
1. **viewport/profiles.gd** takes the section (`pres.profiles`), made like `pres.waves`, with a header whose first line
   is its map line (P50). State only this section uses moves with it; state other sections also use stays in the
   presenter and profiles.gd reaches it through the presenter.
2. **Nothing else changes**: same behaviour, same drafts and their order, same names reachable through the presenter,
   so main.gd, tool_context.gd, tools and tests don't change: the presenter keeps a forwarder for each moved name used
   outside it; one only the presenter used moves without one.
3. Report presenter.gd's size before and after, and profiles.gd's.
4. Your response's `Architecture:` line: `Architecture: viewport/profiles.gd owns <what>`.

Not in this job: main.gd (H187), the confirmed boards / confirmed states / cuts sections (a later step), any rename,
behaviour change, or rewrite while moving.

What can fail:
- A draft drawn twice or left behind after undo, a rejection or a confirmed board: `rebuild_rect_drafts`, `forget_op`
  and `drop_confirmed_drafts` run from history.gd and the presenter's confirmed-boards code. Check: the quick and full
  viewport tests (undo/redo and rejection scenarios), unchanged.
- A tool's preview changing shape: tool_context.gd hands tools copies of `circle_geometry` / `polygon_geometry`
  results. Check: test_tool_context.gd and the tool tests pass unchanged.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope); quick 401/401.
- `python3 tools/architecture_map.py --check` and `python3 tools/dependency_map.py --check`.
