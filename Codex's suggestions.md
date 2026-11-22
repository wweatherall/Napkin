# Codex's suggestions for Shop Sketch

Date: 2026-11-21

## Purpose and status

This is a design handoff for William and Claude: a proposed SketchUp catch-up backlog, design issues to resolve, and William's new request for branching undo history. It is not an instruction to implement every suggestion immediately.

Reconcile proposals with the existing decision log and Work list before assigning implementation work. Preserve existing decision IDs and follow the supersession process in CLAUDE.md. The identifiers below are local to this document, not replacements for the decision log's IDs.

Reconciled for H009 against main 5c0b602 and the revision 60 read-only export in docs/decision-log.md. The original assessment preceded that export; current active decisions override older proposals below. This remains a source review, not a hands-on usability assessment. Check the live Work list and docs/agent-handoff.md for later implementation changes.

“Original SketchUp” here means the familiar desktop modelling workflow. Current documentation also describes newer procedural tools; those are not required for the baseline. Branching history and automatic relationship maintenance are proposed Shop Sketch capabilities, not claims about classic SketchUp.

## Product direction and William's preferences

- Provide immediate, direct, SketchUp-like modelling while preserving a real, editable FreeCAD model.
- Keep everyday work in Shop Sketch. William would prefer to use FreeCAD directly as little as possible.
- Preserve useful relationships: arrays, mirrors, extrusions up to faces, and cuts through parts.
- I26b decides face ties: pushing the same tied face again or typing its new length detaches it; edits to other faces preserve the tie. Moving either part preserves contact by stretching/shrinking the extrusion. Invalid zero/negative lengths are rejected; a vanished face leaves the current measured length with a note and no silent reattachment. Implementation remains T14.
- Linked component edits affect siblings. Show that scope clearly and offer Make Unique.
- A profile drawn on a part's surface should join that part when extruded by default.
- Materials assigned in Godot should carry through FreeCAD into Blender, including intelligent grain handling.
- The main practical deliverable is a buildable model with plans and possibly a cut list. Revisit the drawing generator later. CNC and 3D-printing opportunities can remain future extensions.
- Q22 settles save feedback: the wave means FreeCAD accepted the action; the quiet Saving/Saved indicator means persistence. The earlier autosave-pulse proposal is dropped (T19 built).
- Entering assemblies is built. Q24 parks exploded presentation views until the drawing workflow is revisited; splitting a board into two is not wanted for now.
- Keep the couch discussion outside this backlog's scope.

## Existing progress to preserve

The reviewed source and current CLAUDE.md describe shared snapping, through-cuts, immediate undo previews, worker restart, incremental geometry updates, file switching, native menus, and save acknowledgements.

T12 linked copies/arrays, Make Unique, detachment and family tint are built. T20 assembly entry is built; whole-assembly linked copying remains. T26/T27 mirror groups and arbitrary-face mirror planes are built. T15 wood cards, paint, grain and GLB export metadata are built. Preserve these implementations rather than rebuilding them from the original inventory.

Existing undo preview caching remembers recent confirmed meshes; this is useful infrastructure, but is not itself a durable branching history system.

## Proposed catch-up backlog

### Priority 1: complete everyday editing

#### S01 — Selection and ordinary editing

**Built (T34 on codex/t34-selection, awaiting integration):** Select (Space) supports click, Shift-click toggling, window/crossing boxes, clear selection and context entry. Delete and multi-board move/copy/mirror are single undoable actions. Select first or activate Move first; deleting an entered original promotes a survivor (I43).

SketchUp provides a reusable selection set: dragging one direction selects contained entities; the other selects crossing entities. Adapt this to Shop Sketch's part and feature ownership model rather than blindly selecting arbitrary mesh triangles.

Acceptance: select three boards, move/copy/delete them together, then undo/redo each meaningful action. Tool changes preserve selection when appropriate.

#### S02 — Component and assembly editing scope

