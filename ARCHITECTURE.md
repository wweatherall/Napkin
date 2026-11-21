# Shop Sketch architecture

Reviewed: 2026-11-21 against main 5c0b602 for H009. This maps the inspected source, not a released build. The code and revision 60 decision-log export were checked; baseline quicktest results are recorded below. Updated by Claude 2026-11-21 for the T42 worker split (linked-copies 1739746).

## Implementation status

Everything below is integrated on `linked-copies`: the T42 worker split, FreeCAD-backed typed lengths (H011 / T32, I35) and the native Properties panel (H012 / T46). Claude reviewed and merged the Codex branches on 2026-11-21 (merges after `3db2cff`; worker hooks moved into `serve.py` and `model.py`). Not yet on `main`.

## Reading and decision order

Read CLAUDE.md for project conventions, `docs/decision-log.md` for decisions, and the folder guides (`worker/CLAUDE.md`, `viewport/CLAUDE.md`, `viewport/tools/CLAUDE.md`) for each part's rules and tests. This file maps implementation responsibilities and constraints; it does not supersede accepted decisions. Read [Codex's suggestions.md](<Codex's suggestions.md>) for the proposed feature backlog and branching-history design. The live log requires access through Claude; [docs/decision-log.md](docs/decision-log.md) is its read-only local export. Read [docs/agent-handoff.md](docs/agent-handoff.md) for current assignments; do not change the exported log independently.

When behaviour changes, update the decision log as required there, then keep this map and affected tests current. Proposed boundaries below are explicitly labelled; do not mistake them for existing modules.

## System overview

Shop Sketch is a local desktop application with one Godot process per window, a shared FreeCAD worker for compatible windows, and file-based geometry transfer (W13). Godot handles the immediate modelling experience. A long-running Python worker inside FreeCAD performs authoritative geometry operations. Native FCStd documents remain editable outside Shop Sketch. Blender is an intended rendering consumer, not the modelling engine.

```mermaid
flowchart LR
    U[User] --> T[Godot tools and inference]
    T --> M[main.gd: UI, input, worker process]
    M --> PR[presenter.gd: drafts, boards, states, waves, highlights]
    SC --> PR
    T --> DC[document.gd: operations, sync, save state]
    M <--> DC
    T --> SC[selection.gd: selection, context, hidden]
    M <--> SC
    SC --> DC
    DC --> C[worker_client.gd]
    C -->|newline JSON over localhost TCP| W[serve.py and session.py]
    W --> G[model.py + action mixins: FreeCAD features]
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
| `viewport/main.gd` | Composition root; UI, materials and mesh helpers (`_tri_mesh`, `_lines`), rejection bookkeeping (which later actions go with a rejected one), worker process lifecycle, project switching (window side), camera. Routes worker replies: `sync`/`open`/`saved` to the document controller, the rest to its own handlers; routes the controller's signals to the presenter. Forwards `ops`, `counters`, `seq`, `in_flight`, `dirty`, `model_path`, `out_dir`, `opened`, revisions and `confirmed_ids` to it, and `selection`, `context`, the `body_*` relationship tables, `hover_body` and the context queries to `selection.gd`, and `body_tris` / `body_verts` / `body_edges` / `body_cuts`, `drafts`, `rects`, `op_waves` and the wave calls to `presenter.gd`, so tools and tests keep using `m.<name>` | `_ready`, `_make_tools`, `sync`, `_on_worker`, `_on_synced`, `_on_op_removed`, `_apply_confirmed`, `switch_model` |
| `viewport/document.gd` | Document controller (A31, T39): model path and output folder, the op list and id counters, request numbering and coalescing (`seq`, `in_flight`, `dirty`), gating replies to the current state, confirmed op ids, undo floor, linear redo stack, open/reset, save revisions. No meshes, shaders or camera; reports by signals (`sync_started`, `sent`, `synced`, `sync_failed`, `save_changed`, `op_removed`, `removed`, `idle`). Tested headless by `test_document.gd` with a stand-in client | `sync`, `on_sync_reply`, `on_opened`, `on_saved`, `on_link_up`, `reset`, `open`, `remove_op(s)`, `undo`, `take_redo` |
| `viewport/presenter.gd` | Geometry presentation (A33b, T41), `m.pres`: each board's triangles, corners, edges and cuts (what picking and snapping read), drafts and rectangles, confirmed board nodes built from the per-board mesh files (A29), the 40 remembered confirmed states (A28), the confirmation waves, and the highlights for selection and context (selection overlay, ghosting, hidden boards, mirror plane, linked-copy tint) from what `selection.gd` says. Draws with main's mesh helpers and materials. Signals `boards_read` (main updates selection tables and wood) and `wave_rejected_done` (main removes the op and its dependents) | `apply_confirmed`, `show_confirmed`, `show_state`, `forget_op`, `register_rect`, `begin_wave`, `attach_wave`, `step_waves`, `apply_context`, `show_selection`, `show_siblings`, `reset` |
| `viewport/selection.gd` | Selection and context (A33b, T41), `m.sel`: the selection, the entered assembly or array row, each board's assembly / row / family / array / mirror plane (from `bodies.json`), the hidden set (worked out from `ops`), View > Hidden geometry, the board under the cursor. Its actions (hide, unhide, make assembly, make unique, detach) append ops to the document controller and sync. Draws nothing; reports by signals (`selection_changed`, `context_changed`, `hidden_changed`, `links_changed`, `say`). Tested headless by `test_selection.gd` with a stand-in document | `set_boards`, `unit_of`, `in_context`, `edit_blocked`, `enter_context_of`, `leave_context`, `set_selection`, `refresh_hidden`, `is_hidden`, `hide_selected`, `unhide`, `make_assembly`, `linked_op` |
| `viewport/tools/tool.gd` | Common tool interface and references to viewport/inference | `setup`, `reset`, `click`, `double_click`, `release`, `mouse_moved`, `key`, `typed` |
| `viewport/tools/select_tool.gd` | Selection and entering editing contexts | Tool event methods |
| `viewport/tools/paint_tool.gd` | Paint selected wood onto the picked board/family | Tool event methods |
| `viewport/tools/rect_tool.gd` | Rectangle interaction, preview and operation creation | `commit_rect` |
| `viewport/tools/push_tool.gd` | Push/Pull picking, depth inference, preview, through-cut intent | `commit_push` |
| `viewport/tools/move_tool.gd` | Move/copy/mirror gestures, arrays and operation amendments | `commit_move`, `commit_mirror_move` |
| `viewport/inference.gd` | Shared picking and snapping, visibility checks, axis/plane destinations | `pick`, `snap`, `point`, `axis`, `axis_dest`, `plane_dest` |
| `viewport/worker_client.gd` | TCP framing, buffering, reconnect, pending sends and link signals | `send`, `_process`, `_drain` |
| `worker/replay.py` | Entry point only: puts worker/ on sys.path and calls `serve.main()` (freecadcmd runs it by name) | `main` |
| `worker/common.py` | Shared basics every module takes with `from common import *`: FreeCAD imports, tolerances, `OpError`, `vec`/`unit`, `add_props`, `Frame`, wood cards | `material_card`, `Frame` |
| `worker/model.py: Model` | Reading the document and the building blocks (boards, planes, extrusions, booleans, Tip); combines the action mixins; validates each op | `apply`, `HANDLERS`, `resolve_face`, `edit_frame`, `boolean` |
| `worker/push.py`, `move.py`, `mirror.py`, `assembly.py`, `paint.py`, `visibility.py` | One mixin per kind of action (`PushActions`, ...), working through `self` on the document: rect + push/pull + through-cuts; move, copies, links, arrays, detach, make unique; mirrors; assemblies; paint and grain; hide/unhide (T28) | `op_*`, `show_as_hidden` |
| `worker/export.py` | What the viewport and renders read: bodies.json entries, per-board mesh files and their caches, model.glb, the TechDraw page | `mesh_of`, `board_mesh_file`, `write_glb`, `cuts_of` |
| `worker/session.py: Session` | Live document, applied operation sequence, undo/rebuild, external-edit detection, journal, saves (incl. GuiDocument.xml) | `sync`, `_apply`, `_open_existing`, `export`, `save` |
| `worker/serve.py` | select-based multi-client loop; sessions and single-window ownership by absolute file path; delayed saves and focus notifications | `handle`, `claim`, `let_go`, `release`, `save_pending`, `session_for` |
| `worker/materials.py` | Twelve-species wood library, FreeCAD card installation, texture metadata | `install`, `write_library`, `SPECIES` |
| `worker/drawing.py` | Compose shop drawings and cut list from exported data | Script entry point |
| `viewport/*.gdshader`, `line.gdshaderinc` | Draft/confirmation appearance, depth-biased overlays and anti-aliased lines | Shader parameters |
| `viewport/tests.gd`, `worker/test_*.py` | Scripted UI and geometry/persistence tests | Suite entry points |
| `tools/featuretest.sh`, `quicktest.sh`, `fulltest.sh`, `compare_suites.py` | Test orchestration and geometry comparisons (feature tests without a window; UI tests in the viewport, P07) | Shell entry points |
| `tools/build_app.sh`, `export_presets.cfg` | macOS application packaging | App build |

Tools currently depend directly on `main.gd`; the interface is a convention, not a strongly isolated service boundary. Main runtime-loads tools/tests while those scripts preload Main for typing, avoiding preload cycles.

### Typed lengths and the Properties panel (T32, T46)

| Location | Responsibility | Entry points |
|---|---|---|
| `worker/length_input.py` | Normalize supported measurement notation; evaluate numeric lengths using FreeCAD in a temporary unsaved document; return finite millimetres | `evaluate`, `handle` |
| `viewport/main.gd` length-input additions | Route count syntax locally; read plain lengths at once with `units.gd`; send arithmetic as an asynchronous `length` request, hold the draft and reject stale results before calling the tool | `apply_vcb`, `_on_length`, `length_pending`, `length_id` |
| `worker/object_properties.py` | Describe native property types, values, formulas and permissions; validate and apply a journalled property edit | `related`, `describe`, `inspect`, `apply` |
| `viewport/property_panel.gd` | Selected-piece feature picker, property fields, Value/Expression modes, reference insertion and read-only details | `display`, `message`, `refresh_requested`, `edit_requested` |
| `viewport/main.gd` property additions | Tie inspection to model/selection/sequence; append property edits to `ops`; refresh after confirmation | `_request_properties`, `_on_properties`, `_edit_property` |

The `length` and `inspect_properties` requests are handled in `serve.py`; `property_edit` is in `Model.HANDLERS` and `op_property_edit` (delegating to `object_properties.apply`) in `model.py`. Both new worker modules are covered by the worker hash and the app bundle. `test_properties.py` loads the worker through `test_load`.

## State ownership and authority

| State | Owner | Meaning |
|---|---|---|
| Pointer gesture, typed input, hover, preview | Godot tool / main | Provisional user interaction |
| Desired operation sequence | Godot `document.gd` `ops` | What the client wants the worker to materialize |
| Selection, entered context, hidden set, board relationships as last confirmed | Godot `selection.gd` | What a click stands for; the hidden set follows `ops` at once, the relationships follow `bodies.json` |
| Accepted geometry and model relationships | Live FreeCAD document | Authoritative computed model |
| Saved model | `.FCStd` | Durable native model, including Shop Sketch properties |
| Replay/provenance information | Adjacent `.shopsketch.json` | Operations, statuses, revision and FCStd hash |
| Meshes, bounds, metadata, GLB, drawing outputs | Derived export files | Rebuildable presentation/export products |
| Recently confirmed visible states | Godot `presenter.gd` `_states` / `_boards` | Fast visual restoration; not durable model history |
| Undone actions available to redo | Godot `document.gd` `redo_stack` (T31) | Linear and in memory only: valid while `ops` still has the key recorded at the undo; any other change ends it. Branch history (U01) will replace it |
| Last project preference | Godot `user://settings.cfg` | Application preference |

An operation being confirmed does not mean it has been saved. A visible draft is not an accepted solid. A mesh snapshot cannot restore the full feature graph.

## Lifecycle of an edit

1. A tool receives input through Main and uses the shared inference engine.
2. It renders a draft immediately and commits a semantic operation into `ops`.
3. `sync()` (the document controller's) advances `seq`, marks the desired state dirty, and sends when no request is in flight. Further edits coalesce into a subsequent full-log request.
4. `Session.sync()` compares canonical operation values to the applied sequence, preserving their common prefix.
5. The worker undoes the old tail and applies the new tail. If available FreeCAD undo cannot reach the required state, it rebuilds from operations when permitted by the external-edit floor.
6. Each applied operation runs in a FreeCAD transaction. Failure aborts that operation and records a failure status.
7. Export writes current metadata and changed board meshes. The worker responds with per-operation status and output directory.
8. The document controller passes on only a response for the current `seq` with nothing newer waiting (`synced`); main then applies it, replaces drafts with confirmed board nodes, and runs acceptance/rejection feedback. Rejection handling also considers dependent operations; review `_on_rejected` when adding new operation kinds.
9. After approximately 0.25 seconds of socket inactivity, the worker saves pending documents and sends a separate `saved` notification. Flush/quit paths also drain pending saves.

The current client gates sync results using sequence and dirty state. New asynchronous work must preserve this discipline. Future branching history should additionally identify the exact requested history state and model generation.

### Typed length evaluation

`apply_vcb()` keeps Move copy/divide commands (`3x`, `x3`, `*3`, `/3`) in the tools. Other Rectangle, Push/Pull, Move and mirror inputs are first worked out by `viewport/units.gd` `evaluate_length` / `evaluate_pair`, a port of `length_input.evaluate`: the same rewriting steps, then FreeCAD's rules for this subset (left-to-right `^` after a leading minus, trig in degrees, a unit belongs to the number before it, unit mismatch and division by zero refused). It answers at once, so drafts never wait for FreeCAD, including arithmetic (`5in + 23mm`, `1'-6"` = 6", I35). When unsure (a unit power such as `2mm^2`, a unit after a bracket, `pi mm`) it declines, and the input goes through a `length` request; FreeCAD also supplies the error message for bad input. Rectangle splits its two values at the comma. Decimal commas are therefore not supported by this input path. The viewport sends `default_unit: "mm"`; it does not yet provide a unit-preference UI.

`length_input.evaluate()` normalizes supported mixed fractions and compound imperial measurements, then calls FreeCAD's full `evalExpression` on a temporary feature in an unsaved document. It restores the previous active document afterwards. Unitless results acquire the requested default unit; other results must be finite lengths. This restricted numeric evaluator does not expose model-property references. It supports a fixed set of units/functions, not the whole FreeCAD expression language. I35 makes minus subtraction: `1-1/2"` is half an inch, while `1 1/2"` is one and a half inches. The two must never disagree. `tests/length_cases.json` holds FreeCAD's answers for 2,500 typed lengths (curated cases plus seeded random expressions; regenerate with `freecadcmd tools/length_cases.py` after changing `length_input.py`). `test_length_input.py` checks FreeCAD still gives them; `test_units.gd` checks every local answer matches and that it answers at least 95% of FreeCAD's lengths (1,145 of 1,149 today). The older `parse_length` / `parse_pair` stay in `units.gd` but aren't the input path.

FreeCAD evaluation is asynchronous from Godot's perspective but runs serially in the same worker as geometry, so a declined entry can wait behind a recompute (what the local evaluator answers never does). Main holds the current draft steady and records the tool, model, sequence and tool state with the input ID. New keypresses, clicks or tool changes cancel the pending input; replies must still match that context before reaching `typed()`. Length replies bypass the geometry-sync response path and must not clear its in-flight state. Parsing itself creates no model action, undo step or persistent formula.

### Native property inspection and editing

Plane fits (I40, T53). `worker/plane_fit.py` describes rectangular stock using its
base rectangle, extrusion direction, local dimensions and world frame. The inspection snapshot includes these
frames and native labels under `boards`. Properties captures a viewport face click for the active dimension.
The panel previews four corner rays intersecting the selected face's infinite supporting plane. The worker
independently solves those intersections and builds a solid with a square or sloping end. A `property_edit`
with mode `plane_fit` records the source and target BodyIds, local axis, semantic face and end condition.
The board's new Part::Feature tip stores its source extrusion link and the relationship. Model.apply updates
fitted solids inside the transaction after geometry changes. A `replace_fit` edit restores the native extrusion
with the entered dimension. FreeCAD can open the saved solid directly. Updating the fit requires the Shop Sketch
worker. The prototype supports one fitted dimension per plain rectangular board and rectangular targets.

Session.export includes the rectangular stock frame and current label in each
eligible bodies.json entry (`stock_frame`; `presenter.gd` keeps them as `stock_frames`, remembered with each confirmed state). Push/Pull uses the inference engine's corner, edge and edge-midpoint snaps and this frame to rank reachable
adjacent planes by alignment with the push, breaking ties with the last hovered face. Tab cycles the candidates.
⌥ Option cycles the end condition (I41). Committing a click carries the semantic target in `push_pull.edge_fit` (`target_body`, `face`, `fit_mode` 0 Butt / 1 Slice / 2 Fully reach; absent = Butt) and builds the source and fit in one
transaction. A fit on the low end anchors the opposite end through SSReverse. A direct hit on a different stock face can also create the link. A corner can supply up to three reachable planes. Typed pushes retain their numeric distance. Clicking a dimension text field arms a
one-click reference to a face, corner, edge or midpoint. The click commits the most aligned reachable plane with the
selected fit mode. The explicit picker still previews before Apply. Confirmed and restored viewport meshes
refresh selection tint and discard idle hover geometry. For a numeric pull of an entire ordinary stock face the viewport sends
`push_pull.resize_stock`. The worker changes the native dimension and anchors the opposite end. Earlier journals
without this flag replay their original Boolean feature history. A face push on a fitted board's tied end detaches the fit (I26b, I40): a square end is restored to
the native extrusion at its current length and resized; a sloped end keeps its shape with an empty `SSTargetId`.

Select one piece and open Properties. The panel lists the piece and its native dependency chain, including shared component definitions; it can also insert native object names into expression fields. FreeCAD owns the property schema, value and expression. Godot holds an inspection snapshot and provisional edit text, not an independent property database.

The supported editors cover labels, scalar dimensions, integers, booleans, enumerations and vectors, including local placement translation. Internal names/IDs, structural links, protected metadata, rotation and unsupported/computed types are view-only. Other native fields remain available in expandable details. The panel currently handles one selected piece, not bulk edits. Editing a shared feature affects its linked family; coordinates are local to the owning feature/parent, not automatically world coordinates.

A property edit is a normal `property_edit` operation appended to `ops`, not a separate write request. It records `body`, native `object` name, property path, `mode` (`value` or `expression`), input `value`, and the inspected `{value, expression}` as `expected`. The worker checks that the object is still in the piece's dependency chain, the property is writable and the expected snapshot still matches. The UI supplies `expected`; the worker schema currently permits its omission for programmatic callers.

Expression mode uses the native object's `setExpression`, preserving references such as `Rect001.Length * 2`. Value mode evaluates the input, deliberately clears an existing formula, and assigns the property. The UI explicitly identifies this replacement. Length values use the measurement adapter; persistent formulas use native FreeCAD expression syntax. `Model.apply` recomputes and validates; Session's existing transaction abort rolls back rejected edits, including cycles. Changes follow normal export, confirmation, autosave and journal replay; affected bodies conservatively include every model body because references may reach other pieces. No new journal format or sidecar property store is introduced.

Inspection waits for settled geometry. Main checks the request ID, model, selected body, sequence and dirty/in-flight state before accepting a snapshot; property submissions also require the same confirmed sequence. Switching models clears selection and invalidates the inspection state. Property operations participate in rejection-reference tracking and counter restoration. Undo/redo and reopening run through the existing Session machinery.

## Protocol at a glance

Transport: UTF-8 JSON objects separated by newlines over localhost TCP. Main probes port 7878 with hello and compares the worker identity: the MD5 of every worker `.py` except `test_*`, in name order (`serve.py worker_identity`; main.gd `_worker_identity` computes the same, and a quick-test step checks they agree). A matching worker is shared; a different version or occupied port gets a private worker. Test mode starts its own worker with `SERVE_PORT=0`: the worker binds a port the system picks and writes it to `SERVE_PORT_FILE` (written whole, via rename), which the window reads before connecting, so concurrent test runs can't take the same port (T47; `tools/fulltest.sh` and the socket tests start theirs the same way). `--port=N` selects an external worker.

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

Typed lengths and the Properties panel add:

| Request / operation | Result and routing |
|---|---|
| `length` with `id`, `texts`, optional `default_unit` | Reply `{cmd: "length", id, ok, values}` with millimetres, or `error`; independent of geometry `seq`/`in_flight` |
| `inspect_properties` with `model`, `body`, `seq`, `request_id` | Ownership-checked read; reply echoes `seq`, `request_id`, `model` and includes `properties: {body, objects, references}`; errors retain request identity |
| `property_edit` inside `sync`'s operation list | Native object/property mutation; ordinary per-op confirmation/rejection, export, undo and save path; there is no standalone property-write command |

Each described object includes native `name`, user-facing `label`, type and field records. Fields include property `path`, display `value`, editor `kind`, `editable`, current `expression`, and enumeration choices where applicable. Link references are displayed but cannot be reassigned through this editor.

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
- Viewport `unit_of`, `context`, `in_context`, `edit_blocked` and `is_hidden` control whether a picked board represents a part, assembly, or array. Context entry affects picking and appearance.
- Hidden boards (T28, I37) carry `SSHidden=True` on the board object (op `hide` with `targets` and `hidden`; one op per Hide/Unhide command). FreeCAD's undo restores `SSHidden` but not `Visibility`, so ops never set a board's Visibility: `Session.sync` calls `show_as_hidden()` after every change, and the saved GuiDocument.xml follows it. Boards from files older than T28 get `SSHidden` on opening (`add_hidden_props`, outside any transaction). A flip in place and Make unique keep the board's hidden state; new copies start shown. bodies.json carries `hidden`; the viewport works out the hidden set from `ops` itself (`hidden_boards()`), so hide and its undo show at once. Hidden boards are left out of model.glb (renders; unhide to include them) but stay in drawings and the cut list.
- Identity/metadata include `BodyId`, `RectId`, `SSRole`, `SSOp`, `SSMaterial`, `SSGrain`, `SSHidden`, `AssemblyId`, `SSArray`, and `SSArrayIndex`. Labels are presentation; do not substitute labels for stable identity.

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
| New native geometric feature | An `op_*` in the matching action file (`push.py`, `move.py`, ...), or a new mixin added to `Model` in `model.py`; list the op in `HANDLERS` | Transaction behaviour, export/cache keys, persistence/reopen |
| Component/array/assembly semantics | Model relationship helpers | Main editing context, previews, affected-instance highlighting |
| Material pipeline | `worker/materials.py`, `op_set_material`, `set_tip`, `grain_world`, `write_glb` | Paint tool, wood.gdshader, material/grain cache keys and Blender extras consumer |
| Worker failure/reconnect | `worker_client.gd`, Main lifecycle | `serve`, save acknowledgement and model switching |
| Typed measurement syntax | `length_input.py` first, then its port `units.gd` `evaluate_length`, and `tools/length_cases.py` to rebuild the shared table; Main `apply_vcb` / `_on_length` | I35, count commands, request cancellation, parsing versus persistent expressions |
| Native property UI or edits | `property_panel.gd`, `object_properties.py` | Native permissions, shared definitions, units/frames, stale snapshots, transactions, undo/reopen |
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

Main was split in T39 (document controller) and T41 (selection/context, geometry presenter), 2026-11-21, no behaviour change; it still holds UI, input dispatch, materials and mesh helpers, rejection bookkeeping and the worker process (about 2,000 lines). The worker was split by job in T42 (2026-11-21, no behaviour change): domain operations, export, persistence and transport now live in separate modules (see the table above). T43 per-directory guidance and T44 protocol documentation are still to do.

As features grow, consider extracting:

1. **Document controller (A31 Active, T39; built as `document.gd`, 2026-11-21):** current model, operations, request generation, confirmation and save status. Still to route through it: tools submitting actions (they append to `ops` and call `sync()`), and history (U01).
2. **History store (U01/U02, T35–T36):** immutable action nodes, active cursor, branch heads, persistence and checkpoint policy.
3. **Selection/context controller (A33b Active, T41; built as `selection.gd`, 2026-11-21):** selected units, entered assemblies/arrays, hidden boards and affected-instance scope.
4. **Geometry presenter (A33b Active, T41; built as `presenter.gd`, 2026-11-21; materials and mesh helpers still in main):** draft and confirmed nodes, mesh cache, picking metadata and feedback.
5. **Worker session/export boundaries:** keep transport separate from domain operations, document recovery and derived outputs.

For branching history, retain old futures in a durable graph and materialize an active path through the existing sync interface initially. A 20-row sidebar window is independent of retention depth, FreeCAD's undo capacity and the viewport's 40-state cache. Branch-safe IDs, checkpoints, stale-response handling and external-edit boundaries are prerequisites. Merge should compare semantic dependencies from a common ancestor and preserve both source paths; a successful boolean replay is not sufficient proof of a conflict-free merge. See the suggestions document for staged requirements and acceptance cases.

## Validation and maintenance

For behavioural changes, follow CLAUDE.md: run `tools/quicktest.sh`; run `tools/fulltest.sh` on failure or before merge. Worker tests check native structure, undo/reopen, arrays and relationships. Scripted viewport suites exercise gestures; reference comparisons check volumes/bounds. Visual quality and interaction feel still require real-hardware checks.

`parsecheck.sh` loads every viewport/tool script first. `featuretest.sh` runs the feature tests in parallel: the worker tests (native, runs, arrays, combos, serve, length input and protocol, properties, the T48 scenario on `tests/scenario_fixture.json`), the units parser test the document controller's sequencing test (`test_document.gd`: coalescing, stale and dirty replies, reconnect, open/switch, undo floor, redo) and the selection/context test (`test_selection.gd`: units from outside and inside, entering and leaving, the hidden set following the ops, hide/assembly/unlink ops). `quicktest.sh` runs them alongside the viewport quick suite, dealt into three windows side by side (`tests.gd` `QUICK_LANES`, `--quick-lane=N`; T49), each with its own worker; `fulltest.sh` alongside the recorded and targeted suites at quick pace (`--fast`), in four lanes side by side, each lane with its own worker started on port 0 (T47, T49). Worker tests load the modules with `from test_load import *`. `test_serve.py` covers shared-worker ownership/lifecycle; fulltest also runs recorded suites and targeted checks. After integrating H011/H012 (linked-copies, 2026-11-21): native 96, arrays 10, combos 61, serve 11, units 114, length 23, length protocol 3, properties 28, viewport 63; zero failures. Quick-test steps check that typed arithmetic is worked out locally and a declined input (`60mm^1`) goes to FreeCAD; the rejection scenario types for real. The panel's steps drive its actual controls (inspect, expression edit, confirmed volume, undo).

Known limit: a property edit names its FreeCAD object by internal name (`Extrusion003`). Names are stable on reopen and on rebuild from the journal; branch-safe IDs (T35) must take them into account.

Update this file when adding a module, changing a protocol/schema, moving state ownership, introducing a persistent relationship, or changing save/recovery behaviour. Update it in the same commit as the architectural code change and mention the update in the handoff (AGENTS.md / CLAUDE.md). Before committing, reread the current shared instructions and compare the staged file list against this map. Keep integrated code, delivered branches and proposals distinct, and recheck working-tree changes before acting on an inventory.

### Shared ownership and automated omission checks

Claude and Codex both maintain this map. The author updates it with architectural code changes in their own worktree; the reviewer checks the description against the code. Neither agent needs the other's permission to edit it. Integration preserves unrelated edits from both branches and keeps integration status explicit.

`tools/check_architecture.py` watches non-test Python/Godot modules under worker/ and viewport/, Godot project/scenes, and app packaging. Additions, deletions and renames are included. It is deliberately conservative: modifying a watched file requires a meaningful staged ARCHITECTURE.md change or a commit-message line `Architecture-Impact: none - <specific reason>`. That line asserts there was no architectural change; it does not waive the same-commit requirement when architecture did change. Review must verify both the explanation and the prose; the tool cannot infer semantic accuracy.

The tracked `.githooks/commit-msg` checks the staged snapshot, so an unstaged document edit does not count. Run commits with `git -c core.hooksPath=.githooks commit ...`. Once these files are integrated, `git config core.hooksPath .githooks` can enable the hook by default; first check existing hook configuration and preserve any custom hooks. Configuration is shared by linked worktrees, so do not redirect it to files missing from another active checkout. This delivery does not change shared Git configuration.

`.github/workflows/architecture.yml` runs the guard tests and checks the complete pull-request diff with `--range BASE..HEAD`. The PR check accepts a no-impact rationale from its commit messages and catches missing updates across the PR; it does not enforce per-commit ordering. The local hook enforces staging together, and the reviewer enforces the same-commit rule across the submitted history. Both are omission checks, not automatic documentation writers. `tools/test_check_architecture.py` covers missing updates, rationales, staged versus unstaged docs, real Git diffs, renames and deletion. CI and default hook installation take effect only after integration/configuration; neither is active on the shared checkout merely because this branch exists.

## Native geometry feature mapping

See [FREECAD_FEATURE_MAP.md](FREECAD_FEATURE_MAP.md) for S01–S16 providers, native object types, workbench requirements, evidence and integration limits. William clarified that SketchUp-style actions should translate to reasonable FreeCAD counterparts, including combinations of operations and downloadable workbenches; custom UI/history are allowed. A one-to-one command or stock-FreeCAD-only implementation is not required. The mapping separates geometry capabilities from custom orchestration and unverified rendering/relationship behaviour.
