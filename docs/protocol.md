# Window ↔ worker protocol

The wire protocol's version is **18**: the worker reports it in `hello` (`protocol`), defined once per side (`worker/serve.py` `PROTOCOL_VERSION`, `viewport/main.gd` `PROTOCOL_VERSION`). **Rule: bump it on both sides when a message or a shared-file field changes** (added, removed, renamed or its meaning changed), and update this document. There is no negotiation: a window shares a worker only when the version matches. Existing embedded format identifiers are `oplog/0.1` and `shopsketch-journal/0.1`; binary meshes use Godot's Variant array encoding. Version history, job tags and the old producer/consumer findings: [protocol-archive.md](protocol-archive.md).

## Transport, identity and lifetime

Each TCP stream carries UTF-8 JSON objects, one per LF-terminated line, on `127.0.0.1`. A packet may contain partial or multiple lines; both ends buffer until LF. The worker ignores blank lines. The client emits replies only for parsed JSON dictionaries; the worker catches malformed requests and replies with an error. There is no authentication, request-size limit or per-request cancellation. Geometry travels through shared local files, not TCP. Paths must be accessible to both processes.

Sources: [worker/serve.py](../worker/serve.py):`serve`, nested `handle`/`send`; [viewport/worker_client.gd](../viewport/worker_client.gd):`send`, `_process`, `_drain`.

The window probes port 7878 using `hello`. A worker reporting another protocol version (or none) is treated like one with a different identity: the window starts its own and prints a `SHOPSKETCH ... speaks protocol` line. Identity is the MD5 of the concatenated contents of the worker's immediate `.py` files, sorted by filename, excluding `test_*` (not recursive). A matching worker is shared; an occupied port with a different identity leads to a private worker. Tests use `SERVE_PORT=0` and an atomic `SERVE_PORT_FILE` containing the chosen decimal port and LF. `SERVE_PORT` selects serve mode in `serve.main`; absent it, `OPLOG` and `OUTDIR` select one-off replay, with drawing and immediate save, without TCP.

Sources: [worker/replay.py](../worker/replay.py):entry point; [worker/serve.py](../worker/serve.py):`worker_files`, `worker_identity`, `main`, `serve`; [viewport/worker_process.gd](../viewport/worker_process.gd):`worker_identity`, `probe_worker`, `hello`, `worker_of`, `pick_worker`, `_start_worker`, `_await_port_file`.

One worker holds many sessions but evaluates requests serially on one thread. One connection owns at most one model at a time. Ownership keys are `os.path.abspath` paths, without symlink resolution or OS-wide file locking. Claiming a different available model saves and releases the old one; claiming an occupied model leaves the current ownership alone. Released sessions remain cached. Disconnection saves/releases owned models. Autosave waits for **all** clients to be quiet for 0.25 s after the last handled request. `SERVE_IDLE_EXIT` seconds after the last connection leaves saves pending work and exits the worker (0 disables; macOS app supplies 10 s for the shared worker windows start).

Sources: [worker/serve.py](../worker/serve.py):`serve`, nested `claim`, `let_go`, `release`, `session_for`, `save_pending`.

## Types, units and correlation

Notation: `number` is a JSON number; `integer` is an integral number; `Vec3` is `[number, number, number]`; `?` means optional. IDs and paths are strings. Unless explicitly stated otherwise, points, offsets, sizes and bounding boxes use **millimetres in right-handed world Z-up coordinates**. Normals and grain directions are dimensionless. Durations ending `_ms` and per-op `ms` are milliseconds. Revisions are integers scoped to one saved model; they are different from request `seq`.

The window converts `(x,y,z)` mm to `(x,z,-y)/1000` metres for Godot. The mesh file stays in model coordinates; GLB has already been converted to Y-up metres. Sources: [viewport/main.gd](../viewport/main.gd):`m2g`, `g2m`; [viewport/presenter.gd](../viewport/presenter.gd):`_build_board`; [worker/export.py](../worker/export.py):`mesh_of`, `board_mesh_file`.

`document.gd` owns monotonic `seq` and coalesces desired-state syncs: one request in flight, newest state sent after its answer if dirty. A successful sync answer is applied only when its `seq` equals the current sequence and no newer state is waiting. Failures of the request in flight are reported before that freshness check. One name per meaning: `seq` = the model's state, `request_id` = which request of mine this is, `id` = an op. `inspect_properties` echoes both `seq` and `request_id`; `length` echoes `request_id` (no `seq`). Every other reply (open, hello, flush, bye, quit, errors) echoes the request's `seq`, `null` when the request had none; events (`saved`, `focus`) carry none. Only the reply whose `seq` is the request in flight clears `in_flight`, so an answer from before a reconnect can't stop the next sync being sent. `send_open` advances `seq` and remembers it as the open's; `document.gd:is_current_open` accepts an open reply (success, refusal or error) only with that `seq` and, when it names one, the current model. `main.gd:_on_worker` routes by `cmd`: only `sync` replies reach `on_sync_reply`.

On reconnect the TCP client retries every 0.5 s and drains queued lines; the document reopens if never opened, otherwise resends its full desired op list. This is state reconciliation, not exactly-once delivery. Sources: [viewport/document.gd](../viewport/document.gd):`sync`, `_send`, `on_sync_reply`, `on_link_up`; [viewport/worker_client.gd](../viewport/worker_client.gd):`_process`; [viewport/main.gd](../viewport/main.gd):`_on_link_up`, `_on_properties`, `_on_length`.

## Commands and events

Examples are illustrative JSON lines; timing values, paths, IDs and hashes vary. Fields shown as optional below may be absent; explicit JSON `null` is not generally interchangeable with omission. Every command is dispatched by [worker/serve.py](../worker/serve.py):`serve.handle` (a nested function), except the length evaluator's reply, built by `length_input.handle`.

