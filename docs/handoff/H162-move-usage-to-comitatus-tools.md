### H162 — Move the token benchmarker (tools/usage.py) to comitatus/09_Tools as MEASURE_TOKEN_USE.py

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: open | For: gemini

Item: T143

References: T143 (this item), P69 (the organization's tools live in comitatus/09_Tools; a code base keeps its own),
H154 (named scripts), T117/T126 (passive usage snapshots), H160 (this is the first job meant to run the tools-only gate).

Touches: tools/usage.py (removed), tools/test_usage.py (removed), tools/MEASURE_TOKEN_USE.py (removed),
tools/job.py (`USAGE_TOOL`), tools/test_named_scripts.py, tools/README.md, docs/integrator.md, ARCHITECTURE.md
(the `tools/usage.py` row only).

In the comitatus repo (not in Touches: the check reads Napkin paths): 09_Tools/MEASURE_TOKEN_USE.py (new),
09_Tools/test_measure_token_use.py (new), 09_Tools/README.md.

Reading path:
1. `tools/usage.py` top (`_THIS_REPO`, `DEFAULT_REPO`, `common_git_dir`, the ledger path) and `main`.
2. `tools/job.py` `USAGE_TOOL` and `record_usage`: the passive, fail-open call at take/done/return/merge
   (`SHOPSKETCH_USAGE_TOOL` overrides the path; tools/test_integrate.py stubs it that way, so it needs no change).
3. comitatus `09_Tools/SORT_PRINCIPLES.py` and its README line: the form an organization tool takes.

Today (checked 2026-11-26 on main): `tools/usage.py` (2,764 lines) and `tools/test_usage.py` (757) live in Napkin;
`tools/MEASURE_TOKEN_USE.py` wraps it; `job.py` calls it by path, fail-open. It measures agent sessions (Claude,
Codex, Gemini transcripts), which is the organization's business, not Napkin's. Its default repo is the folder
above its own file, which after a move would be comitatus, not the code base.

Request:
1. **Two branches, one per repo.** Napkin side as usual in your job worktree. Comitatus has no job queue: make a
   worktree of it yourself, `git -C /Users/Will/Sites/comitatus worktree add
   /Users/Will/Sites/comitatus/08_Code_Bases/.worktrees/comitatus/h162 -b gemini/h162-measure-token-use`
  , commit the comitatus side there, and name its branch and commit in your response. Don't
   commit in comitatus's main checkout. The integrator merges the comitatus branch first, then the Napkin one.
2. **Comitatus side.** `09_Tools/MEASURE_TOKEN_USE.py` is `usage.py` moved whole (`git mv` isn't possible across
   repos: copy it, and say in the commit message where it came from and at which Napkin commit), runnable as
   `python3 ../../09_Tools/MEASURE_TOKEN_USE.py <subcommand>` from a code base. Its default repo becomes the git
   top level of the current directory (falling back to today's environment override), so run from Napkin it still
   reads Napkin's `.git/shopsketch-usage.jsonl`; `--repo` works as now. The tests move with it as
   `09_Tools/test_measure_token_use.py`, all passing there (quote the count: same as today's USAGE TESTS). One line
   in `09_Tools/README.md`, in SORT_PRINCIPLES's form. Nothing else in its behaviour or output changes (old names
   such as FRETCHUP_REPO stay: the name purge is a later job).
3. **Napkin side.** Remove `tools/usage.py`, `tools/test_usage.py` and `tools/MEASURE_TOKEN_USE.py`. `USAGE_TOOL`
   points at `<the comitatus folder>/09_Tools/MEASURE_TOKEN_USE.py`, found from the main checkout as `job.py`
   already finds it (`../..` of the main checkout when its parent is `08_Code_Bases`); outside comitatus, or with
   the file missing, it is simply absent and `record_usage` does nothing, as it does today for a missing tool.
   Guides (`docs/integrator.md`, `tools/README.md`) name `python3 ../../09_Tools/MEASURE_TOKEN_USE.py`;
   `test_named_scripts.py` drops its row. In `ARCHITECTURE.md` replace the `tools/usage.py` row's file names with
   one line saying it moved to comitatus/09_Tools (P69), and add `Architecture: ` to your response saying so.

What can fail:
- Snapshots stop silently after the move (path wrong): check, from a job worktree and from the main checkout,
  that `USAGE_TOOL` resolves to the existing comitatus file; quote both paths. A missing file still means no error.
- The default repo becomes comitatus, so `orient`/`bench` read the wrong ledger: check with the moved tests and one
  real `python3 ../../09_Tools/MEASURE_TOKEN_USE.py orient` from the Napkin main checkout (quote its first lines).
- The Napkin gate: this branch changes only `tools/` and Markdown, so `tools/TEST_BEFORE_MERGING.sh` should say
  `scope tools`; quote its scope line and verdict (this job is the first real trial of H160).

Checks:
- comitatus: `python3 09_Tools/test_measure_token_use.py` passes (count equal to today's).
- Napkin: `tools/TEST_BEFORE_MERGING.sh` passes, `scope tools`.
- `git grep -n "tools/usage.py\|MEASURE_TOKEN_USE"` in Napkin shows only history files and the new `../../09_Tools`
  paths (quote the count).
