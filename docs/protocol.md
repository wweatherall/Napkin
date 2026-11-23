# Window ↔ worker protocol

Protocol reference **0.3** (T81, H041: exact circle profiles; includes T70/H042 reply matching), describing main plus H041 (2026-11-22); 0.1 described `8ff1f91` (2026-11-21). This is a documentation version. The wire protocol's own version is **8** (8: A38's journal `floor_copy`; 7: T67's `reserved_ids` in the open reply and the journal; 6: T64's `outside_save` event, `reload` and `keep_mine`, the journal's `floor`, `dropped` and `outside_sha256`; 5: T82's `line` op and Push/Pull's `target.region`; 4: T40's optional `recovered` in the open reply; 3: T79's `save_failed` event and the saved/failed lists in flush, bye and quit): the worker reports it in `hello` (`protocol`), defined once per side (`worker/serve.py` `PROTOCOL_VERSION`, `viewport/main.gd` `PROTOCOL_VERSION`). **Rule: bump it on both sides when a message or a shared-file field changes** (added, removed, renamed or its meaning changed), and update this document. There is no negotiation: a window shares a worker only when the version matches. Existing embedded format identifiers are `oplog/0.1` and `shopsketch-journal/0.1`; binary meshes use Godot's Variant array encoding.

## Transport, identity and lifetime

Each TCP stream carries UTF-8 JSON objects, one per LF-terminated line, on `127.0.0.1`. A packet may contain partial or multiple lines; both ends buffer until LF. The worker ignores blank lines. The client emits replies only for parsed JSON dictionaries; the worker catches malformed requests and replies with an error. There is no authentication, request-size limit or per-request cancellation. Geometry travels through shared local files, not TCP. Paths must be accessible to both processes.

Sources: [worker/serve.py](../worker/serve.py):`serve`, nested `handle`/`send`; [viewport/worker_client.gd](../viewport/worker_client.gd):`send`, `_process`, `_drain`.

The window probes port 7878 using `hello`. A worker reporting another protocol version (or none) is treated like one with a different identity: the window starts its own and prints a `SHOPSKETCH ... speaks protocol` line. Identity is the MD5 of the concatenated contents of the worker's immediate `.py` files, sorted by filename, excluding `test_*` (not recursive). A matching worker is shared; an occupied port with a different identity leads to a private worker. Tests use `SERVE_PORT=0` and an atomic `SERVE_PORT_FILE` containing the chosen decimal port and LF. `SERVE_PORT` selects serve mode in `serve.main`; absent it, `OPLOG` and `OUTDIR` select one-off replay, with drawing and immediate save, without TCP.

Sources: [worker/replay.py](../worker/replay.py):entry point; [worker/serve.py](../worker/serve.py):`worker_files`, `worker_identity`, `main`, `serve`; [viewport/main.gd](../viewport/main.gd):`_worker_identity`, `_probe_worker`, `_hello`, `_worker_of`, `_pick_worker`, `_start_worker`, `_await_port_file`.

One worker holds many sessions but evaluates requests serially on one thread. One connection owns at most one model at a time. Ownership keys are `os.path.abspath` paths, without symlink resolution or OS-wide file locking. Claiming a different available model saves and releases the old one; claiming an occupied model leaves the current ownership alone. Released sessions remain cached. Disconnection saves/releases owned models. Autosave waits for **all** clients to be quiet for 0.25 s after the last handled request. `SERVE_IDLE_EXIT` seconds after the last connection leaves controls worker exit (0 disables; macOS app supplies 10).

Sources: [worker/serve.py](../worker/serve.py):`serve`, nested `claim`, `let_go`, `release`, `session_for`, `save_pending`.

## Types, units and correlation

Notation: `number` is a JSON number; `integer` is an integral number; `Vec3` is `[number, number, number]`; `?` means optional. IDs and paths are strings. Unless explicitly stated otherwise, points, offsets, sizes and bounding boxes use **millimetres in right-handed world Z-up coordinates**. Normals and grain directions are dimensionless. Durations ending `_ms` and per-op `ms` are milliseconds. Revisions are integers scoped to one saved model; they are different from request `seq`.

The window converts `(x,y,z)` mm to `(x,z,-y)/1000` metres for Godot. The mesh file stays in model coordinates; GLB has already been converted to Y-up metres. Sources: [viewport/main.gd](../viewport/main.gd):`m2g`, `g2m`; [viewport/presenter.gd](../viewport/presenter.gd):`_build_board`; [worker/export.py](../worker/export.py):`mesh_of`, `board_mesh_file`.

`document.gd` owns monotonic `seq` and coalesces desired-state syncs: one request in flight, newest state sent after its answer if dirty. A successful sync answer is applied only when its `seq` equals the current sequence and no newer state is waiting. Failures of the request in flight are reported before that freshness check. `inspect_properties` echoes both `seq` and `request_id`; `length` uses its separate `id`. Every other reply (open, hello, flush, bye, quit, errors) echoes the request's `seq`, `null` when the request had none; events (`saved`, `focus`) carry none. Only the reply whose `seq` is the request in flight clears `in_flight`, so an answer from before a reconnect can't stop the next sync being sent. `send_open` advances `seq` and remembers it as the open's; `document.gd:is_current_open` accepts an open reply (success, refusal or error) only with that `seq` and, when it names one, the current model. `main.gd:_on_worker` routes by `cmd`: only `sync` replies reach `on_sync_reply` (T70).

On reconnect the TCP client retries every 0.5 s and drains queued lines; the document reopens if never opened, otherwise resends its full desired op list. This is state reconciliation, not exactly-once delivery. Sources: [viewport/document.gd](../viewport/document.gd):`sync`, `_send`, `on_sync_reply`, `on_link_up`; [viewport/worker_client.gd](../viewport/worker_client.gd):`_process`; [viewport/main.gd](../viewport/main.gd):`_on_link_up`, `_on_properties`, `_on_length`.

## Commands and events