<!-- protocol map: built by tools/protocol_map.py; don't edit by hand -->

| Message | Kind | Request fields | Reply / payload keys | Handler |
|---|---|---|---|---|
| `length` | command | `request_id?`, `default_unit?`, `texts` | `cmd`, `request_id`, `ok`, `values`, `error` | `worker/length_input.py:handle` |
| `hello` | command | `seq?` | `ok`, `cmd`, `seq`, `app`, `protocol`, `worker`, `pid` | `worker/serve.py:serve.handle` |
| `quit` | command | `seq?` | `ok`, `cmd`, `seq`, `**saves`, `**extra`, `error?`, `stopped` | `worker/serve.py:serve.handle` |
| `bye` | command | `seq?` | `ok`, `cmd`, `seq`, `**saves`, `**extra`, `error?` | `worker/serve.py:serve.handle` |
| `flush` | command | `model`, `seq?` | `ok`, `cmd`, `seq`, `**saves`, `**extra`, `error?` | `worker/serve.py:serve.handle` |
| `open` | command | `model`, `fresh?`, `seq?` | `ok`, `cmd`, `error`, `model`, `seq`, `rev`, `ops`, `undo_floor`, `external`, `reserved_ids`, `units?`, `recovered?` | `worker/serve.py:serve.handle` |
| `reload` | command | `model`, `outdir?`, `seq?` | `ok`, `cmd`, `model`, `rev`, `ops`, `undo_floor`, `external`, `seq`, `reserved_ids`, `units?`, `recovered?`, `outdir`, `**info` | `worker/serve.py:serve.handle` |
| `keep_mine` | command | `model`, `outdir?`, `seq?` | `ok`, `cmd`, `model`, `aside`, `rev`, `seq` | `worker/serve.py:serve.handle` |
| `set_units` | command | `model`, `units?`, `seq?` | `ok`, `cmd`, `model`, `units`, `rev`, `seq` | `worker/serve.py:serve.handle` |
| `inspect_properties` | command | `model`, `request_id`, `body`, `seq?` | `ok`, `cmd`, `seq`, `model`, `request_id`, `properties` | `worker/serve.py:serve.handle` |
| `sync` | command | `model?`, `outdir`, `ops`, `oplog`, `drawing?`, `name?`, `seq?` | `ok`, `cmd`, `result`, `outdir`, `seq`, `wall_ms` | `worker/serve.py:serve.handle` |
| `focus` | event | — | `ok`, `cmd`, `model` | `worker/serve.py:serve.handle` |
| `outside_save` | event | — | `ok`, `cmd`, `model`, `rev`, `unsaved` | `worker/serve.py:serve.hold` |
| `save_failed` | event | — | `model`, `rev`, `error`, `ok`, `cmd` | `worker/serve.py:serve.save_pending` |
| `saved` | event | — | `ok`, `cmd`, `model`, `rev` | `worker/serve.py:serve.save_pending` |

<!-- end protocol map -->

### `hello`

Request: `cmd: "hello"`, `seq?`. Success: `ok: true`, `cmd: "hello"`, `seq` (echo or null), `app: "shopsketch"`, `protocol: integer` (the protocol version, currently 18), `worker: string` (32 lowercase hex MD5), `pid: integer`. The window uses the worker only if `protocol` equals its own version and `worker` its own identity.

```json
{"cmd":"hello"}
{"ok":true,"cmd":"hello","seq":null,"app":"shopsketch","protocol":18,"worker":"0123456789abcdef0123456789abcdef","pid":1234}
```

Producer/consumer: [worker/serve.py](../worker/serve.py):`serve.handle`, `worker_identity`; [viewport/worker_process.gd](../viewport/worker_process.gd):`probe_worker` (`hello`, `worker_of`). Probing uses a separate short-lived connection.

### `open`

