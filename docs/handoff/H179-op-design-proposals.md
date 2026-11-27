### H179 — Two proposals for William: push_pull's jobs as separate ops (T159), and how a fit names its face (T161)

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: open | For: gemini

Item: T159
Completes: T161

References: T159, T161 (William, 2026-11-27: "add clarify and separate jobs of push pull to todos", "add think
through this for our to dos"), G08 (refer to geometry, never to FreeCAD's internal numbers), G02, G04, H171 (how
fit/unfit became their own ops and old files were upgraded: the model for any split), A42 (breaking saved-format
changes are acceptable now, with old files upgraded).

Touches: docs/proposals/T159-push-pull.md (new), docs/proposals/T161-fit-faces.md (new).

Reading path:
1. docs/protocol.md `## Operation payloads`: the `push_pull` row and its notes, `fit`/`unfit`, `Plane-fit faces`.
2. worker/push.py `PushActions.op_push_pull` and the functions it branches to (`edge_fit`, `resize_stock`, `to_face`,
   `through`, `region`, `target.face` vs `target.rect`); worker/plane_fit.py `apply`, `snapshot`, `fitted_end`,
   `planar_faces`, and how a face index is re-found by geometry after a change.
3. viewport/tools/push_tool.gd: which gesture sends which push_pull fields.

Today: one `push_pull` op extrudes a profile or face, cuts, cuts through, cuts to an earlier pocket's floor,
resizes stock, fits to an edge, and fills drawn regions. A fit names its target face 0-5 (Left..Top) on plain stock,
but by index into `planar_faces` on other boards; the worker re-finds it by geometry after each change.

Request: write two short proposals (each under ~2 pages), for William to decide from. No code.
1. **T159 push_pull.** List each job push_pull does today: the fields that select it, which gesture sends it, the
   code path. Then propose a split (or say why not): which jobs become their own op types, with names and fields,
   what stays, and how old files upgrade (as H171 did). For each, say what William would notice (nothing, ideally)
   and what gets simpler (code, docs, tests). Give a recommendation and the order of jobs it would take.
2. **T161 fit faces.** Explain in plain words how a fit names its face today and when that can go wrong (a cut adds
   a face, faces reorder, a board is mirrored); check whether the re-find by geometry covers each case, citing
   the tests that prove it or saying none does. Propose either keeping it (and why it meets G08) or naming the face
   by normal and point (what changes, how old files upgrade). Give a recommendation.
   Each proposal ends with the questions William needs to answer, numbered.

Not in this job: any code change.

Checks: none beyond the files existing; the integrator reads both before they go to William.
