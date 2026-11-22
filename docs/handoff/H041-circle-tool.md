### H041 — T81: the Circle tool

Author: Claude (integrator) | Date: 2026-11-22 | Status: answered | For: either

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


Response — Codex, 2026-11-22:

- Ready for review on `codex/h041-circle-tool`, implementation commit `5d8e3be`; based on main through
  `b426d7f`. No merge into main or push. No placeholder IDs or new William decisions.
- Built Circle (C, toolbar and Tools menu), centre then radius by click-click or press-drag-release, typed
  lengths through the shared evaluator (fractional inches included), ground/face snapping, immediate faceted
  draft, Escape, undo/redo and loose-profile restoration. The presenter and snapping iterate a profile's actual
  perimeter. Circle and rectangle profiles share `r` IDs, `RectId` and `target.rect`; document.gd is unchanged.
- Native profiles are exact, fully constrained `Sketcher::SketchObject` circles with an editable radius;
  Push/Pull reuses/clones native sketches in world or board-definition coordinates. Ground pushes make round
  boards; face pushes cut or join, with through-cut expressions and B for separate boards, like Rectangle.
- Verification: `tools/quicktest.sh` passed: **169 viewport checks, 0 failed**, all feature tests passed
  (including **272 scenario checks**, 0 failed). Logs:
  `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-quick.lXZbaUltLN`.
  `tools/fulltest.sh` passed (exit 0): all six suites match, targeted UI and feature tests pass. Logs:
  `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-full.2u5RQvlFaQ`.
  The full run preceded the final two extra scenario cases and UI volume-tolerance correction (bodies.json
  rounds volumes to 0.1 mm³); the final quick run covers those. Earlier quick runs also reproduced the known
  H042 worker-restart and H043 hide failures; both passed in the final run.
- Tests cover exact cylinder/bore/boss volumes, native circular edges and sketch constraints, vertical mirrored
  stock, translated linked stock, an arbitrary plane, reusing a consumed profile, invalid radii, undo, fresh-build
  and reopen parity. UI checks use the real tools, including fractional-inch and sub-mm radii, centre picking,
  undo/redo, round holes/bosses and separate boards. Visually inspected `circle_dowel.png` and
  `circle_hole_boss_board.png` in the quick run's `vp3/shots/`: toolbar fits; round solids and through-hole show.
- Architecture sections changed: **Where responsibilities live** and **Native model and identity**.
  `docs/protocol.md` is now reference **0.2**, adding the `circle` op and defining `target.rect` as a rectangle or
  circle profile ID; H042 should bump from this version. The tool guide includes Circle and its limits.
- Nothing in the H041 request remains open. Existing rectangular-stock plane-fit end conditions remain
  rectangle-only; circles keep point/back-face depth inference. Round-hole Move/array UI remains outside this
  job (exported cut handles are still rectangular). The integrator can update I49/I50's implementation-status
  cells when merging; only T81's result row was edited here.