Request: `cmd: "open"`, `model: string`, `fresh?: boolean = false`, `seq?: integer` (the window always sends one). Success: `ok: true`, `cmd: "open"`, `model: string` (absolute), `seq` (echo or null), `rev: integer`, `ops: Op[]`, `undo_floor: integer`, `external: boolean`, `reserved_ids: string[]` (protocol 7: every ID the document has reserved, sorted; the window adds them to its own), `units?: string` (protocol 9: the model's display units as `<format>:<rounding>`, e.g. `in-frac:1/16`, from Meta `ShopSketchUnits`; omitted when the file has none or an unreadable value, and the window then uses the last units used, I62), `recovered?: {from: "new"|"prev", rev: integer, why: string}` (sent once, when opening found a save that stopped part way and put the newest whole file-and-journal pair in place, A32). `fresh` discards the cached/live document and starts empty; otherwise an existing cached session is reloaded if its disk signature changed. Opening does not export meshes or enqueue a save.

```json
{"cmd":"open","model":"/tmp/chair.FCStd","fresh":false,"seq":7}
{"ok":true,"cmd":"open","model":"/tmp/chair.FCStd","rev":3,"ops":[],"undo_floor":0,"external":false,"seq":7}
{"ok":false,"cmd":"open","error":"already_open","model":"/tmp/chair.FCStd","seq":7}
```

A refusal has exactly `ok: false`, `cmd: "open"`, `error: "already_open"`, `model: string`, `seq`. The owning connection receives a `focus` event. Other errors use the generic envelope below. On an outside edit, the worker adopts successful journal operations but prevents undo below `undo_floor`; without a valid journal it marks the file external. `undo_floor` counts operations, not FreeCAD transactions. Failed journal operations are omitted when reopening.

Producer/consumer: [worker/serve.py](../worker/serve.py):`serve.handle`, `session_for`, `claim`; [worker/session.py](../worker/session.py):`Session._open_existing`; [viewport/document.gd](../viewport/document.gd):`send_open`, `on_opened`; [viewport/history.gd](../viewport/history.gd):`_on_open` (first drops a reply `is_current_open` rejects; then adopts history and requests sync, or closes a duplicate launch/reverts a refused switch).

### `sync`

| Request field | Type and meaning |
|---|---|
| `cmd` | `"sync"` |
| `model?` | string; defaults to `<outdir>/model.FCStd` if omitted/empty; supplying neither usable model nor outdir fails |
| `oplog` | `{ops: Op[], units?: "mm", format?: string, reserved_ids?: string[]}`; `format` is not validated/used by `run_sync`; `reserved_ids` (protocol 7) is the window's reservations, added to the session's registry before the ops are checked |
| `ops` | alternate top-level Op array when `oplog` is absent |
| `outdir?` | string; export folder, defaults to parent of resolved model path |
| `seq?` | echoed correlation value; window sends integer; omitted becomes `null` |
| `drawing?` | boolean, default false; true enables drawings on subsequent saves of this session |
| `name?` | string, default `"live"`; the only place a session's name comes from, becoming `result.oplog` |
| `delay_ms?` | number; test hook, blocking sleep before dispatch for open/inspect/sync/unknown commands |

A non-`mm` `oplog.units` is refused. The normal window supplies `oplog.format = "oplog/0.1"`, `units = "mm"`; there is no schema validator for its format string.

```json
{"cmd":"sync","model":"/tmp/chair.FCStd","outdir":"/tmp/chair-out","seq":4,"drawing":false,"oplog":{"format":"oplog/0.1","units":"mm","ops":[]}}
{"ok":true,"cmd":"sync","seq":4,"wall_ms":1.2,"outdir":"/tmp/chair-out","result":{"oplog":"live","total_ms":0.1,"export_ms":0.8,"how":"nothing","ops":[],"rev":3,"model":"/tmp/chair.FCStd"}}
```

Success has `ok: true`, `cmd`, `seq`, `wall_ms: number`, `outdir: string`, `result: StatusResult`. `wall_ms` includes request handling/export but excludes deferred save. `outdir` is returned as supplied/defaulted, not forcibly made absolute.

| StatusResult field | Type and meaning |
|---|---|
| `oplog` | string, from the request's top-level `name` (default `"live"`) |
| `total_ms`, `export_ms` | number, sync/evaluation time and metadata/mesh export time |
| `how` | `"nothing"`, `"rebuilt"`, or `"undid N, applied M"` |
| `ops` | ordered OpStatus array, one per applied/requested operation |
| `rev` | integer, current saved rev + 1 if dirty (anticipated next save) |
| `model` | absolute model path |

OpStatus: `id: string`, `type: string`, `status: "ok" | "failed"`, `ms: number`; success normally includes `changed: string[]` (may be `null` if a handler returns no list); failure includes `message: string`. `changed` is a handler report, not an exhaustive geometry diff. Failed operations abort their transaction; later operations are still attempted. Thus request `ok: true` does **not** mean every operation succeeded. Example status: `{"id":"pp1","type":"push_pull","status":"failed","message":"unknown rect 'missing'","ms":0.2}`.

Sync keeps the common canonical op prefix, undoes the rest, then applies the new suffix. If required native undo is unavailable it rebuilds; crossing an external undo floor is a request error. Export finishes before the reply (and `status.json` in one-off replay or when `SERVE_STATUS_FILE=1`). Changed/drawing sessions then enter the pending-save map; `saved` is a separate event after persistence.

Producer/consumer: [worker/serve.py](../worker/serve.py):`run_sync`, `serve.handle`; [worker/session.py](../worker/session.py):`canon`, `Session.sync`, `_apply`, `status`, `export`; [viewport/document.gd](../viewport/document.gd):`oplog`, `_send`, `on_sync_reply`; [viewport/history.gd](../viewport/history.gd):`_on_synced`; [viewport/main.gd](../viewport/main.gd):`_on_rejected`; [viewport/presenter.gd](../viewport/presenter.gd):`show_confirmed`, `apply_confirmed`.

### `length`

Request: `cmd: "length"`, `request_id?: correlation value`, `texts: string[]`, `default_unit?: "mm" | "cm" | "m" | "in" | "ft" = "mm"`. Texts are numeric length expressions, each stripped length 1–512 characters. Scalars inherit the default unit; explicit units override it. Success: `cmd: "length"`, `request_id` (echo, default `null`), `ok: true`, `values: number[]` in mm. Any evaluation failure returns `ok: false`, `error: string`, no partial `values`. It does not claim a model, export, save or echo `seq`.

```json
{"cmd":"length","request_id":7,"texts":["2in","1 + 2"],"default_unit":"mm"}
{"cmd":"length","request_id":7,"ok":true,"values":[50.8,3.0]}
{"cmd":"length","request_id":8,"ok":false,"error":"Unknown default unit"}
```

Producer/consumer: [worker/length_input.py](../worker/length_input.py):`handle`, `evaluate`; [worker/serve.py](../worker/serve.py):`serve.handle`; [viewport/main.gd](../viewport/main.gd):`apply_vcb`, `_on_length` (rejects replies after tool/model/seq/gesture state changes).

### `inspect_properties`

Request: `cmd: "inspect_properties"`, `model: string`, `body: string` (BodyId), `request_id: integer` (required on success), `seq?: integer`. Claims the model, so inspecting a different available model releases this connection's previous model. Refuses an already-owned model with the generic error. Success: `ok: true`, `cmd`, `seq` (or `null`), `model: absolute string`, `request_id`, `properties: PropertiesSnapshot`.

```json
{"cmd":"inspect_properties","model":"/tmp/chair.FCStd","body":"b1","seq":4,"request_id":9}
{"ok":true,"cmd":"inspect_properties","model":"/tmp/chair.FCStd","seq":4,"request_id":9,"properties":{"body":"b1","boards":{},"summary":{"label":"Board 1","context":"Board","parametric":false,"dimensions":[]},"objects":[],"references":[]}}
```

The illustrative empty arrays above stand for the native data. Snapshot fields:

- `body: string`; `boards: {BodyId: StockFrame}` for every supported rectangular board (StockFrame below).
- `objects: ObjectDescription[]`: dependency traversal from selected body, excluding origin/axis/plane helper types. Each object: `name: string` (native key), `label: string`, `type: string` (FreeCAD TypeId), `fields: Field[]`.
- Field: `name: string` (display label), `path: string` (native property/subproperty), `value: string` (display value), `kind: "length" | "angle" | "number" | "text" | "bool" | "enum" | "link" | "read"`, `editable: boolean`, `expression: string` (empty if none), `choices?: string[]` (included for scalar properties; meaningful for enum). Placement translations are local mm; angles follow FreeCAD's degree display; vectors Origin/Step/Span are mm; other numeric/vector fields retain their native meaning. Links/shapes/read fields are display-only strings.
- `references: {name: string, label: string}[]`: all document objects with a Shape, for expression references.

Example field: `{"name":"Length","path":"Length","value":"400.0 mm","kind":"length","editable":true,"expression":"","choices":[]}`. Errors retain `request_id` (default `null`) even when inspection fails.

Producer/consumer: [worker/serve.py](../worker/serve.py):`serve.handle`; [worker/object_properties.py](../worker/object_properties.py):`inspect`, `related`, `describe`, `field`; [viewport/main.gd](../viewport/main.gd):`_request_properties`, `_on_properties`; [viewport/property_panel.gd](../viewport/property_panel.gd):`display`.

### `reload` and `keep_mine`

After an `outside_save` event (below), the window answers with one of these. `reload`: request `cmd: "reload"`, `model`, `outdir`, `seq`; reply: the `open` reply's fields with `cmd: "reload"`, plus `changed` / `removed` (BodyIds whose box, volume, area, wood or hiding differ; BodyIds gone), `dropped` (ops the file's revision didn't hold: they leave the op list and stay in the journal as `dropped`, T65) and `outdir` (bodies.json written there). `keep_mine`: request `cmd: "keep_mine"`, `model`, `outdir?`, `seq`; reply `ok`, `cmd: "keep_mine"`, `model`, `aside` (FreeCAD's file, copied to `<model>.freecad-<YYYYmmdd-HHMMSS>.FCStd`, `-2`... if taken), `rev` (ours, saved over it), `seq`. A held model that has to be saved anyway (`flush`, `bye`, `quit`, or a window disconnecting) keeps both the same way; its `saved` entries carry `aside`. The reload reply carries the `units` in FreeCAD's file (absent if none); `keep_mine` keeps the window's.

