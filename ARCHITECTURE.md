# Shop Sketch architecture

Reviewed: 2026-11-21 against main 5c0b602 for H009. This maps the inspected source, not a released build. The code and revision 60 decision-log export were checked; baseline quicktest results are recorded below.

## Reading and decision order

Read CLAUDE.md for project conventions and the decision-log link. This file maps implementation responsibilities and constraints; it does not supersede accepted decisions. Read [Codex's suggestions.md](<Codex's suggestions.md>) for the proposed feature backlog and branching-history design. The live log requires access through Claude; [docs/decision-log.md](docs/decision-log.md) is its read-only local export. Read [docs/agent-handoff.md](docs/agent-handoff.md) for current assignments; do not change the exported log independently.

When behaviour changes, update the decision log as required there, then keep this map and affected tests current. Proposed boundaries below are explicitly labelled; do not mistake them for existing modules.

## System overview

Shop Sketch is a local desktop application with one Godot process per window, a shared FreeCAD worker for compatible windows, and file-based geometry transfer (W13). Godot handles the immediate modelling experience. A long-running Python worker inside FreeCAD performs authoritative geometry operations. Native FCStd documents remain editable outside Shop Sketch. Blender is an intended rendering consumer, not the modelling engine.

```mermaid
flowchart LR
    U[User] --> T[Godot tools and inference]
    T --> M[main.gd: operations, drafts, UI]
    M --> C[worker_client.gd]
    C -->|newline JSON over localhost TCP| W[replay.py: serve and Session]
    W --> G[Model and FreeCAD features]
    G --> F[FCStd and adjacent journal]
    G --> E[bodies.json and per-board meshes]
    E --> M
    W -->|confirmation and saved messages| C
    G --> V[TechDraw views]
    V --> D[drawing.py: shop documents]
    G --> B[GLB rendering export]
```

TCP carries commands/status and output paths. Geometry is read from shared local files. This is not currently a remote-worker protocol: the client and worker assume access to the same filesystem.

## Where responsibilities live

| Location | Current responsibility | Useful entry points |
|---|---|---|
| `viewport/project.godot`, `main.tscn` | Godot configuration and startup scene | Main scene |
| `viewport/main.gd` | Composition root; UI, model state, selection/context, operation submission, drafts, confirmation waves, caches, worker lifecycle, project switching, camera | `_ready`, `_make_tools`, `sync`, `_on_worker`, `_apply_confirmed`, `switch_model` |
| `viewport/tools/tool.gd` | Common tool interface and references to viewport/inference | `setup`, `reset`, `click`, `double_click`, `release`, `mouse_moved`, `key`, `typed` |
| `viewport/tools/select_tool.gd` | Selection and entering editing contexts | Tool event methods |
| `viewport/tools/paint_tool.gd` | Paint selected wood onto the picked board/family | Tool event methods |
| `viewport/tools/rect_tool.gd` | Rectangle interaction, preview and operation creation | `commit_rect` |
| `viewport/tools/push_tool.gd` | Push/Pull picking, depth inference, preview, through-cut intent | `commit_push` |
| `viewport/tools/move_tool.gd` | Move/copy/mirror gestures, arrays and operation amendments | `commit_move`, `commit_mirror_move` |
| `viewport/inference.gd` | Shared picking and snapping, visibility checks, axis/plane destinations | `pick`, `snap`, `point`, `axis`, `axis_dest`, `plane_dest` |
| `viewport/worker_client.gd` | TCP framing, buffering, reconnect, pending sends and link signals | `send`, `_process`, `_drain` |
| `worker/replay.py: Model` | Native features, object relationships, geometry operations and validation | `apply`, `op_*`, `resolve_face`, `edit_frame` |
| `worker/replay.py: Session` | Live document, applied operation sequence, undo/rebuild, external-edit detection, export and persistence | `sync`, `_apply`, `_open_existing`, `export`, `save` |
| `worker/replay.py: serve` | select-based multi-client loop; sessions and single-window ownership by absolute file path; delayed saves and focus notifications | `handle`, `claim`, `let_go`, `release`, `save_pending`, `session_for` |
| `worker/materials.py` | Twelve-species wood library, FreeCAD card installation, texture metadata | `install`, `write_library`, `SPECIES` |
| `worker/drawing.py` | Compose shop drawings and cut list from exported data | Script entry point |
| `viewport/*.gdshader`, `line.gdshaderinc` | Draft/confirmation appearance, depth-biased overlays and anti-aliased lines | Shader parameters |
| `viewport/tests.gd`, `worker/test_*.py` | Scripted UI and geometry/persistence tests | Suite entry points |
| `tools/quicktest.sh`, `fulltest.sh`, `compare_suites.py` | Test orchestration and geometry comparisons | Shell entry points |
| `tools/build_app.sh`, `export_presets.cfg` | macOS application packaging | App build |

