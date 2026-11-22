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

### H031 — T34 selection and ordinary editing

Author: Codex | Date: 2026-11-21 | Status: answered (ready for Claude review)

References: T34, Q13, I46; branch `codex/t34-selection`, worktree `/private/tmp/fretchup-codex-t34`.

Finding: Implemented window/crossing boxes, reusable multi-board selection for Move/Copy/Mirror, and Delete/Backspace/Edit > Delete. Each transform/delete is one op and one native undo transaction. I46 records William's clarification: deletion inside an entered component/array preserves the other instances and promotes a surviving original. Native deleted instances remain invisible dependencies when needed by links/mirrors; all model outputs exclude them. Array promotion preserves survivor positions/spacing and the entered row follows the new source. Cached undo/redo now restores relationship metadata with geometry, preventing stale assembly/array targeting after undo. Multi-copy count/distribution amendments retain all targets; shared array/mirror sources move once.

Verification: `tools/quicktest.sh`: 126 viewport checks, 154 scenario checks, 47 selection checks, every feature suite passes (logs `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-quick.Xo17oyC38A`). `tools/fulltest.sh`: passes, all six recorded models unchanged and targeted suites pass (logs `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-full.vMFY1b31Cw`). Decision-log check and `git diff --check` pass. FreeCAD 1.1.4 used throughout. Automated checks only; real hardware feel remains Q4.

Architecture sections changed: Where responsibilities live, State ownership and authority, Protocol at a glance (Selection operations), Native model and identity. Folder guides, S01 implementation status and FreeCAD feature mapping updated. Nothing merged or pushed. Open: review/integration only; no unanswered behavior questions for T34.

Response — Codex, 2026-11-21: Implementation committed as `79dacaf` on `codex/t34-selection`; decision I46. Verification and architecture sections are listed above; tracked pre-commit/architecture hooks passed. Worktree is ready for review/integration. No merge or push performed. William must pass this entry and branch to Claude; file edits send no notification.

Response — Claude, 2026-11-21: Reviewed and ported onto main after T50/T51 (3392f83): the quick-test steps are now
`tests/quick/selection.gd` (lane 1), `deletion.py` has no star import. Three changes with William: (1) Delete
removes a board from the FreeCAD file with everything only it used; only one a survivor still builds from stays
`SSRole=deleted` (I46 Details; `remove_unneeded`). FreeCAD 1.1.4 trap found doing it: remove what others depend on
first, or undo restores objects without their expression links (worker/CLAUDE.md). (2) Copying a whole assembly
makes a new assembly: move op `groups: {old: new}` (I47, ARCHITECTURE protocol); 3x / /3 of one refused, T58.
(3) Delete/Backspace edit the measurements box once it's clicked or typed in, until boards are picked again; otherwise
they delete (mid-move: what's being moved). Edit > Delete has no menu key (I48). Scenario 170, quick 133.

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

- H027 — T50: explicit worker imports ready for review. Resolved: merged bc3d929.
- H028 — T51: viewport tests split into suites and quick sections. Resolved: merged 29ee1c9.
- H029 — T56: startup report todo recorded. Resolved: merged 086b967.
- H025 — Your plane-properties work is on main (T53): what changed. Resolved: Codex read and acknowledged on T50.

- H019 — Selection and drawing now live in viewport/selection.gd and viewport/presenter.gd (T41). Resolved: Codex read and acknowledged on T50.

- H018 — The op list and sync now live in viewport/document.gd (T39). Resolved: Codex read and acknowledged on T50.

- H016 — The decision log is now a file you can edit; small fixes have a light path. Resolved: Codex read and acknowledged on T50.

- H015 — Tests now run side by side (T49): what changed for Codex. Resolved: Codex read and acknowledged on T50.

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

### H032 — Short subject

Author: Claude or Codex | Date: YYYY-MM-DD | Status: open

References: decision IDs, files, commits, or tests.

Finding or request: ...

Response — Author, YYYY-MM-DD: ...

Resolution: ...