```json
{"cmd":"reload","model":"/tmp/chair.FCStd","outdir":"/tmp/chair-out","seq":10}
{"ok":true,"cmd":"reload","model":"/tmp/chair.FCStd","rev":4,"ops":[],"undo_floor":0,"external":false,"seq":10,"reserved_ids":[],"outdir":"/tmp/chair-out","changed":[],"removed":[],"dropped":[]}
{"cmd":"keep_mine","model":"/tmp/chair.FCStd","seq":11}
{"ok":true,"cmd":"keep_mine","model":"/tmp/chair.FCStd","aside":"/tmp/chair.freecad-20261127-075000.FCStd","rev":5,"seq":11}
```

Producer/consumer: [worker/serve.py](../worker/serve.py):`serve.handle`, `keep_both`, `save_pending`; [worker/session.py](../worker/session.py):`Session.reload_outside`, `Session.copy_outside_aside`; [viewport/main.gd](../viewport/main.gd):`_on_worker`; [viewport/document.gd](../viewport/document.gd):`on_outside_save`, `on_reload_reply`, `on_keep_mine_reply`.

### `set_units`

Request: `cmd: "set_units"`, `model`, `units` (one of `ft-in:1/8`…`1/64`, `in-frac:1/8`…`1/64`, `in-dec:0.1`/`0.01`/`0.001`, `m:0.1`/`0.01`/`0.001`, `cm:1`/`0.1`/`0.01`, `mm:1`/`0.1`/`0.01`; worker/session.py `UNIT_SPECS`), `seq`. Reply: `ok`, `cmd: "set_units"`, `model`, `units`, `rev` (the revision the change will be saved as), `seq`. Not an op: undo doesn't change it. It schedules a save like an action (so the change is kept with nothing after it); an unknown value is an error. The window shows the new units at once and sends them again after an open or a reconnect if the reply never came.

```json
{"cmd":"set_units","model":"/tmp/chair.FCStd","units":"in-frac:1/16","seq":12}
{"ok":true,"cmd":"set_units","model":"/tmp/chair.FCStd","units":"in-frac:1/16","rev":5,"seq":12}
```

Producer/consumer: [worker/serve.py](../worker/serve.py):`serve.handle`; [worker/session.py](../worker/session.py):`Session.set_units`, `UNIT_SPECS`; [viewport/main.gd](../viewport/main.gd):`_on_worker`; [viewport/measure_box.gd](../viewport/measure_box.gd):`on_set_units_reply`.

### `flush`, `bye`, `quit`

