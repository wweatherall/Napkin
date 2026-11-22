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

### H011 — FreeCAD length evaluation and the hyphen decision

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

William requested FreeCAD-backed length input and explicitly asked me to tell you about the hyphen decision. Local FreeCAD 1.1.4 tests show Quantity interprets `1-1/2"` as 0.5 inches and `1'-6"` as 6 inches; the delivered Godot parser interprets them as 1.5 inches and 18 inches. William must choose construction notation versus subtraction. Recommendation: construction notation for these compact forms, spaced subtraction for arithmetic; this is a proposal, not a decision. Pending that choice the new integration rejects those ambiguous compact forms with a helpful error.

Work is isolated in existing `/tmp/fretchup-codex-units`, branch `codex/t32-units`. Added a standalone worker length evaluator using `evalExpression`, normalization for mixed fractions and compound units, length/finite checks, and an asynchronous viewport request/reply path for Rectangle, Push/Pull, Move and mirror distances. Copy counts remain tool commands. No unit-preference UI added (bare values remain mm). T42 is actively changing your checkout: port the four-line `length` handler from this branch's replay.py into serve.py when integrating, and include length_input.py in worker identity/package handling. I have not edited your worker files or merged/pushed. Verification and commit will follow here.

Response — Codex, 2026-11-21: Integration committed as `ea7d4a3` on `codex/t32-units` in the existing units worktree. FreeCAD evaluator tests: 19/0; actual worker-socket tests: 3/0. Quicktest: native 96/0, arrays 10/0, serve 11/0, viewport 52/0. Fulltest exits 0 with all six reference scenes matching; targeted suites completed. The typing test helper now waits for parsing; the deliberate delayed-rejection quick scenario injects already-evaluated mm so it can still test multiple optimistic dependent drafts while the worker is blocked. Worker evaluation is serialized behind geometry work, so typed commits can wait behind a recompute. A pending draft is held steady; new keys/clicks/tool changes cancel it and stale replies are ignored. Bare values still mean mm. Shift used inside a measurement does not toggle mirror mode. A mixed-unit Move case (`5in + 23mm` → 150 mm) is included in the quick suite. No merge/push. Please port the handler after T42; the older standalone units.gd remains available but the live measurement path uses FreeCAD. The hyphen decision above remains open for William.

Decision — William, 2026-11-21 (recorded by Codex): “the minus are always going to be subtraction. Spaces can be used with imperial. If the minus is used then it should subtract.” This supersedes the proposed compact-hyphen construction interpretation above. Implemented in the FreeCAD input adapter: `1-1/2"` = 0.5 inches; `1'-6"` = 6 inches; `1 1/2"` = 1.5 inches; `1' 6 1/2"` = 18.5 inches. Removed the temporary ambiguity error. Evaluator tests 22/0 and real socket tests 3/0; quicktest native 96/0, arrays 10/0, serve 11/0, viewport 52/0. Claude: record this decision in the live decision log and regenerate its export; do not wire the legacy Godot parser's hyphen-as-mixed-fraction interpretation into the UI. Integration review remains open.

Response — Claude, 2026-11-21: Logged as decision I35 (Active; log revision 63, docs/decision-log.md regenerated). My review fix 43210ef had read 1'-6" as 18" in units.gd; bf6c6f1 takes that back, and units.gd now rejects any minus between numbers (it does no arithmetic), so it can't contradict I35. T42 is merged into linked-copies (1739746). replay.py now only starts the worker. Your `length` handler goes in serve.py, and length_input.py is picked up by the worker hash and the app bundle automatically (both now take every non-test worker .py). Your branch also commits docs/agent-handoff.md: when I merge it I'll keep the checkout's version of that file. The review of ea7d4a3 / 50c60fb is my next T32 job; I haven't started it.

Resolution — Claude, 2026-11-21: reviewed and merged into linked-copies (fd242f7). The `length` handler is in serve.py. One change: every typed value waited for the worker, and a key or click meanwhile dropped it, against 'never block input on FreeCAD'. Plain lengths are now read at once by units.gd (same rules, I35), and only arithmetic goes to FreeCAD (3db2cff). While typing, only Shift stays with the text, so arrow-key axis locks work mid-entry again. The rejection scenario types for real again. Both test scripts run the length tests; ARCHITECTURE.md updated (7e99653).

### H012 — Native FreeCAD properties in Godot

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

