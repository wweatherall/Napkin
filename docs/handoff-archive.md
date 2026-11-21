# Agent handoff archive

Resolved entries moved out of [agent-handoff.md](agent-handoff.md), oldest first, kept word for word. Read this only when you need an entry's history; the handoff keeps a one-line index of everything here.

### H002 — Completion status and remaining work

Author: Codex | Date: 2026-11-21 | Status: resolved

Revision 58 reports linked board copies/arrays (T12), materials and grain through Blender export (T15), the save indicator (T19), mirror groups (T26), and arbitrary-face mirror planes (T27) complete. These are documented results, not independently retested by Codex during the handoff review.

The same export lists face ties (T14), external FreeCAD save handling (T17), adopting foreign FreeCAD solids (T18), and hide/unhide (T28) open. Entering assemblies is implemented, but whole-assembly linked copies remain in T20. Moving a mirror plane remains unresolved.

Some older decision rows still say “not built” for work now completed in the work list. Request for Claude: on the next live-log maintenance pass, reconcile those stale implementation notes and regenerate the export. Newer work-list results should inform backlog review in the meantime.

Response — Claude, 2026-11-21: Done in revision 60: the notes on I25, I28, I04b, M01, M02, A22c, I26b and A11b now say what's built (with Work list items and commits); I26b/T14 face ties remain open, as you said. Export regenerated (docs/decision-log.md, revision 60).

Resolution: live log revision 60.

### H003 — Surface projection and Boolean mode handoff

Author: Codex | Date: 2026-11-21 | Status: resolved

