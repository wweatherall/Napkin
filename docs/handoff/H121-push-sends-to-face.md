### H121 — T59 step 2: Push/Pull sends `to_face` when a cut snaps to a pocket's floor

Author: Claude (integrator, fretchup-73) | Date: 2026-11-23 | Status: open | For: either

References: T59, I26b (a cut made up to a face stays tied to it), I40 (a typed distance stays a measurement),
I45 (the face-behind snap), I24 (`through`), H090 (step 1, the worker side: merged), A35 (PROTOCOL_VERSION).

Touches: viewport/tools/push_tool.gd (`_finish_push`, `commit_push`), viewport/main.gd (`PROTOCOL_VERSION`),
worker/serve.py (`PROTOCOL_VERSION`), viewport/tests/quick/push.gd. Not worker/push.py (step 1 built the tie and
its rules; nothing changes there), not presenter.gd (the draft is drawn as today), not ARCHITECTURE.md or
docs/protocol.md: write the protocol change as an `Architecture:` line.

Why: H090 taught the worker to tie a cut to a pocket's floor (`to_face` on a `push_pull` op: the cut's
`LengthFwd` becomes a FreeCAD expression following the floor cutter). Nothing sends it yet, so a pocket cut to
another pocket's floor with the snap is still a plain number: deepen the first pocket and the second stays
behind. The purpose: what the user snapped to is what the model remembers (I26b), and what they typed stays a
number (I40).

Today (checked 2026-11-23): push_tool.gd `_snap_to_face_behind` sets `state.dist` exactly to a depth from
`state.depths` (faces of the same board straight behind the anchor, nearest first) and `state.snap` to "face
behind", or "back face" for the deepest. `_finish_push` (a click or a drag's release) calls
`commit_push(state.dist, state.edge_fit)`; `typed(txt)` calls `commit_push(float(txt))` and leaves
`state.snap` as the last mouse move set it. `commit_push` builds the op; a cut whose distance matches the
deepest depth gets `"through": true`. The worker (push.py `op_push_pull` ~138) answers
OpError("to_face is only for a cut into a board") for `to_face` with `distance >= 0`, `through`, `edge_fit`,
`resize_stock` or `body`, and on a fitted end; a `to_face` whose point lies on no pocket's floor (a step in the
board) gives a plain untied cut, no error.

Request:
1. A pointer commit (`_finish_push`) whose `state.snap` is "face behind" sends
   `"to_face": {"normal": <state.n as [x, y, z]>, "point": <state.anchor + state.n * state.dist as [x, y, z]>}`
   (world mm, the same `Geo.arr3` the face target uses). The point is straight behind where the user grabbed,
   on the face the snap found; the normal faces the same way as the face the cut starts on (H090's rule).
2. Only for a cut the worker can tie, so a snap never makes the worker reject a push the user could make
   before: the target is a rectangle, circle or drawn region on a board (`state.rect != ""` or
   `state.has("region")`, with a board under it), and the op has none of `through`, `body`, `edge_fit`,
   `resize_stock`. Otherwise no `to_face`, and the push is exactly today's.
3. A typed distance never sends it (I40), even when the last mouse move snapped: pass it from `_finish_push`
   into `commit_push` (an argument, as `edge_fit` is) rather than reading `state.snap` inside `commit_push`.
4. Bump `PROTOCOL_VERSION` to 12 on both sides (main.gd and serve.py, A35): a window now sends a field an older
   worker would ignore silently, so the two must not share a worker.

What can fail (each gets a named check in viewport/tests/quick/push.gd, on a 300 × 200 × 18 plank like the
section's first step, with pocket A a 100 × 60 rect at x 40–140, y 40–100 on the top, cut −6 typed):
- Pocket B (a 100 × 40 rect at x 100–200, y 50–90) grabbed over A (at x 120, y 70) and snapped to A's floor:
  its op has `to_face` with normal [0, 0, 1] and point [120, 70, 12], distance −6, no `through`; after the
  wave, A made 10 deep with a `property_edit` (`LengthFwd`, `"10mm"`, as worker/scenario/20_push.py step 2b)
  takes B with it (B's floor follows: check the volume).
- The same push snapped, then a distance typed (`-6`): no `to_face` (I40).
- A push snapped to the back face: `through` and no `to_face`.
- A push out (positive): no `to_face`. B grabbed away from A (at x 170, y 70) and pushed in by the pointer
  without reaching the back face: no snap, no `to_face`.
- Undo of B, then redo: the redone op still carries `to_face` and B is tied again (the op list is the record).
- The quick test's protocol section passes with 12 on both sides, and worker/test_serve.py's check that the
  two versions match.

Reading path: push_tool.gd `click` → `_push_drag` → `_snap_to_face_behind` → `_finish_push` / `typed` →
`commit_push` → worker/push.py `op_push_pull` (the `to_face` guard ~138, then `_find_floor_cutter` ~266) →
worker/test_cut_ties.py (what the worker already proves) → tests/quick/properties.gd (a `property_edit` from
the viewport).

Run the feature tests while building (`tools/featuretest.sh`), the quick test after each change, then `python3
tools/job.py test`. End your response with a Result line; leftovers as Follow-up lines; the protocol change as
an `Architecture:` line; viewport/tools/CLAUDE.md's Push/Pull line (it should mention `to_face`) as a For the
integrator line.