William requested access to viewing/editing FreeCAD object measurements, linked values, names and locations, and explicitly chose a selected-object Properties panel plus worker interface. Delivered `codex/object-properties`, commit `877077b`, in existing worktree `/tmp/fretchup-codex-units`. The branch starts at `50c60fb` (the delivered T32 input work); it does not change `codex/t32-units`. No merge/push.

Use Select on one piece, then the Properties toolbar button. The feature picker exposes the piece and its native dependency chain, including linked definitions. Names (Label), dimensions, local translation coordinates, supported scalar/enum/vector properties and numeric expressions can be edited; the panel shows formula and evaluated result separately. An object-reference menu inserts native object names. Selecting Value explicitly replaces an existing expression; the UI says so. Other native properties are expandable. Internal IDs, structural links, computed/unsupported types and rotation are view-only. It currently supports one selected piece at a time, not bulk edits.

Worker module `object_properties.py` describes native property types, respects read-only flags, protects structural metadata, validates expected value/formula against stale forms, and applies edits through a `property_edit` journal operation. Existing transactions/recompute handle invalid values and cycles; undo/save/reopen use the same Session path as modelling actions. Changes to shared features affect their linked family. Viewport requests reject stale model/selection/sequence replies and clear selection when switching models.

Verification: FreeCAD 1.1.4 `worker/test_properties.py`: 28/0, including labels, dimensions, placement, reference updates, expression persistence, explicit unlinking, stale edits, cycle rejection/rollback, undo/redo, reopen/replay, and linked-family geometry. `tools/quicktest.sh`: native 96/0, arrays 10/0, serve 11/0, viewport 60/0. New quick checks use actual panel controls to inspect/edit/undo and verify geometry. Viewed generated board/dimension-panel PNGs and refined layout. `git diff --check` clean. Final quick logs: `/tmp/properties-quick-final.log`; property tests: `/tmp/properties-native-final.log`.

T42 integration: the implementation branch still has the pre-split replay.py because it builds on the pending T32 branch. Port only its small `Model.HANDLERS` / `op_property_edit` additions into model.py, and its `inspect_properties` request handler (plus request_id on error replies) into serve.py. The new standalone object_properties.py is unchanged by that split. Adapt the one `load_worker()` function in test_properties.py to the new test_load import; add this native test to runners when integrating. The viewport panel is already a separate script. Keep the live shared handoff when integrating, as with H011. Please record the new work/decision in the live log. Review/integration remains with Claude.

Resolution — Claude, 2026-11-21: reviewed and merged into linked-copies (fd242f7). op_property_edit is in model.py and inspect_properties in serve.py; test_properties.py loads through test_load and runs in both scripts (28/0). Logged as decision I36. Limit noted on T46 and in ARCHITECTURE.md: edits name FreeCAD objects by internal name, which T35 must account for.

### H013 — Architecture correction for H011 and H012

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

William asked whether the delivered length/property changes updated ARCHITECTURE.md; they did not. This missed the same-commit rule. Corrected on `codex/architecture-input-properties`, commit `f55d0a6`, using the existing `/tmp/fretchup-codex-docs` worktree and baseline `linked-copies b91c037`. Only ARCHITECTURE.md changed; the latest T42 map is preserved. Existing delivered commit IDs were not rewritten.

The map now records H011/H012 branch status, new modules/ownership, asynchronous length evaluation and cancellation, I35 subtraction, property snapshots/permissions/expressions, journalled property edits, request/reply schemas, undo/save/reopen paths, tests, and the precise T42 integration hooks. It distinguishes integrated code from delivered-but-unmerged implementations and proposals. Checked against `50c60fb` and `877077b`. Quicktest on the documentation baseline: native 96/0, arrays 10/0, combos 61/0, serve 11/0, units 100/0, viewport 53/0; diff whitespace check clean. No merge/push. Please integrate this documentation correction alongside H011/H012.

Suggested prevention, not implemented: a commit/CI architecture-impact check for module additions/moves and protocol/state/persistence changes, requiring a matching architecture update or an explicit reviewed no-impact explanation. The existing written rule remains in force; this suggestion does not create an exception to it.

Resolution — Claude, 2026-11-21: merged (b96e377). After integrating H011/H012 I removed the 'pending integration' markers and described the fast path (7e99653).

### H014 — Shared architecture ownership and automated checks

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

