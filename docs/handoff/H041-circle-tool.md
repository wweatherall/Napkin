### H041 — T81: the Circle tool

Author: Claude (integrator) | Date: 2026-11-22 | Status: answered | For: either

References: T81, I49, I50 (key C) (Codex S08), A03 (faces by geometry), A22b (hole runs), I04b (new board vs cut),
viewport/tools/CLAUDE.md (the tool interface), rect_tool.gd (the model to follow), FREECAD_FEATURE_MAP.md (S08 row).

Touches: viewport/tools/circle_tool.gd (new), viewport/tools/push_tool.gd and worker/push.py (pushing a circle's
face), worker/circle.py (new, a CircleActions class: found by itself, no model.py edit), viewport/presenter.gd (the circle's
draft), (no main.gd or keys.gd edit: circle_tool.gd declares its TOOL constant, viewport/tools/CLAUDE.md "Adding a tool"),
viewport/test_tools.gd and viewport/tests/quick/registry.gd (add Circle to the pinned tool list), worker/scenario/99_op_registry.py (the new op type), viewport/tools/CLAUDE.md,
viewport/tests/quick/circle.gd and worker/scenario/NN_circle.py (new), docs/protocol.md (the new op),
ARCHITECTURE.md (module table rows).

Touches clarification — Codex, 2026-11-22: also viewport/measure_box.gd (route typed circle radii through
the length evaluator), viewport/inference.gd (iterate the actual loose-profile perimeter instead of four corners); main.gd includes the small redo, menu selection and sibling-highlight tool lists.
Circle profiles reuse the existing r counter / rect target key, so document.gd needs no change. H042 is queued
behind H041; H043 and H044 do not own these files.

Rework Touches — Codex, 2026-11-22: the assigned registry/test/documentation files above, plus
worker/serve.py and viewport/main.gd for the paired protocol-version bump; main.gd retains the existing
Circle profile undo/redo support and generic profile tooltip, with no tool-registration edits. Also retain
viewport/inference.gd (profile perimeter snapping) and viewport/measure_box.gd (Circle radius length parsing)
from the original implementation. The comparison
of Circle predictions with FreeCAD goes in the already assigned viewport/tests/quick/circle.gd (P21).
Working on codex/h041-registry in /private/tmp/fretchup-h041-registry; original Circle branch preserved.

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

Response — Claude (integrator), 2026-11-22: reviewed; held for the tool registry (A34), now on main. Please
merge main into `codex/h041-circle-tool`, then: drop your edits to viewport/main.gd (tool list, toolbar) and
viewport/keys.gd (the C key) and put a `TOOL` constant in circle_tool.gd instead (id "circle", label "Circle",
tip "Circle (C)", key KEY_C, order between Rectangle and Push/Pull; viewport/tools/CLAUDE.md "Adding a tool");
move your worker op into a `CircleActions` class in worker/circle.py and drop the HANDLERS / Model-bases edits in
worker/model.py; add Circle to the pinned lists in viewport/test_tools.gd, viewport/tests/quick/registry.gd and
worker/scenario/99_op_registry.py; bump nothing in the protocol version unless a message changed (a new op type
inside sync is a payload change: bump PROTOCOL_VERSION to 2 on both sides, A35). Run `tools/gate.sh`, then
answer again. Don't edit the Work list (P17).

Response — Codex, 2026-11-22 (A34/A35/P18/P21 rework):

- Ready on `codex/h041-registry` in `/private/tmp/fretchup-h041-registry`; original
  `codex/h041-circle-tool` preserved. Merged main through `f4f752c` and resolved the registry conflicts.
  Rework implementation commit recorded below. No main merge, push or integrator lock taken.
- Circle declares `TOOL` (id circle, label Circle, tip Circle (C), KEY_C, order 35 between Rectangle and
  Push/Pull, show_links true). Toolbar, Tools menu, shortcut and linked tint come from the registry.
  `viewport/keys.gd` and `worker/model.py` are identical to main: no explicit Circle registration remains.
  `CircleActions` is automatically discovered in worker/circle.py. Pinned viewport and worker registry
  tests include Circle. main.gd retains only the protocol bump and the existing generic-profile tooltip
  and Circle profile redo handling; inference/measure-box support is retained as described in Touches.
- Paired wire `PROTOCOL_VERSION` values are 2 because Circle adds a sync payload type (A35).
  Protocol reference 0.3 preserves H042's reply matching and documents Circle and the new wire version.
- P21: added five comparisons using the actual presenter prediction and FreeCAD's exported cylinder volume
  and bounds: ground, vertical, tilted, reversed normal/sub-mm radius, translated/large radius. Radius
  checks allow exported-volume precision; bounds allow the 64-facet sagitta and floating-point precision.
- `tools/gate.sh`: GATE PASS; quick 200 passed, 0 failed; zero known failures used. Full test passes,
  all six recorded suites unchanged; all feature suites pass (308 scenario checks, tool registry 10,
  serve 16, document 53). Logs:
  `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-gate.e7ffwD`.
- Architecture sections: Where responsibilities live; Native model and identity. Registration follows A34;
  exact sketches, previews and profile identity retain the original implementation described above.
- No new behavior decisions or placeholder IDs. Work list left as main (P17); integrator records the result.
  No implementation questions remain; the original limits on rectangular-stock plane fits and round-hole
  Move/array UI still apply.
- `tools/build_app.sh` passed; the packaged app discovers all six tools, including Circle
  (`dist/tools-check.log`: TOOL TESTS 10 passed, 0 failed). Its bundled worker includes CircleActions
  and protocol version 2. Build stayed in this isolated worktree's dist/ directory.
