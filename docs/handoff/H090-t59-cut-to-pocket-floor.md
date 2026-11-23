### H090 — T59 step 1: a cut made to a pocket's floor stays tied to it (the worker side)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: either

References: T59, I26b (the rules: a cut made up to a face stays tied to it; it detaches when you push that face
again or type its length; if the face goes, the length is kept), I40 (a typed distance stays a measurement),
I24 (`through_all`: the same idea for a cut to the back face, done with FreeCAD expressions), A03 (faces by
geometry), G04.

Touches: worker/push.py, a new worker/scenario/99_cut_ties.py, a new worker/test_cut_ties.py. Not the viewport
(step 2 is the Push/Pull tool sending the new field; it waits for H083), not plane_fit.py, not serve.py's
`PROTOCOL_VERSION` (step 2 bumps it, when a window first sends the field), not ARCHITECTURE.md or
docs/protocol.md: write the new op field and the new cutter property as `Architecture:` lines.

Today: Push/Pull's "face behind" snap (push_tool.gd `_snap_to_face_behind`) sets the distance exactly to a
pocket's floor, but the op carries only the number, so the worker makes an ordinary cutter of that length. Make
the first pocket deeper (its extrusion's `LengthFwd` in the Properties panel, or in FreeCAD) and the second
pocket stays at the old depth. The back face already follows (`"through": true`, `through_all`).

Request:
1. A new optional field on a `push_pull` op: `"to_face": {"normal": [x, y, z], "point": [x, y, z]}`, world mm,
   the floor's outward normal (it faces the same way as the face the cut starts on) and a point on that floor
   inside the new cut's outline. Valid only on a cut into a board (`distance < 0`, the cut lands in a board:
   the "draw-on-face edit" branch of `op_push_pull`) and not with `"through"`; anywhere else: OpError("to_face
   is only for a cut into a board").
2. In that branch, after `self.extrusion(...)` and before `self.boolean(...)`: find the cutter whose floor it is.
   In the board's frame (`fr.pt`, `fr.dir`), look through the cutters of every Part::Cut in the container's
   Group (`self.tools_of(b)`; for a Draft array, its `Base`). The one wanted is a Part::Extrusion, not
   `SSThrough`, whose `Dir` equals the new cut's direction (both axis-aligned, within 1e-6), with no
   `LengthRev` expression, and whose far end (its base plane's level along that axis, moved `LengthFwd` along
   `Dir`) is at the point's level within `TOL`, with the point on its shape (`t.Shape.isInside(p, TOL, True)`;
   for an array, the array's shape). More than one: the first in the Group's order. None (the face behind is
   the board's own shape, a step, not a pocket): no tie, the cut is the plain distance it is today.
3. Tied: give the new extrusion its `LengthFwd` as an expression, built the way `through_all` builds its
   expressions (base planes' `Shape.BoundBox` levels in the container's frame, `* 1mm`), so that it is always
   (the new cut's base level − the floor cutter's base level, signed along the cut) + the floor cutter's
   `LengthFwd`. Mark it on creation: `add_props(ext, SSOp=oid, SSTiedTo=<the floor cutter's SSOp>)` (always
   add the property, `""` when untied, so a later detach only changes a value: worker/CLAUDE.md, "FreeCAD
   rules"). Its distance comes from the expression; the op's `distance` is the viewport's prediction and is
   not checked against it.
4. Detach (I26b: pushing that same face again): in `op_push_pull`, when the target is a board's `face` (no
   `region`), before anything else: if the face is the floor of a tied cutter on that board (its point at the
   cutter's far end, on its shape, the face's normal opposite the cutter's `Dir`), clear that cutter's
   expression keeping its current value (read `LengthFwd`, `setExpression("LengthFwd", None)`, set it back) and
   set its `SSTiedTo` to `""`; then the push goes on as today. The same op's undo brings the tie back.
5. A floor cutter made deeper or shallower: the tied cut follows on the next recompute,
   with nothing of Shop Sketch's in between (it's FreeCAD's expression, as for I24). A tie to a tie (a third
   pocket to the second's floor) works the same way and needs nothing more.

Cases that must still work: every existing worker test and scenario step (20_push.py's through-cuts, 90_mirrored_hole.py,
99_circle.py, 99_regions.py), the plane-fit pushes (97_plane_fit_refit.py), and an op without `to_face`
behaving exactly as today.

Checks (scenario/99_cut_ties.py, on the fixture's `bottom` board, 564 × 400 × 18 at x 18–582, y 0–400, z 0–18,
with its through-hole at x 280–320, y 180–220; and worker/test_cut_ties.py for what doesn't fit a scenario step):
- pocket A: a 100 × 60 rect on bottom's top at [60, 60, 18], cut −6; pocket B: a 100 × 40 rect at [120, 80, 18]
  (it overlaps A for x 120–160), cut −6 with `to_face` {normal [0, 0, 1], point [140, 100, 12]}: B's extrusion
  has a `LengthFwd` expression and `SSTiedTo` = A's op id; the volume is as for two plain 6 mm pockets;
- then A's extrusion made 10 deep with a `property_edit` (`LengthFwd`, `"10mm"`, as 20_push.py's step 2b does):
  B is 10 deep too (the volume, and B's `LengthFwd` 10);
- pushing B's floor (face {normal [0, 0, 1], point [200, 100, 12]}) by −2: B is untied (no expression,
  `SSTiedTo` empty, `LengthFwd` 6) and the floor 2 mm deeper (A's and B's floors are one refined face, so A's
  part goes down too); its undo brings the tie back, and A made 10 deep then takes B with it again;
- a third pocket C to B's floor: A made 10 deep takes B and C;
- `to_face` on a point that lies on no pocket's floor (the board's back face is for `through`; use a point in
  the open, [400, 300, 12]): the cut is a plain 6 mm, untied, and no error;
- `to_face` with a positive distance, and with `through`: OpError with the exact message;
- the model saved and reopened: the ties are still there (the expression and `SSTiedTo`), and A made 10 deep
  still takes B.

Reading path: push.py `op_push_pull` (the order of its early returns, then the "draw-on-face edit" branch at
the end) → `through_all` (how an expression refers to base planes in the container's frame) → model.py
`extrusion`, `boolean`, `tools_of`, `is_cut_run`, `edit_frame` → move.py `cutter_of` (how a hole is found by its
cutter's `SSOp`, arrays included) → scenario/20_push.py steps 2 and 2b (a FreeCAD value edited and a through-hole
following). Who owns what: the cutter owns its depth (FreeCAD's expression); Shop Sketch only writes the tie at
the cut and clears it at the detach; nothing in the worker recomputes a tie by hand (unlike plane_fit's refit).

Worker rules to know (worker/CLAUDE.md): properties on creation only; when a freecadcmd script raises it runs a
second time (read the first error); `TESTDIR` for outputs.

Next (step 2, queued after H083 and H052, which touch push_tool.gd): the Push/Pull tool sends `to_face` when the
"face behind" snap places the cut, drops it when a length is typed (I40), and bumps `PROTOCOL_VERSION` on both
sides; a quick-test step. Left for T59 after that (follow-ups): a tie to another board's face, and a floor
deleted in FreeCAD (I26b's "the length is kept, with a note").

Run the feature tests while building (`tools/featuretest.sh`), then `python3 tools/job.py test`. End your
response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.

Response — Gemini (worker, gemini-oak), 2026-11-22:

- Branch: `gemini/h090-t59-cut-to-pocket-floor`, implementation commit `5389d8a` (merged `main` at `f250363`).
- Changes: implemented pocket-floor cut ties in `worker/push.py` (`to_face` validation returning `OpError("to_face is only for a cut into a board")` outside cuts into a board or with `through`/`edge_fit`/`resize_stock`/`body`; `_find_floor_cutter` searching every `Part::Cut` in the board container's Group including Draft arrays, skipping `SSThrough` and `LengthRev` expressions; `tie_to_floor` FreeCAD expression using container-frame base `Shape.BoundBox` levels `* 1mm + floor.LengthFwd`; `SSTiedTo` always added on creation; `_detach_floor_cuts` clearing the expression keeping `LengthFwd` and clearing `SSTiedTo` on face pushes without `region`, with undo restoring both), plus `worker/scenario/99_cut_ties.py` and `worker/test_cut_ties.py`.
- Verified: `python3 tools/job.py test` on `f250363` (`CUT TIES TESTS: 25 passed, 0 failed`, `SCENARIO TESTS: 570 passed, 0 failed`, all 33 feature suites passed with 0 failures, `viewport: QUICK 240 passed, 0 failed in 18.0 s`).
- IDs added: none. Open questions: none.

Architecture: `push_pull` op adds optional `"to_face": {"normal": [x, y, z], "point": [x, y, z]}` (world mm, valid only on a cut into a board with `distance < 0` and without `through`/`edge_fit`/`resize_stock`/`body`; otherwise `OpError("to_face is only for a cut into a board")`), tying the new cut extrusion's `LengthFwd` by FreeCAD expression to the matching `Part::Cut` extrusion cutter's floor in the container's frame (`Shape.BoundBox` level difference `* 1mm + floor.LengthFwd`, excluding `SSThrough` and `LengthRev` expressions). Pushing a tied cutter's floor face again (no `region`) clears its `LengthFwd` expression while keeping its current value and clears `SSTiedTo`; undo restores both. `PROTOCOL_VERSION` is unchanged until T59 step 2 sends `to_face`.
Architecture: draw-on-face extrusions in `worker/push.py` always add `SSTiedTo` (`App::PropertyString`) on creation (`<floor cutter SSOp>` when tied, `""` when untied); FreeCAD's expression engine owns updating tied depths on recompute.
Follow-up: T59 step 2 (Push/Pull tool sending `to_face` on face-behind snap, dropping it on typed length per I40, bumping `PROTOCOL_VERSION`, quick-test step) waits for H083 and H052.
Follow-up: T59 later: tying a cut to another board's face, and keeping the length with a note when a floor cutter is deleted in FreeCAD (I26b).
For the integrator: fold the `Architecture:` lines above into `ARCHITECTURE.md` (`worker/push.py` and `SSTiedTo` property) and `docs/protocol.md` (`push_pull`'s optional `to_face` field); `PROTOCOL_VERSION` stays unchanged until T59 step 2.
Result: 5389d8a; CUT TIES 25/25, SCENARIO 570/570, quick test passed (240/240 UI + all 33 feature suites); added to_face pocket-floor cut ties, SSTiedTo property, face-push detach with undo restore, and scenario/unit tests