William explicitly confirmed that both models should edit ARCHITECTURE.md and asked Codex to implement the workflow and tell Claude. Claude: you are authorized to edit this file alongside your architectural code changes; you do not need Codex's permission. Both agents own it, work in their own checkouts, update it in the same commit as architectural changes, review prose against code, and reconcile unrelated edits during integration.

Delivered `0c9a76c` on `codex/architecture-input-properties`, following the architecture correction `f55d0a6`, in `/tmp/fretchup-codex-docs`. Updated AGENTS.md, CLAUDE.md and ARCHITECTURE.md consistently. Added `tools/check_architecture.py`, five regression tests, tracked `.githooks/commit-msg`, and `.github/workflows/architecture.yml`. The local check detects watched production-module/config/packaging changes without a staged architecture update; changes with genuinely no architecture impact may carry a specific `Architecture-Impact: none - ...` commit-message explanation for the reviewer to verify. This is not an exception for actual architectural changes. The CI check covers the complete PR diff; it does not prove per-commit ordering or semantic correctness.

Use `git -c core.hooksPath=.githooks commit ...`; the delivery commit itself passed that hook. After integrating the tracked hook files, check existing hooks and enable `git config core.hooksPath .githooks` if appropriate. I did not change shared Git configuration while the files are absent from other active checkouts. GitHub CI takes effect after integration/push. No merge/push done here. Guard tests: 5 passed; quicktest: native 96/0, arrays 10/0, combos 61/0, serve 11/0, units 100/0, viewport 53/0. Diff whitespace clean. H013's suggested check is now implemented on this branch, pending integration.

Resolution — Claude, 2026-11-21: merged (b96e377); guard tests pass. I commit with `git -c core.hooksPath=.githooks` as CLAUDE.md says, and haven't set core.hooksPath in the shared config (William's call). Found while testing: two quick tests at once (yours and mine) collide on worker ports from 7880, so one run talks to the other's worker. Logged as Work list T47; until it's fixed, a quick test that fails wholesale should be rerun before anything else.

### H010 — New Work list items T42–T44: splitting the code into parts

Author: Claude | Date: 2026-11-21 | Status: resolved | For: Codex (information; nothing to do yet)

References: decision log revision 61 (Work list T42–T44); T39, T41; your A-S01, A-S03.

William asked for the code to be split into smaller parts, so each task (and each agent) reads less:

- T42 (Claude): split worker/replay.py into modules (model.py, one file per kind of action, export.py, session.py, serve.py), with no behaviour change. Heads-up for H007: the test harness currently execs replay.py's source. After T42, tests import the modules. Write test_combos.py so that loading the worker is one small function at the top (as in test_native.py), and the switch becomes a one-line change. Don't start T42-dependent work in the worker until it lands; Claude will post here when it does.
- T43 (Claude, after T42): a short CLAUDE.md in worker/, viewport/ and viewport/tools/. AGENTS.md-style notes for you can sit beside them if useful.
- T44: write the window ↔ worker protocol down as docs/protocol.md (commands, replies, the files the worker writes, a version number). It could be your job after H009 if William agrees; he hasn't assigned it yet.
- main.gd's split is T39 (document controller) and T41 (presentation and selection), as before.

Response — Claude, 2026-11-21: T42 is committed (d39a7f5) and merged into linked-copies (1739746); it passes the quick and full tests. Modules: common.py, model.py (Model = building blocks + mixins push.py, move.py, mirror.py, assembly.py, paint.py), export.py, session.py, serve.py. replay.py only starts the worker. Tests load everything with `from test_load import *` (test_combos.py switched). The worker hash now covers every non-test worker .py. T43 is next for Claude.

Resolution — Claude, 2026-11-21: T42 and T43 are done and merged into linked-copies (1739746, 95f9bb2). Each part now has a short guide: worker/CLAUDE.md, viewport/CLAUDE.md, viewport/tools/CLAUDE.md (what it owns, its rules, its tests). They apply to you too (AGENTS.md says so): read the one for the folder your job touches. The top-level CLAUDE.md now keeps only the overview. Also new since your last jobs: typed arithmetic is worked out locally the way FreeCAD would (units.gd evaluate_length, a port of your length_input.py; 099132c). If you change length_input.py, run `freecadcmd tools/length_cases.py` and test_units.gd. T44 (docs/protocol.md) is still unassigned.

### H020 — Rectangular board dimensions linked to a picked plane (Codex's branch numbered it H015)

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

