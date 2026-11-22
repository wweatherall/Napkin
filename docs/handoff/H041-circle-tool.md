### H041 — T81: the Circle tool

Author: Claude (integrator) | Date: 2026-11-22 | Status: open | For: either

References: T81, I49, I50 (key C) (Codex S08), A03 (faces by geometry), A22b (hole runs), I04b (new board vs cut),
viewport/tools/CLAUDE.md (the tool interface), rect_tool.gd (the model to follow), FREECAD_FEATURE_MAP.md (S08 row).

Touches: viewport/tools/circle_tool.gd (new), viewport/tools/push_tool.gd and worker/push.py (pushing a circle's
face), worker/circle.py (new mixin) and the HANDLERS line in worker/model.py, viewport/presenter.gd (the circle's
draft), viewport/main.gd (the tool list and toolbar segment only), viewport/keys.gd (the key), viewport/tools/CLAUDE.md,
viewport/tests/quick/circle.gd and worker/scenario/NN_circle.py (new), docs/protocol.md (the new op),
ARCHITECTURE.md (module table rows).

Touches clarification — Codex, 2026-11-22: also viewport/measure_box.gd (route typed circle radii through
the length evaluator), viewport/inference.gd (iterate the actual loose-profile perimeter instead of four corners); main.gd includes the small redo, menu selection and sibling-highlight tool lists.
Circle profiles reuse the existing r counter / rect target key, so document.gd needs no change. H042 is queued
behind H041; H043 and H044 do not own these files.

Request: centre click, then radius by drag or typed value (any length syntax the measurements box takes), on the
ground or on a face, snapping like Rectangle. In FreeCAD an exact circle (sketch or Part circle), never a polygon;
the viewport draws facets. Push/Pull turns it into a round board (on the ground, or with New board on) or a round
hole / boss on a face, with the same new-board and cut rules as a rectangle. The key is C (I50, William's call); ask William
before building about anything in the gesture that rect_tool.gd doesn't settle. Checks: scenario
steps for circle → push into a dowel, a round hole through a board, undo/reopen equal a fresh build; a quick
section that draws one with the real tool.
