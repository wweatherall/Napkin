### H046 — T82: the Line tool, closed outlines and split faces

Author: Claude (integrator) | Date: 2026-11-22 | Status: open | For: Codex

References: T82, I51 (lines split faces; Push/Pull acts on the region under the cursor; one op to FreeCAD), I49,
A34 (a new tool is one file), A35 (bump the protocol version for a new op), P21 (the viewport's region must be
tested against FreeCAD's result), A03; Circle (H041, docs/handoff-archive.md) for the pattern: profiles, exact
sketches, push of a profile.

Touches: viewport/tools/line_tool.gd (new), worker/line.py (new, a LineActions class), viewport/regions.gd (new:
the region finding, pure functions) and viewport/test_regions.gd (new, headless; give its feature-test line in your response: H049 owns that script
and the integrator adds it),
viewport/tools/push_tool.gd and worker/push.py (pushing a region), viewport/presenter.gd (line drafts, the region
overlay), viewport/inference.gd (snapping to lines), viewport/test_tools.gd, viewport/tests/quick/registry.gd,
worker/scenario/99_op_registry.py (the pinned lists), viewport/tests/quick/line.gd and worker/scenario/NN_lines.py
(new), viewport/tools/CLAUDE.md, docs/protocol.md, ARCHITECTURE.md. Not viewport/tests/harness.gd,
quick_runner.gd or tools/quicktest.sh (H045).

Request, in two stages (a commit and a gate run each):
1. Lines and closed outlines: the Line tool draws on the ground or a face, snapping like Rectangle and Circle;
   lines are kept as drawings (an op each, undoable, saved) and change no solid; lines that close a loop make a
   face that Push/Pull turns into a board, a cut or a boss, like a rectangle.
2. Split faces (I51): a line across a face splits it into regions; Push/Pull over a face finds the region under the
   cursor from the face's outline and every line on it (regions.gd), previews it at once, and sends one op with
   that region's closed outline. Test the awkward cases in test_regions.gd: crossing lines, a line ending partway
   (it doesn't split), a line ending exactly on an edge or a corner, two lines meeting on an edge, near-overlaps.
   P21: compare the predicted region with the face FreeCAD made (area and bounds) in the scenario.
William's answers (2026-11-22, logged as I58): the key is L; the gesture is the click-click chain (each click
ends a line and starts the next; Esc or clicking the start point ends it; a typed length sets the current line) plus
press-drag-release for a single line (I43's rule). Build on ToolContext (H051, merged 9581352; docs/specs/T88-tool-interface.md) from
the first file: no m.* in line_tool.gd, and uses_main() returns false. What ctx lacks for Line (loose lines,
regions), add to its capability with a test in test_tool_context.gd and say so. Push/Pull hasn't moved to the context yet when you start (it moves after
Line): change push_tool.gd as little as the region push needs.
