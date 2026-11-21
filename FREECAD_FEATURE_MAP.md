# FreeCAD feature map for Shop Sketch

Reviewed 2026-11-21 against the changing local working tree and installed FreeCAD 1.1.4. This maps all S01–S16 suggestions, related relationship/solid-editing proposals, and history/architecture work to their implementation providers. Recheck current implementation before scheduling: Claude is actively adding features.

## Governing requirement — clarified by William

**Translate each SketchUp-style action into a reasonable FreeCAD counterpart, including downloadable workbenches.** Custom UI and history are allowed. A counterpart may be one feature, several FreeCAD operations, or an existing add-on's functionality. There is no requirement for a one-to-one command, identical feature tree, or stock-FreeCAD-only implementation.

This clarification supersedes Codex's earlier overly strict interpretation of “all geometry native.” The goal is to reuse FreeCAD's modelling capabilities and ecosystem rather than invent a separate geometry engine. Reasonable differences in representation are acceptable and should be explained.

Implementation guidance:

- Start with the user's intended result and editing behaviour, then choose the appropriate FreeCAD construction.
- Prefer a simple bundled provider when it fits. Consider downloadable workbenches as legitimate providers when they offer a better counterpart; do not reject a feature solely because it needs an add-on.
- An adapter may translate one gesture into several operations. Custom orchestration is expected; the user should not have to perform those internal steps manually.
- Editability, recomputation, portability and dependency requirements are tradeoffs to document, not an unapproved requirement that every result must have an identical native parametric command.
- If a workflow uses an add-on or a scripted feature, name the implementation and required runtime dependencies. Distinguish an existing downloadable provider from new custom modelling behaviour that still needs development.
- Godot drafts remain provisional previews. Final model geometry is produced through the chosen FreeCAD capability; Blender remains a rendering consumer.
- Availability does not prove integration. Verify the chosen counterpart, supported inputs and save/reopen behaviour before promising it.

The separate decision log was inaccessible (sign-in required). Reconcile representation changes with existing decision IDs.

## How to read the mapping: actions become construction recipes

The tables below identify providers, not mandatory one-to-one substitutions. Each implementation ticket should specify: user gesture → intended result → FreeCAD operation sequence → workbench/dependencies → resulting editable objects → limitations.

Examples using already identified providers:

| SketchUp-style action | Reasonable FreeCAD translation |
|---|---|
| Draw a closed outline and Push/Pull it into a new part | Create a sketch or Draft profile, then a Part Extrusion; organize the result as a board. |
| Push an outline into an existing part | Create the profile, extrude a cutter, and subtract it with Part Cut; alternatively use a Pocket when the chosen representation is a PartDesign Body. |
| Pull a profile outward from an existing surface | Extrude the profile and fuse it to the target part. One user action may create multiple native features. |
| Follow Me around a path | Construct section and path objects and use Part Sweep; for a circular lathe-like result, Part Revolution may be the clearer counterpart. |
| Offset an outline and extrude the border | Part Offset2D, appropriate inner/outer profile arrangement, then extrusion of the resulting region. Validate profile orientation and holes. |
| Rotate-copy repeatedly | Set native placements for simple copies or use a Draft polar array for an editable repeated arrangement. |
| Shape an advanced curved surface | Evaluate an appropriate Curves workbench operation and its inputs when bundled Sketcher/Part tools do not express the intent well. This is a legitimate add-on route, not a fallback forbidden by policy. |
| Split one solid into separate pieces | Part Slice and piece extraction/Slice Apart; translate the pieces into separately addressable parts. |

Keep the existing provider evidence below, but interpret native-feature preferences as recommendations rather than absolute acceptance rules. Cases without a reasonable counterpart should be identified openly; do not disguise them by claiming a similarly named command is equivalent.

## Provider and verification legend

**Core:** built into FreeCAD's document/model system or a bundled workbench.
**GUI:** a FreeCAD interface capability; Shop Sketch implements an equivalent Godot interaction, not a headless call to FreeCAD's window.
**Adapter:** custom orchestration/UI around native model features; no new geometry engine.
**Optional add-on:** installed separately and required wherever its scripted features must recompute.
**Needs spike:** provider exists, but integration or promised behaviour is not yet verified.

Verification below is deliberately scoped. Creating a feature object proves availability, not that every possible input works. A simple round-trip sample proves that sample, not general robustness or integration with Shop Sketch links, mirrors and undo.

## What is already available locally

