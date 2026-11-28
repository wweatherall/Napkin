### H183 — A failed op names the ids it failed on, so the window stops reading FreeCAD's message text

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: gemini

References: William, 2026-11-27 (ChatGPT's architecture review: "rejection grouping sometimes searches
human-readable error messages for body IDs"), document.gd's rejection bookkeeping, docs/protocol.md (`sync`,
OpStatus), comitatus principle C03.

Touches: worker/common.py (`OpError`), worker/session.py (`_apply`, `status`), worker/serve.py (`PROTOCOL_VERSION`),
the worker files that raise an `OpError` naming an id (worker/model.py, worker/push.py, worker/move.py,
worker/assembly.py, worker/mirror.py, worker/paint.py, worker/visibility.py, worker/circle.py, worker/polygon.py: the
raise lines only), viewport/main.gd (`_on_rejected`,
`PROTOCOL_VERSION`), viewport/document.gd (`reject` only), viewport/test_document.gd (the rejection checks),
docs/protocol.md (the OpStatus line). (H182 also touches viewport/test_document.gd: under the hopper this job is
cut from H182's branch.)

Reading path:
1. worker/common.py `OpError`; worker/session.py `_apply` (~755: a failure records `message` only) and `status`
   (~839: the keys copied into OpStatus).
2. viewport/main.gd `_on_rejected` (~747): passes `o["message"]` to `doc.reject`.
3. viewport/document.gd `reject` (~601), the line `if msg.contains("'%s'" % b): root = r`: a later failure whose
   message quotes a board an earlier rejection touched joins that rejection.
4. viewport/test_document.gd ~700-715: the check "an op naming a touched board in FreeCAD's message joins the
   rejection" pins today's behaviour.

Today (checked 2026-11-27): grouping depends on the wording of the worker's errors. About 30 `raise OpError(f"...")`
lines quote an id (`grep -rn "raise OpError(f" worker/*.py | grep "'{"`); rewording one would quietly change which
rejections are grouped.

Request:
1. `OpError(message, about=())`: `about` is the ids (boards, rects, ops, assemblies) the failure is about. Every raise
   that quotes such an id passes it in `about` (`raise OpError(f"unknown body '{bid}'", about=[bid])`). Raises that
   quote something else (a material, units, an op type, a cmd) pass nothing. The messages don't change.
2. `_apply` records `about` on a failed entry when it's non-empty; `status` copies it, so OpStatus has
   `about: string[]` on a failure that named ids. A failure from another exception has none.
3. `_on_rejected` passes `o.get("about", [])` to `doc.reject` as a new last parameter (`about: Array = []`, so the
   existing calls in tests keep working); `reject` matches `e["bodies"]` against `about` and no longer looks inside
   `msg` (the message is still used for the note).
4. docs/protocol.md's OpStatus line names `about`; `PROTOCOL_VERSION` goes 18 → 19 on both sides (a reply field
   changed).
5. The test_document.gd check above passes `about` instead of relying on the message, keeps its name's meaning
   ("...names a touched board..."), and a new check shows a message quoting a board without `about` no longer joins.

Not in this job: rewording any message, `_op_makes` (H182), `_op_refs`, or reporting `about` for successful ops.

What can fail:
- An older worker (protocol 18) talking to the new window: the hello's version check already refuses to share a
  worker of another version, so a mismatched pair can't run. Check: the quick tests start a fresh worker.
- A raise that names a board but was missed: grouping for that failure gets looser (it becomes a rejection of its
  own). Check: list in your response every raise you gave `about` and every quoting raise you left without it, with why.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope); quick 401/401.
- `python3 tools/protocol_map.py --check` passes.

Response (Gemini, gemini-birch-1127-182813):
- Added `about=()` to `OpError` (`worker/common.py`), recorded `about` on failed entries in `Session._apply` when non-empty and copied it in `Session.status` (`worker/session.py`).
- Passed `o.get("about", [])` from `viewport/main.gd` (`_on_rejected`) into `Document.reject(..., about: Array = [])` (`viewport/document.gd`), matching `e["bodies"]` against `about` instead of searching `msg`.
- Updated `viewport/test_document.gd` so the rejection-joining check passes `about` and added a check verifying a message quoting a board without `about` no longer joins.
- Bumped `PROTOCOL_VERSION` 18 -> 19 in `worker/serve.py`, `viewport/main.gd`, `docs/protocol.md` (including `hello` and `OpStatus`), and `worker/test_serve.py`.

Changed from the brief:
- Updated `worker/test_serve.py:57` (`== 18` -> `== 19`) and `docs/protocol.md` `hello` lines 3, 57, 61 (`18` -> `19`) for the protocol version bump. Scope approved by integrator: `"Yes: update worker/test_serve.py's PROTOCOL_VERSION check to 19, and any other test that pins 18 the same way (the bump is in the brief). Name them in Changed from the brief."`

Raises given `about`:
- `worker/assembly.py:26` (`about=[aid]`), `:33` (`about=[t]`), `:45` (`about=[aid]`), `:78` (`about=[o.BodyId]`), `:83` (`about=[o.BodyId]`)
- `worker/circle.py:37` (`about=[rid]`)
- `worker/mirror.py:43` (`about=[nid]`), `:57` (`about=[t]`)
- `worker/model.py:65` (`about=[bid]`), `:153` (`about=[ref["body"]]`), `:155` (`about=[ref["body"]]`), `:181` (`about=[bid]`)
- `worker/move.py:17` (`about=[bid]`), `:19` (`about=[bid]`), `:143` (`about=[oid]`), `:275` (`about=[t]`), `:295` (`about=[t]`)
- `worker/paint.py:26` (`about=[t]`), `:55` (`about=[t]`)
- `worker/polygon.py:45` (`about=[rid]`)
- `worker/push.py:127` (`about=[rid]`), `:186` (`about=[tgt["rect"]]`), `:264` (`about=[op["assembly"]]`), `:278` (`about=[on]`)
- `worker/visibility.py:21` (`about=[t]`)

Quoting raises left without `about`:
- `worker/model.py:124` (`obj.Label`): FreeCAD label, not an op/body id.
- `worker/model.py:337` (`op.get('mode')!r`), `:343` (`op['type']`): op mode and op type, not ids.
- `worker/model.py:364` (`bad[:3]`): FreeCAD object labels, not ids.
- `worker/paint.py:21` (`key`): material key, not an id.
- `worker/polygon.py:53` (`MIN_SIDES`..`MAX_SIDES`): integer side bounds, not an id.
- `worker/serve.py:262,277,293,312` (`os.path.basename(...)`), `:320` (`cmd`): filenames and command name (outside op `_apply`).
- `worker/session.py:86` (`identity` in `accept` before `_apply`), `:375` (`bad_entry` zip member), `:811` (`self.undo_floor` int), `:893` (`units`): request-level / file / unit errors, not op-handler ids.

Result: `tools/TEST_BEFORE_MERGING.sh` passed (GATE PASS: full test passes; QUICK 401/401, 0 failures, 80 s total); `python3 tools/protocol_map.py --check` passed.
