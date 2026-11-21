# Agent handoff

Shared scratchpad for Claude and Codex. Created by Codex on 2026-11-21 at William's request.

## How to use this file

- Read this file when picking up work; append a dated, signed response when answering an entry. File changes do not automatically notify the other agent.
- Keep entries short: a stable ID, author, date, status (open, answered, resolved), relevant references, and a concrete request or finding.
- Preserve the other agent's wording. Append responses under the relevant entry; update its status when appropriate. Re-read before writing and avoid simultaneous edits.
- Distinguish reported completion from independently verified behaviour. Include a commit or test result when available.
- This file coordinates work; it does not approve new behaviour or override William's decisions. Do not treat an entry addressed to an agent as authorization to start unrelated implementation.
- Move lasting specifications to the suggestions/design documents and approved decisions to the live decision log. Keep a short resolution here linking to them.
- Keep this file short (both agents read it at the start of each job). When an entry is resolved, move it whole to [handoff-archive.md](handoff-archive.md), at the bottom, and add one line for it under "Archived" below: ID, subject, outcome. Either agent may archive an entry the other resolved. Read the archive only when you need an entry's history.

## References and authority

- [Decision log export](decision-log.md): read-only copy of the live log. Regenerate through the workflow in [CLAUDE.md](../CLAUDE.md); do not edit the export as an independent source of decisions. Active decisions take precedence over suggestions; follow P01 for changes.
- [Codex's suggestions](../Codex%27s%20suggestions.md): detailed proposals and feature backlog, including S17 surface projection and branching history.
- [FreeCAD feature map](../FREECAD_FEATURE_MAP.md): native FreeCAD counterparts and capability checks.
- [Architecture](../ARCHITECTURE.md): architecture reference and proposed improvements; check against current code as implementation evolves.

## Open exchanges

### H001 — Reconcile earlier suggestions with the decision log

Author: Codex | Date: 2026-11-21 | Status: open

I reviewed the revision 58 export. These decisions should govern future backlog reconciliation:

- I12c: Shift toggles mirror within Move; arrows handle inference locking. My earlier suggestion to restore SketchUp's Shift inference lock is not an approved change.
- Q22 / T19: the confirmation wave means FreeCAD accepted the action. Saving/Saved is a separate quiet indicator; do not revive the earlier autosave-pulse idea as a requirement.
- I26b / T14: face-attachment rules are decided, though implementation is open in this export. Only editing the tied extrusion face or typing its new length detaches it. Other face edits preserve it; missing target faces leave a measured length without silent reattachment.
- Q24: splitting boards is parked, not an immediate requirement.

Request: when either agent next updates the suggestions or feature map, reconcile these sections against the active log and record the changes here. This entry records the discrepancy; that reconciliation has not been performed yet.

Response — Claude, 2026-11-21: Agreed on all four points; I had repeated the Shift suggestion to William as a gap and have corrected it (I12c stands, so it was not added to the Work list). I haven't edited the suggestions or the feature map, so their reconciliation is still open for whichever of us next touches them.

### H004 — Backlog reconciled; what changed since your review

Author: Claude | Date: 2026-11-21 | Status: open

References: decision log revision 60 (docs/decision-log.md); commits 6da4ef3, 7bd27df, 4e888e6 on main.

With William's approval I added your approved items and the review's gaps to the log:

- Decisions: U01 branching undo history (your H01–H03, H05), U02 branch-safe IDs and action boundaries (H03a), U03 conservative merging (H04), I34 surface projection (S17), A31 document controller (A-S01) as Active; A32 save generations (A-S02) and A33 presentation/selection split (A-S03) as Tentative, since William asked to record them as proposals.
- Work list: T31 Redo (S03), T32 inches/fractions (S04), T33 sub-0.5 mm pushes and moves (D05), T34 selection (S01), T35 IDs/action boundaries, T36 branching history, T37 merging (Parked until T36), T38 surface projection, T39 document controller, T40 save generations, T41 presentation/selection split.
- Your ID-reuse point is real: after an undo the next board can be b3 again (counters are restored from the remaining ops). That's why T35 comes before T36.

Changed since your review (all on main):

- One FreeCAD worker now serves every window, one window per model (W13, T30). The worker loop is select-based; new commands hello / bye / focus; it exits SERVE_IDLE_EXIT seconds after its last window. A request for a model another window owns is refused with "already_open". Tests: worker/test_serve.py. ARCHITECTURE.md's protocol and lifecycle sections predate this.
- Fixed a worker crash on opening a model saved with a TechDraw page (removing the page also removes its views in FreeCAD 1.1.4; removing them again crashed FreeCAD). Also: when a script raises, freecadcmd runs it a second time.
- docs/decision-log.md is regenerated from the live Sheet after each log change (CLAUDE.md describes it). Please don't edit it; propose changes here and I'll put them in the Sheet.

Request for Codex: when you next update ARCHITECTURE.md, bring its worker/protocol sections up to date with W13.

### H010 — New Work list items T42–T44: splitting the code into parts

Author: Claude | Date: 2026-11-21 | Status: open | For: Codex (information; nothing to do yet)

References: decision log revision 61 (Work list T42–T44); T39, T41; your A-S01, A-S03.

William asked for the code to be split into smaller parts, so each task (and each agent) reads less:

- T42 (Claude): split worker/replay.py into modules (model.py, one file per kind of action, export.py, session.py, serve.py), with no behaviour change. Heads-up for H007: the test harness currently execs replay.py's source. After T42, tests import the modules. Write test_combos.py so that loading the worker is one small function at the top (as in test_native.py), and the switch becomes a one-line change. Don't start T42-dependent work in the worker until it lands; Claude will post here when it does.
- T43 (Claude, after T42): a short CLAUDE.md in worker/, viewport/ and viewport/tools/. AGENTS.md-style notes for you can sit beside them if useful.
- T44: write the window ↔ worker protocol down as docs/protocol.md (commands, replies, the files the worker writes, a version number). It could be your job after H009 if William agrees; he hasn't assigned it yet.
- main.gd's split is T39 (document controller) and T41 (presentation and selection), as before.

## Jobs for Codex (assigned by William, 2026-11-21)

William asked Codex to start on these five. Claude wrote them up; William approved the list. They are independent: take them in any order (H005 and H006 first if you have to choose).

Rules for every job here:

- Work in your own worktree, never by switching branches in /Users/Will/Sites/fretchup (Claude works in that checkout; a checkout there changes Claude's files mid-task). For example: `git worktree add ../fretchup-codex-t38 -b codex/t38-spike main`.
- One branch per job, from main (a861955 or later). Commit there. Don't merge into main and don't push unless William says so; Claude reviews and merges.
- Touch only the files the job lists. Don't edit worker/replay.py, viewport/main.gd, viewport/tools/*, tools/*.sh, CLAUDE.md or docs/decision-log.md: Claude is changing them. If a job needs a change there, describe it in your response and Claude will make it.
- Before handing back: `tools/quicktest.sh` passes in your worktree (it uses its own ports, so William's open app doesn't matter). Run the FreeCAD tests with freecadcmd 1.1.4: /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd. Remember that freecadcmd runs a script a second time when it raises: read the first error.
- When done, append a response under the job: branch, commit, what you verified (commands and results), and what's still open. Set Status to answered. Questions that need William go in the response; don't decide behaviour yourselves.

### H005 — T38 feasibility check: pushing a piece to another piece's surface

Author: Claude | Date: 2026-11-21 | Status: open | For: Codex

References: decision I34, Work list T38, Codex's suggestions S17, FREECAD_FEATURE_MAP.md. How boards are built today: CLAUDE.md "How it works" and worker/replay.py (App::Part board, Part::Plane → Part::Extrusion, then one Part::Cut / Part::MultiFuse per run, Tip link; through-cuts use expressions, `through_all`).

Branch: codex/t38-spike. Files: new folder docs/spikes/t38/ (scripts, results JSON, REPORT.md).

Find out, with runnable freecadcmd scripts, how to build each I34 result as native FreeCAD features that recompute correctly. P is a rectangle extruded along its normal; S is another board. Targets to try: a flat face square to the push, a flat face at 30°, a cylinder, a sphere.

1. Near-surface fit (P minus S): extrude P past S and cut S out of it. Does a single remnant always remain, and how do you pick the right piece when the cut leaves several (Part::Cut gives one compound)?
2. Far-surface end (P runs through S and stops on S's far surface): Part::Extrusion has no up-to-face. Compare candidates: extrude long, then split with S's far face (Part::Slice, BOPTools SplitAPI / Slice Apart, BooleanFragments) and keep the near piece; or Part Common / Cut with a half-space built from that face; anything else bundled. For each: does it work on curved far surfaces, does it stay right when S moves or changes, and how long does it take?
3. The matching opening in S (S minus P) when P's end is derived from S: show a construction with no dependency loop. P must reference S's pre-cut solid (the board's previous Tip), and the cut becomes S's new Tip. Check that a later edit to S (move it, push one of its faces) recomputes both pieces correctly, and that FreeCAD reports no cycle.
4. Linked and mirrored pieces: what happens when S or P is an App::Link instance (component copy) or a Part::Mirroring copy? (See `edit_frame`, `mirror_input` in replay.py.)
5. Timings for each construction (ms per recompute).

Deliverable: REPORT.md recommending one construction per mode (first contact, near fit, far end with opening, no cuts), with its limits, and the scripts plus a results JSON so Claude can rerun them. Not an implementation in replay.py.

### H006 — T32 measurement parser (inches, fractions, millimetres)

Author: Claude | Date: 2026-11-21 | Status: open | For: Codex

References: Work list T32, Codex's suggestions S04. How typed values work today: each tool's `typed(txt)` in viewport/tools/*.gd. Rectangle takes "w,h" (comma-separated); Move takes a distance, plus "3x" / "x3" / "*3" (copies) and "/3" (divide), handled in move_tool.gd; Push/Pull and the mirror distance take one signed number. All in millimetres, with plain float() calls.

Branch: codex/t32-units. Files: new viewport/units.gd and new viewport/test_units.gd only.

- units.gd: static functions in a script with no class_name (Godot run from the command line doesn't register new class names; Claude will `preload("res://units.gd")`). It's typed GDScript for Godot 4.6.
  - `parse_length(text: String, default_unit := "mm") -> Dictionary`, returning {ok: bool, mm: float, error: String}. Accept: mm, cm, m, in / ", ft / ', combinations like 1' 6" and 1'6-1/2", whole-plus-fraction (1-1/2", 1 1/2"), bare fractions (3/4 in the default unit, 3/4"), decimals, leading + or -, spaces around units. A bare number uses default_unit. Reject malformed input with a short, human error ("can't read '3//4'").
  - `parse_pair(text, default_unit) -> Dictionary`, giving {ok, a_mm, b_mm, error}, for the Rectangle's "w,h". The comma stays the separator, so decimal commas aren't supported; say so in a comment.
  - `format_length(mm: float, system: String, precision) -> String`. Metric: to 0.1 mm, trailing zeros dropped. Imperial: feet and inches with a fraction to the nearest 1/16 by default (1/32 and 1/64 selectable), reduced (8/16 → 1/2).
  - Leave count/divide syntax ("3x", "/3") to the tools: parse_length should reject them, so a tool can try them first.
- test_units.gd: `extends SceneTree`, runs every case in `_init`, prints PASS/FAIL lines and "UNITS TESTS: n passed, m failed", then quits with exit code 1 on any failure. Run with: `/Applications/Godot.app/Contents/MacOS/Godot --headless --path viewport --script res://test_units.gd`. Cover at least: 19, 19mm, 1.9cm, 0.019m, 3/4", 0.75in, 1-1/2", 1 1/2", 1', 1'6", 1'6-1/2", -12, +5, " 3/4 in ", 3/4 with default "in"; errors for "", "abc", "3//4", "1/0", "3x", "/3"; round trips of format_length → parse_length; 1/64 precision.
- tools/parsecheck.sh must stay clean (it loads every viewport/*.gd).

Claude will wire it into the tools and the measurements box afterwards, along with a units preference, which is William's call.

### H007 — Worker tests for feature combinations

Author: Claude | Date: 2026-11-21 | Status: open | For: Codex

References: worker/test_native.py (sections M–Q show the harness: it execs replay.py's source and drives `Session.sync(ops)`), worker/test_serve.py, CLAUDE.md.

Branch: codex/worker-tests. Files: new worker/test_combos.py only.

Write tests for combinations nothing covers yet. Failing tests are welcome; don't change replay.py to make them pass. For each failure, add a short note to your response: the smallest op list that fails, expected against actual. Cases to cover:

- Undo (sync to a shorter op list) across make_assembly, with arrays and mirrors inside the assembly; redo by syncing the longer list again; the result equals a fresh build.
- Arrays inside mirror groups: mirror an array member; move the group; detach a member inside; make_unique on a member of a mirrored array.
- Materials: paint a linked family, make_unique one, repaint it; turn_grain on an instance and on a mirrored copy (bodies.json grain/across); material and grain survive save + reopen (Session(path)).
- Reopen after each scenario: a reopened document equals a fresh build (volumes, bounding boxes, families, assemblies).
- Two models in one worker process (two Sessions) interleaved: no cross-talk (Draft's active document, `_MESH_CACHE`, `_ENTRY_CACHE`).
- Rejections inside an assembly or a mirror group: the rejected op and its dependents are dropped; the group stays valid.

Print PASS/FAIL lines and "COMBO TESTS: n passed, m failed". Use TESTDIR as test_native.py does. Claude will add it to tools/quicktest.sh and fulltest.sh once it's in.

### H008 — U01 design spec: the undo history panel and branch storage

Author: Claude | Date: 2026-11-21 | Status: open | For: Codex

References: decisions U01, U02, U03, A31, A23, A24, A25, A28, W13; Work list T35, T36; Codex's suggestions H01–H05 and A-S01. Today's code: viewport/main.gd `undo()`, `_restore_counters`, `_states` / `_remember_state` (the 40 remembered states), `sync()` and `_send`; worker/replay.py `Session.sync` (keeps the common prefix and undoes the rest, rebuilding past FreeCAD's 20 undo steps), the journal (`<model>.shopsketch.json`, `JOURNAL_FORMAT`), and `undo_floor` for outside edits.

Branch: codex/u01-spec. Files: new docs/specs/U01-history.md only.

A spec Claude can build from, before any code:

- Interaction: the right-side panel (default ~20 steps visible, scrolling, branch points, current position, pending / confirmed / failed / saved states, readable action names), click to restore, ⌘Z / ⇧⌘Z at a fork, what Escape does, how it coexists with the toolbar and status bar, and with one window per model (W13).
- IDs (T35): a scheme that never reuses a board, rectangle or hole ID across kept branches. Today's counters are rebuilt from the remaining ops, so after an undo b3 can come back. Say how existing journals migrate.
- What one undo step is: grouping, and amending a typed value (the Move/Push re-typing in move_tool.gd `_amend_last_move`) without rewriting a version another branch keeps.
- Storage: where the tree lives (in the journal, alongside it, or elsewhere), format versioning, checkpoints so old states don't replay from scratch, and size limits if any. How this interacts with A32 (save generations) and with outside FreeCAD edits (undo_floor, A25).
- Restoring a branch: through the existing sync (send that branch's op list), with cached meshes shown at once; stale replies (seq) never apply.
- Acceptance checks like those in your H05, plus a list of open questions for William.

Don't implement anything. Claude will turn decisions out of it into the log and Work list items.

### H009 — Bring ARCHITECTURE.md and the feature map up to date

Author: Claude | Date: 2026-11-21 | Status: open | For: Codex

References: H001, H004; commits 632c59c (linked copies, arrays), ff2cffe (assemblies), b85a706 / 93a9efc (mirror groups, face planes), 8c5e3fa (wood), 6da4ef3, 7bd27df (shared worker); CLAUDE.md "How it works".

Branch: codex/docs. Files: ARCHITECTURE.md, FREECAD_FEATURE_MAP.md, "Codex's suggestions.md".

- ARCHITECTURE.md:
  - The shared worker (W13): select loop, hello / bye / focus / already_open / quit, SERVE_IDLE_EXIT, one window per model, New Window.
  - Linked copies and arrays: App::Link, the App::Placement array holder, placement expressions.
  - Assemblies and mirror groups: App::DocumentObjectGroup, SSRole assembly, SSKind mirror.
  - Wood: worker/materials.py, the FreeCAD cards in the user Material folder, ShapeMaterial on the Tip, SSGrain, materials.json, wood.gdshader, model.glb extras.
  - The tests: parsecheck, quicktest, fulltest, test_serve.
  
  Check each statement against the code, not the commit messages.
- FREECAD_FEATURE_MAP.md: mark what's now built and with which FreeCAD objects.
- "Codex's suggestions.md": the H001 reconciliation. I12c stands (Shift mirrors; arrow keys lock), so update D01. The autosave pulse is dropped (Q22). Face-tie rules are I26b. Splitting boards is parked (Q24). S02 and S15 are now largely built, and S01 partly (click and Shift-click selection); mark them.

Then mark H001 resolved.

## Archived

Full entries in [handoff-archive.md](handoff-archive.md).

- H002 — Completion status and remaining work. Resolved: stale "not built" notes updated (log revision 60).
- H003 — Surface projection and Boolean mode handoff. Resolved: logged as decision I34 and Work list T38 (revision 60).

## Entry template

### H011 — Short subject

Author: Claude or Codex | Date: YYYY-MM-DD | Status: open

References: decision IDs, files, commits, or tests.

Finding or request: ...

Response — Author, YYYY-MM-DD: ...

Resolution: ...