The installed FreeCAD application includes Part, Sketcher, Draft, PartDesign, TechDraw, Material, Measure, Assembly, BIM, CAM, Mesh and other standard modules. No extra workbench is needed for the ordinary modelling backlog.

The current app already has rectangle/extrusion/boolean modelling, movement/copying, mirrors, arrays, components, Make Unique/detachment support and assembly/context work. Worker dispatch at review includes rect, push_pull, mirror, make_component, move, set_material, detach, make_unique and make_assembly. New frontend work may be in progress; “remaining” below often means exposing or completing a capability.

## S01–S06: editing, input and inference

| ID / remaining behaviour | FreeCAD provider | Persistent result / integration | Limits and validation |
|---|---|---|---|
| S01: selection sets, crossing/window selection, multi-object commands | GUI selection/tree plus core object identity and Placement; document removeObject for deletion | Godot selection resolves BodyId and editing context; one semantic action submits the selected native objects' edits | Selection is UI state. Dependency-aware deletion needs a defined policy; removing an object is not proof that its dependents survive. Multi-target moves must not move a shared array twice. |
| S02: components, Make Unique, nested assemblies and edit scope | Core App::Link, native definitions, document copyObject; App::DocumentObjectGroup for existing app assemblies | Finish current component/context implementation. Existing Make Unique deep-copies the definition; array detachment removes placement expressions | Group is organizational and does not supply a shared assembly Placement. Preserve current group strategy; switching to App::Part/Assembly requires scope and link tests. |
| S03: undo, redo, cancellation | Core document transactions, undo(), redo(); UndoMode = 1 in command-line sessions | Wrap semantic actions in transactions/replay. Godot handles Escape and action grouping | Native redo is linear; new edits discard its old continuation. Persistent branches are our permitted history adapter, not a built-in FreeCAD undo tree. |
| S04: units, fractions, precise values, corrections | Core FreeCAD.Units.Quantity and unit-aware native properties/expressions | Parse to canonical mm/degrees; preserve dimension types; amend native properties/actions | Verified Quantity('3/4 in') is 19.05 mm. Tool-specific comma-separated dimensions, copy syntax and post-action correction remain frontend grammar. Remove app interaction thresholds that block valid sub-millimetre input. |
| S05: measuring distances/angles and guides | Measure workbench; Draft dimensions; Sketcher dimensional/reference constraints and construction geometry | Use sketch construction lines/points for persistent reference geometry; Draft dimension objects or TechDraw dimensions for annotations | Choose temporary overlay versus persistent model reference explicitly. Finite construction lines are not identical to infinite SketchUp guides. Measurement display is not a driving constraint. |
| S06: inference, local planes, parallel/perpendicular/center snapping | Draft Snap and working planes; Sketcher constraints for persistent geometric relationships | Godot implements responsive picking from native geometry. Store lasting coincidence/parallel/perpendicular/dimensional intent as Sketcher constraints or supported expressions/attachments | Draft's snapping widget is GUI code, not a drop-in headless Godot snap engine. Temporary snapping does not automatically create a model constraint. Exact curve data must be exported for exact curve inference. |

Sources: [Draft snapping](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Draft_Snap.md), [Undo API](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Std_Undo.md). Local providers: Mod/Draft/draftmake/make_dimension.py, Mod/Draft/draftmake/make_clone.py and the app's Model methods.

## S07–S11: geometry creation and modification

