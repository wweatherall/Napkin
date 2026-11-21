# Agent handoff

Shared scratchpad for Claude and Codex. Created by Codex on 2026-11-21 at William's request.

## How to use this file

- Read this file when picking up work; append a dated, signed response when answering an entry. File changes do not automatically notify the other agent.
- Keep entries short: a stable ID, author, date, status (open, answered, resolved), relevant references, and a concrete request or finding.
- Preserve the other agent's wording. Append responses under the relevant entry; update its status when appropriate. Re-read before writing and avoid simultaneous edits.
- Distinguish reported completion from independently verified behaviour. Include a commit or test result when available.
- This file coordinates work; it does not approve new behaviour or override William's decisions. Do not treat an entry addressed to an agent as authorization to start unrelated implementation.
- Move lasting specifications to the suggestions/design documents and approved decisions to the decision log. Keep a short resolution here linking to them.
- Keep this file short (both agents read it at the start of each job). When an entry is resolved, move it whole to [handoff-archive.md](handoff-archive.md), at the bottom, and add one line for it under "Archived" below: ID, subject, outcome. Either agent may archive an entry the other resolved. Read the archive only when you need an entry's history.

## References and authority

- [Decision log](decision-log.md): William's decisions, open questions, Work list and tunables (P09). Either agent records a decision William makes, in the commit it belongs to. Active decisions take precedence over suggestions; follow P01 for changes.
- [Codex's suggestions](../Codex%27s%20suggestions.md): detailed proposals and feature backlog, including S17 surface projection and branching history.
- [FreeCAD feature map](../FREECAD_FEATURE_MAP.md): native FreeCAD counterparts and capability checks.
- [Architecture](../ARCHITECTURE.md): architecture reference and proposed improvements; check against current code as implementation evolves.

## Open exchanges

### H015 — Tests now run side by side (T49): what changed for Codex

Author: Claude | Date: 2026-11-21 | Status: open (for Codex to read, then archive)

References: T49, T47, T45; branch t49-parallel-tests (9da1697, 3f4915c, eb23b02). ARCHITECTURE.md sections changed: Worker link (transport: test workers on port 0) and Tests.

Finding: (1) `SERVE_PORT=0 SERVE_PORT_FILE=<f>` makes the worker bind a free port and write it to f; every test starts its worker that way, so your runs and Claude's no longer collide. (2) `tools/quicktest.sh` opens three Godot windows (`--quick-lane=N`; `--one` for a single window); each quick-test section is a `_q_<name>()` in tests.gd, listed in `QUICK_LANES` and the `match` in `_run_quick_test`. A new section goes in both. (3) `worker/test_native.py` section H (runs of cuts and merges) is now `worker/test_runs.py`; their shared helpers, `OPS` and `HOPS` are in `worker/test_native_common.py`. (4) In a freecadcmd test that ends with `sys.exit`, print the summary line with `flush=True`, or it is lost. Quick test ~8 s, full test ~15 s.

## Jobs for Codex (assigned by William, 2026-11-21)

H005–H009 are done and archived (reviewed and merged by Claude, 2026-11-21). The rules below still apply to new jobs.

William asked Codex to start on these five. Claude wrote them up; William approved the list. They are independent: take them in any order (H005 and H006 first if you have to choose).

Rules for every job here:

- Work in your own worktree, never by switching branches in /Users/Will/Sites/fretchup (Claude works in that checkout; a checkout there changes Claude's files mid-task). For example: `git worktree add ../fretchup-codex-t38 -b codex/t38-spike main`.
- One branch per job, from main (a861955 or later). Commit there. Don't merge into main and don't push unless William says so; Claude reviews and merges.
- Touch only the files the job lists. Don't edit worker/replay.py, viewport/main.gd, viewport/tools/*, tools/*.sh or CLAUDE.md: Claude is changing them. If a job needs a change there, describe it in your response and Claude will make it.
- Before handing back: `tools/quicktest.sh` passes in your worktree (it uses its own ports, so William's open app doesn't matter). Run the FreeCAD tests with freecadcmd 1.1.4: /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd. Remember that freecadcmd runs a script a second time when it raises: read the first error.
- When done, append a response under the job: branch, commit, what you verified (commands and results), and what's still open. Set Status to answered. Questions that need William go in the response; don't decide behaviour yourselves.

## Archived

Full entries in [handoff-archive.md](handoff-archive.md).

- H010 — New Work list items T42–T44: splitting the code into parts. Resolved: T42 and T43 done (1739746, 95f9bb2); T44 unassigned.
- H001 — Reconcile earlier suggestions. Resolved: aligned with I12c, Q22, I26b and Q24 in codex/docs (8a01e3c), merged f92bc8d.

- H002 — Completion status and remaining work. Resolved: stale "not built" notes updated (log revision 60).
- H003 — Surface projection and Boolean mode handoff. Resolved: logged as decision I34 and Work list T38 (revision 60).
- H004 — Backlog reconciled; what changed since your review. Resolved: ARCHITECTURE.md brought up to date with W13 in H009 (8a01e3c, merged f92bc8d).
- H005 — T38 feasibility check: pushing a piece to another piece's surface. Resolved: T38 feasibility report merged (640609a); Work list T38 updated (log revision 62).
- H006 — T32 measurement parser (inches, fractions, millimetres). Resolved: parser merged (80175fa) with two review fixes (43210ef); in both test scripts.
- H007 — Worker tests for feature combinations. Resolved: test_combos.py merged (61 checks), run by both test scripts.
- H008 — U01 design spec: the undo history panel and branch storage. Resolved: U01 spec merged (c26c14e); its five questions wait for T36.
- H009 — Bring ARCHITECTURE.md and the feature map up to date. Resolved: docs merged (f92bc8d); spot-checked against the code.
- H011 — FreeCAD length evaluation and the hyphen decision. Resolved: merged with a local fast path for plain lengths (3db2cff, fd242f7); I35 logged.
- H012 — Native FreeCAD properties in Godot. Resolved: Properties panel merged (fd242f7); logged as I36, Work list T46 done.
- H013 — Architecture correction for H011 and H012. Resolved: ARCHITECTURE.md correction merged (b96e377), then updated to the integrated state (7e99653).
- H014 — Shared architecture ownership and automated checks. Resolved: shared ownership and the architecture check merged (b96e377); Claude commits with the hook.

## Entry template

### H015 — Short subject

Author: Claude or Codex | Date: YYYY-MM-DD | Status: open

References: decision IDs, files, commits, or tests.

Finding or request: ...

Response — Author, YYYY-MM-DD: ...

Resolution: ...
