### H157 — T142 step 2: picking a to-do up, its jobs linked with their progress, Done by itself when the last merges

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: queued (after H156) | For: either

References: T142, P68 (William, 2026-11-26: "register you picking it up from the to-do list; once it's turned into
jobs, each of those linked to it; once the last has finished, marked done automatically"), P67, H156 (the On the board
status this builds on), H153 (Work list items are files), P66 (06_To-dos), T134.

Touches: tools/log.py, tools/sort_decision_log.py (`board_statuses` and its helpers, `STATUSES`), tools/integrate.py (`update_statuses`, `record_results`), tools/job.py (`board`), tools/org_todos.py (`integrator_items`), tools/startup.py (`report_ids`), tools/test_log.py, tools/test_sort_decision_log.py, tools/test_integrate.py, tools/test_job.py, tools/test_org_todos.py, tools/test_startup.py, docs/integrator.md (the job-writing and merge lines this changes).

Reading path:
1. H156's response and code first: `board_statuses`, how a job is matched to its item (heading `T<n>` or `Item:`), the
   `On the board (...)` status and `Completes:` at merge. Re-date "Today" below against main when you start.
2. `03_Past_Decisions/work/<ID>.md` (H153's format): the status line and `Result / next step:`.
3. `docs/handoff-archive.md`: a merged job's entry ends `Resolution: merged into main by the integrator, <date>.`;
   an abandoned one has another Resolution. That is how a script tells merged from dropped.
4. `org_todos.py` `integrator_items` and `startup.py` `report_ids`: where the to-dos and an item's lines are shown.

Today (written 2026-11-26 before H156 merged): H156 adds `On the board (H0NN, ...)` while an item has open jobs and
`Done` at merge only with `Completes:`. Picking an item up isn't recorded, merged jobs drop off the item, and a job's
progress shows only on the board.

Request (P68):
1. **Picking up**: `python3 tools/log.py pick T147` sets `Status: Picked up (<who>, <date>)` (who: `--as <name>`,
   default `integrator`). Only an `Open` item can be picked up (else say its status and do nothing). The integrator
   guide says to run it when taking an item off the to-do list to turn into jobs.
2. **Linked jobs, with progress**: the item's file gets a `Jobs:` line under its status line, written by
   `board_statuses` (never by hand): every job ever matched to the item, in ID order, each with its state from the
   handoff and the queue: `queued`, `ready`, `in progress (gemini)`, `for review`, `merged <short commit>`, `dropped`.
   A job stays listed after it merges (that is the item's history); one archived without a merge shows `dropped`.
   Example: `Jobs: H150 merged 4bb59a0 · H151 in progress (gemini)`.
3. **The status follows the jobs**: `Picked up` or `Open` with at least one job not merged or dropped -> `On the board
   (<the unfinished ones>)`; every listed job merged or dropped and at least one merged -> `Done` (index line to the
   archive), by itself; every listed job dropped -> `Open`. `Completes:` (H156) still works but is no longer needed:
   say so in docs/integrator.md. An item `Done`, `Parked` or `Split` is never moved; `log.py set T147 --status Open`
   reopens one (its `Jobs:` line stays, and a new job joins it).
4. **The to-do lists**: `06_To-dos/waiting_on_integrator` (org_todos.py) gets one file per `Open` Work list item that is
   not waiting on William (those are already in `waiting_on_William`), and one per `Picked up` item, named and marked
   so ("picked up 2026-11-26"); an item `On the board` or `Done` has no to-do file (on the board, the to-do is done).
   H156's "last job merged; next step" files are replaced by this rule.
5. **Showing it**: `log.py show T147` and `startup.py T147` print the `Jobs:` line with the item.

What can fail:
- The integrator writes the first job of a two-job plan, and it merges before the second is written: the item goes
  Done too early. The rule for that: write all of an item's jobs in one commit (the second as `queued (after ...)`),
  which docs/integrator.md says; if it happens anyway, `log.py set --status Open` and the next job joins the item.
- A job heading naming two items: link it to each (as H156 decided; follow its choice).
- Merged jobs from before this change (archived entries): `board_statuses` may link them when it first runs, so old
  items show their history; it must not mark a Parked or Split item Done.

Checks, each failing without the change:
- tools/test_log.py: "pick moves an Open item to Picked up with who and when"; "pick refuses an item that isn't Open".
- tools/test_sort_decision_log.py: "a picked-up item with a queued job is On the board and lists the job";
  "an item lists its merged job with its commit and keeps it listed"; "an item is Done by itself when its last
  linked job merges"; "an item whose only job was dropped goes back to Open"; "a Parked item is never moved".
- tools/test_org_todos.py: "an Open item not waiting on William is an integrator to-do"; "a picked-up item's to-do
  says picked up"; "an item On the board has no to-do file".
- tools/test_startup.py: "a named item's lines include its Jobs line".