| ID / feature | Preferred FreeCAD provider and action | Editable representation and worker route | Verification / caveat |
|---|---|---|---|
| S07: Rotate | Core Placement and Rotation; Draft Rotate as UI precedent | Transform the native object's placement about chosen pivot/axis; linked definition remains shared | Native math/provider available. Integrate local/world frames, mirrors and arrays; don't rotate the displayed mesh alone. |
| S07: radial copies | Draft.make_polar_array(base, number, angle, center, use_link=True) | Bundled Draft Array Python feature backed by links; edit count/angle/axis/center | Simple array created, saved, reopened and recomputed. Translate Shop Sketch's copy-count convention to Draft's actual element count and test it explicitly. |
| S08: Line, Circle, Arc, polygon and rotated rectangle | Sketcher::SketchObject with Part.LineSegment, Part.Circle and arc geometry; alternatively bundled Draft wire/circle/arc objects | Prefer sketches for editable profiles; add constraints through Sketcher, place sketch in local plane; keep simple existing plane rectangles supported | Sketch object and circle/extrusion verified. Sketch geometry is planar: rotate its Placement to orient it in 3D. Profile closure, multiple loops and holes need integration cases. |
| S08: editing/trimming profiles and regions on faces | Sketcher editing/trim/constraints; Part boolean/face operations where appropriate | Edit source sketch, then recompute downstream native extrusion/cut/fuse | SketchUp-style drawing an edge on an arbitrary finished face does not automatically produce an equivalent editable FreeCAD feature. Decide whether editing a source profile or adding a new cutter/profile; do not silently replace the solid with a mesh. |
| S08: extrude arbitrary closed profiles | Part::Extrusion Base, Dir, LengthFwd/LengthRev, Solid; Part::Cut / MultiFuse to combine | Extend the existing board/Tip pipeline to accept sketches, not only rectangles | Native circle extrusion passed round-trip. Open paths may create surfaces; require closed valid profiles for physical boards. |
| S09: Offset | Part::Offset2D with Source, Value, Join, Fill, Intersection/SelfIntersection properties | Native offset feature linked to source sketch/wire; feed output into extrusion | Simple circle offset passed round-trip. Test concavity, nested loops, collapsing offsets and self-intersections before claiming general support. This is not Scale. |
| S10: proportional/nonuniform scale | Part::Scale with Base, Uniform/UniformScale or XScale/YScale/ZScale; App::Link Scale/ScaleVector for instance cases | Native scale feature, or instance scale where appropriate; coordinate transforms around chosen anchor | Part scale passed round-trip and recomputed when its source box changed. Nonuniform scale can change circles to ellipses and distort holes; that is expected scaling, not smart resizing. |
| S10: lengthening while preserving stock thickness and holes | Edit native sketch dimensions, plane dimensions, extrusion lengths and expressions | Change the feature that owns the intended dimension; let supported dependent features recompute | No universal “resize any solid intelligently” command is assumed. Scope this initially to supported feature graphs; do not infer arbitrary design intent from final shape. |
| S11: Follow Me / sweep | Part::Sweep with Sections, Spine, Solid, Frenet and Transition | Native sweep retaining section/path references, attached to the board's feature graph | Straight-path circle sweep passed round-trip. Curved paths, corners, twist and self-intersections require separate geometry cases. |
| S11: turned forms | Part::Revolution with source, axis and angle | Native revolution; use this rather than approximating a lathe with mesh rotation | Feature availability/properties verified; full round-trip case not run. |
| S11: lofts where useful | Part::Loft with Sections, Solid, Ruled/Closed | Native feature between editable sections | Type availability verified; compatible sections and twist still require testing. |
| S11: fillet/chamfer | Part::Fillet / Part::Chamfer with Base and edge/radius definitions | Native dress-up feature linked to its base | Simple box fillet and chamfer passed round-trip. Edge identification and topology changes remain limitations; failed dress-ups must preserve the valid predecessor. |

Why Part first: the app uses App::Part boards with Part features. These providers fit that structure. PartDesign has many corresponding tools but imposes a Body/profile/history model; avoid mixing in a PartDesign feature just because its toolbar name matches.

