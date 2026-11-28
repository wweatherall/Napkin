### H182 — What an op creates: the window and FreeCAD agree, checked by one shared table

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: open | For: gemini

References: William, 2026-11-27 (ChatGPT's architecture review: "the worker knows how to execute an operation, but
several other components independently determine what that operation means"), T67 (document-wide ID claims,
`creations`), W-rejection grouping (document.gd's rejection bookkeeping), comitatus principle C03.

Touches: viewport/document.gd (`_op_makes`, `_op_refs`), viewport/test_document.gd (one new check block),
worker/test_branch_ids.py (one new check block), tests/op_creations.json (new).

Reading path:
1. worker/session.py `creations` (~line 50): every id an op makes, in order: the op's id, a push_pull's `body`,
   `new_ids`, a make_assembly's `new_id`, `group`, and each id in `groups`.
2. viewport/document.gd `_op_makes` (~582): the window's copy, used by `reject` to decide which later rejections
   built on an earlier one.
3. viewport/document.gd `reject` (~601): `e["ids"]` is filled from `_op_makes`; a later op whose `_op_refs` hits one
   of those ids joins that rejection.

Today (checked 2026-11-27): `_op_makes` lists the op's id, a push_pull's `body` and `new_ids`, but not a
make_assembly's `new_id` or `group` / `groups`, and `_op_refs` doesn't list a push_pull's `assembly` (sent when a
board is drawn inside an entered assembly: push_tool.gd ~419, worker/push.py ~261). So if a make_assembly is
rejected, a board drawn inside that assembly is treated as a rejection of its own instead of going with it. Today
no symptom has been seen; the rule is written twice and the copies have drifted.

Request:
1. `_op_makes` returns the same ids, in the same order, as `creations` (ids only, not their ownership keys): add a
   make_assembly's `new_id` (when non-empty), `group`, and every id in `groups` (a list or a single id per source,
   as `creations` reads it).
2. **tests/op_creations.json**: a list of cases `{"op": {...}, "makes": [...]}`, at least one per branch of
   `creations` (a plain op, push_pull with `body`, `new_ids`, make_assembly, `group`, `groups` with a list and with
   a single id). Both sides read the same file so they can't drift again:
   - worker/test_branch_ids.py: `[i for i, _ in creations(op)] == makes` for each case.
   - viewport/test_document.gd: `d._op_makes(op) == makes` for each case.
3. `_op_refs` lists a push_pull's `assembly` when present, so a board drawn inside an assembly refers to it.
4. A rejection check in test_document.gd: a rejected make_assembly, then a push_pull with that `assembly`: the
   second joins the first (`joined` true, one note "... (and 1 action that built on it)").

Not in this job: `_op_refs` beyond the `assembly` line, `_op_touches`, the rejection message matching (H183), or changing `creations`.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope); quick 401/401.
- Changing one `makes` entry in tests/op_creations.json makes both the Python and the GDScript check fail (try it
  and put it back; say so in the response).