**Largely built (T12, T20 phase 1, T26):** linked-instance highlighting, Make Unique, separate array detachment, grouping and visible assembly/array/mirror editing context. Remaining: linked copies of whole assemblies (T20 phase 2) and any deeper nesting/name-management requirements. Distinguish shape linkage from array placement membership.

SketchUp separates component definitions from instances and provides Make Unique. Its editing context tells the user what geometry they are changing.

Acceptance: before editing one linked leg, affected siblings are identifiable. Making it unique preserves placement, material, editable features, and its array membership. Detaching from an array does not implicitly make its geometry unique.

#### S03 — Redo and consistent cancellation

Complete redo and specify Escape at each tool stage. Cancel a gesture before leaving an editing context. Group history into meaningful user actions rather than raw pointer events or internal worker steps.

Implement this in harmony with H01–H05 below: a fresh edit after undo must retain the abandoned future branch.

Acceptance: undo/redo a copy array, linked edit, and uniqueness change while the worker is both idle and catching up. No stale reply restores the wrong state.

#### S04 — Shared measurements and precise input

Use one parser for metric/imperial suffixes, fractions, signed distances, and consistent post-action correction. Reject malformed input clearly. Separate display rounding from stored precision. Allow precise typed values regardless of zoom level or grid settings.

Acceptance: use 3/4 inch, 19 mm, fractional millimetres, and a negative move without changing tools or project units. Correct the last operation's value before starting another action.

#### S05 — Measurement and construction guides

Add Tape Measure, angle measurement, offset guide lines, guide points, and hide/clear guides. Guides help inference but are not physical geometry or cut-list entries.

Acceptance: locate a hole at specified offsets from two edges without creating temporary solids.

### Priority 2: remove geometric limitations

#### S06 — Complete inference and locking

Extend endpoint/midpoint/edge snapping with acquired reference points, parallel/perpendicular inference, face-plane locking, and part-local axes. Use consistent gestures across tools. Clearly distinguish a temporary alignment from a persistent model relationship.

Acceptance: draw or move parallel to an angled member while referencing another part's endpoint; lock the desired direction and continue picking references without losing it.

#### S07 — Rotate and rotational copies

Pick a pivot, establish an axis or plane, infer or type an angle, and optionally copy. Add radial arrays after ordinary rotation works reliably. Use local as well as world directions.

Acceptance: rotate a rail around its actual joint location, then make evenly spaced rotational copies. Linked geometry and grain orientation behave predictably.

#### S08 — Lines, circles, arcs, and closed profiles

Start with Line, Circle, and useful arc gestures. Generate extrudable faces from closed planar profiles, with editing and trimming. Define how drawing on an existing face creates an editable region without accidentally changing neighbouring parts.

Preserve analytic curves in FreeCAD. Viewport tessellation must not become the authoritative radius or snapping geometry.

Acceptance: draw a rounded profile, extrude it, cut a circular hole, revise its radius, and save/reopen it with the same exact geometry.

#### S09 — Offset

Offset a face boundary or connected planar profile by a typed distance. Specify treatment of tight corners, concave regions, holes, and self-intersections. Provide a meaningful failure instead of surprising topology.

Acceptance: produce a consistent-width frame from one outline and change the width later.

#### S10 — Scale versus deliberate resizing

Offer scale about a chosen anchor, while distinguishing proportional scaling from changing a board's length or an assembly's span. Define instance-only scaling versus definition edits.

Acceptance: lengthen a board without changing stock thickness or hole diameter; separately scale an imported reference uniformly. Do not imply those are the same operation.

#### S11 — Sweep / Follow Me, then fillet and chamfer

Sweep a profile along a path while retaining editable inputs. Classic SketchUp Follow Me supplies the interaction precedent; retaining the path/profile offers a stronger revision workflow. Explicit fillet/chamfer tools can provide a related CAD advantage.

Acceptance: create a moulding or turned profile and change its section afterward without reconstructing the result manually.

### Priority 3: make larger models manageable

#### S12 — Navigation and visibility

