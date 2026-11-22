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

### H016 — The decision log is now a file you can edit; small fixes have a light path

Author: Claude | Date: 2026-11-21 | Status: open (for Codex to read, then archive)

References: P08, P09, T52; branches log-todos-light-path, t52-log-structure (6236efa, 11ea593, 36c6dd5). ARCHITECTURE.md sections changed: none (one pointer line in the intro).

Finding: (1) P09: the claude.ai Sheet is retired; `docs/decision-log.md` is the log. Record a decision William makes in your chat there, in the commit it belongs to, following P01. (2) T52: Superseded rows have their own table; a row ending "(Details below.)" has its full text at `### <ID>` under Details. Keep new rows short; long text goes in a Details section. The pre-commit hook sorts tables and Details; `python3 tools/sort_decision_log.py --check` also matches marked rows to sections. (3) P08: small fixes (nothing William would notice, no protocol / format / boundary / saving change, ~30 lines) go on `codex/small-fixes` after the quick test, with no handoff entry; list them for William.

### H018 — The op list and sync now live in viewport/document.gd (T39)

Author: Claude | Date: 2026-11-21 | Status: open (for Codex to read, then archive)

References: T39, A31; branch t39-document-controller (a15b1d7). ARCHITECTURE.md sections changed: System overview (diagram), Where responsibilities live, State ownership, Lifecycle of an edit, Proposed evolution, Validation.

Finding: (1) `viewport/document.gd` (the document controller, `m.doc`) owns `ops`, `counters`, `seq` / `in_flight` / `dirty`, which sync reply counts, `confirmed_ids`, the undo floor, the redo stack, open / reset and the save revisions; it reports by signals and knows nothing of meshes. main.gd forwards the old names, so `m.ops.append(op); m.sync()` still works. (2) Removal goes through it: `op_removed(op)` is where main takes away what an op drew; a new op kind that draws something extra cleans it up in main.gd `_on_op_removed`. (3) New feature test: `viewport/test_document.gd` (headless, 38 checks; `DOCUMENT TESTS`). (4) T41 (presentation and selection/context out of main.gd) is next; main.gd will move again.

### H019 — Selection and drawing now live in viewport/selection.gd and viewport/presenter.gd (T41)

Author: Claude | Date: 2026-11-21 | Status: open (for Codex to read, then archive)

References: T41, A33b; branch t41-split-main (b718d00, 1fd8afe). ARCHITECTURE.md sections changed: System overview (diagram), Where responsibilities live (main, presenter, selection rows), State ownership, Proposed evolution, Validation.

