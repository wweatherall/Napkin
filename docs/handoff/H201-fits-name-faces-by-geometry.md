### H201 — A fit names its target face by geometry, follows flips and rotations, and detaches when the face is gone (T161, T163, I75-I77)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: open | For: codex | Item: T161

References: I75 (a fit names its face by {normal, point}), I76 (it stays live when the target is flipped, mirrored or
rotated; the 90-degree pause for rectangular targets; a rotation ending in the pause leaves it paused), I77 (when the
face is cut away or deleted it detaches, keeping its length, without "Reference unavailable"), T163 (the flip bug),
docs/proposals/T161-fit-faces.md, A43, T165 (William's user test, later), P73.

Touches: worker/plane_fit.py (`_def`, `planar_faces`, `_resolve_face`, `apply`), viewport/tools/push_tool.gd
(`_edge_inference`'s option: send `option.plane_normal` / `option.plane_point`), worker/model.py (`op_fit` only),
worker/serve.py and viewport/main.gd (PROTOCOL_VERSION), docs/protocol.md (fit and new_board.fit), tests/op_contracts.json,
worker/update_old_files.py (new in H199) and worker/test_update_old_files.py (new in H199) (integer `face` -> {normal, point}),
worker/test_properties.py, worker/test_plane_fit.py (new), 03_Past_Decisions/decision-log.md (the FIT_PAUSE_DEG Tunables row,
added with the log tool's `add tunable`).

Reading path:
1. docs/proposals/T161-fit-faces.md section 2 (the three uncovered cases) and worker/plane_fit.py `_def` (only
   `App::Part` / `App::Link`), `_resolve_face` (re-finds the face by SSTargetNormal + SSTargetPoint, nearest parallel
   face, no distance limit).
2. worker/mirror.py `op_mirror`: `replace=True` swaps the board for a `Part::Mirroring` under the same BodyId.

Request (in this order; each step's test first, P10):
1. T163: a test that fits a shelf to a panel, flips the panel (`mirror`, `replace=True`), recomputes, and shows today's
   detach. Then make `_def`/`planar_faces` accept `Part::Mirroring` so the fit follows (I76).
2. The fit op's `face` becomes `{normal, point}` (world mm, like every FaceRef); push_tool.gd sends it; the worker
   resolves it against the target's planar faces. The updater converts any integer `face` (none on disk today).
3. I76 for a rectangular target: the fit uses whichever of the two opposite faces faces the fitted board. As the
   target rotates, it holds its face up to 90 degrees; within FIT_PAUSE_DEG (a tunable, start at 2 degrees) of 90 it
   pauses (the board keeps its length, the fit isn't removed); past that it resumes on the opposite face. Rotating both
   boards together changes nothing. A rotation that ends in the pause leaves it paused; rotating on resumes it; it
   saves and reopens paused. Tests at 45, 89, 90, 91 and 180 degrees, and both boards rotated together.
4. I77: when no face of the target matches any more (cut away, or the target deleted), the fit detaches instead of
   jumping to another parallel face; the board keeps its length; the message is not "Reference unavailable": until
   H202's look is chosen, it shows no message at all, and the fit's state is `detached` in bodies.json so H202 can draw it.
   Undo of the cut brings the fit back. Tests for the cut, the delete and the Undo.

Not in this job: the detachment's look (H202), other shapes than rectangular targets for the rotation rule.

What can fail:
- A paused or detached fit lost on save/reopen (G09). Check: a test saves a paused fit and a detached one and reopens both.
- An existing fit test whose target is cut later now detaches where it used to jump. Check: name each such test in
  `Changed from the brief:` with why it's I77.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope); the full field audit passes.
