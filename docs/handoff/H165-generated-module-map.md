### H165 — Architecture step 1: a module map generated from each file's own header line

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: open | For: gemini

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