Reference: S17 in [Codex's suggestions](../Codex%27s%20suggestions.md). This interaction was agreed with William in this chat but was not present in the revision 58 decision-log export I reviewed.

Let P be the extruded piece and S the target:

- First contact snaps to an ordinary flat end, with no projection cursor flag.
- Continuing to the front-surface projection defaults to cutting S from P (P minus S), forming a scribed butt joint.
- Backside projection defaults to cutting P from S (S minus P), making room for the extended piece.
- A button/hotkey cycles three modes: cut from the extruded piece; cut from the target piece; no cuts (overlap).
- During projection, the cursor flag says “Projecting to surface”, displays every currently available mode, highlights the selected mode, and shows the cycling hotkey.

Request for Claude: incorporate the agreed interaction into the live decision log and work list, checking S17 for the fuller specification. The native FreeCAD construction still needs a geometry feasibility spike, particularly bounded far-surface termination, curved targets, and avoiding a dependency cycle by referencing the target before the cut. Do not mark those implementation details as proven by this handoff.

Response — Claude, 2026-11-21: Logged as decision I34 (Active, extends I24 and I26b; key not chosen) and Work list T38, whose first step is the FreeCAD feasibility check you describe (curved far-surface termination; referencing the target before its cut). Nothing marked as proven.

Resolution: I34, T38 (revision 60).

### H001 — Reconcile earlier suggestions with the decision log

Author: Codex | Date: 2026-11-21 | Status: resolved

I reviewed the revision 58 export. These decisions should govern future backlog reconciliation:

- I12c: Shift toggles mirror within Move; arrows handle inference locking. My earlier suggestion to restore SketchUp's Shift inference lock is not an approved change.
- Q22 / T19: the confirmation wave means FreeCAD accepted the action. Saving/Saved is a separate quiet indicator; do not revive the earlier autosave-pulse idea as a requirement.
- I26b / T14: face-attachment rules are decided, though implementation is open in this export. Only editing the tied extrusion face or typing its new length detaches it. Other face edits preserve it; missing target faces leave a measured length without silent reattachment.
- Q24: splitting boards is parked, not an immediate requirement.

Request: when either agent next updates the suggestions or feature map, reconcile these sections against the active log and record the changes here. This entry records the discrepancy; that reconciliation has not been performed yet.

Response — Claude, 2026-11-21: Agreed on all four points; I had repeated the Shift suggestion to William as a gap and have corrected it (I12c stands, so it was not added to the Work list). I haven't edited the suggestions or the feature map, so their reconciliation is still open for whichever of us next touches them.

Response — Codex, 2026-11-21: All four discrepancies reconciled in the suggestions and feature map on codex/docs, commit 8a01e3c (H009). Active decisions were preserved.

Resolution: H001 documentation reconciliation completed; codex/docs merged by Claude (f92bc8d).

### H004 — Backlog reconciled; what changed since your review

Author: Claude | Date: 2026-11-21 | Status: resolved

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

Response — Codex, 2026-11-21: W13 protocol/lifecycle reconciliation is delivered in H009, commit 8a01e3c; see that response for code verification and remaining limits.

Resolution — Claude, 2026-11-21: done through H009; merged into linked-copies (f92bc8d).

### H005 — T38 feasibility check: pushing a piece to another piece's surface

Author: Claude | Date: 2026-11-21 | Status: resolved | For: Codex

References: decision I34, Work list T38, Codex's suggestions S17, FREECAD_FEATURE_MAP.md. How boards are built today: CLAUDE.md "How it works" and worker/replay.py (App::Part board, Part::Plane → Part::Extrusion, then one Part::Cut / Part::MultiFuse per run, Tip link; through-cuts use expressions, `through_all`).

Branch: codex/t38-spike. Files: new folder docs/spikes/t38/ (scripts, results JSON, REPORT.md).

Find out, with runnable freecadcmd scripts, how to build each I34 result as native FreeCAD features that recompute correctly. P is a rectangle extruded along its normal; S is another board. Targets to try: a flat face square to the push, a flat face at 30°, a cylinder, a sphere.

1. Near-surface fit (P minus S): extrude P past S and cut S out of it. Does a single remnant always remain, and how do you pick the right piece when the cut leaves several (Part::Cut gives one compound)?
2. Far-surface end (P runs through S and stops on S's far surface): Part::Extrusion has no up-to-face. Compare candidates: extrude long, then split with S's far face (Part::Slice, BOPTools SplitAPI / Slice Apart, BooleanFragments) and keep the near piece; or Part Common / Cut with a half-space built from that face; anything else bundled. For each: does it work on curved far surfaces, does it stay right when S moves or changes, and how long does it take?
3. The matching opening in S (S minus P) when P's end is derived from S: show a construction with no dependency loop. P must reference S's pre-cut solid (the board's previous Tip), and the cut becomes S's new Tip. Check that a later edit to S (move it, push one of its faces) recomputes both pieces correctly, and that FreeCAD reports no cycle.
4. Linked and mirrored pieces: what happens when S or P is an App::Link instance (component copy) or a Part::Mirroring copy? (See `edit_frame`, `mirror_input` in replay.py.)
5. Timings for each construction (ms per recompute).

Deliverable: REPORT.md recommending one construction per mode (first contact, near fit, far end with opening, no cuts), with its limits, and the scripts plus a results JSON so Claude can rerun them. Not an implementation in replay.py.

Response — Codex, 2026-11-21: Completed on `codex/t38-spike`, commit `7886e7b`, worktree `/tmp/fretchup-codex-t38`. See `docs/spikes/t38/REPORT.md`, runnable `spike.py`, and `results.json`. Native Cut → start-connected CompoundFilter plus Common/Fuse makes a curved far end and matching socket without a dependency loop. All 20 matrix cases passed nine geometry/reopen checks (flat, 30°, cylinder, sphere × plain/target-link/target-mirror/P-link/P-mirror). Ran FreeCAD 1.1.4 with TESTDIR=/tmp/fretchup-t38-final; quicktest passed native 96, arrays 10, serve 11, viewport 52. Struggles/limits: instance placement and bounded-end checks were essential; shape validity alone initially hid incorrect endpoints. Partial coverage, concave targets, combined linked mirrors, and downstream pushes after the socket need integration work. Upstream target edits recompute; redirecting to the post-cut Tip would cycle. Part.makeHalfSpace is not exposed here. No app implementation, merge or push. App worktree creation stalled; isolated Git worktree used instead. Ready for Claude review.

Resolution — Claude, 2026-11-21: reviewed and merged into linked-copies (640609a). Reran spike.py with freecadcmd 1.1.4 into a fresh TESTDIR: 20/20 cases, no errors. Recommended construction noted on Work list T38 (revision 62); the limits listed in REPORT.md become T38's integration tests.

### H006 — T32 measurement parser (inches, fractions, millimetres)

Author: Claude | Date: 2026-11-21 | Status: resolved | For: Codex

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

Response — Codex, 2026-11-21: Completed `codex/t32-units`, commit `df0ff3c`, worktree `/tmp/fretchup-codex-units`. Added only units.gd and test_units.gd. Exact assigned Godot command: 90 passed, 0 failed; quicktest (including parsecheck): native 96, arrays 10, serve 11, viewport 52, all zero failures. Parser accepts metric, signed feet/inches, mixed and bare fractions; formatting rounds/reduces 1/16, 1/32 or 1/64 and metric 0.1 mm. Rejected malformed double-hyphen fractions and unsupported count/divide input. `precision` means imperial denominator; invalid formatting arguments return an empty string. Struggle: sandboxed Godot crashed while opening its user log; rerun with required filesystem access passed. Tool/UI wiring and units preference remain for Claude/William as assigned. No merge or push.

Resolution — Claude, 2026-11-21: reviewed and merged into linked-copies (80175fa). Reran test_units.gd: 90/0. Two fixes on top (43210ef): the architectural form 1'-6" (and 1'-6-1/2") is accepted, and a length under an inch formats as 3/4" rather than 0 3/4". Now 99 checks, run by quicktest.sh and fulltest.sh. Bare 1'6 (no inch mark) is still rejected; whether to accept it goes to William with the units preference when T32 is wired in.

### H007 — Worker tests for feature combinations

Author: Claude | Date: 2026-11-21 | Status: resolved | For: Codex

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

Response — Codex, 2026-11-21: Completed `codex/worker-tests`, commit `17b0763`, worktree `/tmp/fretchup-codex-combos`. Only worker/test_combos.py added. FreeCAD 1.1.4 command with TESTDIR=/tmp/fretchup-combos-final: COMBO TESTS 61 passed, 0 failed. Covers live undo and reopened-history replay across assemblies with arrays/mirrors, mirrored-array detach/unique, linked-family paint/unique/repaint and instance/mirror grain/across, save/reopen against fresh geometry/family/group snapshots, interleaved Sessions including a Draft hole array, and rejected grouping/dependent moves. Failure records include replayable ops in TESTDIR/failures.json (empty in final run). Quicktest passed native 96, arrays 10, serve 11, viewport 52. Struggle: corrected the test fixture to use the actual top-level cut reference for hole-array moves; no worker defect remained in the final matrix. Dependency pruning is viewport behaviour: test checks worker failure statuses and then simulates the pruned resend, rather than falsely claiming Session prunes the client log. Claude still needs to wire the script into test runners. No worker edits, merge or push.

Follow-up — Codex, 2026-11-21: H010 loader request addressed in additional commit `f26767e` on the same branch (after `17b0763`). Worker loading is now one small function at the top, ready to replace with imports after T42. Re-ran COMBO TESTS: 61/0 and quicktest: 96/0 native, 10/0 arrays, 11/0 serve, 52/0 viewport. T42/T43 are left to Claude; T44 remains unassigned.

Resolution — Claude, 2026-11-21: reviewed and merged into linked-copies. Reran: 61/0. Checked that snapshots hold real geometry (expected volumes, holes subtract 450 mm³ each) and that a broken expectation fails. Wired into quicktest.sh and fulltest.sh (003f42e). After T42 its load_worker() switches to imports.

### H008 — U01 design spec: the undo history panel and branch storage

Author: Claude | Date: 2026-11-21 | Status: resolved | For: Codex

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

Response — Codex, 2026-11-21: Completed `codex/u01-spec`, commit `fb2933e`, worktree `/tmp/fretchup-codex-history`; only docs/specs/U01-history.md added. Read actual undo/amend/cache/sync/journal and W13 code. Spec covers panel/forks, immutable action revisions, UUID migration preserving legacy IDs, multi-op atomic action boundaries, journal tree/checkpoints, stale-response identity, external-edit epochs and save generations. Quicktest passed native 96, arrays 10, serve 11, viewport 52. Struggles/design findings: current transactions are per op, not per multi-op action; save resets undo_floor; current mesh cache is not durable history; saved rev alone cannot identify a branch. Spec identifies needed integration changes without implementing them. Five proposed policy questions for William are listed at the end (redo choice, amendment display, external epochs, cache budget, A32 prerequisite); they are not silently treated as approved. Ready for Claude review; no merge or push.

Resolution — Claude, 2026-11-21: reviewed and merged into linked-copies (c26c14e). Linked from Work list T36 (revision 62). The five questions go to William one at a time when T36 starts.

### H009 — Bring ARCHITECTURE.md and the feature map up to date

Author: Claude | Date: 2026-11-21 | Status: resolved | For: Codex

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

Response — Codex, 2026-11-21: Completed `codex/docs`, commit `8a01e3c`, worktree `/tmp/fretchup-codex-docs`. Updated only ARCHITECTURE.md, FREECAD_FEATURE_MAP.md and Codex's suggestions.md. Checked serve/ownership/probing/shutdown code, native link/array/group/material/export paths, Select tool and test scripts against main 5c0b602. Quicktest passed native 96, arrays 10, serve 11, viewport 52; git diff --check clean. Added H010's T42/T43 as future work, not existing modules. Reconciled H001 (Shift intentionally mirrors; Q22 save indicator; I26b ties decided; Q24 splitting parked), S01 partly built, S02/S15 largely built. Important limit: write_glb emits texture paths/scales and grain/across in custom extras, not Blender texture-node wiring; documented the consumer/portability check still needed. W13 worker identity hashes replay.py only, not supporting modules; documentation now says that precisely. H001 resolved on this branch and archived; integration remains Claude's review. No merge or push.

Resolution — Claude, 2026-11-21: reviewed and merged into linked-copies (f92bc8d). Spot-checked: SERVE_IDLE_EXIT, the MD5 script identity, worker_client.gd, 12 species. The test-runner notes predate the units and combo tests being wired in (now done).
