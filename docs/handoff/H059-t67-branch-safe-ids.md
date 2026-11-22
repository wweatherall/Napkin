### H059 — T67: IDs that never collide across kept history branches

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: Codex

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

Response — Codex, 2026-11-22 (scope question; no implementation yet):

Claimed on `codex/h059-t67-branch-safe-ids` in `/Users/Will/Sites/fretchup-h059`.
The current Touches list cannot cover the requested guarantee: direct counter allocation remains in
`viewport/tools/rect_tool.gd`, `circle_tool.gd`, `push_tool.gd`, `move_tool.gd`,
`viewport/selection.gd` and `viewport/main.gd`. Only Line currently uses ToolContext.document.next_id.
Updating document.gd and that adapter alone would leave new boards, profiles, copies, assemblies and most
ops using the old IDs. These sites need to call the document allocator, with affected tests adjusted.
Asked William to authorize that scope expansion or return this job for revised scope; queue marked waiting.
No code changed and no tests run. Worker naming inspection also found `worker/common.py:board_label`
formats numeric b IDs, with consumers in model.py, move.py and mirror.py; readable naming needs preserving.

Scope approval — William, 2026-11-22 (relaying Claude): include the direct allocation sites in
viewport/tools/, selection.gd and main.gd; only ID allocation and affected tests there. William also approved
readable-name substitutions in main.gd and selection.gd messages so random IDs are not displayed.
Decision placeholders: P-new-1 (allocation scope), W-new-1 (readable message substitutions).
Affected tests include tools/compare_suites.py: recorded geometry/status comparisons resolve random IDs to their
friendly serials for comparison with the existing deterministic references; no test runner script changes.

Architecture: document.gd owns permanent ID reservations and allocates `<prefix><friendly serial>_<128 random bits>`
with Godot Crypto; every production allocation site routes through it. Counters serve friendly numbering only,
restored from all reserved legacy/new IDs, and reservations survive undo, rejection, outside reload and reopen.
Architecture: the oplog sync request and open/reload reply add `reserved_ids`; protocol version 7 on both sides.
Session owns an IdRegistry with stable creation claims across typed amendments. New random IDs are checked before
geometry changes; old serial-ID clients/fixtures retain their mutable-slot compatibility. Journal 0.1 adds optional
`reserved_ids` and `id_owners`; existing ops/native IDs remain verbatim. Native BodyId/RectId/SSOp/AssemblyId/SSLineId
and legacy op strings seed reservations; no branch tree, history migration or node schema is introduced (T71).
Architecture: common.board_label accepts the new suffix while keeping Board N names. document display helpers
keep random tokens out of main's tooltip/status/rejection displays and selection's linked-board messages.
For the integrator: update ARCHITECTURE.md and docs/protocol.md with these ownership, journal and protocol fields;
update the viewport/tools/CLAUDE.md action recipe from direct counters to document.next_id during integration.
