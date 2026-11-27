### H180 — The structural report: the merge works out what changed in the structure, the worker only explains it

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: answered | For: gemini

References: P31 (workers supply a structural report; "schema and submission timing remain to be designed": this is
the design), P32 (the integrator verifies it against the code at review), P28 (`Architecture:` lines), P50 (header
lines are map lines), H165 (module map), H174 (dependency map), comitatus principles C05 and C06 (generate what can
be generated; one spot per idea).

Touches: tools/integrate.py (a new structure step between the gate and the "Changed from the brief" stop, and the
pre-commit Architecture check it calls), tools/dependency_map.py (a `diff(old_text, new_text)` helper only),
tools/architecture_map.py (a `diff(old_text, new_text)` helper only), tools/test_integrate.py,
tools/test_dependency_map.py, tools/test_architecture_map.py, BOARD.md (step 6's `Architecture:` wording only),
docs/integrator.md (the review step that reads Architecture lines).

Reading path:
1. BOARD.md step 6: what a worker's response holds today (`Architecture: <what>` lines).
2. tools/integrate.py: the "Changed from the brief" stop (P44) and `--continue`: the new stop works the same way.
3. docs/dependency-map.md and ARCHITECTURE.md's module map: one line per file; tools/dependency_map.py and
   tools/architecture_map.py build them.

Today (checked 2026-11-27): a worker writes free-form `Architecture: <what>` lines; the integrator reads the diff to
see whether they're true. Nothing compares them with what the code actually changed, though both maps are now
generated from the code.

Design (the integrator's, under P31; William: "follow the org principles and project principles"):
- **What the merge works out itself** (nothing for the worker to write): from main's and the merged tree's maps,
  - files added or removed;
  - each file whose module-map line (its header sentence) changed, old and new;
  - each dependency added or removed (`a uses b`), from docs/dependency-map.md.
- **What only the worker can say:** why. Its `Architecture:` lines take three forms (any number of each):
  - `Architecture: <file> owns <what>` for a new file, or a file that now owns state or a job it didn't;
  - `Architecture: <a> uses <b>: <why>` for a new dependency;
  - `Architecture: <free text>` for anything else (as today).

Request:
1. **The structure step at merge**: after the gate passes, integrate.py prints the worked-out changes as a short list
   and checks them against the response: every added file needs an `owns` line naming it, every added dependency a
   `uses` line naming both files. Anything unexplained stops the merge like a "Changed from the brief" line
   (`for you now: structure: <a> now uses <b>, not explained`), and `--continue` accepts it after review. Removed
   files and removed dependencies are only printed. A merge with no structural change prints nothing.
2. `diff(old_text, new_text)` helpers in both map tools return those changes (tested on their own).
3. BOARD.md step 6 shows the three forms in one line each; docs/integrator.md's review step says the merge checks
   them and the integrator confirms they're true (P32).

Not in this job: the proposed/ghosted map (T136), anything the worker's other response lines do.

What can fail:
- A stop on every merge: only added files and added dependencies need explaining. Check: a test merge with a
  header-only change passes without a stop.
- A dependency renamed by a file move (H177 moves code out of main.gd) shows as one removed and one added: the
  added one needs explaining, which is right.
- A worker naming a file differently (`main.gd` vs `viewport/main.gd`): match on the short names the map uses.

Checks:
- The three test files above: an added file with and without its `owns` line, an added dependency with and without
  its `uses` line, no change at all.
- `tools/TEST_BEFORE_MERGING.sh` passes (scope tools).

Response — Gemini (gemini-alder-1127-102946), 2026-11-27:
Branch: `gemini/h180-structural-report`, commit: `cc5868e`.

Implemented the structural report design:
- Added `diff(old_text, new_text)` in `tools/architecture_map.py` (added/removed files and changed header sentences) and `tools/dependency_map.py` (added/removed `(source, target)` edges, resolving short names to full paths so short-name collisions don't look like removed+added edges).
- Added `check_structure` between `run_gate` and `pause_for_map` in `tools/integrate.py`. It compares `HEAD`'s maps with the live merged tree's maps, prints a short `structure:` list (nothing when there are no structural changes), and checks added files against `Architecture: <file> owns ...` and added dependencies against `Architecture: <a> uses <b>: ...` (matching both short map names and full paths). Unexplained additions stop the merge staged under `for you now:` (`structure: ...`), and `--continue` accepts them after review; removed files, removed dependencies, and header-only changes do not stop.
- Updated `BOARD.md` step 6 with the three `Architecture:` forms and `docs/integrator.md` with the review/P32 check.
- Added tests in `tools/test_architecture_map.py` (12/12), `tools/test_dependency_map.py` (20/20), and `tools/test_integrate.py` (100/100, updating `MERGE_ORDER` for `check_structure`), and ran `tools/TEST_BEFORE_MERGING.sh` (GATE PASS, scope tools, 132 s) and `python3 tools/job.py test` (all 22 tools suites passed, 58 s).

Architecture: integrate.py uses architecture_map.py: diff main's and the merged tree's module maps in check_structure
Architecture: integrate.py uses dependency_map.py: diff main's and the merged tree's dependency maps and resolve short names in check_structure
Result: cc5868e; gate (scope tools) + quicktest (22 tools suites) + test_integrate (100/100) + test_dependency_map (20/20) + test_architecture_map (12/12) passed; added map diff() helpers, integrate.py check_structure step, and BOARD.md/integrator.md docs