Examples are illustrative JSON lines; timing values, paths, IDs and hashes vary. Fields shown as optional below may be absent; explicit JSON `null` is not generally interchangeable with omission. Every command is dispatched by [worker/serve.py](../worker/serve.py):`serve.handle` (a nested function), except the length evaluator's reply, built by `length_input.handle`.

### `hello`

Request: `cmd: "hello"`, `seq?`. Success: `ok: true`, `cmd: "hello"`, `seq` (echo or null), `app: "shopsketch"`, `protocol: integer` (the protocol version, currently 7), `worker: string` (32 lowercase hex MD5), `pid: integer`. The window uses the worker only if `protocol` equals its own version and `worker` its own identity.

```json
{"cmd":"hello"}
{"ok":true,"cmd":"hello","seq":null,"app":"shopsketch","protocol":3,"worker":"0123456789abcdef0123456789abcdef","pid":1234}
```

Producer/consumer: [worker/serve.py](../worker/serve.py):`serve.handle`, `worker_identity`; [viewport/main.gd](../viewport/main.gd):`_probe_worker` (`_hello`, `_worker_of`). Probing uses a separate short-lived connection.

### `open`

Request: `cmd: "open"`, `model: string`, `fresh?: boolean = false`, `seq?: integer` (the window always sends one). Success: `ok: true`, `cmd: "open"`, `model: string` (absolute), `seq` (echo or null), `rev: integer`, `ops: Op[]`, `undo_floor: integer`, `external: boolean`, `reserved_ids: string[]` (protocol 7, T67: every ID the document has reserved, sorted; the window adds them to its own), `recovered?: {from: "new"|"prev", rev: integer, why: string}` (sent once, when opening found a save that stopped part way and put the newest whole file-and-journal pair in place, A32). `fresh` discards the cached/live document and starts empty; otherwise an existing cached session is reloaded if its disk signature changed. Opening does not export meshes or enqueue a save.

```json
{"cmd":"open","model":"/tmp/chair.FCStd","fresh":false,"seq":7}
{"ok":true,"cmd":"open","model":"/tmp/chair.FCStd","rev":3,"ops":[],"undo_floor":0,"external":false,"seq":7}
```

A refusal has exactly `ok: false`, `cmd: "open"`, `error: "already_open"`, `model: string`, `seq`. The owning connection receives a `focus` event. Other errors use the generic envelope below. On an outside edit, the worker adopts successful journal operations but prevents undo below `undo_floor`; without a valid journal it marks the file external. `undo_floor` counts operations, not FreeCAD transactions. Failed journal operations are omitted when reopening.

Producer/consumer: [worker/serve.py](../worker/serve.py):`serve.handle`, `session_for`, `claim`; [worker/session.py](../worker/session.py):`Session._open_existing`; [viewport/document.gd](../viewport/document.gd):`send_open`, `on_opened`; [viewport/main.gd](../viewport/main.gd):`_on_open` (first drops a reply `is_current_open` rejects; then adopts history and requests sync, or closes a duplicate launch/reverts a refused switch).

### `sync` and `replay`

| Request field | Type and meaning |
|---|---|
| `cmd` | `"sync"` or `"replay"`; replay starts a fresh session every time |
| `model?` | string; defaults to `<outdir>/model.FCStd` if omitted/empty; supplying neither usable model nor outdir fails |
| `oplog` | `{ops: Op[], units?: "mm", format?: string, name?: string, reserved_ids?: string[]}`; `format`/nested `name` are not validated/used by `run_sync`; `reserved_ids` (protocol 7, T67) is the window's reservations, added to the session's registry before the ops are checked |
| `ops` | alternate top-level Op array when `oplog` is absent |
| `outdir?` | string; export folder, defaults to parent of resolved model path |
| `seq?` | echoed correlation value; window sends integer; omitted becomes `null` |
| `drawing?` | boolean, default false; true enables drawings on subsequent saves of this session |
| `name?` | string, default `"live"`; becomes `result.oplog` (independent of nested oplog name) |
| `delay_ms?` | number; test hook, blocking sleep before dispatch for open/inspect/sync/replay/unknown commands |

A non-`mm` `oplog.units` is refused. The normal window supplies `oplog.format = "oplog/0.1"`, `units = "mm"`, `name = "Shop Sketch session"`; there is no schema validator for its format string.

```json
{"cmd":"sync","model":"/tmp/chair.FCStd","outdir":"/tmp/chair-out","seq":4,"drawing":false,"oplog":{"format":"oplog/0.1","units":"mm","name":"Shop Sketch session","ops":[]}}
{"ok":true,"cmd":"sync","seq":4,"wall_ms":1.2,"outdir":"/tmp/chair-out","result":{"oplog":"live","total_ms":0.1,"export_ms":0.8,"how":"nothing","ops":[],"rev":3,"model":"/tmp/chair.FCStd"}}
```

**Replay also replies with `cmd: "sync"`**, not `"replay"`. Success has `ok: true`, `cmd`, `seq`, `wall_ms: number`, `outdir: string`, `result: StatusResult`. `wall_ms` includes request handling/export but excludes deferred save. `outdir` is returned as supplied/defaulted, not forcibly made absolute.

| StatusResult field | Type and meaning |
|---|---|
| `oplog` | string, request's top-level name or `"live"` |
| `total_ms`, `export_ms` | number, sync/evaluation time and metadata/mesh export time |
| `how` | `"nothing"`, `"rebuilt"`, or `"undid N, applied M"` |
| `ops` | ordered OpStatus array, one per applied/requested operation |
| `rev` | integer, current saved rev + 1 if dirty (anticipated next save) |
| `model` | absolute model path |

OpStatus: `id: string`, `type: string`, `status: "ok" | "failed"`, `ms: number`; success normally includes `changed: string[]` (may be `null` if a handler returns no list); failure includes `message: string`. `changed` is a handler report, not an exhaustive geometry diff. Failed operations abort their transaction; later operations are still attempted. Thus request `ok: true` does **not** mean every operation succeeded. Example status: `{"id":"pp1","type":"push_pull","status":"failed","message":"unknown rect 'missing'","ms":0.2}`.