Tools currently depend directly on `main.gd`; the interface is a convention, not a strongly isolated service boundary. Main runtime-loads tools/tests while those scripts preload Main for typing, avoiding preload cycles.

## State ownership and authority

| State | Owner | Meaning |
|---|---|---|
| Pointer gesture, typed input, hover, preview | Godot tool / main | Provisional user interaction |
| Desired operation sequence | Godot `ops` | What the client wants the worker to materialize |
| Accepted geometry and model relationships | Live FreeCAD document | Authoritative computed model |
| Saved model | `.FCStd` | Durable native model, including Shop Sketch properties |
| Replay/provenance information | Adjacent `.shopsketch.json` | Operations, statuses, revision and FCStd hash |
| Meshes, bounds, metadata, GLB, drawing outputs | Derived export files | Rebuildable presentation/export products |
| Recently confirmed visible states | Godot `_states` / `_boards` | Fast visual restoration; not durable model history |
| Last project preference | Godot `user://settings.cfg` | Application preference |

An operation being confirmed does not mean it has been saved. A visible draft is not an accepted solid. A mesh snapshot cannot restore the full feature graph.

## Lifecycle of an edit

1. A tool receives input through Main and uses the shared inference engine.
2. It renders a draft immediately and commits a semantic operation into `ops`.
3. `sync()` advances `seq`, marks the desired state dirty, and sends when no request is in flight. Further edits coalesce into a subsequent full-log request.
4. `Session.sync()` compares canonical operation values to the applied sequence, preserving their common prefix.
5. The worker undoes the old tail and applies the new tail. If available FreeCAD undo cannot reach the required state, it rebuilds from operations when permitted by the external-edit floor.
6. Each applied operation runs in a FreeCAD transaction. Failure aborts that operation and records a failure status.
7. Export writes current metadata and changed board meshes. The worker responds with per-operation status and output directory.
8. Main applies a current response, replaces drafts with confirmed board nodes, and runs acceptance/rejection feedback. Rejection handling also considers dependent operations; review `_on_rejected` when adding new operation kinds.
9. After approximately 0.25 seconds of socket inactivity, the worker saves pending documents and sends a separate `saved` notification. Flush/quit paths also drain pending saves.

The current client gates sync results using sequence and dirty state. New asynchronous work must preserve this discipline. Future branching history should additionally identify the exact requested history state and model generation.

## Protocol at a glance

Transport: UTF-8 JSON objects separated by newlines over localhost TCP. Main probes port 7878 with hello and compares replay.py's MD5 identity. A matching worker is shared; a different version or occupied port gets a private worker. The identity currently hashes replay.py only, not every supporting module. Test mode uses a separate port; `--port=N` selects an external worker.