Add standard views, orthographic/perspective switching, Zoom Extents, Zoom Selection, hide/show, isolate, and object locking. Preserve an unfinished gesture while the user orbits/pans/zooms.

Acceptance: reach and edit an interior joint without moving the surrounding assembly, then restore the prior view/visibility state.

#### S13 — A small assembly browser

Show named parts and assemblies with selection, visibility, and linkage information. Physical structure should be the default view; feature history can be revealed when needed.

SketchUp's Outliner demonstrates coordinated viewport/tree selection and nested organization. Keep this assembly browser conceptually distinct from the undo-history tree.

Acceptance: find, rename, isolate, and select a nested part through the browser and see the corresponding viewport state.

#### S14 — Inspection and saved views

Add section planes, transparent/X-ray inspection, and saved views. A section plane changes visibility without changing physical geometry. Define selection/snapping through hidden or clipped geometry deliberately.

Acceptance: inspect a joint internally, save the inspection view, and return to it without affecting geometry or material quantities.

#### S15 — Materials from modelling to rendering

**Largely built (T15, M03/M04):** wood cards, Paint/Wood menu, T grain rotation, physical texture scale, face/end-grain viewport textures, ShapeMaterial on the FreeCAD Tip and SSGrain on the definition. GLB exports texture-path/scale and grain/across extras. A Blender consumer still needs to interpret those extras; exported metadata is not proof of a ready-textured Blender scene.

Q30 decides longest-edge grain by default, 90° rotation and shared grain orientation across linked copies, with separate texture patches. Further proposals, not current requirements: finish separate from species/substrate and face-specific finishes. Validate stable texture appearance under transformations and actual Blender consumption rather than treating the entire material pipeline as missing.

Acceptance: rotate, resize, copy, mirror, and make a part unique; grain follows the physical part and remains stable across save/reopen and Blender export. Resizing normally reveals more grain rather than stretching the texture.

#### S16 — Project reuse and exchange

Add Save As/Duplicate, reusable part insertion, and reference-image import with scale calibration. Choose exchange formats based on real workflows. Define how files carry history and material references when copied or shared.

Acceptance: create a variant without overwriting the original, insert a reusable part, and calibrate an image to a known measurement.

## Agreed modelling todo

#### S17 — Surface projection with selectable joint-cut direction

Status: William requested adding this agreed interaction to the todos. Implementation and exact FreeCAD construction are still to be developed and validated. Reconcile this local ID with the main decision log.

Let P be the piece being extruded and S the target piece. The operation extends P toward a surface of S and supports fitting the joint against that surface. It is not limited to cutting a pocket into the same board.

Snap progression:

1. **First contact:** retain an ordinary flat extrusion end, perpendicular to the push direction, at the first contact with S. No cursor flag appears at this snap.
2. **Front-side surface projection:** continuing the drag offers a snap that shapes the joint against the target's near surface across the profile. For a prism approaching a sphere, this can produce a concave scribed end fitting the sphere.
3. **Backside surface projection:** a farther snap can terminate the extruded piece against the target's far surface. Default to cutting space for P in S rather than automatically cutting away P's overlapping volume.

For a planar target surface perpendicular to the extrusion direction, first contact and front-side projection can occupy the same position. Curved or angled targets make their differing results apparent. Define front/back along the extrusion direction, not relative to the camera. Partial coverage, multiple surface intersections, tangencies and ambiguous targets require a preview and explicit supported-case rules.

Three cyclic options:

| Option | Boolean roles / result | Default |
|---|---|---|
| Cut extruded piece | P minus S; retain S intact | Front-side projection |
| Cut target piece | S minus P; retain P intact | Backside projection |
| No cuts | Keep both pieces, including any overlap | Explicit choice |

The selected surface controls extrusion termination; the selected option controls which piece loses material. No cuts disables joint subtraction, not necessarily the selected surface-bounded termination. Retain source geometry/features for editable, reversible results.

Cursor flag and control:

- During projection show “Projecting to surface”.
- Display every currently applicable option together; highlight the active option and show the hotkey that cycles them.
- Provide a cycle button/control as well as the hotkey. Choose a key after auditing existing bindings; none has been agreed yet.
- First-contact snapping remains unlabelled. Explain unavailable cases rather than silently changing the target or Boolean direction.
- Preview the complete result and clearly indicate which piece will lose material.
- Interaction recommendation accepted as part of this handoff: automatic front/back defaults apply until the user explicitly cycles; the chosen mode then stays selected for the remainder of that gesture. Reset this override for the next gesture.

FreeCAD translation and limits:

- Use native/bundled/workbench geometry operations: an extrusion or surface-bounded construction for P, followed by Part Cut (P minus S or S minus P) where selected. A single user action may create several FreeCAD features.
- A straight extrusion ending at the farthest bounding-box distance is not equivalent to termination on a curved far surface. Investigate native up-to-surface or trimming/splitting constructions suitable for the current Part-based board graph; document the selected provider in FREECAD_FEATURE_MAP.md before implementation is called complete.
- The backside mode must construct the intended P before using it as a cutter for S. Avoid circular dependencies: a P end derived from S must reference an appropriate pre-cut version of S, not the result that itself depends on P.
- Verify what the action affects when P or S is linked, mirrored or in an array; obey established editing-scope rules and highlight affected siblings.

Acceptance:

- Prism approaching a sphere: first contact gives a flat end with no flag; front projection defaults to a concave scribed P with S intact.
- Backside projection defaults to a suitably terminated P and a matching opening/socket in S.
- Cycling yields all three intended outcomes, including overlap with no subtraction; no unintended disconnected remnant is mistaken for the requested P.
- Repeat for angled and perpendicular planar targets, including coincident first-contact/projected snap positions.
- An explicit mode choice survives moving between front/back projection snaps during the gesture.
- The cursor flag shows applicable options, current selection and cycling hotkey.
- Undo/redo treats the completed joint construction as one meaningful action. Save/reopen and native FreeCAD recomputation preserve both geometry and dependencies.

## Design issues to resolve early

### D01 — Intentional shortcut difference from SketchUp

Resolved by I12c: Shift toggles Mirror inside Move; arrow keys lock axes/planes (I20). This is William's explicit choice. The earlier proposal to reserve Shift for inference locking is withdrawn. Keep hints and modifier state legible; do not add a separate Mirror tool or change this shortcut without the decision-log supersession process.

### D02 — Tool-first still needs selection and ownership boundaries

Users need to indicate which objects a tool affects. Joining an extrusion to a board is different from grouping boards into an assembly. SketchUp's groups/components prevent unrelated geometry from sticking together; Shop Sketch needs an equally legible boundary.

### D03 — Snapping is not the same as attachment

Show whether an action means fixed distance, up to face, or through part. Store explicit relationship intent, not only the resulting coordinates. Provide inspection, release, and repair interactions.

I26b is decided: same-face push/new length detaches; other-face edits preserve the tie; linked copies follow together and chains propagate. A vanished target freezes the current length as a measurement with a note; never silently reattach. Loss of overlap keeps following with a subtle colour cue. Point snaps do not create ties. T14 must implement these rules; they are no longer open design questions.

### D04 — Shape and placement relationships must stay separate

An edit may change a shared definition, move one instance, move an entire array, change spacing, or reposition a mirror plane. The interface and draft preview must reflect the full affected set. Verify this against the current linked-copies implementation.

### D05 — Separate tolerance, snapping, display precision, and minimum feature size

At review time, Push/Pull ignored distances below 0.5 mm. That obstructs small rebates and clearances. Recheck the current code, then separate geometric validity tolerance from pointer snapping and display rounding. Typed precision should not depend on screen zoom.

### D06 — Angled parts require local coordinates throughout

Rotation alone is insufficient. Rectangle orientation, grids, inference, measurements, mirror planes, grain, and cut-list dimensions should agree on local part axes. Review world-axis assumptions before expanding angled modelling.

