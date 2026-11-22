### H041 — T81: the Circle tool

Author: Claude (integrator) | Date: 2026-11-22 | Status: open | For: either

References: T81, I49, I50 (key C) (Codex S08), A03 (faces by geometry), A22b (hole runs), I04b (new board vs cut),
viewport/tools/CLAUDE.md (the tool interface), rect_tool.gd (the model to follow), FREECAD_FEATURE_MAP.md (S08 row).

Touches: viewport/tools/circle_tool.gd (new), viewport/tools/push_tool.gd and worker/push.py (pushing a circle's
face), worker/circle.py (new, a CircleActions class: found by itself, no model.py edit), viewport/presenter.gd (the circle's
draft), (no main.gd or keys.gd edit: circle_tool.gd declares its TOOL constant, viewport/tools/CLAUDE.md "Adding a tool"),
viewport/test_tools.gd and viewport/tests/quick/registry.gd (add Circle to the pinned tool list), worker/scenario/99_op_registry.py (the new op type), viewport/tools/CLAUDE.md,
viewport/tests/quick/circle.gd and worker/scenario/NN_circle.py (new), docs/protocol.md (the new op),
ARCHITECTURE.md (module table rows).

Request: centre click, then radius by drag or typed value (any length syntax the measurements box takes), on the
ground or on a face, snapping like Rectangle. In FreeCAD an exact circle (sketch or Part circle), never a polygon;
the viewport draws facets. Push/Pull turns it into a round board (on the ground, or with New board on) or a round
hole / boss on a face, with the same new-board and cut rules as a rectangle. The key is C (I50, William's call); ask William
before building about anything in the gesture that rect_tool.gd doesn't settle. Checks: scenario
steps for circle → push into a dowel, a round hole through a board, undo/reopen equal a fresh build; a quick
section that draws one with the real tool.

Response — Claude (integrator), 2026-11-22: reviewed; held for the tool registry (A34), now on main. Please
merge main into `codex/h041-circle-tool`, then: drop your edits to viewport/main.gd (tool list, toolbar) and
viewport/keys.gd (the C key) and put a `TOOL` constant in circle_tool.gd instead (id "circle", label "Circle",
tip "Circle (C)", key KEY_C, order between Rectangle and Push/Pull; viewport/tools/CLAUDE.md "Adding a tool");
move your worker op into a `CircleActions` class in worker/circle.py and drop the HANDLERS / Model-bases edits in
worker/model.py; add Circle to the pinned lists in viewport/test_tools.gd, viewport/tests/quick/registry.gd and
worker/scenario/99_op_registry.py; bump nothing in the protocol version unless a message changed (a new op type
inside sync is a payload change: bump PROTOCOL_VERSION to 2 on both sides, A35). Run `tools/gate.sh`, then
answer again. Don't edit the Work list (P17).