| Command/event | Purpose |
|---|---|
| `hello` | Return app identity, worker script hash and process ID for compatibility probing |
| `open` with `model`, optional `fresh` | Open/adopt a session; returns operations, revision, external-edit flag and undo floor |
| `sync` with `model`, `oplog`, `outdir`, `seq`, optional `drawing` | Materialize desired operation sequence and export metadata/meshes |
| `replay` | Fresh-session replay path |
| `flush` | Save pending work now |
| `bye` | Save and release this connection's model, then disconnect this window |
| `quit` | Save and stop only if no other client remains; otherwise release the requesting client (`stopped: false`) |
| `focus` / `already_open` | Notify the owner to come forward; refuse the second opener. A newly launched duplicate window closes, while File > Open reports the refusal |
| `saved` event with `model`, `rev` | Successful persistence acknowledgement |

The loop multiplexes sockets with `select` but executes geometry serially; it is not parallel FreeCAD evaluation. Autosave waits for all windows to be quiet for 0.25 s. `SERVE_IDLE_EXIT` controls exit after the last connection leaves (app startup supplies 10 s; direct worker default 0 disables it). File > New Window (⌘⇧N) opens a distinct Untitled model. Ownership is local to this worker and absolute path; it is not an OS-wide lock against external FreeCAD or another worker version.

`oplog/0.1` uses millimetres; `run_sync` rejects other units. Errors can occur at request level or per operation. The journal format is currently `shopsketch-journal/0.1`. Check `Model.HANDLERS` and each `op_*` implementation for the authoritative operation schema; there is not a separate comprehensive typed protocol definition.

## Native model and identity

- A board is an `App::Part` containing native features and a `Tip` pointing at its current result.
- Typical base: `Part::Plane` → `Part::Extrusion`. Consecutive cuts share a `Part::Cut` with compound cutters; consecutive additions use `Part::MultiFuse`. Older per-operation boolean chains remain supported.
- Cutter identity follows `SSOp`, not the boolean containing it. Use `cutter_of` / `tools_of`.
- Through-cuts carry `SSThrough` and expression-driven extrusion lengths (`through_all`). Do not equate this with complete arbitrary face-attachment support.
- Component instances are `App::Link` objects referring to shared definitions. Copying a plain board converts it to a component. Make Unique copies its definition while retaining applicable array placement.
- Array holders are `App::Placement` objects with count, origin, step, span and distribution properties. Member placements use expressions. Detaching clears placement linkage independently of shape linkage.
- Mirrors use `Part::Mirroring`. Linked sources need a compound wrapper to preserve placement with supported FreeCAD versions; use `mirror_source()` rather than assuming `.Source` is the board.
- Assemblies use `App::DocumentObjectGroup` with `SSRole=assembly` and `AssemblyId`, not transformed `App::Part` containers. This avoids FreeCAD link/mirror scope problems. Assembly movement explicitly moves members and their arrays.
- Mirror groups are those organizational assemblies with `SSKind=mirror`: outside, movement moves the group; inside, movement reflects between the source and mirrored member and the plane is displayed. Moving the plane itself is not implemented.
- Viewport `unit_of`, `context`, `in_context`, and `edit_blocked` control whether a picked board represents a part, assembly, or array. Context entry affects picking and appearance.
- Identity/metadata include `BodyId`, `RectId`, `SSRole`, `SSOp`, `SSMaterial`, `SSGrain`, `AssemblyId`, `SSArray`, and `SSArrayIndex`. Labels are presentation; do not substitute labels for stable identity.

Face references are geometric `{body, normal, point}` descriptions rather than face indices. `resolve_face` finds a planar face matching normal and point containment and rejects missing/ambiguous matches. This avoids reliance on face numbering but does not guarantee persistence through topology changes.

Model coordinates are Z-up millimetres; Godot coordinates are Y-up metres. Use existing conversion helpers. `Frame` and `edit_frame()` translate edits through component placements and mirrors into definition coordinates. New tools must not assume world and local frames coincide.

## Files, persistence and recovery

`Session.save()` exports GLB when an output directory exists, writes a temporary FCStd, optionally adds TechDraw data through a separate document, writes GUI visibility information, replaces the model file, then writes its journal with revision and hash.