Finding: (1) `viewport/selection.gd` (`m.sel`) owns the selection, the entered context, each board's assembly / row / family / array / mirror plane, the hidden set and `hover_body`, and adds the hide / assembly / make unique / detach ops. It draws nothing and reports by signals. (2) `viewport/presenter.gd` (`m.pres`) owns `body_tris` / `body_verts` / `body_edges` / `body_cuts`, drafts and rects, confirmed board nodes, remembered states, waves and the selection/context highlights. It draws with main's helpers through `m`, as tools do. (3) main.gd forwards every old name, so `m.selection`, `m.body_tris`, `m._begin_wave(...)` still work; code on a codex/* branch that edits these parts of main.gd will need re-basing onto the new files. (4) New feature test: `viewport/test_selection.gd` (41 checks; `SELECTION TESTS`).


### H025 — Your plane-properties work is on main (T53): what changed

Author: Claude | Date: 2026-11-21 | Status: open (for Codex to read, then archive)

References: T53, I40, I41, I42, T54; your H015-H019 (archived as H020-H024: main had already used H015-H019).

Ported onto main after T41, so the viewport side moved: board frames are `presenter.gd` `stock_frames` (main
forwards `m.stock_frames`), the selection tint and idle-hover refresh are in presenter `_show_boards`, the Tab and
Properties-pick input stays in main.gd. Review fixes: pushing a tied end again now detaches it (I26b said so; it
used to add a union while the fit kept following), and fit result lengths are written to 0.1 mm (`plane_fit.mm`;
`%.3g` gave 1.05e+03). New with William: the three end conditions in Push/Pull, ⌥ Option cycles them (I41;
`edge_fit.fit_mode`). Board names "Board N" now cover copies, mirrors and made-unique boards too (I42,
`common.board_label`). To do: T54. The decision log: your branch's copy was older than main's (it would have put
T39 back to In progress); AGENTS.md now says to merge main before editing the log and to log every choice William
makes for you, names included. Start new work from main; `codex/plane-properties` is done.
### H027 — T34 selection and ordinary editing

Author: Codex | Date: 2026-11-21 | Status: answered (ready for Claude review)

References: T34, Q13, I43; branch `codex/t34-selection`, worktree `/private/tmp/fretchup-codex-t34`.

Finding: Implemented window/crossing boxes, reusable multi-board selection for Move/Copy/Mirror, and Delete/Backspace/Edit > Delete. Each transform/delete is one op and one native undo transaction. I43 records William's clarification: deletion inside an entered component/array preserves the other instances and promotes a surviving original. Native deleted instances remain invisible dependencies when needed by links/mirrors; all model outputs exclude them. Array promotion preserves survivor positions/spacing and the entered row follows the new source. Cached undo/redo now restores relationship metadata with geometry, preventing stale assembly/array targeting after undo. Multi-copy count/distribution amendments retain all targets; shared array/mirror sources move once.

Verification: `tools/quicktest.sh`: 126 viewport checks, 154 scenario checks, 47 selection checks, every feature suite passes (logs `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-quick.Xo17oyC38A`). `tools/fulltest.sh`: passes, all six recorded models unchanged and targeted suites pass (logs `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-full.vMFY1b31Cw`). Decision-log check and `git diff --check` pass. FreeCAD 1.1.4 used throughout. Automated checks only; real hardware feel remains Q4.

Architecture sections changed: Where responsibilities live, State ownership and authority, Protocol at a glance (Selection operations), Native model and identity. Folder guides, S01 implementation status and FreeCAD feature mapping updated. Nothing merged or pushed. Open: review/integration only; no unanswered behavior questions for T34.

Response — Codex, 2026-11-21: Implementation committed as `79dacaf` on `codex/t34-selection`; decision I43. Verification and architecture sections are listed above; tracked pre-commit/architecture hooks passed. Worktree is ready for review/integration. No merge or push performed. William must pass this entry and branch to Claude; file edits send no notification.

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

- H026 — Documentation ownership and stale guidance cleanup. Resolved: William approved merge/push of T55 (d3b7aee); P10 recorded, quick/full tests passed.

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
- H020 — Rectangular board dimensions linked to a picked plane. Resolved: Ported onto main as T53 (4cdfcf2); logged as I40/I41/I42.
- H021 — Push/Pull infers a linked target face at an edge. Resolved: Ported onto main as T53 (4cdfcf2); I40.
- H022 — Dimensions disappeared after detaching and pulling again. Resolved: Ported onto main as T53 (4cdfcf2).
- H023 — Midpoint face links, direct dimension picking and selection tint. Resolved: Ported onto main as T53 (4cdfcf2); I39 logged, superseded by I40.
- H024 — Corner picks link to adjacent faces. Resolved: Ported onto main as T53 (4cdfcf2). Review fixes: re-pushing a tied end detaches it (b300dac); fit lengths in mm (b300dac). End conditions in Push/Pull, ⌥ cycles (29adca0, I41).

## Entry template

### H028 — Short subject

Author: Claude or Codex | Date: YYYY-MM-DD | Status: open

References: decision IDs, files, commits, or tests.

Finding or request: ...

Response — Author, YYYY-MM-DD: ...

Resolution: ...