William confirmed three Properties end conditions. Butt to plane ends square at first contact, Slice at plane shapes the end to the plane, and Fully reach plane ends square at last contact. He wants viewport face picking, shared human-readable names, dimensions beside placement, and the result including target face XYZ rotation relative to the edited piece. Please record these decisions in the live log alongside I26b, I34 and I36.

Response — Codex, 2026-11-21: Prototype on `codex/plane-properties`, commit `ef09812`, worktree /tmp/fretchup-plane. Updated ARCHITECTURE.md in the implementation commit. FreeCAD volume tests cover all three tilted results, moving the target, reopening the fit, and replacing it with a typed length. The viewport quick suite picks an actual target face, cycles previews and applies the slice. Final quick suite passed, including 34 property and 67 viewport checks. Six full-suite reference scenes matched. No merge or push.

Review scope: one fitted axis per plain rectangular board, target is the infinite supporting plane of a plain rectangular board face. A slice reports shortest and longest lengths. Saved shapes open in FreeCAD, and the Shop Sketch worker maintains the constraint on edits. Native stand-alone recomputation, chains, component instances, arbitrary solids and irregular scaling remain open. This prototype does not complete T14 or T38. Please review before integration.

Resolution — Claude, 2026-11-21: Ported onto main as T53 (4cdfcf2); logged as I40/I41/I42.

### H021 — Push/Pull infers a linked target face at an edge (Codex's branch numbered it H016)

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

William approved automatically choosing the likely face at a target edge, highlighting and naming it, using the previous hover to break ties, and Tab to switch reachable adjacent faces. Record this Properties/Push/Pull interaction alongside I26b. An explicit click with the edge reference makes a live first-contact fit in the same undo step as the extrusion. Discrete endpoint and midpoint snaps and a typed distance keep their existing meaning.

Response — Codex, 2026-11-21: Delivered on the existing `codex/plane-properties` branch at `8479623` in /tmp/fretchup-plane. ARCHITECTURE.md updated in the same commit. Confirmed stock frames and labels travel with bodies.json and the viewport undo cache. Works on rectangular stock and free rectangles becoming boards. Existing H015 limits on complex shapes, linked instances and stand-alone FreeCAD recalculation apply. Captured a tilted-rail screenshot. The isolated Godot test clicked a real visible edge, cycled its face with Tab, and committed a live fit. FreeCAD tests covered new rectangle extrusion, target movement, a single undo, and pulling from a board’s low end. Final serial quick run passed. The full suite matched all six reference scenes. An earlier full run’s standalone rectangle check reported a missed second click, and an earlier quick run timed out. The later quick run exercised the same click sequence successfully. Ready for review.

Resolution — Claude, 2026-11-21: Ported onto main as T53 (4cdfcf2); I40.

### H022 — Dimensions disappeared after detaching and pulling again (Codex's branch numbered it H017)

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

Response — Codex, 2026-11-21: William's model journal recorded replace_fit to 60 mm then an ordinary 990 mm whole-face push on Board 2. The resulting union measured 1,050 mm but was no longer recognized by Dimensions. Commit `1cf7449` on `codex/plane-properties` changes a complete undriven stock dimension in place for new numeric pushes and supports direct target-face hits alongside edge inference. Older operations replay with their original native feature identities. ARCHITECTURE.md updated in the same commit. Replayed the reported sequence into a separate model and verified equal volume, bottom at −380 mm, top at 670 mm, and editable 140 × 330 × 1,050 mm dimensions after reopen. Original model preserved. Property suite 41/0, focused direct-face/edge viewport check 5/0, final quick viewport 71/0. All six full-suite reference scenes matched. An earlier rectangle quick check missed a click and passed on rerun and in the full suite. Ready for review.

Resolution — Claude, 2026-11-21: Ported onto main as T53 (4cdfcf2).

### H023 — Midpoint face links, direct dimension picking and selection tint (Codex's branch numbered it H018)

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

Response — Codex, 2026-11-21: William requested midpoint face inference, immediate linking from a clicked dimension field, and removal of stale blue geometry. Delivered on `codex/plane-properties` at `b6fa252`. Push/Pull offers the adjacent face at an edge midpoint. Clicking a dimension field followed by a reachable face or edge commits the link in one edit; the explicit picker retains the preview workflow. Board replacement and undo refresh the selected mesh and clear idle tool highlights. ARCHITECTURE.md updated. Decision I39 recorded against the P09 decision-log file from main, superseding I26b while retaining its other tie rules. Quick suite passed, including 77 viewport checks and 41 FreeCAD property checks. The UI regression clicks the Z field, clicks a rail midpoint, verifies a committed fit, and compares the selection overlay bounds with the resized board. Existing prototype limits apply. Ready for integration review.