### D07 — Curves need exact geometry independent of the display mesh

Keep circles/arcs exact in the model, and use those definitions for dimensions and snapping. Tessellation should control viewport appearance only. Define whether edge selections refer to an entire analytic curve or a displayed segment.

## New user request: persistent branching undo history

### William's requested experience

William wants an undo tree on the right side of the interface, showing roughly 20 levels by default and allowing scrolling to reach older history. Undoing several actions and starting a new path must preserve the old path so it remains accessible. He would also like to merge a newer path into an older one when there are no conflicts.

This is an explicit product request. The interaction and implementation details below are Codex proposals requiring reconciliation with the design log.

### H01 — A scrollable history panel

- Use the right side for a history panel with the active path, current position, and visible branch points.
- Interpret “20 deep” as the default visible/recent window, not a retention limit. Scrolling should expose older reachable history. The exact layout and scroll direction can be tuned.
- Scroll the panel when the pointer is over it without zooming the model. Scrolling alone should not change the model.
- Give actions readable names such as “Cut mortise,” “Move array,” or “Make left leg unique.” Distinguish pending, confirmed, failed, and saved states without presenting every internal event as an undo step.
- Proposal: clicking a state restores it; hovering may highlight affected parts, but should not silently commit a history switch.
- Allow branch names and collapse inactive branches. Keep selection/assembly hierarchy separate from history even if they share a sidebar container.

### H02 — Undo preserves abandoned futures

Example:

```text
Start → Board → Cut mortise → Copy legs → Add rail
                         \→ Change thickness → New rail
```

After returning to “Cut mortise” and editing, both later paths remain available. Undo moves to a parent state. Redo follows the chosen child path; at a fork the chosen continuation must be visible and changeable. Clicking another branch restores that branch's state.

Proposal: preserve the tree across application restarts. A default visible depth of 20 and a mesh cache of 40 must not silently discard history. Any future history pruning needs explicit retention semantics.

Clarify whether changes to camera, selection, visibility, and materials belong in model undo, separate view history, or neither. Geometry and material edits should be recoverable; incidental mouse motion should not be recorded.

### H03 — History architecture and persistence

Agreed scope update (2026-11-21): William approved adding persistent branching history using the existing worker sync mechanism to the branching-history todos. Preserve alternate paths across restarts and materialize the selected path through the worker. Specific storage/checkpoint designs below remain proposals to reconcile with the decision log.

The existing common-prefix sync and FreeCAD transactions are useful execution mechanisms. They do not by themselves retain alternate futures.

Proposed design:

- Store immutable action/state nodes with stable, branch-safe IDs, parent references, semantic action descriptions, and schema/version information.
- Keep an active history cursor and branch heads. A fresh edit from an older state creates a new child without deleting existing children.
- Represent amendments carefully: typing a corrected value may appear as one user action, but must not mutate history already referenced by another branch.
- Materialize the active path into the existing worker interface initially. Use checkpoints to bound replay cost when an old branch is outside FreeCAD's available undo stack.
- Use cached meshes for immediate previews, but restore authoritative geometry, properties, relationships, and IDs before declaring the branch confirmed. A viewport snapshot alone is not a model state.
- Make history IDs unambiguous across branches; restoring per-path counters must not create collisions during later merges.
- Associate worker replies with the requested history state and request generation so a delayed response cannot replace a newer branch selection.
- Persist the history graph, active cursor, checkpoints, and current FCStd revision coherently, with recoverable detection of partial saves.
- Decide where full history lives: extend the adjacent journal, embed appropriate data, or another documented format. Preserve the current decision that the active model is a real editable FCStd file; do not imply that a mesh cache is the authoritative model.
- Define Save As/share behaviour so a copied project does not unknowingly lose the history needed to restore its branches.
- External FreeCAD edits are a separate reconciliation problem. Preserve the existing undo floor and outside-edit protections; do not rebuild from an old branch in a way that silently erases external work.