Sync keeps the common canonical op prefix, undoes the rest, then applies the new suffix. If required native undo is unavailable it rebuilds; crossing an external undo floor is a request error. Export and `status.json` finish before the reply. Changed/drawing sessions then enter the pending-save map; `saved` is a separate event after persistence.

Producer/consumer: [worker/serve.py](../worker/serve.py):`run_sync`, `serve.handle`; [worker/session.py](../worker/session.py):`canon`, `Session.sync`, `_apply`, `status`, `export`; [viewport/document.gd](../viewport/document.gd):`oplog`, `_send`, `on_sync_reply`; [viewport/main.gd](../viewport/main.gd):`_on_synced`, `_on_rejected`; [viewport/presenter.gd](../viewport/presenter.gd):`show_confirmed`, `apply_confirmed`.

### `length`

Request: `cmd: "length"`, `id?: correlation value`, `texts: string[]`, `default_unit?: "mm" | "cm" | "m" | "in" | "ft" = "mm"`. Texts are numeric length expressions, each stripped length 1–512 characters. Scalars inherit the default unit; explicit units override it. Success: `cmd: "length"`, `id` (echo, default `null`), `ok: true`, `values: number[]` in mm. Any evaluation failure returns `ok: false`, `error: string`, no partial `values`. It does not claim a model, export, save or echo `seq`.

```json
{"cmd":"length","id":7,"texts":["2in","1 + 2"],"default_unit":"mm"}
{"cmd":"length","id":7,"ok":true,"values":[50.8,3.0]}
{"cmd":"length","id":8,"ok":false,"error":"Unknown default unit"}
```

Producer/consumer: [worker/length_input.py](../worker/length_input.py):`handle`, `evaluate`; [worker/serve.py](../worker/serve.py):`serve.handle`; [viewport/main.gd](../viewport/main.gd):`apply_vcb`, `_on_length` (rejects replies after tool/model/seq/gesture state changes).

### `inspect_properties`

Request: `cmd: "inspect_properties"`, `model: string`, `body: string` (BodyId), `request_id: integer` (required on success), `seq?: integer`. Claims the model, so inspecting a different available model releases this connection's previous model. Refuses an already-owned model with the generic error. Success: `ok: true`, `cmd`, `seq` (or `null`), `model: absolute string`, `request_id`, `properties: PropertiesSnapshot`.

```json
{"cmd":"inspect_properties","model":"/tmp/chair.FCStd","body":"b1","seq":4,"request_id":9}
{"ok":true,"cmd":"inspect_properties","model":"/tmp/chair.FCStd","seq":4,"request_id":9,"properties":{"body":"b1","boards":{},"objects":[],"references":[]}}
```

The illustrative empty arrays above stand for the native data. Snapshot fields:

- `body: string`; `boards: {BodyId: StockFrame}` for every supported rectangular board (StockFrame below).
- `objects: ObjectDescription[]`: dependency traversal from selected body, excluding origin/axis/plane helper types. Each object: `name: string` (native key), `label: string`, `type: string` (FreeCAD TypeId), `fields: Field[]`.
- Field: `name: string` (display label), `path: string` (native property/subproperty), `value: string` (display value), `kind: "length" | "angle" | "number" | "text" | "bool" | "enum" | "link" | "read"`, `editable: boolean`, `expression: string` (empty if none), `choices?: string[]` (included for scalar properties; meaningful for enum). Placement translations are local mm; angles follow FreeCAD's degree display; vectors Origin/Step/Span are mm; other numeric/vector fields retain their native meaning. Links/shapes/read fields are display-only strings.
- `references: {name: string, label: string}[]`: all document objects with a Shape, for expression references.

Example field: `{"name":"Length","path":"Length","value":"400.0 mm","kind":"length","editable":true,"expression":"","choices":[]}`. Errors retain `request_id` (default `null`) even when inspection fails.

Producer/consumer: [worker/serve.py](../worker/serve.py):`serve.handle`; [worker/object_properties.py](../worker/object_properties.py):`inspect`, `related`, `describe`, `field`; [viewport/main.gd](../viewport/main.gd):`_request_properties`, `_on_properties`; [viewport/property_panel.gd](../viewport/property_panel.gd):`display`.

### `reload` and `keep_mine` (A36, T64)

After an `outside_save` event (below), the window answers with one of these. `reload`: request `cmd: "reload"`, `model`, `outdir`, `seq`; reply: the `open` reply's fields with `cmd: "reload"`, plus `changed` / `removed` (BodyIds whose box, volume, area, wood or hiding differ; BodyIds gone), `dropped` (ops the file's revision didn't hold) and `outdir` (bodies.json written there). `keep_mine`: request `cmd: "keep_mine"`, `model`, `outdir?`, `seq`; reply `ok`, `cmd: "keep_mine"`, `model`, `aside` (FreeCAD's file, copied to `<model>.freecad-<YYYYmmdd-HHMMSS>.FCStd`, `-2`... if taken), `rev` (ours, saved over it). A `flush`, `bye` or `quit` of a held model with unsaved actions does the same as `keep_mine`; its `saved` entries carry `aside`.

### `flush`, `bye`, `quit`

