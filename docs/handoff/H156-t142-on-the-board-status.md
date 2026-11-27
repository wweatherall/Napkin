### H156 — T142: a Work list item is "On the board" while it has jobs and Done when its last one merges, all by script

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: open | For: either

References: T142, P67 (William, 2026-11-26: option C, scripted so it isn't manual work), P17 (statuses), T91 (Result
lines), H153 (Work list items are files), T130 (queued jobs unblock themselves).

Touches: tools/sort_decision_log.py (`STATUSES`, `QUEUED`, `status_problems`, a new `board_statuses` helper), tools/integrate.py (`entry_item`, `update_statuses`, `record_results`, `set_status`), tools/job.py (`board`), tools/org_todos.py (`integrator_items`), tools/test_sort_decision_log.py, tools/test_integrate.py, tools/test_job.py, tools/test_org_todos.py, docs/integrator.md (the "Writing jobs" and "Review and merge" lines this changes), docs/agent-handoff.md (the entry template's header lines only).

Reading path:
1. `integrate.py` `entry_item`: how a job's item is found today (the `T<n>` in its heading, or `--status`).
2. `integrate.py` `update_statuses` and `set_status`: the integrator's `--status` verdict at merge; `record_results`
   appends the job's `Result:` line to the item's file.
3. `sort_decision_log.py` `STATUSES` and `QUEUED` (`Open (queued: H040)`): the allowed Work list statuses.
4. `job.py` `board`: runs on every commit on main that touches the handoff or the board (the hook) and in both of
   `integrate.py`'s merge paths: the place a reconciliation can run without anyone remembering it.

Today (checked 2026-11-26 on main): an item stays `Open` while its jobs run; at merge the integrator types `--status
Done` or runs `set_status` by hand (this session: T145, T147). Nothing marks an item as having jobs.

Request (P67):
1. **The status**: `On the board (H150, H151)`, the IDs of the item's jobs that are open, queued, in progress or
   answered (in ID order). It replaces `Open (queued: H040)`, which nothing writes any more (convert any found).
2. **Which jobs are an item's**: an entry in `docs/handoff/` whose heading names `T<n>` (as `entry_item` reads it
   now), or whose `Item: T<n>` line names it (new optional header line, for a job whose heading doesn't). Entries for
   the integrator (no `For: Claude|Codex|Gemini|either`) don't count.
3. **One function moves the status both ways**, `board_statuses(root)` (sort_decision_log.py or a helper it owns):
   for every Work list item that is `Open` or `On the board (...)`: jobs found -> `On the board (<their IDs>)`; none
   -> `Open`. `Done`, `Parked` and `Split` are never touched. `job.py board` calls it (so the hook, both merge paths
   and `job.py board` all keep it right), and it changes only the status line of the item's file.
4. **Done at merge**: a job brief may say `Completes: T147` in its header. When `integrate.py` merges a job with that
   line, after recording its Result it sets the item `Done` (moving its index line to the archive). A merged job
   without it leaves the item to `board_statuses`: still `On the board` if other jobs remain, else `Open` (with the
   Result on it, so the next step is visible). `--status` keeps working and wins over `Completes:`.
5. **The to-do list**: `org_todos.py` `integrator_items` adds each `Open` Work list item whose `Result / next step`
   has a merged Result (a job finished, the item isn't): "T147: its last job merged; next step or Done". Items that
   never had a job stay off the list (most are William's or later).
6. **Docs**: the entry template gets `Completes:` and `Item:` as optional header lines; docs/integrator.md's job-writing
   line says to add `Completes:` to an item's last job, and its merge line that statuses now move themselves.

What can fail:
- A returned or abandoned job: its entry goes back to open (returned: still On the board) or is archived without a
  merge (abandoned: back to Open). Both follow from item 3, with no special case.
- Two items named in one heading ("T145 findings: T147 ..."): count the job for each named item that is `Open` or
  `On the board`; say in your response what you did.
- A branch made before this change: its merge still works (the hook and `job.py board` run on main after it).

Checks, each failing without the change:
- tools/test_sort_decision_log.py: "an Open item with a queued job is On the board with its ID"; "an item whose last
  job is archived goes back to Open"; "Done and Parked items are never moved".
- tools/test_integrate.py: "a job with Completes: marks its item Done at merge"; "a merged job without it leaves the
  item On the board while another job remains, else Open with the Result".
- tools/test_job.py: "job.py board updates the item statuses from the handoff".
- tools/test_org_todos.py: "an Open item whose job merged without completing it waits on the integrator".
