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

### H030 — Tools share one press rule now (T57): what changed for Codex

Author: Claude | Date: 2026-11-21 | Status: open (for Codex to read, then archive)

References: I43 (replaces I29), I44, I45, T57; viewport/tools/tool.gd, viewport/tools/CLAUDE.md, ARCHITECTURE.md (module table: tool.gd, inference.gd rows); merge cb09ad7.

Finding: (1) Rectangle, Push/Pull and Move decide press-and-drag versus click-and-click with one rule in `tool.gd`: a tool that starts on a press calls `press_started(screen)`, `press_moved(screen)` on every move, and in `release` asks `press_released()` (`drag` true = finish now). A new tool that starts on a press uses these rather than its own thresholds; the interface is in the tools guide. (2) `inference.gd` has `on_grid(p)` (the grid step of `snap` without point snaps). (3) New quick section `tests/quick/press.gd` (lane 2).

### H032 — Your T50, T51, T56 and T34 are on main: what changed, and what's left

Author: Claude | Date: 2026-11-21 | Status: open (for Codex to read, then archive)

References: H027–H029, H031 (archived), H030; I46, I47, I48, Q32, T58, T54; merges bc3d929 (T50), 29ee1c9 (T51), 086b967 (T56), 14bfafb (T34); ARCHITECTURE.md sections: module table (selection.gd, select_tool.gd, worker mixins incl. deletion.py), state ownership table, "Selection operations (T34)", the deleted-instances bullet.

Finding: (1) All four of your branches are reviewed and merged; main also has the drag-lag work (T57, read H030). (2) IDs moved: main had taken I43–I45, T57 and H030 while T34 was open, so T34's rows are now I46 (Delete removes a board from the file unless a survivor needs it), I47 (copying a whole assembly makes a new assembly), I48 (Delete / Backspace rules), T58 and H031. Rebase anything that cites the old numbers. (3) Changes on top of your T34: `worker/deletion.py` `remove_unneeded()` actually removes objects nobody needs, removing what others depend on first (FreeCAD 1.1.4 drops expression links on undo in the other order; written up in worker/CLAUDE.md). `move` takes `groups: {old AssemblyId: new}` when copying a whole assembly (`assembly.py` `copy_into_assembly`); a copy row of an assembly is refused (T58). In `main.gd`, Delete/Backspace edits the measurements box once you have clicked it or typed, else deletes the selection, or in Move what's being moved (I48). New checks: scenario removal and assembly-copy steps, quick `selection.gd` and `assembly.gd` checks.

Still open (William decides when): Q32 (settle the Delete rules on real hardware), T58 (rows of assemblies), T54 (plane fits re-fit every board). A small fix is pending: a `QUICK_LANES` entry naming a missing section file makes the quick test hang until the 120 s timeout instead of failing.

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
- Use the IDs given here; if you need a new decision or Work list ID, take a placeholder (I-new-1, T-new-1) and
  the integrator numbers it at merge.
- Before handing back: `tools/quicktest.sh` passes in your worktree (own ports; William's open app doesn't
  matter). FreeCAD tests run with freecadcmd 1.1.4; it runs a script a second time when it raises: read the first error.
- Commit with `git -c core.hooksPath=.githooks commit`. Don't merge into main or push.
- When done, append a response under your job: branch, commit, what you verified (commands and results),
  architecture sections changed, what's still open. Set Status to answered and tell William it's ready for review.
  Behaviour choices are William's: ask in chat, one question at a time, with a recommendation.

### H033 — T74 + T77: IDs numbered at merge, one handoff file per entry

Author: Claude (integrator) | Date: 2026-11-21 | Status: open | For: a second Claude session

References: T74, T77, P09, P11; the I43–I45 clash (H032); tools/sort_decision_log.py (an existing log tool to copy the style of).

Touches: tools/number_ids.py (new) + tools/test_number_ids.py (new), docs/handoff/ (new, one file per open entry),
docs/agent-handoff.md (becomes the rules + an open list built from docs/handoff/), docs/decision-log.md (P09's ID
rule if needed, the T74/T77 rows), CLAUDE.md and AGENTS.md (the "Working with Codex" handoff/ID lines only),
tools/featuretest.sh only to add the new test to its list (one line; H034 also edits this file: add your line last).

Request: (1) T74: a branch writes placeholders (I-new-1, T-new-1, H-new-1, ...); `tools/number_ids.py` run on main
at merge replaces each with the next free number across the decision log, handoff files and the branch's
commit-touched docs, and reports what it did. A dry-run mode. Tests for: no placeholders, two kinds at once,
a placeholder cited in several files gets one number. (2) T77: open entries move to `docs/handoff/H0NN-slug.md`;
`docs/agent-handoff.md` keeps the how-to, the rules above, and an open list the script (or a small companion)
rebuilds from the folder; archiving moves a file to the archive the same way as today. Migrate H030, H032 and
H033–H035 last, after merging main (Codex will have written responses in H034/H035 by then). Ask William
before changing anything an agent would notice beyond what T74/T77 say.

### H034 — T76: split worker/test_scenario.py into a file per feature

Author: Claude (integrator) | Date: 2026-11-21 | Status: open | For: Codex

References: T76, P07, T48; bfbfa67 (the quick test finds its sections by name, the model to follow).

Touches: worker/test_scenario.py (becomes a thin runner or goes), worker/scenario/*.py (new, one per feature),
tests/scenario_fixture.json if its layout must change, tools/featuretest.sh (the scenario line; this job may edit
this one file under tools/; H033 adds one line to it too, keep yours to the scenario entry), worker/CLAUDE.md
(the scenario-test paragraph), CLAUDE.md (only the sentence "A new feature gets steps in `worker/test_scenario.py` first").

Request: same steps, same answers, same order where order matters (later steps build on earlier ones; keep
that chain explicit, e.g. numbered file names). The runner finds feature files by name, so a new feature adds a
file and edits nothing shared; a file listed but missing fails, it doesn't hang. Report the step count before
and after (must match) and `tools/featuretest.sh` timing before and after.

### H035 — T44: write the window ↔ worker protocol down (docs/protocol.md)

Author: Claude (integrator) | Date: 2026-11-21 | Status: open | For: Codex (a second session, or after H034)

References: T44, W13, A27, A29; ARCHITECTURE.md line ~290 (already points at T44).

Touches: docs/protocol.md (new), ARCHITECTURE.md (one link line where it mentions T44; nothing else),
docs/decision-log.md (the T44 row only). Read-only on code.

Request: every command and reply (hello, open, sync, replay, flush, bye, quit, saved, focus, and any others the
code has), with fields, types, units and an example; the files the worker writes (bodies.json, meshes,
materials.json, model.glb, the journal) and their fields; a protocol version number. Take it from the code
(worker/replay.py and the worker modules, viewport/document.gd and the worker link in viewport/), not from
memory or older docs, and cite file:function for each message. List any mismatches you find between the two
sides as findings; don't fix code in this job.

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

### H036 — Short subject

Author: Claude or Codex | Date: YYYY-MM-DD | Status: open

References: decision IDs, files, commits, or tests.

Touches: the files this job expects to change (P11).

Finding or request: ...

Response — Author, YYYY-MM-DD: ...

Resolution: ...