Each file replacement is atomic; the FCStd and journal are not one atomic multi-file transaction. A crash between replacements can leave a detectable mismatch. Opening compares revision/hash and treats unmatched or externally modified documents conservatively, including an undo floor. Live watching/merging of outside edits and adoption of arbitrary foreign solids are still identified as future work in CLAUDE.md.

Save failures currently log an error in `save_pending`; there is no dedicated save-failure event in that path. Do not interpret confirmation or a missing error toast as proof of durability. Explicit save-error/retry behaviour is a useful future contract improvement.

Main picks/probes/starts the worker (`_pick_worker`), watches loss (`_watch_worker`), and reopens/resubmits after reconnection. With a shared worker, a window waits for the shared port to become free before attempting restart; closing one window sends bye rather than killing everyone's worker. Private app-started workers use quit; test connections are separate. `worker_client.gd` handles TCP reconnection and framing. Preserve ownership when changing recovery.

## Geometry and drawing exports

- `bodies.json` describes current bodies, geometry metadata, appearance and relationship information.
- `meshes/<board>-<key>.bin` stores packed triangle positions, normals, edges and corners. `board_mesh_file` writes it; `_build_board` reads it. Change both ends together.
- Main reuses board nodes by mesh filename plus material/grain appearance key and remembers a bounded set of confirmed states (currently 40). Cache eviction must not become history deletion.
- `model.glb` is generated at save time. Material extras include face/end texture paths, real texture size and species; node extras include `grain_zup` and `across_zup`. The export writes base-colour PBR materials plus these custom extras, not ready-wired Blender texture nodes. A Blender consumer must interpret the extras and resolve the texture files; this review does not establish a complete rendered .blend workflow.
- `worker/materials.py` installs FreeCAD cards under the user `Material/Shop Sketch` directory (v1-1 on this Mac). `op_set_material` sets the shared definition's SSMaterial and Tip ShapeMaterial; `set_tip` carries that card forward. SSGrain is definition-local, defaults to the longest axis, and `turn_grain` switches longest/middle axes. Linked siblings share it; export transforms grain/across into world coordinates.
- `materials.json` supplies the viewport library. `paint_tool.gd`, the Wood menu and T grain rotation expose it. `wood.gdshader` uses world position projected along grain/across with physical texture scale and mirrored end-grain repeats; no per-face UV mesh is required.
- TechDraw supplies view geometry. `drawing.py` reads `views.json`, `bodies.json`, and `status.json`, producing SVG/cut-list CSV and, when CairoSVG is available, PDF/PNG.
- The drawing composer currently uses fixed A3 layout and scales. Its existence does not imply arbitrary-page layout or a complete Blender material pipeline.

## Where to implement a change

| Change | Start here | Also review |
|---|---|---|
| New drawing/manipulation tool | New script under `viewport/tools` | Main registration, inference, worker handler, rejection dependencies, tests |
| Snap/axis/plane behaviour | `inference.gd` | Every tool and coordinate conversion |
| New native geometric feature | `Model` in `replay.py` | Transaction behaviour, export/cache keys, persistence/reopen |
| Component/array/assembly semantics | Model relationship helpers | Main editing context, previews, affected-instance highlighting |
| Material pipeline | `worker/materials.py`, `op_set_material`, `set_tip`, `grain_world`, `write_glb` | Paint tool, wood.gdshader, material/grain cache keys and Blender extras consumer |
| Worker failure/reconnect | `worker_client.gd`, Main lifecycle | `serve`, save acknowledgement and model switching |
| New persistent history | Proposed history owner, not mesh cache | Session replay, IDs, journal schema, external edits, worker request identity |
| Drawing layout | `drawing.py` | TechDraw generation and data schema |
| Packaging/runtime paths | `build_app.sh`, `_beside_project` | Worker and drawing dependencies inside bundle |

For a new operation, define intent, input units/frame, target identity, affected relationships, native representation, validation, undo unit, persistence, and export invalidation before adding UI polish.