These are architecture proposals, not a request to replace the worker immediately.

### H03a — Branch-safe identities and meaningful action boundaries

Status: William approved adding these requirements to the undo-history todo list on 2026-11-21. This records agreement on the requirements, not approval of every implementation proposal in H03.

- Give newly created objects identities that cannot collide across retained branches. Restoring or replaying an existing branch preserves its original object identities; creating a different object after undo allocates a new identity. Human-readable names remain separate.
- Distinguish object IDs, user-action IDs, history-state IDs and worker-request IDs. Associate worker results with the document and requested state so an obsolete response cannot replace the currently selected state.
- Record meaningful user actions as undo steps. “Create leg array · 6 copies” is one action even if it creates a definition, instances, an array holder and placement expressions underneath. One Undo reverses the complete action. Preview mouse movements are not separate history entries.
- Preserve immediate numeric correction as a coherent editing experience. Correcting a move distance can appear as revising the same action, but must not mutate an earlier version retained by another branch. Keep immutable versions internally where needed.
- Introduce identity and action-grouping foundations before building the full history sidebar. Route actions through the document controller (A-S01); keep execution operations and native FreeCAD transactions distinct from user-facing history entries.

Acceptance:

- Create a board, undo its creation, then create a different board on a new branch: both have distinct IDs and restore correctly after reopening.
- Undo/redo a six-copy array as one action, including all associated relationships.
- Correct an action's numeric value after a branch retains its earlier version: both versions remain exactly recoverable.
- Receive an old worker response after changing branches/documents: it does not replace the current state.

### H04 — Merge branches conservatively

Agreed scope update (2026-11-21): William approved adding conservative branch merging once reliable history restoration is established. Start with supported independent edits, preview the combined result, flag unresolved dependencies/conflicts, and retain both original branches. This is a todo approval, not an instruction to implement merging immediately.

Start with an explicit command: apply changes from a source branch onto a target branch, with a preview of the combined result. Identify the common ancestor and compare semantic changes on each side.

First useful scope: independent changes to unrelated parts with no shared definitions, attachments, arrays, mirrors, or other dependencies. “Different object IDs” and “both operations replay without errors” are not sufficient evidence of independence.

Detect or conservatively flag:

- Competing changes to the same property or geometric feature.
- Delete-versus-edit and split/replacement of referenced faces.
- Edits to different instances of the same shared definition.
- Array membership/count/spacing conflicts and mirror-source changes.
- A changed support face used by an attachment or through-cut on the other branch.
- Newly created object-ID collisions and missing referenced objects.
- Material or local-axis changes that interact with geometry edits.
- Cases where replay succeeds but changes the intended relationship or introduces unwanted intersections.

For supported non-conflicting cases, construct a candidate in an isolated document, recompute it, verify references and solid validity, and preview the changes. Geometry validity alone does not prove design intent. If independence cannot be established, label the merge unresolved rather than guessing.

Accepting a merge creates a new history state and records both its source and target provenance. Preserve both original branches. Initially, the executable history may remain a primary-parent action sequence with merge provenance; a full multi-parent DAG can follow if needed. Define Undo from a merge as returning to the pre-merge target state; Redo reapplies that merge result.

Later, a conflict UI can offer keep target, take source, or manual repair per supported conflict. Never silently use last-writer-wins for geometric relationships.

### H05 — Delivery stages and acceptance checks

1. Implement the agreed branch-safe identity and action-boundary requirements in H03a alongside linear undo/redo.
2. Preserve alternate futures in memory and expose the right-side tree.
3. Persist branches and restore them after restart, using checkpoints for older states.
4. Add branch naming, comparisons, and navigation polish.
5. Add conservative merging for explicitly supported independent edits.
6. Add more relationship-aware merges and manual conflict resolution only after the simpler cases are reliable.

Acceptance scenarios:

- Make A → B → C; undo to A; create D. Both A → B → C and A → D survive switching branches and restarting.
- Browse more than 20 actions without truncating retained history.
- Return to an old state beyond the viewport cache and FreeCAD undo stack; restore exactly through checkpoint/replay.
- Rapidly select different branches while work is pending; stale replies never replace the selected branch.
- Rejected operations and their dependent drafts do not corrupt either branch.
- Merge edits to independent boards; verify both changes, then undo/redo the merge.
- Flag conflicting edits to a shared component even when different visible instances were selected.
- Flag deletion of a face referenced by the other branch.
- Interrupted saving and external FreeCAD changes produce a recoverable state without silently losing branches or external edits.

## Agreed architecture todo

### A-S01 — Extract a document controller

Status: William approved adding this to the todo list on 2026-11-21. Implementation has not been requested in this discussion. Reconcile this local identifier with the main decision log when scheduling work.

Create a document controller that owns the active model path, desired operation sequence, request sequencing, worker synchronization, confirmed state and saved revision. Tools submit semantic actions; the controller emits pending, confirmed, rejected and save-status events. Coordinate undo through this boundary, with a separate history store when branching is introduced.

Keep gestures and immediate previews in the tools/viewport, transport in the worker client, and geometry validity in FreeCAD. The controller should not depend on camera, shader or mesh-node details.

Deliver incrementally:

1. Move operations, sync, request tracking and response coordination behind the controller while retaining existing rendering behaviour.
2. Move document opening/switching and save-state management.
3. Route future history navigation through the same boundary.

Acceptance: existing quick/full checks appropriate to the change pass; rapid edits followed by undo, delayed responses, worker reconnect and document switching cannot apply a stale state. Geometry confirmation and save acknowledgement remain distinct. Immediate previews remain responsive. Add focused tests of controller sequencing without requiring viewport rendering where practical.

## Additional architecture suggestions

William requested recording these suggestions on 2026-11-21. They are proposals for consideration, not instructions to implement immediately or settled choices of storage format/module interfaces.

### A-S02 — Strengthen autosave recovery and failure reporting

Keep the existing frequent autosave. Improve interruption recovery and failure handling rather than increasing save frequency.

Current basis: FCStd and journal replacements are individually atomic but happen separately. Revision/hash checks detect mismatches; a save interrupted between writes can leave different generations. The current save-failure path logs an error without a dedicated failure notification to the interface. Persistent branching history increases the importance of preserving a matching model/history pair.

Proposed work:

- Associate the model and journal/history with a common save generation.
- Preserve the previous complete generation while preparing and validating the new pair. Only retire recovery data after the new generation is complete according to a documented commit/recovery scheme.
- On opening, identify the newest complete recoverable generation and report recovery when needed. Do not silently discard external FreeCAD edits or overwrite a newer unmatched file; preserve it for reconciliation.
- Emit explicit save-failure information. Show that changes remain unsaved, retain the live work, provide retry, and retry automatically where appropriate.
- Preserve the convenient directly editable FCStd file. Choose the exact staging, backup and commit-record arrangement after considering external edits, portability, disk usage and Save As behaviour.
- Keep geometry confirmation distinct from successful persistence of the matching model/history generation.

Acceptance: simulate interruption at each persistence boundary and a write failure; recover a coherent generation without silently losing retained branches or external edits. An unsuccessful save never produces a false saved indication. A later successful retry clears the failure state.

### A-S03 — Extract geometry presentation and selection/context responsibilities

Extract these incrementally from main.gd as upcoming features need them. Preserve current behaviour rather than combining extraction with a large redesign.

Geometry presenter responsibilities:

- Draft and confirmed mesh nodes, affected-part highlighting, confirmation/rejection animations and visual-state caches.
- Respond to document-controller events and update only affected geometry.
- Provide immediate cached previews for history navigation while authoritative restoration proceeds.
- Keep presentation separate from geometry validity, history authority and save status. A displayed cached mesh is not proof that a branch has been restored or saved.