| Command | Request fields | Success reply | Effects |
|---|---|---|---|
| `flush` | `cmd`, `seq?`, `model?` | `cmd: "flush"`, `seq` (or null), the save lists | Attempts all pending saves across all clients (only `model`'s, when given: closing a window); connection stays open |
| `bye` | `cmd`, `seq?` | `cmd: "bye"`, `seq` (or null), the save lists | Attempts this connection's pending saves, releases ownership, closes socket |
| `quit` | `cmd`, `seq?` | `cmd: "quit"`, `seq` (or null), `stopped: boolean`, the save lists | With another connected client: false, save and release this connection only; otherwise save all pending and exit serve loop (even when a save failed: the window asked first, I55) |

The save lists (T79): `saved: [{model, rev}]` (the saves this request landed), `failed: [{model, rev, error}]` (the ones it couldn't; `rev` is the revision it tried). `ok` is true only when `failed` is empty; otherwise `error` names each model that couldn't be saved and why.

```json
{"cmd":"flush","seq":5}
{"ok":true,"cmd":"flush","seq":5,"saved":[{"model":"/tmp/chair.FCStd","rev":4}],"failed":[]}
{"cmd":"flush","seq":6,"model":"/tmp/chair.FCStd"}
{"ok":false,"cmd":"flush","seq":6,"saved":[],"failed":[{"model":"/tmp/chair.FCStd","rev":5,"error":"PermissionError: the folder tmp is read-only"}],"error":"couldn't save chair.FCStd: PermissionError: the folder tmp is read-only"}
{"cmd":"bye"}
{"ok":true,"cmd":"bye","seq":null,"saved":[],"failed":[]}
{"cmd":"quit"}
{"ok":true,"cmd":"quit","seq":null,"saved":[],"failed":[],"stopped":true}
```

Each row is an independent request/reply example, not one stream after bye. Save events may precede lifecycle acknowledgements. A save that fails stays pending (T79): the timer's autosave doesn't keep retrying it, but the next sync of that model, flush, bye or quit does, and each failed attempt sends `save_failed`. `quit.stopped` depends on **connections**, including probes, not just owned documents.

Producer: [worker/serve.py](../worker/serve.py):`serve.handle`, `save_pending`, `let_go`, `release`. Consumer: closing a window (`main.gd:_request_close`, `document.gd:begin_close`) waits for the sync in flight, sends `flush` with its `model`, and closes on an ok answer with the latest revision saved; otherwise it asks Retry / Close without saving / Cancel (I55; no answer in `CLOSE_WAIT_S` asks too). Then [viewport/main.gd](../viewport/main.gd):`_shutdown_worker` sends bye for a shared worker (waits up to 4 s) or quit for a private worker (then kills if still running); `document.gd:on_flush_reply` takes flush's answers; [worker/test_serve.py](../worker/test_serve.py) uses flush and checks lifecycle behaviour. `main.gd:_on_worker` sends flush replies to `document.gd:on_flush_reply` and drops bye and quit (an error one is shown in the status line); none reach sync state.

### `saved`, `save_failed`, `outside_save` and `focus` events

`outside_save` (A36): `cmd: "outside_save"`, `model`, `rev` (the file's ShopSketchRev), `unsaved: boolean` (actions not yet on disk). FreeCAD saved the open model; the worker holds it (no autosave writes over the file) until the window sends `reload` or `keep_mine`.


Both are unsolicited, worker → window only; there is no matching request or seq.

```json
{"ok":true,"cmd":"saved","model":"/tmp/chair.FCStd","rev":4}
{"ok":false,"cmd":"save_failed","model":"/tmp/chair.FCStd","rev":5,"error":"PermissionError: the folder tmp is read-only"}
{"ok":true,"cmd":"focus","model":"/tmp/chair.FCStd"}
{"ok":false,"cmd":"open","error":"already_open","model":"/tmp/chair.FCStd","seq":7}
```

`saved` includes `model: absolute string`, `rev: integer`, sent only to the owner after successful pending save. `save_failed` (T79) includes `model`, `rev` (the revision it tried; the session's own revision doesn't move, so the retry saves that one) and `error` (`ExceptionType: message`; a read-only folder says so), sent to the owner after each failed attempt; the window shows "Couldn't save: <message>" until a `saved` (I54). `focus` includes `model: absolute string`, sent to the existing owner when another connection's **open** is refused. Sync/inspection ownership errors do not send focus. The owner foregrounds its window; the refusing reply goes to the second connection.

Producer/consumer: [worker/serve.py](../worker/serve.py):`save_pending`, `serve.handle`; [viewport/main.gd](../viewport/main.gd):`_on_worker`, `_on_open`; [viewport/document.gd](../viewport/document.gd):`on_saved` (matches normalized model path; monotonically advances saved revision; clears `save_error`), `on_save_failed` (sets `save_error`, the message without the exception's name).

### Generic request errors

```json
{"cmd":"unrecognized","seq":6}
{"ok":false,"cmd":"unrecognized","error":"OpError: unknown cmd 'unrecognized'","seq":6}
```

Envelope: `ok: false`, `cmd: string | null`, `error: string` (`ExceptionType: message`), `seq: echoed value | null`. Invalid JSON can yield null cmd/seq. Inspection additionally echoes `request_id`. The special `already_open` refusal and evaluator errors have their own envelopes above. Unknown commands fail rather than being ignored. No standalone `saved`, `focus`, `property_edit`, undo or redo command exists; the latter edits are represented by changing the desired operation list.

Producer/consumer: [worker/serve.py](../worker/serve.py):`serve.handle`; [worker/length_input.py](../worker/length_input.py):`handle`; [viewport/main.gd](../viewport/main.gd):`_on_worker`; [viewport/document.gd](../viewport/document.gd):`on_sync_reply`.

## Operation payloads (`oplog/0.1`)

All Ops have `id: string` and `type: string`; IDs are journal identities and should be stable/unique within the sequence. New IDs (T67, protocol 7) are `<prefix><serial>_<32 lowercase hex>` (128 random bits), e.g. `b3_0123…cdef`; the worker refuses a sync whose new-style ID collides with another or changes owner (`ID collision` / `ID already reserved`), and old serial IDs (`b3`, `pp7`) are accepted as they always were. Displays show the serial part only (`Board 3`, `pp7`). The worker canonicalizes numbers to 9 decimal places for prefix comparison (18 equals 18.0). Every accepted op creates one native transaction. This table describes fields read by current handlers, rather than promising complete upfront validation. Unknown fields are generally ignored. Source dispatch: [worker/model.py](../worker/model.py):`Model.HANDLERS`, `apply`.

FaceRef = `{body: string, normal: Vec3, point: Vec3}`: world face identified geometrically, never FreeCAD face number. Plane = `{normal: Vec3, origin: Vec3, xdir?: Vec3}` or `{on: FaceRef, xdir?: Vec3}`. Normal/direction inputs are normalized; plane xdir is projected into its plane. Without xdir, horizontal planes use world X, others use world Z cross normal; y = normal cross x. Source: [worker/model.py](../worker/model.py):`resolve_face`, `plane_from`.

| Type | Fields beyond id/type | Source |
|---|---|---|
| `rect` | `plane: Plane`, `size: [number,number]` positive mm, `corner?: [number,number] = [0,0]` plane-local mm | [push.py](../worker/push.py):`PushActions.op_rect` |
| `circle` | `plane: Plane`, `radius: number` finite, at least 0.001 mm; `center?: [number,number] = [0,0]` plane-local mm. Native fully constrained sketch circle; shares the profile namespace (`RectId`) with rectangles. Viewport allocates `r` IDs for both. | [circle.py](../worker/circle.py):`CircleActions.op_circle` |
| `line` | `plane: Plane` (the drawing's plane; the start point is its origin), `end: [x,y,z]` world mm; `outline?: [[x,y,z], ...]` ordered world-mm polygon with no repeated final vertex, on the segment that closes a loop (makes a line profile with this op's id as `RectId`); `snap_start?`, `snap_end?: boolean` keep a snap to existing geometry across the 0.1 mm gap between native-edge and face tessellations (unsnapped ends keep 0.001 mm). Points are projected onto the plane. Changes no solid. Viewport allocates `r` IDs. | [line.py](../worker/line.py):`LineActions.op_line` |
| `push_pull` | `target: {rect: string}` (rectangle, circle or line profile ID) or `{face: FaceRef}`, optionally with `region: {outline, holes, normal, lines}` (a drawn cell, T82: full-precision world-mm points, the saved line ids that bound it; with `face` or `rect` it must fit that source, alone it is free closed stock; the worker validates coplanarity, simple outlines, holes, normal, containment and the line references), `distance: number` nonzero signed mm along normal; `body?: string` requests new/separate BodyId (otherwise a free profile defaults to `<id>_body`); `assembly?: string` new board's assembly; `through?: boolean = false` for negative cuts; `resize_stock?: boolean`; `edge_fit?: {target_body: string, face: integer, fit_mode?: integer = 0}`; `to_face?: {normal: Vec3, point: Vec3}` (T59, H090: world mm, an earlier pocket's floor the cut goes to; the cut is tied to that floor by expression; only on a cut into a board, `distance < 0`, without `through`, `edge_fit`, `resize_stock` or `body`, else `to_face is only for a cut into a board`; no window sends it yet, so no protocol bump until one does) | [push.py](../worker/push.py):`PushActions.op_push_pull` |
| `move` | `targets: string[]`, `vector: Vec3`; `copy?: boolean = false`, `count?: integer = 1` copies excluding original, `divide?: boolean = false` distributes copies across vector instead of repeating vector; `new_ids?: string[]` consumed target-by-target, then copy-by-copy (fallback `<target>_<i+1>` for i starting 1); `selection?: boolean`, `detach?: boolean`; `groups?: {old AssemblyId: new AssemblyId}` for copying whole assemblies once | [move.py](../worker/move.py):`MoveActions.op_move`, `move_selection` |
| `move` with cut | additionally `cut: {body: string, op: string}` selects a rectangular cutter/row; same vector/copy/count/divide fields; targets may be empty; new_ids unused for cutter arrays | [move.py](../worker/move.py):`MoveActions.move_cut` (called by `op_move`) |
| `mirror` | `targets: string[]`, `plane: {point: Vec3, normal: Vec3}`, `replace?: boolean = false`, `new_ids?: string[]` (fallback `<target>_m`), `group?: string` mirror assembly ID if originals ungrouped; replacement retains original BodyId | [mirror.py](../worker/mirror.py):`MirrorActions.op_mirror` |
| `make_component` | `body: string`, `name: string` | [move.py](../worker/move.py):`MoveActions.op_make_component` |
| `detach` / `make_unique` | `targets: string[]`; detach clears array membership; unique deep-copies shared definition | [move.py](../worker/move.py):`MoveActions.op_detach`, `op_make_unique` |
| `make_assembly` | `targets: string[]`, `new_id: string`, `name?: string = new_id` | [assembly.py](../worker/assembly.py):`AssemblyActions.op_make_assembly` |
| `set_material` | `targets: string[]`, `material: string` library key (empty clears); linked definitions share material | [paint.py](../worker/paint.py):`PaintActions.op_set_material` |
| `turn_grain` | `targets: string[]`; toggles definition's longest/middle axis, including linked siblings | [paint.py](../worker/paint.py):`PaintActions.op_turn_grain` |
| `hide` | `targets: string[]`, `hidden?: boolean = true` | [visibility.py](../worker/visibility.py):`VisibilityActions.op_hide` |
| `delete` | `targets: string[]`, deduplicated; invalid target aborts whole action; preserves definitions still needed by survivors | [deletion.py](../worker/deletion.py):`DeleteActions.op_delete` |
| `property_edit` | `body: string`, `object: string` native name, `property: string` native path, `value: string`, `mode: "value" | "expression"`; `expected?: {value: string, expression: string}` guards stale forms | [object_properties.py](../worker/object_properties.py):`apply`; [model.py](../worker/model.py):`Model.op_property_edit` |
| `property_edit`, plane fit | `mode: "plane_fit"`, `body: string`, `target_body: string`, `axis: integer 0..2`, `face: integer 0..5`, `fit_mode: integer 0..2`, `reverse?: boolean = false`; no object/property/value required | [plane_fit.py](../worker/plane_fit.py):`apply` |
| `property_edit`, replace fit | `mode: "replace_fit"`, `body: string`, `axis: integer` matching existing fit, `value: string` positive length; restores plain stock and detaches fit | [plane_fit.py](../worker/plane_fit.py):`replace`, `_restore` |

Plane-fit faces: 0 Left, 1 Right, 2 Front, 3 Back, 4 Bottom, 5 Top in **target stock-local axes**. Modes: 0 Butt to plane, 1 Slice at plane, 2 Fully reach plane. Axis 0/1/2 denotes source stock length/width/extrusion axis, not necessarily world X/Y/Z. Selection moves resolve shared sources once; assembly rows are currently refused. Handler rejection is conveyed through OpStatus, not a separate command.

Example minimal board op list:

```json
[{"id":"r1","type":"rect","plane":{"normal":[0,0,1],"origin":[0,0,0]},"size":[400,300]},
 {"id":"pp1","type":"push_pull","target":{"rect":"r1"},"distance":18,"body":"b1"}]
```

Other representative payloads:

```json
[{"id":"mv1","type":"move","targets":["b1"],"vector":[0,0,100],"copy":true,"new_ids":["b2"]},
 {"id":"m1","type":"mirror","targets":["b1"],"plane":{"point":[600,0,0],"normal":[1,0,0]},"new_ids":["b3"]},
 {"id":"pr1","type":"property_edit","body":"b1","object":"Plane","property":"Length","value":"450mm","mode":"value"}]
```

## Shared files

### Publication and locations

`run_sync` writes `bodies.json`, changed mesh files, the material library (once per output folder per worker), and `status.json` into outdir before success. Save writes `model.glb` into the pending save's outdir, the actual model into its requested path, and its journal beside it; drawing saves also write `views.json`. If several syncs coalesce before saving, the latest pending outdir for that model wins. Paths are not a remote transfer mechanism.

JSON outputs other than materials use `atomic_json` (`<path>.tmp`, then `os.replace`). Mesh and GLB also use temp + rename. These individual publications are atomic, not a transaction across all files. `.FCStd` uses `<model>.saving.FCStd` then rename; journal is written **after** that rename. `materials.json` is a direct write. Sources: [worker/serve.py](../worker/serve.py):`run_sync`, `serve.save_pending`; [worker/session.py](../worker/session.py):`atomic_json`, `Session.export`, `save`; [worker/export.py](../worker/export.py):`board_mesh_file`, `write_glb`; [worker/materials.py](../worker/materials.py):`write_library`.

### `bodies.json`

JSON array, one entry per live board, including hidden boards and excluding deleted/source/definition objects. Source: [worker/session.py](../worker/session.py):`Session.export`; consumers [viewport/presenter.gd](../viewport/presenter.gd):`apply_confirmed`, `_build_board`, `_load_cuts`; [viewport/selection.gd](../viewport/selection.gd):`set_boards`; [viewport/main.gd](../viewport/main.gd):`_on_boards_read`.

| Field | Type and meaning |
|---|---|
| `id` | string BodyId |
| `material` | string material key, empty if unassigned |
| `component` | string component name or null; mirrors append `" (mirrored)"` |
| `grain`, `across` | Vec3 world directions, dimensionless, rounded to 6 places |
| `world_bbox` | `[xmin,ymin,zmin,xmax,ymax,zmax]` world mm |
| `size` | three sorted ascending local extents, mm, rounded to 2 places; not axis-labelled |
| `volume_mm3` | number, world solid volume rounded to 1 place |
| `cuts` | `{op: string, kind: "cut", lo: Vec3, hi: Vec3}[]`, world mm cutter bounds clipped to board bounds where intersecting; one per cutter solid/array copy, rectangular drawn cuts only |
| `stock_frame` | StockFrame or null |
| `mesh` | basename string, resolved as `<outdir>/meshes/<mesh>` |
| `color` | `[r,g,b]` numbers, nominal 0..1 |
| `family` | string shared native definition name, empty unless at least two exported boards share it |
| `array` | string native array holder name or empty |
| `assembly` | string AssemblyId or empty |
| `row` | string row source BodyId or empty |
| `hidden` | boolean |
| `mirror_plane` | `[]` or `[point: Vec3, normal: Vec3]` world mm/dimensionless |

StockFrame, from [worker/plane_fit.py](../worker/plane_fit.py):`snapshot`: `label: string`, `origin: Vec3` world mm, `axes: [Vec3,Vec3,Vec3]` unit world directions, `sizes: [number,number,number]` local length/width/extrusion mm; `plane: string`, `extrusion: string` native names; `fitted: boolean`, `reverse: boolean`, `linked_axis: integer` (-1 when absent, otherwise 0..2), `result: string` display summary. Only supported direct rectangular stock produces this snapshot; unsupported/link/mirror shapes can yield null.

Example entry (board from the minimal ops above):

```json
[{"id":"b1","material":"","component":null,"grain":[1,0,0],"across":[0,1,0],"world_bbox":[0,0,0,400,300,18],"size":[18,300,400],"volume_mm3":2160000,"cuts":[],"stock_frame":{"label":"Board 1","origin":[0,0,0],"axes":[[1,0,0],[0,1,0],[0,0,1]],"sizes":[400,300,18],"plane":"Plane","extrusion":"Extrusion","fitted":false,"reverse":false,"linked_axis":-1,"result":""},"mesh":"b1-0123456789abcdef.bin","color":[0.82,0.8,0.76],"family":"","array":"","assembly":"","row":"","hidden":false,"mirror_plane":[]}]
```

Labels/native object names and geometry-derived mesh keys are illustrative. `cuts` is not a full boolean feature history. Source: [worker/export.py](../worker/export.py):`cuts_of`, `component_of`, `material_of`, `material_color`.

### `meshes/<BodyId>-<key>.bin`

`key` is first 16 SHA-1 hex characters of `repr(shape_key(obj))`, an in-process native geometry/placement identity, not a portable content hash. Files contain **four consecutive arrays**, with no file header, version marker or alignment padding between them:

| Order | Array data |
|---|---|
| 1 | triangle positions: three Vec3 per triangle, clockwise viewed from outside |
| 2 | normals: one dimensionless outward Vec3 per triangle vertex |
| 3 | edge segments: two position Vec3 per segment (curves discretized with 0.1 mm deflection) |
| 4 | corners: FreeCAD topological vertex positions |

Each array: little-endian `uint32 tag = 36` (PackedVector3Array), `uint32 count`, then `count × 3` little-endian float32 components. Byte length `8 + count * 12`. Positions are world Z-up **mm**; normals are dimensionless. Triangles tessellate at 0.1 mm deflection. For example, an array containing `[1,2,3]` begins with hex `24 00 00 00 01 00 00 00 00 00 80 3f 00 00 00 40 00 00 40 40`.

The worker writes only absent geometry keys and removes the previous file tracked for that board/outdir when the name changes. The viewport caches built nodes, so old states need not reread removed files. There is no comprehensive orphan-file cleanup or validation of a supplied mesh's tags/lengths in the consumer. Sources: [worker/export.py](../worker/export.py):`shape_key`, `_pv3`, `board_mesh_file`; [viewport/presenter.gd](../viewport/presenter.gd):`_build_board` (`decode_u32` count and `bytes_to_var`), `_remember_state`.

### `materials.json`

Array of library entries, in species insertion order. Fields: `key: string`, `name: string`, `uuid: string`, `color: [number,number,number]`, `texture: string` JPEG basename, `grain: "u" | "v"` texture grain axis, `size_mm: number` square texture extent, `end_texture: string` JPEG basename, `end_size_mm: number`. Consumer resolves textures in project/bundle `materials/textures`, not relative to outdir. Example entry: `{"key":"white-oak","name":"White Oak","uuid":"9b5e3aa9-aa43-5250-bdc5-2c87fffe21a0","color":[0.809,0.668,0.456],"texture":"Wood022.jpg","grain":"u","size_mm":600,"end_texture":"white-oak_end.jpg","end_size_mm":175}`.

Sources: [worker/materials.py](../worker/materials.py):`library`, `material_uuid`, `write_library`; [worker/session.py](../worker/session.py):`Session.export`; [viewport/main.gd](../viewport/main.gd):`_load_wood_library`, `_wood_material`.

### `model.glb`

Binary glTF 2.0 for renders, written at save (not each sync), excluding hidden boards. GLB header: magic `glTF`, version 2, total byte length (little-endian u32). JSON chunk is padded with spaces to 4-byte alignment; nonempty scenes also have a BIN chunk with padded vertex/normal data. Empty model has a JSON-only valid empty scene.

JSON fields written by `write_glb`: `asset: {version: "2.0", generator: "Shop Sketch worker 0.2"}` (generator absent for empty scene), `scene: 0`, `scenes: [{nodes: integer[]}]`, `nodes`, `meshes`, `materials`, `accessors`, `bufferViews`, `buffers`. Each node: `name: BodyId`, `mesh: integer`, `extras: {body_id: string, material: string, component: string|null, grain_zup: Vec3, across_zup: Vec3, state: "confirmed"}`. Grain extras remain **Z-up**, unlike converted vertex geometry.

Each mesh: `name: BodyId`, `primitives: [{attributes: {POSITION: accessor index, NORMAL: accessor index}, material: material index}]`; unindexed triangles, float32 VEC3 accessors (`componentType = 5126`, count = vertex count); POSITION includes min/max. BufferView has buffer 0, byteOffset, byteLength and target 34962; buffers has byteLength. Materials: `name` (key or `"unassigned"`), `pbrMetallicRoughness: {baseColorFactor: [r,g,b,1], metallicFactor: 0, roughnessFactor: 0.8}`; wood materials add `extras: {wood: string, texture: absolute JPEG path, texture_grain_along: string, texture_size_mm: number, end_texture: absolute JPEG path, end_size_mm: number}`. Textures are external metadata, not embedded glTF textures/UVs. Example node: `{"name":"b1","mesh":0,"extras":{"body_id":"b1","material":"","component":null,"grain_zup":[1,0,0],"across_zup":[0,1,0],"state":"confirmed"}}`.

Source: [worker/export.py](../worker/export.py):`mesh_of` (Y-up metres), `write_glb`; [worker/session.py](../worker/session.py):`Session.save`. The viewport consumes per-board mesh files, not this render export.

### Model `.FCStd` and `<stem>.shopsketch.json` journal

The native FreeCAD model is authoritative; its archive includes `Document.xml`, native shape data and `GuiDocument.xml`. `Session.save` increments document Meta `ShopSketchRev` (string integer), saves a copy, optionally regenerates TechDraw there, injects/preserves visibility/view metadata, then replaces the model. The journal filename replaces `.FCStd`, e.g. `/tmp/chair.shopsketch.json`, not `/tmp/chair.FCStd.shopsketch.json`.

Journal fields: `format: "shopsketch-journal/0.1"`, `rev: integer`, `file_sha256: string` (64 hex of landed FCStd bytes), `model: string` basename including extension, `name: string` stem, `ops: Op[]`, `status: JournalStatus[]` in corresponding order. JournalStatus has `status: "ok" | "failed"`, `ms: number`, optional `changed: string[] | null`, optional `message: string`; id/type are in the matching op, not duplicated in status.

```json
{"format":"shopsketch-journal/0.1","rev":4,"file_sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","model":"chair.FCStd","name":"chair","ops":[],"status":[]}
```

On reopen, revision/hash equality establishes that model matches journal. Only successful ops are adopted. Missing/wrong-format journal or a mismatched rev/hash marks external; the surviving history becomes an undo floor. Model and journal publication are separate atomic replacements; interruption between them can therefore be detected as an external/mismatched state. Sources: [worker/common.py](../worker/common.py):`JOURNAL_FORMAT`; [worker/session.py](../worker/session.py):`journal_path`, `Session.save`, `_open_existing`, `write_gui_document`.

Journal fields added by T67 (H059): `reserved_ids` (sorted strings: every ID reserved, kept when ops are undone or dropped) and `id_owners` (`{id: owner}`, which op made each ID, stable across typed amendments); both optional, an older journal opens as before.

Journal fields added by T64 (A36): `floor` (undo stops here: ops before it can't be taken back, A25; kept across saves and sessions), `dropped` (`[{op, after_rev, at}]`: actions an outside save didn't hold, for T65), `outside_sha256` (written the moment an outside save is seen; opening a file with that sha opens it external instead of recovering, A32).

Journal field added by A38 (H087, protocol 8): `floor_copy` (`{sha256, ops}`: the sha256 of `<model>.floor.FCStd`, a copy of the document as it stood at the undo floor, and the floor it was written at); optional, written only when the floor came from a FreeCAD change. A journal without it reads as no copy: undoing past the floor then needs a rebuild that is refused (`can't undo past the FreeCAD edit: its copy is missing`) rather than one that would drop FreeCAD's change.

### `status.json`, `views.json`, startup port file

`status.json` contains exactly the StatusResult inside the latest sync reply, without the outer ok/cmd/seq/wall_ms/outdir fields. Example: `{"oplog":"live","total_ms":0.1,"export_ms":0.8,"how":"nothing","ops":[],"rev":4,"model":"/tmp/chair.FCStd"}`. Source: [worker/serve.py](../worker/serve.py):`run_sync`.

`views.json` is an object `{Front: string, Top: string, Right: string, Iso: string}` containing TechDraw SVG markup, e.g. `{"Front":"<svg>...</svg>","Top":"<svg>...</svg>","Right":"<svg>...</svg>","Iso":"<svg>...</svg>"}`. It is refreshed only by drawing saves; an old file can remain otherwise. The saved copy also contains the native Drawing page, Template and views; the live document does not. Sources: [worker/export.py](../worker/export.py):`add_drawing_page`; [worker/session.py](../worker/session.py):`Session.save`.

The optional `SERVE_PORT_FILE` is plain decimal text with LF, e.g. `49152\n`, atomically replaced through `.tmp`. The test window reads/deletes it. Sources: [worker/serve.py](../worker/serve.py):`serve`; [viewport/main.gd](../viewport/main.gd):`_await_port_file`.

## Findings from comparing producer and consumer

These are observed code limitations/mismatches, not changes made by the original documentation job. Separately completed fixes are marked below.

1. **Fixed: wire protocol version.** `hello` now carries `protocol` (currently 2; `serve.PROTOCOL_VERSION`, `main.gd PROTOCOL_VERSION`, bumped when a message or file field changes), and `main.gd:_worker_of` refuses a worker reporting another version, as it does a different implementation MD5 (the window starts its own). Still not done: no negotiation, and the oplog format string is emitted but not validated. Checks: `worker/test_serve.py` (hello carries the version both sides define), quick section `protocol`. Was: no wire protocol version; `hello` carried only an implementation MD5. Sources: `serve.handle`, `serve.PROTOCOL_VERSION`; `main.gd:_probe_worker`, `_worker_of`; `document.gd:oplog`.
2. **Fixed (T70 / H042): lifecycle replies are routed by cmd.** `main.gd:_on_worker` passes only `sync` replies to `on_sync_reply`; lifecycle replies are dropped (errors shown), and `on_sync_reply` itself ignores any reply whose seq isn't the request in flight. Original finding: **Lifecycle replies are not routed in the general client.** `main.gd:_on_worker` handles open/length/inspect/focus/saved, then forwards every other dictionary to `document.gd:on_sync_reply`. A normal `flush`/hello/bye/quit success has no result and can reach sync-only logic (null/missing seq or missing result). Current app hello uses its own probe; shared shutdown reads raw bytes; flush is used by socket tests. The issue concerns using these commands through the ordinary reply signal. Sources: `serve.handle`; `main.gd:_on_worker`, `_probe_worker`, `_shutdown_worker`; `document.gd:on_sync_reply`.
3. **Fixed (T78 / H038): drawing intent while busy.** `document.gd:request_drawing` retains a per-model pending flag while a sync is in flight. The next `_send` carries `drawing: true` alongside the latest ops and consumes the flag; later ordinary syncs send false. `reset` clears queued intent when switching models. Once enabled, the worker's session drawing flag stays true. Sources: `document.gd:request_drawing`, `_send`, `on_sync_reply`, `reset`; `serve.run_sync`.
4. **Fixed (T70 / H042): open replies are correlated.** The window sends `seq` with every open and the worker echoes it (with the absolute model) on success, refusal and error; `document.gd:is_current_open` drops a reply that isn't for the latest open and the current model. Original finding: **Open replies lack freshness correlation.** `open` success/refusal does not echo seq, and `main.gd:_on_open` does not compare returned model against current model before adopting ops. Unlike sync/inspection, rapid switches cannot distinguish a stale open response by request identity. Sources: `serve.handle`; `document.gd:send_open`, `on_opened`; `main.gd:_on_open`.
5. **Fixed (T79, H048): a failed save stays pending and is reported.** `save_pending` keeps a failed save (retried on the next sync, flush, bye or quit, not by the timer), sends `save_failed`, and flush / bye / quit answer with `saved` / `failed` lists, `ok` only when nothing failed; closing a window waits for its latest revision (I54, I55). Checks: `worker/test_serve.py` (a read-only folder), `viewport/test_document.gd`, quick section `save_failure`. Was: `save_pending` logs exceptions, removes the pending entry, and flush/bye/quit can still reply ok; only `saved` positively acknowledges a landed revision. The window's shutdown wait is bounded rather than a guaranteed saved-revision handshake. Sources: `serve.save_pending`, `serve.handle`; `main.gd:_shutdown_worker`; `document.gd:on_saved`.
6. **Replay's reply command is sync.** This is the implemented alias, so a consumer correlating reply cmd strictly to replay would fail. Current window sends sync, not replay. Sources: `serve.handle`; `document.gd:_send`.
7. **Nested oplog name is ignored for status naming.** The window sends `oplog.name`; `run_sync` uses top-level `name`, so its normal status says `oplog: "live"`. Sources: `document.gd:oplog`, `_send`; `serve.run_sync`.

H035 was read-only on code. Findings not marked fixed remain for integrator review and any separately authorized fixes.
