### H146 — T130: Auto-unblock queued jobs immediately when their dependencies merge and push

Author: Gemini (integrator, gemini-cedar-1124-2201) | Date: 2026-11-24 | Status: open | For: either

References: T130, P16, P39, P49.

Touches: tools/job.py, tools/integrate.py, tools/test_job.py, tools/test_integrate.py.

Reading path:
1. `tools/job.py` (`jobs_from`, `main_view`, `takeable`, `status`, `table`, `board_text`, `take`, `watch`) — how `Status: queued (after H0NN)` is parsed, displayed, and filtered when picking a Ready job.
2. `tools/integrate.py` (`clean_up_job`, `record_results`, `push_main`) — what runs right after a job merges and before/during `git push origin main`.

Today (verified 2026-11-24 on `main`):
- `tools/job.py` `jobs_from()` (line 210) sets `kind = "queued"` whenever `Status:` begins with `queued`, and extracts `waits` from `after ([^)]*)`.
- `takeable()` (line 266) skips any job with `j["kind"] != "ready"`, even when every `H\d+` dependency listed in `waits` has already been merged (no longer in active `docs/handoff/` on `main`, or marked `state == "merged"` in queue state).
- `tools/integrate.py` marks the merged job in queue state and pushes `main`, without flipping `Status: queued (after H0NN)` to `open` on dependent handoff entries.
- Result: jobs waiting on a merged dependency stay stuck as `Queued`, so `job.py take` / `take --wait` / `status` report "nothing Ready" until the integrator manually edits the dependent handoff files.

Request:
1. **Automatic dependency resolution in `tools/job.py`**:
   - Parse `H\d+` dependency IDs from a queued job's `waits` string (e.g. `H126` from `queued (after H126)` or `H126`, `H128` from `queued (after H126, H128)`).
   - A dependency ID `dep` is **resolved** if it is NOT an unmerged entry in the current `jobs` list (i.e. not present in `jobs`, or its state in `st["jobs"]` is `"merged"`).
   - If a `queued` job has at least one `H\d+` dependency ID in `waits` AND all of its `H\d+` dependency IDs are resolved:
     - Treat it as **Ready** (`kind == "ready"`, with `waits` cleared to `""`) in `takeable()`, `status()`, `table()`, `watch()`, and `take` / `take --wait`, so a waiting worker can take it the instant its blocker is merged/pushed.
   - If a `queued` job has multiple `H\d+` dependencies and only some are resolved, keep it `queued` and show only the remaining unresolved IDs in `waits`.
   - If a `queued` job's `waits` has NO `H\d+` dependency ID (e.g. `Status: queued` or `Status: queued (waiting on William)`), do NOT auto-unblock it — it stays `queued` until the integrator opens it.
2. **Persist the unblocked status on `main` in `tools/integrate.py` before pushing**:
   - In `tools/integrate.py`, right after `clean_up_job()` marks the merged job(s) merged (and before `push_main()` pushes `origin main`), scan `docs/handoff/*.md` on `main` for any `Status: queued (after ...)` whose `H\d+` dependencies are now all resolved (using the shared helper from `tools/job.py`).
   - For any such file, update its `Status:` field in the `Author:` metadata line from `queued (after ...)` to `open` (if some `H\d+` dependencies remain, rewrite `queued (after <remaining>)`), rebuild `BOARD.md` (via `job.board`) and `docs/agent-handoff.md` (via `handoff.list` / index update), and commit the unblock cleanly on `main` before `push_main()` runs so `origin/main` immediately reflects the unblocked Ready jobs!
   - Also print a clear `say(...)` line listing any jobs unblocked (e.g., `unblocked H127 (after H126)`).
   - Keep `tools/integrate.py`'s existing stop/pause behaviour (P28/P44) unchanged.

Checks:
- `tools/test_job.py`:
  - A job with `Status: queued (after H126)` stays `Queued` (not takeable) while `H126` is open/in-progress/answered, and immediately becomes `Ready` (takeable by `takeable()` and `take`, shown as `**Ready**` in `table()` / `status()`) once `H126` is archived/merged (absent from `docs/handoff/` or `state == "merged"`).
  - Multi-dependency `Status: queued (after H126, H128)` stays `Queued` (showing only `H128`) when only `H126` is merged, and becomes `Ready` once both are merged.
  - Non-ID wait `Status: queued (waiting on William)` or bare `Status: queued` is NOT auto-unblocked.
- `tools/test_integrate.py`:
  - Integrating and pushing a blocker job (`H126`) automatically flips a dependent `Status: queued (after H126)` handoff file to `Status: open`, rebuilds `BOARD.md`, commits, and pushes so the dependent job is immediately Ready on `main` and `origin/main`.
  - Partial dependency resolution (`after H126, H128` when `H126` merges) rewrites the Status to `queued (after H128)` and keeps it `Queued`.
- Run `python3 -m unittest discover -s tools -p 'test_*.py'` (and `tools/job.py test`) to verify all tool tests pass.
