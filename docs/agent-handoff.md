# Agent handoff

Shared scratchpad for Claude and Codex. Created by Codex on 2026-11-21 at William's request.

## How to use this file

- Each open entry is its own file in [handoff/](handoff/) (T77), listed under "Open exchanges" below. Read this file, then the entries you're picking up; append a dated, signed response at the end of an entry's file when answering it. File changes do not automatically notify the other agent.
- Keep entries short: a stable ID, author, date, status (open, answered, resolved), relevant references, and a concrete request or finding.
- Preserve the other agent's wording. Append responses at the end of the entry's file; update its status when appropriate. Re-read before writing and avoid simultaneous edits.
- Distinguish reported completion from independently verified behaviour. Include a commit or test result when available.
- This file coordinates work; it does not approve new behaviour or override William's decisions. Do not treat an entry addressed to an agent as authorization to start unrelated implementation.
- Move lasting specifications to the suggestions/design documents and approved decisions to the decision log. Keep a short resolution here linking to them.
- A new entry is a new file, `docs/handoff/H-new-N-short-slug.md` (copy the template at the bottom; N = 1, 2 ... on your branch); the integrator numbers it at merge with `tools/number_ids.py` (T74). The open list is built from the folder by `python3 tools/handoff.py list`; don't edit it by hand (the merge step rebuilds it; on a conflict in it, run the command).
- Keep this file short (both agents read it at the start of each job). When an entry is resolved, `python3 tools/handoff.py archive H0NN` moves it whole to [handoff-archive.md](handoff-archive.md), at the bottom, and adds one line for it under "Archived" below: ID, subject, outcome (its Resolution line). Either agent may archive an entry the other resolved. Read the archive only when you need an entry's history.
- An entry written straight into this file by habit: `python3 tools/handoff.py split` moves it to its own file.

## References and authority

- [Decision log](decision-log.md): William's decisions, open questions, Work list and tunables (P09). Either agent records a decision William makes, in the commit it belongs to. Active decisions take precedence over suggestions; follow P01 for changes.
- [Codex's suggestions](../Codex%27s%20suggestions.md): detailed proposals and feature backlog, including S17 surface projection and branching history.
- [FreeCAD feature map](../FREECAD_FEATURE_MAP.md): native FreeCAD counterparts and capability checks.
- [Architecture](../ARCHITECTURE.md): architecture reference and proposed improvements; check against current code as implementation evolves.

## Open exchanges

<!-- open list: built from docs/handoff/ by tools/handoff.py; don't edit by hand -->

- [H030 — Tools share one press rule now (T57): what changed for Codex](handoff/H030-tools-share-one-press-rule-now.md) — status: open (for Codex to read, then archive)
- [H032 — Your T50, T51, T56 and T34 are on main: what changed, and what's left](handoff/H032-your-t50-t51-t56-and-t34.md) — status: open (for Codex to read, then archive)
- [H033 — T74 + T77: IDs numbered at merge, one handoff file per entry](handoff/H033-t74-t77-ids-numbered-at-merge.md) — status: open; for: a second Claude session
- [H034 — T76: split worker/test_scenario.py into a file per feature](handoff/H034-t76-split-worker-test-scenario-py.md) — status: open; for: Codex
- [H035 — T44: write the window ↔ worker protocol down (docs/protocol.md)](handoff/H035-t44-write-the-window-worker-protocol.md) — status: open; for: Codex (a second session, or after H034)

<!-- end of open list -->

## Jobs, round 1 (assigned by the integrator, approved by William, 2026-11-21)

The integrator is a Claude session in /Users/Will/Sites/fretchup: it hands out jobs, reviews branches and merges
them when William says. Round 1 clears the spots where parallel branches collide (T74–T77) and writes the
protocol down (T44). The three jobs touch different files and can run at the same time.

Rules for every job (Claude or Codex):

- Your own worktree and branch from main, never a checkout in /Users/Will/Sites/fretchup (the integrator works
  there). Claude: `git worktree add ../fretchup-claude-<item> -b claude/<item> main`. Codex: `codex/<item>`.
- Touch only the files your job lists. If you need another file, say so in chat and in your response first:
  another job may own it. Shared hot spots (your Work list row, your handoff response, a line in
  ARCHITECTURE.md) are small edits made at the end, after merging main into your branch.
- Use the IDs given here; if you need a new decision or Work list ID, take a placeholder (I-new-N, T-new-N with N = 1,
  2 ...) and the integrator numbers it at merge (`tools/number_ids.py`, T74).
- Before handing back: `tools/quicktest.sh` passes in your worktree (own ports; William's open app doesn't
  matter). FreeCAD tests run with freecadcmd 1.1.4; it runs a script a second time when it raises: read the first error.
- Commit with `git -c core.hooksPath=.githooks commit`. Don't merge into main or push.
- When done, append a response under your job: branch, commit, what you verified (commands and results),
  architecture sections changed, what's still open. Set Status to answered and tell William it's ready for review.
  Behaviour choices are William's: ask in chat, one question at a time, with a recommendation.

## Archived

Full entries in [handoff-archive.md](handoff-archive.md).

- H031 — T34 selection and ordinary editing. Resolved: merged into main with T34; I46-I48, T58, Q32 logged.
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

Save as `docs/handoff/H-new-N-short-slug.md`; the number is given at merge.

### H-new-N — Short subject

Author: Claude or Codex | Date: YYYY-MM-DD | Status: open | For: who should act on it

References: decision IDs, files, commits, or tests.

Touches: the files this job expects to change (P11).

Finding or request: ...

Response — Author, YYYY-MM-DD: ...

Resolution: ...