Sources: [Part command implementation](https://github.com/FreeCAD/FreeCAD/blob/main/src/Mod/Part/Gui/Command.cpp), [Part Scale](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Part_Scale.md), local FreeCAD 1.1.4 feature introspection and round-trip checks described below.

## Face relationships: native representation decision required

**Through-all:** PartDesign::Pocket natively supports through-all behaviour. The app currently achieves its Part-based equivalent using expression-driven cutter extents and a native Cut. Preserve and test that existing route for its supported shapes.

**Up to face:** PartDesign::Pad and Pocket have UpToFace/UpToShape properties, verified in this installation. They are the native reference features, but their Body/support rules mean they are not a direct replacement for the current Part::Extrusion.

For the current graph, first investigate supported planar relationships expressed through native placements, sketch constraints, expressions and attachment references. An expression referencing a part's explicit dimension is different from finding an arbitrary face geometrically. If the desired target cannot be represented robustly with native dependencies, choose a deliberate PartDesign Body workflow or limit the feature. Do not maintain the final geometry through a Shop Sketch-only recompute callback.

Changing a driven length to fixed length means releasing its native driver/reference and setting a value. The UI gesture is custom; recomputation must remain native. Still clarify whether width/thickness edits also release the relationship. References that disappear should produce a repairable error, not silent reassignment.

[Native Pad options and limitations](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/PartDesign_Pad.md).

## S12–S16: organization, views, materials and exchange

| ID / feature | FreeCAD provider | What Shop Sketch supplies / limits |
|---|---|---|
| S12: standard views, orthographic/perspective, fit selection/model, orbit/pan/zoom | Standard GUI camera commands, including ViewFitAll, ViewFitSelection and camera projection controls | Equivalent Godot camera behaviour; no geometry change or new workbench. GUI commands cannot simply execute in the command-line worker. |
| S12: hide/show/isolate and lock | Native visibility and GUI selectability controls | Godot filters and state persistence; define whether “lock” means unselectable or forbidding edits. Do not equate GUI selectability with an immutable model. |
| S13: assembly browser | FreeCAD tree, App::DocumentObjectGroup, App::Link and object labels | Godot hierarchy view and selection synchronization. Current assembly metadata must round-trip; no new assembly solver is needed for organization. |
| S14: section inspection and transparency | Standard GUI clipping plane and object appearance/transparency; TechDraw section views for drawings | Godot clipping/appearance equivalents. Camera clipping is visualization, not a physical Part Cut. Export actual drawing sections through TechDraw. |
| S14: saved views | Std FreezeViews / working-view commands | FreeCAD frozen views can be saved separately as .cam; they are not automatically stored in FCStd. A full SketchUp-style scene including visibility/material variants needs a custom allowed view-state adapter and an explicit interchange plan. |
| S15: materials | Bundled Material system and native ShapeMaterial/appearance; optional Render WB for render-specific material data | Replace reliance on only SSMaterial text when implementing full material semantics. Species/substrate, finish, grain frame and renderer mapping need a data-model spike. |
| S15: grain and Blender rendering | Optional FreeCAD Render WB provides material/texture mapping and standalone Cycles support | Not proof of a complete .blend workflow. Validate texture transforms, per-piece variation, mirrored grain, end-grain, physical scale and export. Godot/Blender adapters are allowed, but don't claim unverified mapping survives automatically. |
| S16: Save As/duplicate and part reuse | Core saveAs, document copying/merging and App::Link/external links where appropriate | Project/history packaging and stable IDs are app work. Referenced external files need dependency management; generic imported solids may not have editable source features. |
| S16: reference image and calibration | Built-in Std Import image plane, included image file, XSize/YSize and Placement | Native image plane already supports calibration in FreeCAD GUI. Godot needs image rendering and calibration interaction. No obsolete Image workbench download required. |
| S16: exchange | Bundled Import/Part for CAD exchange; Mesh for meshes; TechDraw for drawing output | Prefer FCStd for native features; STEP transfers CAD geometry but not the full feature history; STL/OBJ are mesh exchange. Validate per-format headless availability and units. |

Sources: [standard GUI commands](https://github.com/FreeCAD/FreeCAD/blob/main/src/Gui/Workbench.cpp), [frozen views](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Std_FreezeViews.md), [image import/calibration](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Std_Import.md), [Render](https://github.com/FreeCAD/FreeCAD-render), [Render material mapping](https://github.com/FreeCAD/FreeCAD-render/blob/master/docs/Materials.md).

## Other suggestions and their providers

- **Split a solid:** bundled Part Slice / Slice Apart / Boolean Fragments, implemented in BOPTools. Slice Apart uses a slice plus extracted pieces; piece-count changes require care. These are editable native/bundled feature routes, not arbitrary editing of tessellated faces. [Slice Apart](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Part_SliceApart.md).
- **Explode for presentation:** move links/copies in a separate presentation arrangement using native Placement, preserving construction positions. Animated explode/reassembly is custom presentation or an evaluated add-on; not the same command as splitting a solid or exploding a compound.
- **Enter a part to change constituent features:** expose existing native sketch, extrusion and boolean properties. This is frontend navigation; recomputation remains FreeCAD's. Moving a feature independently may invalidate the result and needs normal validation.
- **Plans:** bundled TechDraw pages, projected/section/detail views and dimensions. The app's existing drawing.py is a custom layout adapter around FreeCAD output. A custom cut-list aggregation is also app logic; grain/stock dimensions must be modeled explicitly rather than inferred solely from bounding boxes.
- **Persistent branches (H01–H03a):** custom history graph/checkpoints and state restoration through native actions. Native transactions execute the selected history path. FreeCAD alone will show the active model; it will not acquire Shop Sketch's branch browser automatically.
- **Branch merging (H04–H05):** custom semantic conflict detection and orchestration, expressly permitted by William's UI/history clarification. A geometric Fuse is not a history merge. Combined geometry must be generated by native FreeCAD actions and validated there.
- **Controller, save recovery, presenter/context extraction (A-S01–A-S03):** application infrastructure around FreeCAD. No new geometry provider or workbench needed.
- **D01–D07 design issues:** shortcuts, ownership, snap-versus-attachment, linkage scope, numerical input, local frames and exact-curve export are integration contracts across the above providers, not missing geometry kernels. In particular, the app's 0.5 mm Push/Pull cutoff is an interaction policy to revisit, not evidence FreeCAD cannot model smaller distances.

## Workbench/download decisions

| Provider | Recommendation |
|---|---|
| Part + Sketcher + Draft | Use bundled versions for the core backlog. No download needed. Draft's Python-defined features are normal FreeCAD dependencies, not Shop Sketch-specific features. |
| PartDesign | Already bundled. Evaluate a deliberate Body-based route for general up-to-face behaviour; do not migrate the existing board graph casually. |
| TechDraw, Material, Measure, Import, Mesh | Already bundled; use for their corresponding tasks. GUI portions need Godot equivalents or a separately tested GUI path. |
| Assembly | Already bundled, but unnecessary for a simple outliner/grouping feature. Only adopt its joint solver if assembly constraints become a requirement. |
| Curves WB | Optional for advanced NURBS/surface work beyond basic arcs, sweeps and lofts. Local v1-1 package metadata shows 0.6.83, but runtime compatibility was not tested. Do not make it a baseline dependency. [Upstream](https://github.com/tomate44/CurvesWB). |
| Render WB | Optional candidate for FreeCAD-managed render materials and standalone Cycles. Installation via Addon Manager is documented; not installed as part of this task. Validate dependencies and the intended Blender workflow before selecting it. |
| A new Shop Sketch workbench | Not necessary to create the listed geometry. Could later expose history/metadata controls inside FreeCAD, but would be a new custom UI dependency, not an already available geometry provider. |
| Other furniture/exploded-view add-ons | Not required for S01–S16. Evaluate only for a specific unmet workflow; no blanket dependency recommendation. |

## Implementation gate for each geometry feature

Before marking a feature ready:

1. Identify the native object type or bundled/add-on provider and the editable properties.
2. Create a minimal valid sample in an isolated document through the intended command-line API.
3. Save FCStd; reopen and recompute in a fresh FreeCAD process without importing Shop Sketch code. Add-on features must have their documented dependency installed.
4. Change the relevant native property in FreeCAD and verify that dependents update correctly.
5. Exercise links, mirrors, rotated placements and assemblies that the feature claims to support.
6. Verify semantic undo/redo, rejection and branch restoration through the app adapter.
7. Verify exact geometry and references independently of Godot tessellation; verify material/view exports separately.

A valid first mesh alone is not completion. A less-parametric representation can be a reasonable counterpart if its editing limitations are explicit; do not present it as preserving relationships it cannot recompute.

## Verification performed for this map

Separate FreeCAD processes were used; no existing model or running worker was touched. Installed version reported 1.1.4.

- Instantiated and inspected native types: Sketcher::SketchObject, Part::Extrusion, Revolution, Sweep, Loft, Offset2D, Fillet, Chamfer, Scale, Mirroring, PartDesign::Pad/Pocket, App::Link and App::DocumentObjectGroup.
- Built simple extrusion, 2D offset, scale, fillet, chamfer, sweep and Draft polar-array samples. All produced valid non-null shapes, saved and reopened/recomputed successfully in the probe process. The 2D offset correctly has zero volume.
- Changed the box feeding the Scale feature after reopen: its volume updated from 640000 to 768000 cubic mm. This tests that dependency, not every feature's edit behaviour.
- A separate undo sample had one redo entry after undo; creating a new alternative edit reduced redo count to zero. This confirms ordinary redo does not preserve the abandoned branch.
- Fractional-inch input parsed through FreeCAD.Units.Quantity.
- Full app integration, clean-process round-trip of every provider, GUI commands, general face attachment, advanced curves and material/grain export remain unverified. The first sweep test used an incorrectly oriented sketch; correcting the sketch Placement produced the passing native sweep sample.

Probe files/results were created under /tmp/fretchup-native-mapping. The result JSON is copied alongside this document under docs/freecad-capability-check.json for review. These focused checks are capability evidence, not substitutes for the repository's quick/full suites when implementation changes.