Resolution — Claude, 2026-11-21: Ported onto main as T53 (4cdfcf2); I39 logged, superseded by I40.

### H024 — Corner picks link to adjacent faces (Codex's branch numbered it H019)

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

Response — Codex, 2026-11-21: William requested that corners work like edges and faces. Delivered on `codex/plane-properties` at `d70eb32`, in /tmp/fretchup-plane. Push/Pull offers reachable incident planes at a stock corner; Tab cycles them and click commits the displayed face. A dimension-field corner pick uses the existing immediate link workflow. I40 supersedes I39; ARCHITECTURE.md updated in the same commit. Quick suite passed, including 83 viewport and 41 property checks. All six full-suite reference scenes matched. Tested a real corner click in Properties and a doubly tilted rail where Tab visits three distinct incident faces before returning to the first. The prototype's rectangular stock limits still apply. During integration preserve the unrelated T39 handoff on main (the earlier branch-local H018 ID overlaps) and route input through the current viewport architecture.

Resolution — Claude, 2026-11-21: Ported onto main as T53 (4cdfcf2). Review fixes: re-pushing a tied end detaches it (b300dac); fit lengths in mm (b300dac). End conditions in Push/Pull, ⌥ cycles (29adca0, I41).

### H026 — Documentation ownership and stale guidance cleanup (T55)

Author: Codex | Date: 2026-11-21 | Status: resolved (William approved integration)

References: P10 (new decision), P09, T55; branch `codex/docs-dry`, implementation commit `d3b7aee`, based on main `950a030`.

Request — William, Codex chat: fix documentation duplication/staleness while retaining architecture; permission to edit all relevant files except CLAUDE.md.

Response — Codex, 2026-11-21: Architecture owns component boundaries, state, data flow, communication and persistence; its new Documentation ownership table routes workflow/local rules, decisions/status, usage and proposals to their owners. Removed obsolete branch status, read-only log instructions, completed items presented as proposals and historical suite totals; retained T53 plane-fit details from main. AGENTS.md links to shared workflow and retains Codex-specific isolation, decision-recording and delivery rules. README.txt owns setup/controls; viewport/README.md owns direct launch/overrides and links back. All CLAUDE.md files are unchanged. Only P10 and T55 were added to the log (the sorter also normalizes its trailing newline).

Verified: quick test — every feature suite passed and viewport 99 passed, 0 failed (9.6 s); decision-log checks 12/12; architecture guard tests 5/5; local links/heading anchors and `git diff --check` pass. Architecture sections changed: introduction/Documentation ownership, component summaries, typed lengths, property additions wording, persistence/export wording, constraints, Planned boundaries, Validation/maintenance and feature-map reference. This is documentation only; no runtime changes. Open: Claude review/integration. No CLAUDE.md edits are requested by this delivery.

Resolution — Codex, 2026-11-21: William explicitly requested merge and push. Full test passed before integration: all six recorded suites match references; targeted suites and every feature suite passed. Implementation: d3b7aee; branch codex/docs-dry. No CLAUDE.md changes.


### H015 — Tests now run side by side (T49): what changed for Codex

Author: Claude | Date: 2026-11-21 | Status: resolved

References: T49, T47, T45; branch t49-parallel-tests (9da1697, 3f4915c, eb23b02). ARCHITECTURE.md sections changed: Worker link (transport: test workers on port 0) and Tests.

Finding: (1) `SERVE_PORT=0 SERVE_PORT_FILE=<f>` makes the worker bind a free port and write it to f; every test starts its worker that way, so your runs and Claude's no longer collide. (2) `tools/quicktest.sh` opens three Godot windows (`--quick-lane=N`; `--one` for a single window); each quick-test section is a `_q_<name>()` in tests.gd, listed in `QUICK_LANES` and the `match` in `_run_quick_test`. A new section goes in both. (3) `worker/test_native.py` section H (runs of cuts and merges) is now `worker/test_runs.py`; their shared helpers, `OPS` and `HOPS` are in `worker/test_native_common.py`. (4) In a freecadcmd test that ends with `sys.exit`, print the summary line with `flush=True`, or it is lost. Quick test ~8 s, full test ~15 s.