| Command | Request fields | Success reply | Effects |
|---|---|---|---|
| `flush` | `cmd`, `seq?`, `model?` | `cmd: "flush"`, `seq` (or null), the save lists | Attempts all pending saves across all clients (only `model`'s, when given: closing a window); connection stays open |
| `bye` | `cmd`, `seq?` | `cmd: "bye"`, `seq` (or null), the save lists | Attempts this connection's pending saves, releases ownership, closes socket |
| `quit` | `cmd`, `seq?` | `cmd: "quit"`, `seq` (or null), `stopped: boolean`, the save lists | With another connected client: false, save and release this connection only; otherwise save all pending and exit serve loop (even when a save failed: the window asked first, I55) |

The save lists: `saved: [{model, rev}]` (the saves this request landed), `failed: [{model, rev, error}]` (the ones it couldn't; `rev` is the revision it tried). `ok` is true only when `failed` is empty; otherwise `error` names each model that couldn't be saved and why.

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

Each row is an independent request/reply example, not one stream after bye. Save events may precede lifecycle acknowledgements. A save that fails stays pending: the timer's autosave doesn't keep retrying it, but the next sync of that model, flush, bye or quit does, and each failed attempt sends `save_failed`. `quit.stopped` depends on **connections**, including probes, not just owned documents.

Producer: [worker/serve.py](../worker/serve.py):`serve.handle`, `save_pending`, `let_go`, `release`. Consumer: closing a window (`save_prompts.gd:request_close`, `document.gd:begin_close`) waits for the sync in flight, sends `flush` with its `model`, and closes on an ok answer with the latest revision saved; otherwise it asks Retry / Close without saving / Cancel (I55; no answer in `CLOSE_WAIT_S` asks too). Then [viewport/worker_process.gd](../viewport/worker_process.gd):`shutdown_worker` sends bye for a shared worker (waits up to 4 s) or quit for a private worker (then kills if still running); `document.gd:on_flush_reply` takes flush's answers; [worker/test_serve.py](../worker/test_serve.py) uses flush and checks lifecycle behaviour. `main.gd:_on_worker` sends flush replies to `document.gd:on_flush_reply` and drops bye and quit (an error one is shown in the status line); none reach sync state.

### `saved`, `save_failed`, `outside_save` and `focus` events

All four are unsolicited, worker → window only; there is no matching request or `seq`.

- `saved`: `ok: true`, `cmd: "saved"`, `model: absolute string`, `rev: integer`, sent only to the owner after successful pending save (drives the viewport's quiet 'Saved' indicator, Q22).

```json
{"ok":true,"cmd":"saved","model":"/tmp/chair.FCStd","rev":4}
```

- `save_failed`: `ok: false`, `cmd: "save_failed"`, `model`, `rev` (the revision it tried; the session's own revision doesn't move, so the retry saves that one) and `error` (`ExceptionType: message`; a read-only folder says so), sent to the owner after each failed attempt; the window shows "Couldn't save: <message>" until a `saved`.

```json
{"ok":false,"cmd":"save_failed","model":"/tmp/chair.FCStd","rev":5,"error":"PermissionError: the folder tmp is read-only"}
```

- `outside_save`: `ok: true`, `cmd: "outside_save"`, `model`, `rev` (the file's ShopSketchRev), `unsaved: boolean` (actions not yet on disk). Every `WATCH_S` (0.25 s) the worker stats each open model's file; a change that holds still for one look and isn't our own bytes is FreeCAD's save (each save also looks just before writing, A36, T64). The worker holds the model (no autosave writes over the file) until the window sends `reload` or `keep_mine`.

```json
{"ok":true,"cmd":"outside_save","model":"/tmp/chair.FCStd","rev":4,"unsaved":true}
```

- `focus`: `ok: true`, `cmd: "focus"`, `model: absolute string`, sent to the existing owner when another connection's **open** is refused. Sync/inspection ownership errors do not send focus. The owner foregrounds its window; the refusing reply goes to the second connection.

```json
{"ok":true,"cmd":"focus","model":"/tmp/chair.FCStd"}
```

Producer/consumer: [worker/serve.py](../worker/serve.py):`save_pending`, `serve.hold`, `serve.handle`; [viewport/main.gd](../viewport/main.gd):`_on_worker`; [viewport/history.gd](../viewport/history.gd):`_on_open`; [viewport/document.gd](../viewport/document.gd):`on_saved` (matches normalized model path; monotonically advances saved revision; clears `save_error`), `on_save_failed` (sets `save_error`, the message without the exception's name), `on_outside_save`.

### Generic request errors

```json
{"cmd":"unrecognized","seq":6}
{"ok":false,"cmd":"unrecognized","error":"OpError: unknown cmd 'unrecognized'","seq":6}
```

Envelope: `ok: false`, `cmd: string | null`, `error: string` (`ExceptionType: message`), `seq: echoed value | null`. Invalid JSON can yield null cmd/seq. Inspection additionally echoes `request_id`. The special `already_open` refusal and evaluator errors have their own envelopes above. Unknown commands fail rather than being ignored. No standalone `saved`, `focus`, `property_edit`, undo or redo command exists; the latter edits are represented by changing the desired operation list.

Producer/consumer: [worker/serve.py](../worker/serve.py):`serve.handle`; [worker/length_input.py](../worker/length_input.py):`handle`; [viewport/main.gd](../viewport/main.gd):`_on_worker`; [viewport/document.gd](../viewport/document.gd):`on_sync_reply`.

## Operation payloads (`oplog/0.1`)

All Ops have `id: string` and `type: string`; IDs are journal identities and should be stable/unique within the sequence. New IDs are `<prefix><serial>_<32 lowercase hex>` (128 random bits), e.g. `b3_0123…cdef`; the worker refuses a sync whose new-style ID is created twice or changes owner (`ID collision`); an ID reserved with no owner yet (an undone action that never reached the worker) is claimed by the first op that creates it, and old serial IDs (`b3`, `pp7`) are accepted as they always were. Displays show the serial part only (`Board 3`, `pp7`). The worker canonicalizes numbers to 9 decimal places for prefix comparison (18 equals 18.0). Every accepted op creates one native transaction. This table describes fields read by current handlers, rather than promising complete upfront validation. Unknown fields are generally ignored. Source dispatch: [worker/model.py](../worker/model.py):`Model.HANDLERS`, `apply`.

FaceRef = `{body: string, normal: Vec3, point: Vec3}`: world face identified geometrically, never FreeCAD face number. Plane = `{normal: Vec3, origin: Vec3, xdir?: Vec3}` or `{on: FaceRef, xdir?: Vec3}`. Normal/direction inputs are normalized; plane xdir is projected into its plane. Without xdir, horizontal planes use world X, others use world Z cross normal; y = normal cross x. Source: [worker/model.py](../worker/model.py):`resolve_face`, `plane_from`.

| Type | Fields beyond id/type | Source |
|---|---|---|
| `rect` | `plane: Plane`, `size: [number,number]` positive mm, `corner?: [number,number] = [0,0]` plane-local mm, `x?: [number,number,number]` optional first-edge direction projected orthogonal to `n` (Rotated Rectangle, omitted for axis-aligned rects) | [push.py](../worker/push.py):`PushActions.op_rect` |
| `circle` | `plane: Plane`, `radius: number` finite, at least 0.001 mm; `center?: [number,number] = [0,0]` plane-local mm. Native fully constrained sketch circle; shares the profile namespace (`RectId`) with rectangles. Viewport allocates `r` IDs for both. | [circle.py](../worker/circle.py):`CircleActions.op_circle` |
| `polygon` | `plane: Plane`, `radius: number` finite circumradius, at least 0.001 mm; `sides: integer` 3 to 64; `x?: [number,number,number]` direction from the centre to the first corner (projected into the plane, sent unrounded; omitted: the plane's x); `center?: [number,number] = [0,0]` plane-local mm. Native constrained sketch (`SSRole = polygon-profile`); shares the profile namespace (`RectId`); the viewport allocates `r` IDs. | [polygon.py](../worker/polygon.py):`PolygonActions.op_polygon` |
| `line` | `plane: Plane` (the drawing's plane; the start point is its origin), `end: [x,y,z]` world mm; `outline?: [[x,y,z], ...]` ordered world-mm polygon with no repeated final vertex, on the segment that closes a loop (makes a line profile with this op's id as `RectId`); `snap_start?`, `snap_end?: boolean` keep a snap to existing geometry across the 0.1 mm gap between native-edge and face tessellations (unsnapped ends keep 0.001 mm). Points are projected onto the plane. Changes no solid. Viewport allocates `r` IDs. | [line.py](../worker/line.py):`LineActions.op_line` |
| `arc` | `plane: Plane` as `line` (the start point is its origin, or `on` a face), `mid: [x,y,z]` (a point on the arc halfway along) and `end: [x,y,z]` world mm, on the plane; `snap_start?`, `snap_end?` as `line`. One circular arc through the three points; refused if a point is non-finite or off the plane, two coincide, or they are collinear. Changes no solid; Push/Pull regions name it in `region.lines` like a line. Viewport allocates `r` IDs (protocol 10). | [arc.py](../worker/arc.py):`ArcActions.op_arc` |
| `push_pull` | `target: {rect: string}` (rectangle, circle, polygon or line profile ID) or `{face: FaceRef}`, optionally with `region: {outline, holes, normal, lines}` (a drawn cell: full-precision world-mm points, the saved line ids that bound it; with `face` or `rect` it must fit that source, alone it is free closed stock; the worker validates coplanarity, simple outlines, holes, normal, containment and the line references), `distance: number` nonzero signed mm along normal; `body?: string` requests new/separate BodyId (otherwise a free profile defaults to `<id>_body`); `assembly?: string` new board's assembly; `through?: boolean = false` for negative cuts; `resize_stock?: boolean`; `edge_fit?: {target_body: string, face: integer, fit_mode?: integer = 0}`; `to_face?: {normal: Vec3, point: Vec3}` (world mm, an earlier pocket's floor the cut goes to; the cut is tied to that floor by expression; only on a cut into a board, `distance < 0`, without `through`, `edge_fit`, `resize_stock` or `body`, else `to_face is only for a cut into a board`; since protocol 12 the window sends it on a pointer cut snapped to a face behind (`push_tool.gd` `_finish_push` → `commit_push`): the starting face's normal and the point straight behind the grab at the cut's depth; only on a rectangle, circle or region target on a board, never for a typed distance, I40) | [push.py](../worker/push.py):`PushActions.op_push_pull` |
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
| `fit` | `body: string`, `target_body: string`, `axis: integer 0..2`, `face: integer` (0..5 on rectangular stock, else an index into the target's `planar_faces`; the worker keeps it by geometry after `apply`), `fit_mode: integer 0..2`, `reverse?: boolean = false` | [plane_fit.py](../worker/plane_fit.py):`apply`; [model.py](../worker/model.py):`Model.op_fit` |
| `unfit` | `body: string`, `axis: integer` matching existing fit, `value: string` positive length; restores plain stock and detaches fit | [plane_fit.py](../worker/plane_fit.py):`replace`, `_restore`; [model.py](../worker/model.py):`Model.op_unfit` |

Plane-fit faces: 0 Left, 1 Right, 2 Front, 3 Back, 4 Bottom, 5 Top in **target stock-local axes**. Modes: 0 Butt to plane, 1 Slice at plane, 2 Fully reach plane. Axis 0/1/2 denotes source stock length/width/extrusion axis, not necessarily world X/Y/Z. Selection moves resolve shared sources once; assembly rows are currently refused. Handler rejection is conveyed through OpStatus, not a separate command. Files saved before protocol 17 have their fits upgraded when opened.

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

`Model.HANDLERS` (the `op_*` methods) and each `op_*` implementation are the authoritative operation schema; there is no separate typed protocol definition.

### Notes on selection ops

`move` with `selection: true`, `targets: [BodyId, ...]`, `vector`, optional `copy`, `count`, `divide`, `new_ids` and `detach` is one native transaction. A move resolves shared array/mirror sources once through the assembly motion algebra; inside an array, selected copies detach before motion. Copy uses source-major new IDs, one per source per offset. `mirror` uses several BodyIds and the existing plane/replace/new_ids schema. Drafts and confirmation waves contain each affected board. Retyping a multi-copy count/span retains its full target set. A copy that includes every member of an assembly carries `groups: {old AssemblyId: new AssemblyId}` for a single copy, or `groups: {old AssemblyId: [new AssemblyId, ...]}` for a row (T58, I52); group ids are ordered by offset while board ids remain source-major. Each copied assembly has its own group of linked boards. The worker still reads the single-string form in existing journals.

`delete` with `id` and `targets: [BodyId, ...]` removes the selected instances and promotes surviving originals (I46), in one transaction.

### Notes on fits, pocket-floor ties and hide

- `push_pull.edge_fit` carries `{target_body, face, fit_mode}` (`0` Butt / `1` Slice / `2` Fully reach; absent = Butt). `push_pull.resize_stock` resizes an entire ordinary stock face. `push_pull.to_face` carries `{point, normal}` on a pointer cut whose snap is "face behind" (never on a typed distance, nor with `through`, `body`, `edge_fit`, or `resize_stock`).
- `fit` records source and target `BodyId`s, local axis, semantic face and end condition; `unfit` restores the native extrusion with the entered dimension.
- `plane_fit.snapshot()` exports `fitted_end: {face, normal, point}` on fitted boards, and `rectangular: False` with `planar_faces` (point and normal per face; `fitted_end.face` is its index in that list) on non-rectangular/cut boards; `bodies.json` carries `stock_frame` and `hidden`.
- `hide` carries `targets` and `hidden` (one op per Hide/Unhide command).


## Shared files

### Publication and locations

`run_sync` writes `bodies.json`, changed mesh files, and the material library (once per output folder per worker) into outdir before success; it writes `status.json` only in one-off replay (no `SERVE_PORT`) or when `SERVE_STATUS_FILE=1`. Save writes `model.glb` into the pending save's outdir and the actual model into its requested path (one file per model; nothing is written beside it); drawing saves also write `views.json`. If several syncs coalesce before saving, the latest pending outdir for that model wins. Paths are not a remote transfer mechanism.

JSON outputs use `atomic_json` (`<path>.tmp`, then `os.replace`; `materials.json` the same way in `write_library`). Mesh and GLB also use temp + rename. These individual publications are atomic, not a transaction across all files. `.FCStd` uses `<model>.saving.FCStd` then atomic `os.replace`. Sources: [worker/serve.py](../worker/serve.py):`run_sync`, `serve.save_pending`; [worker/session.py](../worker/session.py):`atomic_json`, `Session.export`, `save`, `finalize_fcstd`; [worker/export.py](../worker/export.py):`board_mesh_file`, `write_glb`; [worker/materials.py](../worker/materials.py):`write_library`.

### `bodies.json`

JSON array, one entry per live board, including hidden boards and excluding deleted/source/definition objects. Source: [worker/session.py](../worker/session.py):`Session.export`; consumers [viewport/presenter.gd](../viewport/presenter.gd):`apply_confirmed`, `_build_board`, `_load_cuts`; [viewport/selection.gd](../viewport/selection.gd):`set_boards`; [viewport/history.gd](../viewport/history.gd):`_on_boards_read`.

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

StockFrame, from [worker/plane_fit.py](../worker/plane_fit.py):`snapshot`: `label: string`, `origin: Vec3` world mm, `axes: [Vec3,Vec3,Vec3]` unit world directions, `sizes: [number,number,number]` local length/width/extrusion mm; `plane: string`, `extrusion: string` native names; `fitted: boolean`, `reverse: boolean`, `linked_axis: integer` (-1 when absent, otherwise 0..2), `result: string` display summary, and (protocol 13, when `fitted` is true and `fitted_end()` resolves) `fitted_end: {face: integer (0..5 on rectangular stock; on a non-rectangular board, its index in `planar_faces`), normal: Vec3, point: Vec3}` giving the fitted end's real world outward normal and point. Only supported direct rectangular stock produces this snapshot; unsupported/link/mirror shapes can yield null.

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

Sources: [worker/materials.py](../worker/materials.py):`library`, `material_uuid`, `write_library`; [worker/session.py](../worker/session.py):`Session.export`; [viewport/appearance.gd](../viewport/appearance.gd):`load_library`, `wood_material`.

### `model.glb`

Binary glTF 2.0 for renders, written at save (not each sync), excluding hidden boards. GLB header: magic `glTF`, version 2, total byte length (little-endian u32). JSON chunk is padded with spaces to 4-byte alignment; nonempty scenes also have a BIN chunk with padded vertex/normal data. Empty model has a JSON-only valid empty scene.

JSON fields written by `write_glb`: `asset: {version: "2.0", generator: "Shop Sketch worker 0.2"}` (generator absent for empty scene), `scene: 0`, `scenes: [{nodes: integer[]}]`, `nodes`, `meshes`, `materials`, `accessors`, `bufferViews`, `buffers`. Each node: `name: BodyId`, `mesh: integer`, `extras: {body_id: string, material: string, component: string|null, grain_zup: Vec3, across_zup: Vec3, state: "confirmed"}`. Grain extras remain **Z-up**, unlike converted vertex geometry.

Each mesh: `name: BodyId`, `primitives: [{attributes: {POSITION: accessor index, NORMAL: accessor index}, material: material index}]`; unindexed triangles, float32 VEC3 accessors (`componentType = 5126`, count = vertex count); POSITION includes min/max. BufferView has buffer 0, byteOffset, byteLength and target 34962; buffers has byteLength. Materials: `name` (key or `"unassigned"`), `pbrMetallicRoughness: {baseColorFactor: [r,g,b,1], metallicFactor: 0, roughnessFactor: 0.8}`; wood materials add `extras: {wood: string, texture: absolute JPEG path, texture_grain_along: string, texture_size_mm: number, end_texture: absolute JPEG path, end_size_mm: number}`. Textures are external metadata, not embedded glTF textures/UVs. Example node: `{"name":"b1","mesh":0,"extras":{"body_id":"b1","material":"","component":null,"grain_zup":[1,0,0],"across_zup":[0,1,0],"state":"confirmed"}}`.

Source: [worker/export.py](../worker/export.py):`mesh_of` (Y-up metres), `write_glb`; [worker/session.py](../worker/session.py):`Session.save`. The viewport consumes per-board mesh files, not this render export.

### Model `.FCStd` and embedded journal (one file per model, 2026-11-27)

The native FreeCAD model is authoritative; its archive includes `Document.xml`, native shape data, `GuiDocument.xml`, and (when an undo floor came from FreeCAD) `ShopSketchFloor.FCStd`. Saved format changed on 2026-11-27 (A42): everything the journal holds lives inside the `.FCStd` itself, with nothing written beside the model. `Session.save` increments document Meta `ShopSketchRev` (string integer), writes `ShopSketchUnits` (protocol 9, when the model has units; kept on the Session so a rebuild doesn't lose them), `ShopSketchOps` (protocol 11: the revision's `ok` ops as compact JSON), and `ShopSketchJournal` (compact JSON of the journal below), saves a copy to `<model>.saving.FCStd`, optionally regenerates TechDraw there, injects `ShopSketchContentSha256` (a SHA-256 of the zip's contents excluding `GuiDocument.xml`, `ShopSketchFloor.FCStd`, and `ShopSketchContentSha256` itself), `GuiDocument.xml`, and `ShopSketchFloor.FCStd` if needed, then atomically renames `<model>.saving.FCStd` over the model.

`ShopSketchJournal` fields: `format: "shopsketch-journal/0.1"`, `rev: integer`, `ops: Op[]`, `status: JournalStatus[]` in corresponding order. JournalStatus has `status: "ok" | "failed"`, `ms: number`, optional `changed: string[] | null`, optional `message: string`; id/type are in the matching op, not duplicated in status.

Optional fields (a journal without them opens as before):

- History and IDs: `reserved_ids` (sorted strings: every ID reserved, kept when ops are undone or dropped) and `id_owners` (`{id: owner}`, which op made each ID, stable across typed amendments).
- Undo floor and outside saves: `floor` (undo stops here: ops before it can't be taken back, A25; kept across saves and sessions), `dropped` (`[{op, after_rev, at}]`: actions an outside save didn't hold).
- Undo copy: `floor_copy` (`{sha256, ops}`: the sha256 of the `ShopSketchFloor.FCStd` entry inside the zip, a copy of the document as it stood at the undo floor, and the floor it was written at), written only when the floor came from a FreeCAD change. A journal without it reads as no copy: undoing past the floor then needs a rebuild that is refused (`can't undo past the FreeCAD edit: its copy is missing`) rather than one that would drop FreeCAD's change.

```json
{"format":"shopsketch-journal/0.1","rev":4,"ops":[],"status":[],"floor":0,"dropped":[],"reserved_ids":[],"id_owners":{}}
```

On reopen, `ShopSketchContentSha256` and `ShopSketchRev == rev` establish that the file is ours (FreeCAD's own save changes `Document.xml`, so `content_sha256` mismatches). Only successful ops are adopted. Missing/wrong-format journal or a mismatched rev/hash marks external; the surviving history becomes an undo floor. Any leftover `<model>.saving.FCStd` from an interrupted save is removed on open. Pre-A42 models with `<stem>.shopsketch.json` (and `<stem>.floor.FCStd`) beside them still open and upgrade themselves on the first save, which removes the legacy sidecars (leaving `.unmatched` files alone) only after the rename lands. Sources: [worker/common.py](../worker/common.py):`JOURNAL_FORMAT`; [worker/session.py](../worker/session.py):`read_journal`, `content_sha256`, `finalize_fcstd`, `Session.save`, `_open_existing`, `_build_gui_document`.

### `status.json`, `views.json`, startup port file

`status.json` is written only by one-off replays (no `SERVE_PORT`) or in serve mode when `SERVE_STATUS_FILE=1` (`tools/fulltest.sh`), never on ordinary edits in the app; it contains exactly the StatusResult inside the latest sync reply, without the outer ok/cmd/seq/wall_ms/outdir fields. Example: `{"oplog":"live","total_ms":0.1,"export_ms":0.8,"how":"nothing","ops":[],"rev":4,"model":"/tmp/chair.FCStd"}`. Source: [worker/serve.py](../worker/serve.py):`run_sync`.

`views.json` is an object `{Front: string, Top: string, Right: string, Iso: string}` containing TechDraw SVG markup, e.g. `{"Front":"<svg>...</svg>","Top":"<svg>...</svg>","Right":"<svg>...</svg>","Iso":"<svg>...</svg>"}`. It is refreshed only by drawing saves; an old file can remain otherwise. The saved copy also contains the native Drawing page, Template and views; the live document does not. Sources: [worker/export.py](../worker/export.py):`add_drawing_page`; [worker/session.py](../worker/session.py):`Session.save`.

The optional `SERVE_PORT_FILE` is plain decimal text with LF, e.g. `49152\n`, atomically replaced through `.tmp`. The test window reads/deletes it. Sources: [worker/serve.py](../worker/serve.py):`serve`; [viewport/worker_process.gd](../viewport/worker_process.gd):`_await_port_file`.
