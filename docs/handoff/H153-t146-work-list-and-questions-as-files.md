### H153 — T146 step 2: Work list items and open questions as one file each

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: answered | For: either

References: P65 (William, 2026-11-26: the Work list as single files too; Tunables stay a table), T146, H152 (rulings
as files: this job reuses its machinery), P23, P17 (allowed statuses), T91 (Result lines), T93 (Waiting on William),
T74 (placeholders).

Touches: tools/log.py, tools/sort_decision_log.py, tools/number_ids.py, tools/startup.py (`work_list_ids`, `cited_ids`, `report_ids`, `waiting_rows`, `waiting_on_william`), tools/integrate.py (`set_status`, `record_result`, `record_results`, `draft_results`, `entry_item`, `result_line`, `archive_entries`, `settle_log`), tools/job.py (`done`), 03_Past_Decisions/, tools/test_log.py, tools/test_sort_decision_log.py, tools/test_number_ids.py, tools/test_startup.py, tools/test_integrate.py, tools/test_log_archive.py, tools/test_bookkeeping.py, tools/test_follow_ups.py, tools/test_job.py, CLAUDE.md (the decision-log paragraph), docs/integrator.md (lines naming the Work list's table).

Reading path:
1. H152's response and its code first: the ruling file format, how `sort_decision_log.py` turns rows into files and
   builds the indexes, `log.py`'s `add`/`show`/`set`, and `number_ids.py`'s file renaming. Reuse them; don't copy.
2. The tables this job converts, in `03_Past_Decisions/decision-log.md`: `## Open questions` (`| # | Question | Status |
   Notes |`) and `## Work list` (`| # | Item | Status | Covers | Result / next step |`); in `decision-archive.md`:
   `## Decided questions` and `## Done work`, plus their `### <ID>` Details.
3. Who writes a Work list row today: `log.py` `add T` and `note`; `integrate.py` `set_status` (the verdict; Done
   moves it to the archive) and `draft_results`/`record_result` (step 8: a job's Result line appended to the last
   column); `job.py` `done` (checks there is a Work list item for the result).
4. Who reads one: `startup.py` `work_list_ids` and `cited_ids` (a named T row and the rows its Covers column cites),
   `waiting_rows` (an Open row whose last column says "your call" with no decision ID after it shows under Waiting on
   William, T93), `report_ids`; `sort_decision_log.py` `status_problems` (allowed statuses, and `Open (queued: H040)`).

Today (checked 2026-11-26 on main 8ed856c, H152 merged): rulings are files in `03_Past_Decisions/rulings/`, with
H152's helpers in `tools/sort_decision_log.py` to reuse: `RULINGS_DIR`, `RULING_SECTIONS`, `folder_ids`, `parse_entry`,
`read_entry`, `read_entries`, `write_entry`, `format_ruling`, `row_to_ruling`, `index_row`, `generate_indexes`,
`_ruling_rows_in`. The questions and Work list are still tables. H152 dropped the principles' generated Explains
column (a 4-column index line would be read as a ruling row to convert): item 6 brings it back in `log.py show`.

Request: every Work list item becomes `03_Past_Decisions/work/<ID>.md` and every question
`03_Past_Decisions/questions/<ID>.md`, whatever its status (Open, Done, Decided and the rest stay in the same folder;
only the indexes change, as for rulings). Tunables stay a table in `decision-log.md` (P65).

1. **The files (exactly so):**

       # T147 — <the Item's first sentence, cut at 90 characters with "...">

       Status: Open | Covers: A03, I26b, T145

       <the Item cell, whole>

       Result / next step: <the cell, whole>

       ## Details

       <the "### T147" Details text, when it has one>

   A question: `# Q34 — <title>`, `Status: Open`, the Question text, then `Notes: <the Notes cell>`, then Details.
   `Status:` keeps today's values, `Open (queued: H040)` included, and `status_problems`' rules move to the files.
2. **Indexes**: `## Open questions` and `## Work list` in `decision-log.md` become generated one-line indexes of the
   open ones (`| <ID> | <title text> | <Status> |`), and `## Decided questions` and `## Done work` in the archive of
   the closed ones, the same way as H152's ruling indexes.
3. **Writers**: `log.py add Q|T` writes the file; `log.py note <ID> "<text>"` appends to the `Result / next step:`
   line (`Notes:` for a question) as it appends to the cell today; `log.py set <ID> --status S` works for T and Q.
   `integrate.py` `set_status` and `record_result` write the file (a Done item no longer moves; its index line moves to
   the archive's index). Each keeps its output and its messages, so the integrator's lines read as before.
4. **Readers**: `startup.py` reads T and Q files (a named T and the IDs its Covers line cites; Waiting on William's
   "your call" rule applied to the `Result / next step:` text, unchanged otherwise; its output no longer than
   today's). `job.py` `done` finds the Work list item in `work/`.
5. **Converting**: the same tidy as H152's (a T or Q row found in a table becomes its file), so a branch made before
   this change is converted when it merges.
6. **Explains, back (lost in H152)**: `log.py show G01` ends with `Explains: <the IDs of the Active and Tentative
   rulings whose Principles name G01>`, worked out from the files (none: `Explains: —`). Nothing is stored for it.

What can fail (P42: the project's memory again):
- A cell lost in conversion: every T and Q row's cells and Details come through word for word.
- `integrate.py` step 8 on a branch made before this change: its Result line still lands on the item (in its file).
- Waiting on William: every row it lists today is still listed after the conversion, and no new one appears (compare
  `startup.py`'s Waiting lines before and after on the real log, and quote both in your response).
- Placeholders: a branch's `work/T-new-1.md` is numbered and renamed at merge, its citations renumbered.

Checks, each failing without the change:
- tools/test_sort_decision_log.py: "every Work list and question row becomes its file, word for word"; "a Done item's
  index line is in the archive's index, its file unmoved"; "an old branch's T row is moved into its file by the tidy".
- A conversion check on the real log, run once before committing (IDs before = files after, every cell's text in
  its file): quote the counts.
- tools/test_log.py: "note appends to a Work list file's Result line"; "add T writes a placeholder file on a branch".
- tools/test_integrate.py: "a job's Result line is appended to its Work list file"; "--status Done keeps the file and
  moves its index line".
- tools/test_log.py: "show G01 lists the rulings that name it (Explains)".
- tools/test_startup.py: "a named T item's lines and its Covers rows come from files"; "a 'your call' item in a file is
  waiting on William".
- `tools/featuretest.sh` and the quick test pass.

Response — Gemini (gemini-larch-1126-1913), 2026-11-26:
- Branch: `gemini/h153-t146-work-list-and-questions-as-files`, commit: `2f57f10`.
- Converted Work list items to `03_Past_Decisions/work/<ID>.md` and questions to `03_Past_Decisions/questions/<ID>.md`, with generated 3-column index tables in `03_Past_Decisions/decision-log.md` (`## Work list`, `## Open questions`) and `03_Past_Decisions/decision-archive.md` (`## Done work`, `## Decided questions`); `## Tunables` remains a table.
- Conversion check on the real log: 148 work items (40 open, 108 done) and 37 questions (10 open, 27 decided); verified 185/185 cells and Details sections word-for-word in their files (fixed `row_to_work` / `row_to_question` joining any unescaped `|` in the trailing cell, e.g. `T92`).
- Waiting on William before conversion:
  `  (nothing)`
  `  Integrator: after a clear, re-arm the queue watch: job.py watch --next in the background (docs/integrator.md); no timed check-ins`
- Waiting on William after conversion:
  `  (nothing)`
  `  Integrator: after a clear, re-arm the queue watch: job.py watch --next in the background (docs/integrator.md); no timed check-ins`
- Reused `sort_decision_log.py` helpers for `work/` and `questions/` in `tools/log.py` (`add`, `set`, `note`, `show`, plus `Explains:` in `show G01`), `tools/number_ids.py`, `tools/startup.py` (`report_ids`, `waiting_rows`, `waiting_on_william`), and `tools/integrate.py` (`set_status`, `record_result`, `all_rows`, `settle_log`, `rebuild_and_check`). Updated `CLAUDE.md` and `docs/integrator.md`.
- Verified: `python3 tools/job.py test` passed on `2f57f10` (all 38 feature test suites including 25/25 `test_sort_decision_log.py`, 63/63 `test_log.py`, 53/53 `test_number_ids.py`, 62/62 `test_startup.py`, 86/86 `test_integrate.py`, 37/37 `test_log_archive.py`, 14/14 `test_bookkeeping.py`, 27/27 `test_follow_ups.py`, 197/197 `test_job.py`, and 399/399 viewport quick).
- Architecture: `03_Past_Decisions/work/<ID>.md` and `03_Past_Decisions/questions/<ID>.md` now hold Work list items and questions; `decision-log.md` and `decision-archive.md` hold generated 3-column indexes for them alongside rulings.
- Result: 2f57f10; quicktest passed (feature tests 38 suites, viewport quick 399/399); Work list items and questions atomized into 03_Past_Decisions/work/ and questions/ with generated indexes, Explains restored in log.py show, and tools/tests/docs updated.