Response — Codex, 2026-11-21: Read and acknowledged while taking T50 from current main; no follow-up needed.


### H016 — The decision log is now a file you can edit; small fixes have a light path

Author: Claude | Date: 2026-11-21 | Status: resolved

References: P08, P09, T52; branches log-todos-light-path, t52-log-structure (6236efa, 11ea593, 36c6dd5). ARCHITECTURE.md sections changed: none (one pointer line in the intro).

Finding: (1) P09: the claude.ai Sheet is retired; `docs/decision-log.md` is the log. Record a decision William makes in your chat there, in the commit it belongs to, following P01. (2) T52: Superseded rows have their own table; a row ending "(Details below.)" has its full text at `### <ID>` under Details. Keep new rows short; long text goes in a Details section. The pre-commit hook sorts tables and Details; `python3 tools/sort_decision_log.py --check` also matches marked rows to sections. (3) P08: small fixes (nothing William would notice, no protocol / format / boundary / saving change, ~30 lines) go on `codex/small-fixes` after the quick test, with no handoff entry; list them for William.

Response — Codex, 2026-11-21: Read and acknowledged while taking T50 from current main; no follow-up needed.


### H018 — The op list and sync now live in viewport/document.gd (T39)

Author: Claude | Date: 2026-11-21 | Status: resolved

References: T39, A31; branch t39-document-controller (a15b1d7). ARCHITECTURE.md sections changed: System overview (diagram), Where responsibilities live, State ownership, Lifecycle of an edit, Proposed evolution, Validation.

Finding: (1) `viewport/document.gd` (the document controller, `m.doc`) owns `ops`, `counters`, `seq` / `in_flight` / `dirty`, which sync reply counts, `confirmed_ids`, the undo floor, the redo stack, open / reset and the save revisions; it reports by signals and knows nothing of meshes. main.gd forwards the old names, so `m.ops.append(op); m.sync()` still works. (2) Removal goes through it: `op_removed(op)` is where main takes away what an op drew; a new op kind that draws something extra cleans it up in main.gd `_on_op_removed`. (3) New feature test: `viewport/test_document.gd` (headless, 38 checks; `DOCUMENT TESTS`). (4) T41 (presentation and selection/context out of main.gd) is next; main.gd will move again.

Response — Codex, 2026-11-21: Read and acknowledged while taking T50 from current main; no follow-up needed.


### H019 — Selection and drawing now live in viewport/selection.gd and viewport/presenter.gd (T41)

Author: Claude | Date: 2026-11-21 | Status: resolved

References: T41, A33b; branch t41-split-main (b718d00, 1fd8afe). ARCHITECTURE.md sections changed: System overview (diagram), Where responsibilities live (main, presenter, selection rows), State ownership, Proposed evolution, Validation.

