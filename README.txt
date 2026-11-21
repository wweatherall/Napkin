Shop Sketch - Mac

A tool-first woodworking modeller with an editable FreeCAD model underneath.

Setup and launch
- Developed and tested with FreeCAD 1.1.4 and Godot 4.6, installed in /Applications.
- Run tools/build_app.sh to make dist/Shop Sketch.app; rebuild after updating the source.
  The app opens your last model, or Documents/Shop Sketch/Untitled.FCStd on first use.
- For development, double-click "Start Shop Sketch.command". It opens models/model.FCStd;
  its worker log is worker.log. If macOS blocks the downloaded launcher, right-click > Open.
- File > New / Open switches models; File > New Window opens another model.
  A compatible worker is shared between windows; the app starts/restarts it as needed.
- Models autosave as .FCStd with an adjacent .shopsketch.json journal. Close Shop Sketch
  before editing its model in FreeCAD; live merging of outside edits is planned work.
- Drawing export produces SVG and a cut-list CSV; PDF/PNG also need CairoSVG in the
  Python environment used by the drawing script (python3 -m pip install cairosvg).

Controls
- Space: Select. Shift-click adds/removes; double-click enters an assembly or array.
- R: Rectangle. Click a face or ground, then click or type width,height and Return.
- P: Push/Pull. Pick a rectangle or face, then click or type a distance; minus cuts.
  A rectangle on a face joins that board by default; B toggles a new board.
  Tab cycles target faces for a face link; Option cycles its end condition.
- M: Move a board, or grab a hole by its wall. Option toggles copy; Shift toggles mirror.
  Arrows cycle axis lock, plane lock, free. After copying, 8x makes a row; /8 spreads it.
- Type lengths with units, fractions or arithmetic; Return applies the value.
- Cmd+Z: Undo. Shift+Cmd+Z: Redo. Cmd+G: Make assembly. U: Make unique.
- H: Hide selection or hovered board. Shift+H: Unhide all. View > Hidden geometry
  shows hidden pieces for picking; Edit offers additional unhide actions.
- Wood menu: choose/paint material. T: Turn grain. Properties panel: inspect/edit one piece.
- G: Grid snap. D: Drawing export. Esc: cancel gesture, then clear selection, then leave context.
- Orbit: middle/right drag or two fingers on a trackpad. Pan: Shift with either gesture.
  Zoom: wheel or pinch.

Feedback
Draft geometry appears immediately while FreeCAD computes the native model. A confirmation
wave finishes when accepted; a red wave takes back rejected work and its dependent actions.
You can continue working before confirmation. The save indicator separately reports persistence.
The default renderer is Compatibility; changing renderers is not needed to use these features.

Documentation
- CLAUDE.md: shared development workflow, build/test commands and project overview.
- AGENTS.md: Codex-specific instructions.
- ARCHITECTURE.md: system map, state ownership, communication and persistence.
- worker/CLAUDE.md, viewport/CLAUDE.md, viewport/tools/CLAUDE.md: local rules and tests.
- viewport/README.md: direct Godot launch and command-line overrides.
- docs/decision-log.md: approved decisions, open questions and the Work list.
  Current capabilities and planned work are tracked there, rather than duplicated in a "not yet" list.
