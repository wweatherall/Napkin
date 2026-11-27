### H165 — Architecture step 1: a module map generated from each file's own header line

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: answered | For: gemini

Item: T138

References: T138 (this item; plan agreed 2026-11-26: a generated one-line-per-module map, the brief carrying it under
8 KB), T136 (the proposed map, step 3), P28 (ARCHITECTURE.md is the integrator's; the map changes with the code),
William's principle "Documentation should be in one spot per idea; if in several, can it be written automatically?"

Touches: tools/architecture_map.py (new), tools/test_architecture_map.py (new), ARCHITECTURE.md (a new generated
section only), .githooks/pre-commit, viewport/save_prompts.gd (header line), viewport/worker_process.gd (header line).

Reading path:
1. ARCHITECTURE.md "Where responsibilities live" (lines 61-124, ~30 KB): the hand-kept table this map will replace in
   step 2 (not in this job).
2. The file headers: `.gd` files start `extends ...` then `## <description>` lines; `.py` files a module docstring
   (`"""<first line>`); `.sh` files a `# <description>` line after the shebang. 101 of the 103 code files have one.
3. `.githooks/pre-commit`: how the board's job table is rebuilt and staged on commit (the same pattern for the map).

Today (checked 2026-11-27 on main): the module table is written by hand, 65 rows, about 30 KB of ARCHITECTURE.md's
81 KB, and drifts from the code; every file except `viewport/save_prompts.gd` and `viewport/worker_process.gd`
already describes itself in its first lines; the 28 ALL_CAPS scripts in tools/ are one-call wrappers listed in
tools/README.md (H154).

Request:
1. **`tools/architecture_map.py`** writes, between `<!-- module map: built by tools/architecture_map.py; don't edit
   by hand -->` and `<!-- end module map -->` in ARCHITECTURE.md, one line per code file: `` `path` — <its header's
   first sentence> ``, grouped by folder (`viewport/`, `viewport/tools/`, `worker/`, `tools/`), in path order. Code
   files: `*.gd`, `*.py`, `*.sh` in those four folders, not tests (`test_*`, `viewport/tests/`) and not the ALL_CAPS
   wrappers, which get one line for the lot: `` `tools/<NAME>.py|.sh` — one named script per action, listed in
   tools/README.md (H154) ``. The first sentence is the header text up to the first `. ` or line end, joined across
   the header's continuation lines, cut at 160 characters with `…`. Put the section just above "## Where
   responsibilities live", titled `## Module map (generated)`, with one line under the title saying what it is and
   that a file's line comes from its own header. Leave the hand-kept table as it is (step 2 decides what moves).
2. **`--check`**: exits 1, naming the files, if a code file has no header line or the section differs from what it
   would write. The pre-commit hook rebuilds and stages the section when a code file or ARCHITECTURE.md is
   committed (as it does for the board), then runs `--check`; a file without a header refuses the commit with a
   message naming it and saying what to add.
3. **The two files without headers** get one each, written from reading them (what the file owns, in the form of its
   neighbours' headers).
4. Report the section's size in bytes and lines. The target for step 2 is a brief under 8 KB, so say how far over or
   under the map alone is, and which ten files' lines are longest.

What can fail:
- A header in a form the parser doesn't know (a `#` comment before the docstring, `@tool` before `extends`): check
  every file in the repo parses to a non-empty line; quote any the parser had to special-case.
- The hook rebuilding inside a worktree or a merge: it only rewrites the marked section. Check: test_architecture_map.py
  with a temp repo: rebuild twice is a no-op; text outside the markers is untouched.
- check_architecture.py's watched-code rule (commit-msg hook): adding header lines to two viewport files is watched code;
  the commit says `Architecture-Impact: none - header comments only`.

Checks:
- tools/test_architecture_map.py (new; featuretest picks it up): parsing each header form; grouping and order; the
  wrapper line; `--check` failing on a missing header and on a stale section; idempotent rebuild.
- `python3 tools/architecture_map.py --check` passes on the branch.
- `tools/TEST_BEFORE_MERGING.sh` passes (two viewport files change, so `scope full`).

### Response (Gemini, 2026-11-27)

Branch: `gemini/h165-generated-module-map` at `cc37b6e` (plus this handoff commit).

Implemented:
- `tools/architecture_map.py`: scans `viewport/`, `viewport/tools/`, `worker/`, `tools/` (non-test, non-`ALL_CAPS` wrappers), parses `.gd` (`@tool`/`extends`/`class_name` + `##`), `.py` (`ast.get_docstring`), and `.sh` (shebang + `#`), joins continuation lines, extracts the first sentence (up to `. ` or line end, cut at 160 chars with `…`), writes the `## Module map (generated)` section in `ARCHITECTURE.md` with the single `tools/<NAME>.py|.sh` wrapper line, and supports `--check`. Every code file in the repo parsed cleanly to a non-empty line without file-specific special cases.
- `viewport/save_prompts.gd` and `viewport/worker_process.gd`: added `## ...` header lines after `extends ...`.
- `.githooks/pre-commit`: rebuilds and stages `ARCHITECTURE.md` when any `viewport/`, `worker/`, or `tools/` `.gd`/`.py`/`.sh` file or `ARCHITECTURE.md` is staged, then runs `tools/architecture_map.py --check`.
- `tools/test_architecture_map.py`: 9 checks covering all header forms, grouping/order, wrapper line, `--check` on missing/stale, idempotent rebuild, and pre-commit hook behaviour in a temp git repo.

Map size and longest lines:
- Full `## Module map (generated)` section: **9,874 bytes**, **89 lines**.
- Map body alone (between markers): **9,633 bytes**, **78 module lines** (81 lines including group blank lines) — **1,441 bytes over** the 8 KB (8,192-byte) target (1,633 bytes over 8,000 bytes).
- Ten longest lines:
  1. 190 chars: `- \`tools/compare_suites.py\` — Compare viewport suite results with the reference runs: python3 tools/compare_suites.py <runs dir> [suite...] Each suite's final boards must match (volume with…`
  2. 190 chars: `- \`tools/personal_space.py\` — Personal spaces (T134, T150): one folder per member in comitatus/04_Personal_Space/<name>/ (opus-integrator, gemini-coder, ...), each with a Log.md (what you d…`
  3. 188 chars: `- \`viewport/inference.gd\` — The one snapping and inference engine every tool uses (T4, Q16): what's under the cursor (pick), point snaps in SketchUp's order (endpoint > midpoint > on edge…`
  4. 188 chars: `- \`tools/length_cases.py\` — Writes tests/length_cases.json: what FreeCAD's length input (worker/length_input.py evaluate) gives for a fixed set of typed lengths, plus random expressions b…`
  5. 188 chars: `- \`tools/sort_decision_log.py\` — Keep the decision log tidy (P23): two files with the same IDs, 03_Past_Decisions/decision-log.md (live) and 03_Past_Decisions/decision-archive.md (history)`
  6. 188 chars: `- \`tools/start_worker.sh\` — Opens a Terminal window running a Claude worker with Remote Control (F005, P38): the same as typing cd <this checkout> ; claude ; /remote-control ; Check the b…`
  7. 185 chars: `- \`worker/materials.py\` — Shop Sketch's wood library (T15, M03): one table, written out as FreeCAD material cards (.FCMat) where FreeCAD looks for user materials, and as materials.json…`
  8. 185 chars: `- \`tools/build_app.sh\` — Builds "dist/Shop Sketch.app" for this Mac: the viewport packed into Resources, run by a copy of the Godot program (no export templates needed), plus the FreeC…`
  9. 184 chars: `- \`tools/quicktest.sh\` — Quick check, after every change (~12 s): the feature tests (tools/featuretest.sh: every test_* file in worker/, tools/ and viewport/, no window) beside the UI…`
  10. 183 chars: `- \`viewport/tools/select_tool.gd\` — Select (Space): click a board (from outside, its whole assembly or array row) to select it; Shift-click adds or removes; click empty space to clear`

Verified:
- `python3 tools/architecture_map.py --check` passed.
- `python3 tools/test_architecture_map.py`: `ARCHITECTURE MAP TESTS: 9 passed, 0 failed`.
- `tools/TEST_BEFORE_MERGING.sh`: `GATE PASS: full test passes; QUICK 401 passed, 0 failed in 42.6 s ; 0 known failure(s); 162 s total`.
- `python3 tools/job.py test`: passed on `cc37b6e`.

Result: cc37b6e; ARCHITECTURE MAP TESTS 9/9, architecture_map.py --check, TEST_BEFORE_MERGING.sh GATE PASS (QUICK 401/401, full suites), job.py test passed; added tools/architecture_map.py, tools/test_architecture_map.py, generated module map in ARCHITECTURE.md, pre-commit rebuild/check, and headers in viewport/save_prompts.gd and viewport/worker_process.gd