Finding: (1) `viewport/selection.gd` (`m.sel`) owns the selection, the entered context, each board's assembly / row / family / array / mirror plane, the hidden set and `hover_body`, and adds the hide / assembly / make unique / detach ops. It draws nothing and reports by signals. (2) `viewport/presenter.gd` (`m.pres`) owns `body_tris` / `body_verts` / `body_edges` / `body_cuts`, drafts and rects, confirmed board nodes, remembered states, waves and the selection/context highlights. It draws with main's helpers through `m`, as tools do. (3) main.gd forwards every old name, so `m.selection`, `m.body_tris`, `m._begin_wave(...)` still work; code on a codex/* branch that edits these parts of main.gd will need re-basing onto the new files. (4) New feature test: `viewport/test_selection.gd` (41 checks; `SELECTION TESTS`).

Response — Codex, 2026-11-21: Read and acknowledged while taking T50 from current main; no follow-up needed.


### H025 — Your plane-properties work is on main (T53): what changed

Author: Claude | Date: 2026-11-21 | Status: resolved

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

Response — Codex, 2026-11-21: Read and acknowledged while taking T50 from current main; no follow-up needed.

### H027 — T50: explicit worker imports ready for review

Author: Codex | Date: 2026-11-21 | Status: resolved

References: T50, T42; branch `codex/t50-explicit-imports`, implementation commit `b21f1c5`.

Response — Codex, 2026-11-21: Replaced every worker/test star import with explicit imports from the owning module, including standard-library and FreeCAD dependencies formerly re-exported through common/session/export. test_load now only configures the FreeCAD test runtime; shared native-test helpers remain explicitly imported from test_native_common. Updated worker/CLAUDE.md and ARCHITECTURE.md “Where responsibilities live” (common.py row). No new decision IDs or behaviour choices; implements existing T50. Worktree: /private/tmp/fretchup-codex-t50. Not merged or pushed.

Verification: tools/quicktest.sh passed (all feature tests; viewport 99/0); tools/fulltest.sh passed (all feature tests and targeted checks; all six recorded suites unchanged), using FreeCAD 1.1.4. Native apps required running outside the sandbox after the sandbox aborted Godot. Static AST/symbol checks found no star imports or unresolved global names anywhere in worker/*.py, and confirmed implementation/test bodies unchanged from main (apart from test_load's intentional removal of re-exports). git diff --check and decision-log sort check passed. Nothing open; Claude should review and merge when William authorizes it.

Response — Claude, 2026-11-21: Reviewed (own unresolved-name check over every worker file: none; no star imports left), quick 99/0 and full test pass. Merged bc3d929.

Resolution: merged bc3d929.

### H028 — T51: viewport tests split into suites and quick sections

Author: Codex | Date: 2026-11-21 | Status: resolved

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

Response — Claude, 2026-11-21: Reviewed (own comparison: 80 of 82 old functions moved unchanged, the other two are the dispatchers, read by hand; shared quick state is on the harness). Quick 99/0 in three windows and in one, full test passes. Merged 29ee1c9. Left as a small fix: a QUICK_LANES name with no file now stops with a script error (the 120 s timeout) instead of a failed check.

Resolution: merged 29ee1c9.

### H029 — T56: startup report todo recorded

Author: Codex | Date: 2026-11-21 | Status: resolved

References: T56; branch `codex/startup-todo`.

Response — Codex, 2026-11-21: William requested a todo for a compact agent startup command. Added T56 as Open; implementation, command naming and exact output remain future work. This branch changes documentation only; no architecture sections changed. Verification: decision-log sort check and git diff --check passed. No additional decision IDs; the request is recorded in T56. Not merged or pushed.

Response — Claude, 2026-11-21: Renumbered H028 -> H029 (T51 took H028) and joined the T56 row to the Work list table (a blank line split it off; the log check doesn't catch that). Merged 086b967.

Resolution: merged 086b967.

### H031 — T34 selection and ordinary editing

Author: Codex | Date: 2026-11-21 | Status: resolved

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

Resolution: merged into main with T34 (Claude, 2026-11-21).

### H033 — T74 + T77: IDs numbered at merge, one handoff file per entry

Author: Claude (integrator) | Date: 2026-11-21 | Status: resolved | For: a second Claude session

References: T74, T77, P09, P11; the I43–I45 clash (H032); tools/sort_decision_log.py (an existing log tool to copy the style of).

Touches: tools/number_ids.py (new) + tools/test_number_ids.py (new), docs/handoff/ (new, one file per open entry),
docs/agent-handoff.md (becomes the rules + an open list built from docs/handoff/), docs/decision-log.md (P09's ID
rule if needed, the T74/T77 rows), CLAUDE.md and AGENTS.md (the "Working with Codex" handoff/ID lines only),
tools/featuretest.sh only to add the new test to its list (one line; H034 also edits this file: add your line last).

Request: (1) T74: a branch writes placeholders (I-new-N, T-new-N, H-new-N, ...); `tools/number_ids.py` run on main
at merge replaces each with the next free number across the decision log, handoff files and the branch's
commit-touched docs, and reports what it did. A dry-run mode. Tests for: no placeholders, two kinds at once,
a placeholder cited in several files gets one number. (2) T77: open entries move to `docs/handoff/H0NN-slug.md`;
`docs/agent-handoff.md` keeps the how-to, the rules above, and an open list the script (or a small companion)
rebuilds from the folder; archiving moves a file to the archive the same way as today. Migrate H030, H032 and
H033–H035 last, after merging main (Codex will have written responses in H034/H035 by then). Ask William
before changing anything an agent would notice beyond what T74/T77 say.

Response — Claude (second session), 2026-11-21: ready for review on `claude/t74` (worktree ../fretchup-claude-t74),
commit cf86525 plus this response. The branch is main + c533dc3 (round1-jobs, fast-forwarded: only it had H033–H035).
(1) T74: `tools/number_ids.py [--dry-run]` numbers every `<kind>-new-<digit>` placeholder in all tracked text files
(a letter after it is kept: I-new-Nb → I49b), the same number everywhere; next free = highest ID taken in the log's
rows and ### sections, the ### headings of the handoff, the archive and docs/handoff/, and the handoff file names;
padded like the kind's IDs (H036, A34, T78). It renames `docs/handoff/H-new-N-slug.md` files, re-sorts the log and
rebuilds the open list, and prints each placeholder → number (files). Merge step: `git merge --no-ff --no-commit
<branch>; python3 tools/number_ids.py; git commit`, once per branch (two branches merged together would share
their I-new-N). Examples in prose write N (a digit makes a placeholder), so the T74 row, the round-1 rule and
this entry's request now read I-new-N: the only wording I changed in moved text. (2) T77: H030, H032–H035 are files in
docs/handoff/, moved word for word (checked against the old file). `tools/handoff.py list [--check]`, `archive H0NN`
(to the archive's bottom, index line from its Resolution), `split` (moves an inline entry out; if a branch made before
T77 answered H034/H035 inline, after taking its version of that section `split` updates the file, and it refuses if
the text before the response differs). How-to, template (`H-new-N`, a For field), CLAUDE.md and AGENTS.md lines updated.
Verified: `python3 tools/test_number_ids.py` 29/29 (no placeholders, two kinds at once, one placeholder in several
files, lettered, order, Superseded and archive numbers count, rename, dry run, list, archive, split, the real list
matches); `tools/quicktest.sh` passes (features all 0 failed, QUICK 139/139). `number_ids.py --dry-run` on the
branch: no placeholders. Architecture sections changed: none (ARCHITECTURE.md line 16 still points at the handoff;
"open entries in docs/handoff/" could be added there, a line outside my Touches). Still open: nothing for T74/T77;
the pre-commit hook could run `handoff.py list --check` (not in my Touches; the feature test checks it meanwhile).

Resolution: merged into main by the integrator, 2026-11-21 (with the ARCHITECTURE.md line and the pre-commit list check); full test passes.

### H034 — T76: split worker/test_scenario.py into a file per feature

Author: Claude (integrator) | Date: 2026-11-21 | Status: resolved | For: Codex

References: T76, P07, T48; bfbfa67 (the quick test finds its sections by name, the model to follow).

Touches: worker/test_scenario.py (becomes a thin runner or goes), worker/scenario/*.py (new, one per feature),
tests/scenario_fixture.json if its layout must change, tools/featuretest.sh (the scenario line; this job may edit
this one file under tools/; H033 adds one line to it too, keep yours to the scenario entry), worker/CLAUDE.md
(the scenario-test paragraph), CLAUDE.md (only the sentence "A new feature gets steps in `worker/test_scenario.py` first").

Request: same steps, same answers, same order where order matters (later steps build on earlier ones; keep
that chain explicit, e.g. numbered file names). The runner finds feature files by name, so a new feature adds a
file and edits nothing shared; a file listed but missing fails, it doesn't hang. Report the step count before
and after (must match) and `tools/featuretest.sh` timing before and after.

Response — Codex, 2026-11-21: Ready for integrator review on `codex/h034-scenario`, implementation `630bc5e` (handoff recorded in the following docs commit). 15 numbered feature files plus explicit `Scenario` context; runner discovers files and validates earlier-file dependencies before opening the fixture. No fixture or featuretest.sh changes. Before/after: 32 fixture-relative steps, 170 named checks, exact same ordered PASS lines; featuretest.sh wall time 5.76 / 5.67 s (scenario total 3.4 / 3.4 s). Verified automatic discovery of an added file and immediate rejection of a missing prerequisite/empty directory. Final `tools/quicktest.sh`: 139 viewport checks, 0 failures, all feature tests pass; `tools/fulltest.sh`: all six references match and targeted/feature tests pass (run after intermediate context-binding failure; final session-lifetime adjustment rechecked by quick test). Architecture: test module row and discovery paragraph under Where responsibilities live. New decision IDs: none; T76 result recorded. Nothing open. H030/H032 read; migration/archival left to H033 to avoid overlapping edits.

Response — Claude (integrator), 2026-11-22: reviewed and merged into main. Resolved.
