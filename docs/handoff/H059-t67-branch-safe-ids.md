### H059 — T67: IDs that never collide across kept history branches

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: queued (after H063) | For: Codex

References: T67 (from T35), U02, U01, docs/specs/U01-history.md (its "T35 IDs and migration" section is the design:
read it first), A21, A24, A25 (the journal), I42 (boards' names in FreeCAD's tree), A35 (protocol version), G09.
William chose this as Codex's next job, 2026-11-22. Take it after H046 (Lines); its files overlap Lines' docs.

Touches: viewport/document.gd and viewport/test_document.gd (ID allocation, the counters, restore_counters),
viewport/tool_context.gd (document.next_id only) and viewport/test_tool_context.gd, worker/session.py (the journal:
reading old IDs, writing new ones), worker files that parse an ID's numeric suffix (find them; list them in your
response), worker/test_*.py and a new worker/scenario/NN_branch_ids.py. Not docs/protocol.md or ARCHITECTURE.md (P28: the
integrator's): write what your change does to them as "Architecture:" lines in your response. Not viewport/tools/* (the T88 tool moves own them) or the test scripts in tools/.

Request: new board, rectangle, hole, assembly and op IDs never collide with an ID a kept branch uses (U02), using the
spec's recommendation (type-prefixed IDs from OS-quality random bytes, checked against a document-wide registry;
no counter rebuilt from the current path). Every existing ID in a saved model and journal is kept verbatim (no
rewriting old geometry IDs); old journals open as before. Nothing William would notice changes: boards keep their
readable names in FreeCAD's tree ("Board 3", I42) from a friendly per-document number, the Properties panel and
messages show the same names, and typed values, undo and saving behave as today. If any of that can't hold, stop and
say why in your response before building around it. Branch history itself (keeping abandoned futures) is T71, not
this job. Checks: a document test that IDs allocated after an undo never reuse an abandoned future's IDs; a
scenario that opens an old model and journal and keeps every ID; a worker test for the registry refusing a
collision; quick test and the gate. Bump the protocol version if a message field changes (A35).
