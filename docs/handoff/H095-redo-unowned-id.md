### H095 — Redo after undoing an action that never reached the worker no longer blocks every sync (H092 finding 8)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: either

References: T67 / H059 (IDs that never collide: `next_id`, `reserved_ids`, `IdRegistry`), H092 finding 8, the
integrator follow-up in docs/follow-ups.md about reserving every string (not this job: leave it).

Touches: worker/session.py (`IdRegistry.accept` only), worker/test_branch_ids.py. Not the viewport, not the
protocol (nothing on the wire changes). It touches a different part of session.py from H093 and H094 (queued); it runs first.

Today (checked 2026-11-22): document.gd `next_id` reserves a new ID locally at once, and every sync sends
`reserved_ids`. Draw something while a sync is in flight (the new op only marks `dirty`), then Undo before the
answer: the next sync carries the ID in `reserved_ids` but no op that creates it, so the worker reserves it with
no owner. Redo puts the op back, and `IdRegistry.accept` refuses it on every sync while that op is in the list:
`ID already reserved: <id>` (session.py, `if identity in self.reserved and identity not in owners`). The window
can't sync again until the op is removed.

Request: in `IdRegistry.accept`, a modern ID that is reserved but has no owner is claimed by the first op that
creates it: its owner is recorded and the sync goes on. Still refused, as today: a modern ID created twice in
one op list (`ID collision`) and one whose recorded owner differs (`ID collision`). The `ID already reserved`
error goes away; say in your response whether anything else relied on it (grep: nothing in the tests did on
2026-11-22). Legacy IDs unchanged.

Checks (worker/test_branch_ids.py): a session; sync [rect r, push p] with `reserved_ids` also holding a new
board ID B no op creates (the undone action); then sync the same ops plus a push that creates B: ok, B's owner is
that push; then the same op list again: ok; then a different op creating B (another type, or another op id with
`body: B`): `ID collision`. Every existing check still passes.

Reading path: viewport/document.gd `next_id` → `oplog` (what a sync sends) → `undo` / `redo`; worker
session.py `creations` → `IdRegistry.accept` → `Session.sync` (where accept runs). Who owns what: the window
allocates IDs; the worker's registry is the document's memory of them.

Run the feature tests while building (`tools/featuretest.sh`), then `python3 tools/job.py test`. End your
response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.

Response — Gemini (gemini-spark), 2026-11-22:
- Branch: `gemini/h095-redo-unowned-id`, code commit `9430a3c`.
- Change: removed the `if identity in self.reserved and identity not in owners: raise OpError(f"ID already reserved: {identity}")` check in `worker/session.py` (`IdRegistry.accept`). The first op creating an unowned reserved modern ID now claims it and records its owner; duplicate creations in one op list and creations whose recorded owner differs still raise `ID collision`. Legacy IDs are unchanged.
- What relied on `ID already reserved`: grep found no code or test referencing the message string, but one existing check in `worker/test_branch_ids.py` (`rejects('a reservation without a claim is never reassigned', ...)`) relied on it via bare `except OpError:`. Updated that check to verify claiming an unowned reservation and rejecting reassignment with `ID collision`, kept every other existing check, and added the `Session.sync` redo/collision checks (including duplicate creation of an unowned reserved ID in one op list). Outside tests, only `docs/protocol.md` (line 187, Ops section) mentions `ID already reserved` (left untouched per P28).
- Verified: `tools/featuretest.sh` (33/33 suites passed; `BRANCH IDS TESTS: 16 passed, 0 failed`) and `python3 tools/job.py test` on `9430a3c` (all 33 feature suites passed, `QUICK 240 passed, 0 failed`).
- IDs added: none. Open questions: none.

Architecture: docs/protocol.md (Ops section): remove `ID already reserved` from the worker's sync ID-refusal errors; `IdRegistry.accept` now lets the first op creating an unowned reserved modern ID claim and record ownership of it, while still refusing duplicate creations in one op list or a different recorded owner with `ID collision` (wire protocol and `ARCHITECTURE.md` unchanged).
For the integrator: remove `/ ID already reserved` from `docs/protocol.md` (Ops section, line 187) at merge.
Result: 9430a3c; branch_ids 16/16, feature tests 33/33, quick test 240/240 passed; IdRegistry.accept lets the first op creating an unowned reserved modern ID claim it while keeping ID collision checks