## Architectural constraints worth preserving

- Never block normal input while waiting for FreeCAD; distinguish provisional, accepted and saved states.
- New operations must have transaction-safe failure and leave a valid prior model when rejected.
- Add FreeCAD properties at object creation where possible; property additions inside transactions have undo caveats documented in CLAUDE.md.
- Set the active FreeCAD document before invoking Draft helpers.
- Use MultiFuse for overlapping additive features; a Fuse of overlapping compound members can miscount volume.
- Apply overlay depth bias in shaders, not moved geometry nodes; moving overlays previously broke picking.
- Use the existing anti-aliased strip-line implementation rather than primitive one-pixel lines.
- Keep test delays, forced rejections and synthetic input hooks confined to tests.

## Proposed evolution, not current implementation

Main currently concentrates UI, model coordination, caches, selection, history-like state, process lifecycle and rendering. Replay combines domain operations, persistence, export and transport. These are practical extraction seams, not a reason for a large rewrite.

Later handoff H010 (decision-log revision 61) records planned T42 worker-module extraction and T43 per-directory guidance, assigned to Claude. Those modules do not exist at this review baseline; recheck paths and test loaders when they land. T44 protocol documentation is proposed follow-on work, not part of H009.

As features grow, consider extracting:

1. **Document controller (A31 Active, T39):** current model, operations, request generation, confirmation and save status.
2. **History store (U01/U02, T35–T36):** immutable action nodes, active cursor, branch heads, persistence and checkpoint policy.
3. **Selection/context controller (A33 Tentative):** selected units, entered assemblies/arrays and affected-instance scope.
4. **Geometry presenter (A33 Tentative):** draft and confirmed nodes, mesh cache, picking metadata and feedback.
5. **Worker session/export boundaries:** keep transport separate from domain operations, document recovery and derived outputs.

For branching history, retain old futures in a durable graph and materialize an active path through the existing sync interface initially. A 20-row sidebar window is independent of retention depth, FreeCAD's undo capacity and the viewport's 40-state cache. Branch-safe IDs, checkpoints, stale-response handling and external-edit boundaries are prerequisites. Merge should compare semantic dependencies from a common ancestor and preserve both source paths; a successful boolean replay is not sufficient proof of a conflict-free merge. See the suggestions document for staged requirements and acceptance cases.

## Validation and maintenance

For behavioural changes, follow CLAUDE.md: run `tools/quicktest.sh`; run `tools/fulltest.sh` on failure or before merge. Worker tests check native structure, undo/reopen, arrays and relationships. Scripted viewport suites exercise gestures; reference comparisons check volumes/bounds. Visual quality and interaction feel still require real-hardware checks.

`parsecheck.sh` loads every viewport/tool script first. `quicktest.sh` runs native, arrays and shared-server tests alongside the single viewport quick suite. `test_serve.py` covers shared-worker ownership/lifecycle; fulltest also runs recorded suites and targeted checks. This documentation branch passed quicktest: native 96, arrays 10, serve 11, viewport 52; zero failures. No runtime files changed. New standalone parser/combo tests on other Codex branches are review deliverables, not yet part of main's test runners.

Update this file when adding a module, changing a protocol/schema, moving state ownership, introducing a persistent relationship, or changing save/recovery behaviour. Keep current facts distinct from planned work, and recheck working-tree changes before acting on an inventory.

## Native geometry feature mapping

See [FREECAD_FEATURE_MAP.md](FREECAD_FEATURE_MAP.md) for S01–S16 providers, native object types, workbench requirements, evidence and integration limits. William clarified that SketchUp-style actions should translate to reasonable FreeCAD counterparts, including combinations of operations and downloadable workbenches; custom UI/history are allowed. A one-to-one command or stock-FreeCAD-only implementation is not required. The mapping separates geometry capabilities from custom orchestration and unverified rendering/relationship behaviour.
