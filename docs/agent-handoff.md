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

### H027 — T50: explicit worker imports ready for review

Author: Codex | Date: 2026-11-21 | Status: answered (ready for Claude review)

References: T50, T42; branch `codex/t50-explicit-imports`, implementation commit `b21f1c5`.

Response — Codex, 2026-11-21: Replaced every worker/test star import with explicit imports from the owning module, including standard-library and FreeCAD dependencies formerly re-exported through common/session/export. test_load now only configures the FreeCAD test runtime; shared native-test helpers remain explicitly imported from test_native_common. Updated worker/CLAUDE.md and ARCHITECTURE.md “Where responsibilities live” (common.py row). No new decision IDs or behaviour choices; implements existing T50. Worktree: /private/tmp/fretchup-codex-t50. Not merged or pushed.

Verification: tools/quicktest.sh passed (all feature tests; viewport 99/0); tools/fulltest.sh passed (all feature tests and targeted checks; all six recorded suites unchanged), using FreeCAD 1.1.4. Native apps required running outside the sandbox after the sandbox aborted Godot. Static AST/symbol checks found no star imports or unresolved global names anywhere in worker/*.py, and confirmed implementation/test bodies unchanged from main (apart from test_load's intentional removal of re-exports). git diff --check and decision-log sort check passed. Nothing open; Claude should review and merge when William authorizes it.

### H028 — T51: viewport tests split into suites and quick sections

Author: Codex | Date: 2026-11-21 | Status: answered (ready for Claude review)

References: T51, P07, T49; branch `codex/t51-test-suites`.

Request: William asked Codex to complete T51.

Response — Codex, 2026-11-21: `viewport/tests.gd` is now a 50-line test-mode dispatcher. `viewport/tests/harness.gd`
owns the shared viewport reference, 40 input/timing/assertion helpers and quick-run counters/timing. Each of the
21 UI suites is in `tests/suites/`; each of 19 quick sections is in `tests/quick/`. `tests/quick_runner.gd` owns
QUICK_LANES and loads those sections in the same order using the same harness (including the dependent
reject → trackpad → models → worker sequence). Add a quick section file and list its name in QUICK_LANES;
there is no second dispatch match to maintain. Parse checking now covers all new scripts; folder guides updated.

Verified: `tools/quicktest.sh`: all feature tests and 99 viewport checks passed (8.8 s viewport, three windows).
`tools/quicktest.sh --one`: all feature tests and 99 viewport checks passed (23.5 s viewport, concurrent with full).
`tools/fulltest.sh`: exit 0; all six recorded suites unchanged against existing references; all targeted and feature
tests passed. One-off extraction audit compared every suite, quick section and helper body against main:
unchanged apart from entry method names and shared-harness qualifiers. `git diff --check` passed.
Test runs needed normal app-data/GUI access: sandboxed Godot could not open its user log and crashed.

Architecture sections changed: Where responsibilities live (test files, harness ownership and runtime loading),
Planned boundaries (T51 implemented). No behavior decisions or new decision IDs. No open implementation questions.
Implementation: `d11211c`. Nothing merged or pushed; ready for review on this branch.

### H029 — T56: startup report todo recorded

Author: Codex | Date: 2026-11-21 | Status: answered (ready for review)

References: T56; branch `codex/startup-todo`.

Response — Codex, 2026-11-21: William requested a todo for a compact agent startup command. Added T56 as Open; implementation, command naming and exact output remain future work. This branch changes documentation only; no architecture sections changed. Verification: decision-log sort check and git diff --check passed. No additional decision IDs; the request is recorded in T56. Not merged or pushed.

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

### H030 — Short subject

Author: Claude or Codex | Date: YYYY-MM-DD | Status: open

References: decision IDs, files, commits, or tests.

Finding or request: ...

Response — Author, YYYY-MM-DD: ...

Resolution: ...
