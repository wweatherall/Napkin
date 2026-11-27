### H175 — The merge tools: six things the integrator did by hand on 2026-11-27, made automatic

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: answered | For: gemini

References: William, 2026-11-27 ("What is being done by hand that should be automated?"), comitatus principles C05
("can it just be a Python script?") and C08 (make your work environment better), docs/follow-ups.md (two of these
are follow-ups there: clear them when done), P44.

Touches: tools/integrate.py (`settle_handoff`, `settle_log`/the merge's log step, `--continue`, the Item-status step),
tools/number_ids.py (`apply`, which files it rewrites), tools/launch.py (`session_name`, or wherever the name is
made: line ~45), tools/job.py (a `merged` command), tools/test_integrate.py, tools/test_number_ids.py,
tools/test_launch.py, tools/test_job.py, docs/integrator.md (the lines these change), docs/follow-ups.md (the two
lines this job clears).

Reading path:
1. tools/integrate.py docstring (its steps), `settle_handoff` (~line 424), `settle_log` (~222), the stop for "Changed
   from the brief" and `--continue`, and where `Item: T<n>` sets the item's status at merge.
2. tools/number_ids.py `apply` and its list of files (`ID_FILES`, `ENTRY_FOLDERS`).
3. tools/launch.py where the session name is made (`f"{agent}-{random.choice(WORDS)}-{now:%m%d-%H%M}"`).
4. tools/job.py `merged(root, branch)` (~line 1041).

Today (checked 2026-11-27): each of these happened today and was fixed by hand:
1. **H168's merge put back an old broken link.** `settle_handoff` keeps main's docs/agent-handoff.md whole, so a
   branch that rewrote its hand-written parts (the how-to) lost them.
2. **H166's merge dropped the Process rulings' index lines** from decision-log.md until the log tidy was run by hand;
   the gate caught it (follow-up in docs/follow-ups.md). The merged log isn't tidied against both rulings folders
   before the gate.
3. **After a gate failure fixed by hand, nothing could finish the merge**: `--continue` said "no paused merge", or
   refused because files changed since the gate passed, even after `tools/gate.sh` passed again. The integrator
   committed the merge by hand twice (H166, H168) and then had to delete `.git/shopsketch-integrate.json`.
4. **Those hand-committed merges stayed "for review" in the queue** until `job.merged()` was called from Python.
5. **Two workers launched in the same minute got the same name** (`gemini-ash-1127-0729`), so their prompt files
   overwrote each other.
6. **`number_ids.py` renumbers placeholders inside history files** (handoff-archive.md: examples of `I-new-1` in an
   old brief became `I73`; follow-up in docs/follow-ups.md).
7. **Merging one step of a multi-step item marked the whole item Done** (T138 after H165 and after H167, reopened by
   hand both times).

Request: fix each, with a test each:
1. Handoff: settle docs/agent-handoff.md three-way: the generated parts (open list, Archived) are rebuilt by
   `handoff.py tidy`; for the hand-written rest, take the branch's text when main's is unchanged since the merge
   base, main's when the branch's is unchanged, and stop with a conflict when both changed.
2. Log: the merge runs the log tidy (with both rulings folders) on the merged tree before the gate.
3. `--continue` after a gate failure: if the merge is still in progress, `python3 tools/MERGE_JOB.py --continue
   --regate ...` re-runs the gate on the current tree and, on a pass, finishes the merge exactly as an unpaused one
   would (results, archive, queue, push). The state file is always removed when a merge finishes or is aborted.
4. `python3 tools/job.py merged <ID>` marks a job merged in the queue (for any merge finished outside integrate.py).
5. Session names are unique: add the seconds, or a suffix when the name is taken.
6. `number_ids` leaves history files alone: docs/handoff-archive.md and decision-archive.md's archived entries are
   never rewritten (only new entries being archived in this merge are).
7. An item a job names with `Item: T<n>` goes back to Open at merge, with "step merged (H0NN)" in its result; it goes
   Done only when the brief says `Completes: T<n>` (docs/integrator.md says this, replacing "no longer needed").

Not in this job: anything else in integrate.py, the gate itself.

What can fail:
- A real conflict in the handoff's hand-written text silently resolved: both changed -> the merge stops. Check: test.
- `--regate` finishing a merge whose gate failed: it finishes only on a pass. Check: test with a failing gate.
- A placeholder in a new entry left unnumbered because its file is an archive: only entries already archived before
  this merge are skipped. Check: test_number_ids.py.

Checks:
- The four test files above, one case per item.
- `tools/TEST_BEFORE_MERGING.sh` passes (scope tools).

Response — Gemini (gemini-cherry-1127-0955), 2026-11-27:
Done all seven items:
1. `tools/integrate.py` (`settle_handoff`, `_handoff_handwritten`): settles `docs/agent-handoff.md` three-way on the hand-written text (taking branch when main is unchanged from base, main + inline entries when branch is unchanged, stopping with a conflict when both changed) and rebuilds the open list and `## Archived` with `handoff.split` and `handoff.tidy`.
2. `tools/integrate.py` (`rebuild_and_check`): runs `number_ids.tidy_log(root)` (which passes both rulings folders via `sort_decision_log.ruling_dirs(root)`) before `check_files` and `run_gate`.
3. `tools/integrate.py` (`run_gate`, `load_continuation`, `check_start`): saves merge state (`gate_failed: True`) on gate failure; `--continue --regate` stages working-tree fixes and re-runs the gate, finishing only on pass; `--continue` without `--regate` refuses while `gate_failed` is set; stale state files are removed when a merge finishes, is aborted (`MERGE_HEAD` missing), or a new merge starts.
4. `tools/job.py` (`merged_job`, `merged <ID>`): marks a job merged in the queue and cleans up its worktree/branch for merges finished outside `integrate.py`.
5. `tools/launch.py` (`session_name`): adds seconds (`%m%d-%H%M%S`) and appends `-2`, `-3`, ... when `scratch/launch/<name>.txt` already exists.
6. `tools/number_ids.py` (`_archived_lines`, `defined`, `plan`, `apply`): skips already-archived entries in `docs/handoff-archive.md` and `03_Past_Decisions/decision-archive.md` while still numbering new entries being archived in the merge; cleared both follow-up lines in `docs/follow-ups.md`.
7. `tools/integrate.py` (`record_result`, `draft_results`) & `tools/sort_decision_log.py` (`board_statuses`): items without `Completes: T<n>` return to `Open` when their linked jobs finish, with `step merged (H0NN)` in their result; `Completes: T<n>` marks them `Done`. Updated `docs/integrator.md`.

Changed from the brief: With integrator scope approval (`job.py wait --scope`), updated `tools/sort_decision_log.py` (`board_statuses`) and `tools/test_sort_decision_log.py` so `On the board` items return to `Open` when their last linked job merges without `Completes:`, and updated `tools/test_bookkeeping.py` for the `step merged (H060)` result format.

Result: 743ad20; `tools/TEST_BEFORE_MERGING.sh` (scope tools) passed (148 s); `test_launch.py` 16/16, `test_number_ids.py` 55/55, `test_job.py` 201/201, `test_integrate.py` 93/93, `test_sort_decision_log.py` 36/36, `test_bookkeeping.py` 14/14; automated 7 merge-tool fixes.