Selection/context controller responsibilities:

- Selected units and the current assembly/array editing context.
- Resolve whether a picked board represents itself, its array or its assembly, and whether it is editable in the current context.
- Supply consistent target and affected-instance information to Move, future Rotate/Delete, and material tools.
- Coordinate context exit with tool cancellation so Escape has a consistent order; tools retain ownership of their active gestures.

Suggested interaction: selection/context identifies targets → tool defines intent → document controller submits and tracks the action → presenter displays preview and confirmed result. FreeCAD remains responsible for geometric validity.

Acceptance: existing selection, context entry/exit, linked-instance highlighting, immediate previews and confirmation behaviour remain intact. New tools consume shared targeting rules rather than duplicating them. History navigation never treats visual cache restoration as authoritative document restoration.

## Recommended sequencing

Selection and edit scope → precise input and guides → inference and rotation → profiles and offset → navigation and assemblies → materials and sweeps.

Start history architecture planning alongside the early editing work. Do not defer branch-safe IDs and action boundaries until after a linear redo system is deeply entrenched. Ship branch preservation before attempting automatic merge.

For each modelling feature, verify: create → revise → undo/redo → branch/switch where applicable → save/reopen → inspect in FreeCAD. Measure human interaction on real hardware as well as worker timings.

## Official SketchUp references

These are reference behaviours, not a requirement to clone every feature or shortcut. Documentation was consulted on 2026-11-21.

- [Selecting Geometry](https://help.sketchup.com/en/sketchup/selecting-geometry): selection sets and crossing/window selection.
- [Components](https://help.sketchup.com/en/sketchup/components): definitions versus instances and transformation scope.
- [Changing a Single Component Instance](https://help.sketchup.com/en/sketchup/changing-single-component-instance): Make Unique.
- [Managing Units of Measurement](https://help.sketchup.com/en/managing-units-measurement): units, precision, typed measurements, and inspection.
- [Using Guides](https://help.sketchup.com/en/using-guides): construction lines and points.
- [Drawing Basics and Concepts](https://help.sketchup.com/en/sketchup/introducing-drawing-basics-and-concepts): line drawing and inference.
- [Flipping, Mirroring, and Rotating](https://help.sketchup.com/en/sketchup/flipping-mirroring-rotating-and-arrays): pivot, rotation plane, and numeric angles. Modern Flip UI is not a historical-baseline requirement.
- [Drawing Basic Shapes](https://help.sketchup.com/en/sketchup/drawing-basic-shapes): rectangles, circles, and polygons.
- [Offsetting a Line from Existing Geometry](https://help.sketchup.com/en/sketchup/offsetting-line-existing-geometry): profile offset and overlap handling.
- [Scaling Your Model or Parts of Your Model](https://help.sketchup.com/en/sketchup/scaling-your-model-or-parts-your-model): scale anchors and instance/definition scope.
- [Extruding with Follow Me](https://help.sketchup.com/en/sketchup/extruding-follow-me): classic profile/path interaction; current documentation also covers newer procedural behaviour.
- [Viewing a Model](https://help.sketchup.com/en/sketchup/viewing-model): navigation, standard views, and projection.
- [Hierarchies in the Outliner](https://help.sketchup.com/en/sketchup/working-hierarchies-outliner): names, hierarchy, visibility, and coordinated selection.
- [Creating and Using Section Planes](https://help.sketchup.com/en/sketchup/slicing-model-peer-inside): non-destructive inspection.

## FreeCAD implementation mapping

See [FREECAD_FEATURE_MAP.md](FREECAD_FEATURE_MAP.md) for S01–S16 providers, native object types, workbench requirements, evidence and integration limits. William clarified that SketchUp-style actions should translate to reasonable FreeCAD counterparts, including combinations of operations and downloadable workbenches; custom UI/history are allowed. A one-to-one command or stock-FreeCAD-only implementation is not required. The mapping separates geometry capabilities from custom orchestration and unverified rendering/relationship behaviour.
