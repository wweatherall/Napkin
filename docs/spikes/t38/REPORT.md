# T38 native FreeCAD feasibility report

Codex, 2026-11-21. Decision I34, handoff H005. Experiment, not app implementation.

## Recommendation

The requested front fit and curved far-end/socket are feasible using bundled FreeCAD features for the tested fully covering convex targets. No downloaded workbench or custom geometry kernel is required.

| Mode | Recommended construction |
| --- | --- |
| First contact | Ordinary Part::Extrusion with flat end at the first contact distance. App snapping computes the distance; this spike does not implement snapping. |
| Cut pushed piece, near fit | Long P → Part::Cut(P, S-before-cut) → bundled CompoundFilter, collision-pass against a thin solid at P's start. Keep the single start-connected remnant, not every solid returned by Cut. |
| Far end with target opening | Inside = Part::Common(P, S-before-cut). FarP = Part::MultiFuse(Near, Inside), Refine enabled. Socket = Part::Cut(S-before-cut, FarP). FarP fills the approach plus the portion inside S, terminating on S's far surface. |
| No cuts | Preserve S and retain the chosen bounded extrusion construction (Near or FarP for that surface snap); omit Socket. This mode allows overlap. Free drag remains an ordinary finite extrusion. |

All operation objects above are persistent document features. CompoundFilter is FreeCAD's bundled Part module Python feature, not a new Shop Sketch algorithm. Its collision-pass stencil follows the starting profile in a production implementation. Do not select a fragment by its index: ordering can change.

## Evidence and reproduction

Run from the repository root, using a new output directory:

```sh
TESTDIR=/tmp/t38-rerun /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd docs/spikes/t38/spike.py
```

The script writes results.json and 20 editable FCStd examples. The committed results.json records FreeCAD 1.1.4 results on this Mac. It catches case errors to avoid freecadcmd's second execution after an uncaught exception: inspect `errors` and every `checks` field, not merely the process exit code.

Twenty cases: square flat face, 30-degree flat face, transverse cylinder, sphere; each with plain features, target App::Link, target Part::Mirroring, pushed-piece App::Link, pushed-piece Part::Mirroring. All 20 passed the nine recorded checks. Each starts with two Cut remnants, selects one near solid, forms one bounded far solid, recomputes after five placement/dimension changes, has no invalid document states or socket overlap, and preserves far-piece volume after save/reopen. Initial and modified geometry, face probes and timings are recorded individually. The extrusion is 10 × 10 × 100 mm; curved target radius starts at 20 mm.

Placement traps found while developing the experiment: an App::Link needs its instance placement explicitly assigned; changing its source placement is not a substitute for moving that instance. The angled target must be rotated about its actual centre. Early tests passed shape validity with the extrusion still extending to 100 mm, so the final checks also require two remnants, a bounded endpoint and a changed endpoint after edits.

This is a feature-level test. It does not exercise Shop Sketch's App::Part ownership, edit_frame, sibling-edit policy, Tip/material propagation, or UI. Moving a link instance and changing source dimensions are tested; propagation into every sibling is an integration concern. Mirror normal/Base and source transforms remain different operations. For a mirrored App::Link, preserve the existing Compound wrapper workaround in replay.py; the combined link-plus-mirror case is not covered by this matrix.

## Alternatives compared

- **Cut alone:** two solids in every initial case. Returning the whole compound is wrong. Collision-pass against the start stencil successfully selects the near one in this matrix.
- **Slice by solid / BooleanFragments:** bundled BOPTools persistent features recompute correctly and provide fragments, but do not decide which fragments constitute the intended far endpoint. They still need selection and a union. The simpler Cut/Common/Fuse recipe makes the dependency and intent explicit.
- **Slice by individual face:** direct SplitAPI probes are in results.json. A sphere has one closed curved face; slicing with it yields three pieces (before, inside, after), not a distinct far-face trim. A cylindrical side similarly includes both near and far intersections. Planar end faces are easier but do not generalize to all targets. The face probes are transient shape operations, not a proven persistent face-reference implementation.
- **Half-space:** `Part.makeHalfSpace` is not exposed by this installed Python module (AttributeError in probes). No parametric half-space construction is established by this spike. Even if available through another route, choosing a half-space from a closed sphere surface does not isolate the far boundary as a plane would.

## Dependencies, subsequent edits and cycles

The feature graph is acyclic by construction:

```text
P profile → long P ─┬─ Cut(P, S0) → start filter ─┐
                   └─ Common(P, S0) ────────────┴─ FarP
S0 (target before joint) ───────────────────────── Cut(S0, FarP) → new target Tip
```

P never references the new socket Tip. Source target placement and thickness/radius changes recompute Near, FarP and Socket in the matrix; mirrored sources move in the reflected direction. FreeCAD reports no Invalid states. That check plus the explicit directed graph is the evidence here; this is not a general cycle detector.

**A later feature appended after the socket is not automatically an edit to S0.** If a user pushes the target's new final face, Claude must decide how the existing face-tie rules map that action to the pre-joint source. Redirecting FarP to the final socket Tip would create a cycle. Editing the upstream thickness is proven; arbitrary new downstream pushes are not. Preserve this distinction in the implementation plan.

## Timings

Warm per-feature touch + document recompute, mean of three samples, milliseconds. These include dirty downstream dependents, so columns must not be summed or described as isolated kernel timings. Whole-graph edits are separately recorded with five samples per case.

| Plain target | Cut + dependents | Filter + dependents | Common + dependents | Fuse + socket | Socket | Slice | Fragments |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Flat | 30.9 | 24.2 | 20.2 | 13.4 | 7.3 | 9.7 | 9.1 |
| 30° | 29.9 | 22.9 | 19.9 | 14.6 | 7.4 | 9.6 | 9.1 |
| Cylinder | 40.8 | 31.7 | 31.7 | 21.3 | 9.8 | 10.6 | 10.9 |
| Sphere | 127.2 | 97.6 | 114.5 | 86.0 | 38.8 | 32.0 | 32.1 |

These small examples are feasibility measurements, not an interactive performance guarantee. The existing draft/confirmation loop remains necessary.

## Limits and implementation gates

- This recipe assumes every extrusion ray meets one contiguous target interval, the profile starts outside S, and S fully spans the profile. Partial coverage can leave a bridge around S and keep an untrimmed end; concave or disconnected targets can create multiple intervals. Do not silently accept those cases. Validate endpoint/single-solid/coverage conditions and retain the last valid result; product handling beyond I26b needs William's decision.
- Long P must extend beyond the target but not become an arbitrary permanent 100 mm limit. Production needs an expression-driven conservative extent in the push frame. This test uses a fixed extent sufficient for its target edits.
- The stencil must stay anchored to P's start and be smaller than its valid length. Zero/negative lengths, lost overlap and vanished faces must follow I26b rather than quietly selecting another fragment.
- Surface targeting, topology changes, arbitrary board rotations, combined linked mirrors, actual downstream face pushes, fabrication clearance and large models remain integration tests. No clearance was introduced: the socket exactly excludes P.
- No app files were modified. Existing `tools/quicktest.sh`: native 96/0, arrays 10/0, serve 11/0, viewport 52/0.
