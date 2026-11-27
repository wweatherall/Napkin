### H152 — T146 step 1: one file per ruling in Napkin/03_Past_Decisions/rulings/, written and read by log.py

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: open | For: either

References: T146, P61 (move first, split later), P23 (live and archive halves), P09, P01, T92 (log.py), T74 (placeholder
IDs), P57/P60/P64 (the comitatus layout), T138/T134 (smaller briefs: the reason for this).

Touches: tools/log.py, tools/sort_decision_log.py, tools/number_ids.py, tools/startup.py (`report_ids`, `tentative_principles`, the log-top printing), tools/integrate.py (`settle_log`, `LOG`, `ARCHIVE`), .githooks/pre-commit (the decision-log block), 03_Past_Decisions/, tools/atomize_log.py (new), tools/test_log.py, tools/test_sort_decision_log.py, tools/test_number_ids.py, tools/test_startup.py, tools/test_integrate.py, tools/test_log_archive.py, tools/test_bookkeeping.py, tools/test_follow_ups.py, tools/test_job.py, CLAUDE.md (the decision-log paragraph), docs/integrator.md (lines naming the log's tables), docs/agent-handoff.md (its References line only).

Reading path:
1. `03_Past_Decisions/decision-log.md`'s top (down to `## Decisions`): what the file holds and the rules the tools keep.
2. `tools/sort_decision_log.py` docstring, then `tidy` (rows move between the two files by status), `generate` (the
   Subjects index's Decisions column and the principles' Explains column are generated), `layout_problems` and
   `check_files` (what `--check` refuses).
3. `tools/log.py` `add` (writes a row with the next number or a placeholder), `note` (Work list rows only), `show_id`
   and `subject_group` (what `show` prints).
4. `tools/number_ids.py` `taken`, `defined` and the `DEFINES_*` patterns: how a placeholder is found and numbered,
   and how handoff files are renamed (`H152-slug.md` -> `H150-slug.md`).
5. `tools/integrate.py` `settle_log`: the three-way merge of the two log files at merge time.
6. `tools/startup.py` `report_ids` (around line 176) and `tentative_principles`: what the brief reads from the log.

Today (checked 2026-11-26 on main 48b60d1): the log is two big tables files, `decision-log.md` (137 KB: Subjects,
Principles, Decisions in one `###` group per subject, Open questions, Work list, Tunables, Details) and
`decision-archive.md` (97 KB: Superseded decisions, Decided questions, Done work, Details). A brief that names five
rulings still sends an agent to grep two large files, and two branches that add rows conflict in the same tables
(`settle_log` exists for that).

Request: every **ruling** (a principle, G, and every decision: A, D, I, M, P, U, W and any other decision letter,
Active, Tentative or Superseded) becomes one file, `03_Past_Decisions/rulings/<ID>.md`. Questions (Q), Work list
items (T) and Tunables stay as tables in the two files they are in now: they are working lists, not rulings (T146 is
about rulings; a later step can take them on).

1. **The file (the format; keep it exactly so, other tools will read it):**

       # I34 — <the decision's first sentence, cut at 90 characters with "...">

       Status: Active | Subject: Push/Pull | Principles: G01, G04 | Date: 2026-11-21
       Replaces / replaced by: <the cell, or —>
       Where in the code: <the cell, or —>

       <the Decision cell, whole>

       Why: <the Why cell>

       ## Details

       <the "### I34" Details section's text, when it has one; otherwise no Details heading>

   A principle (G) has `Status:` and `Date:` only on its status line (no Subject, no Principles), and no `Where in the
   code` line unless its row has one. A Superseded decision keeps the subject and principles its archive row folded
   into its Principles cell (`archived_row`: "<subject>; <principles>"), split back out. Text is copied unchanged,
   except that `(Details below.)` at the end of a cell is dropped (the Details are in the same file now). The title
   line is generated from the Decision text: `log.py` rewrites it when the text changes; nobody edits it by hand.
2. **The two files keep a generated index instead of the tables.** In `decision-log.md`, `## Principles` and
   `## Decisions` (still one `###` group per subject, in the Subjects index's order) list one line per Active or
   Tentative ruling: `| <ID> | <title text> | <Status> |`, built from the files by `sort_decision_log.py` (like the
   Explains and Decisions columns today, which stay generated). In `decision-archive.md`, `## Superseded decisions`
   becomes the same kind of index for Superseded rulings. The top of `decision-log.md` (its how-to paragraphs) is
   rewritten to say where rulings live and how to read one (`log.py show I34`, or the file).
3. **Moving rows into files is part of tidying.** `sort_decision_log.py` tidy turns any ruling **row** it finds in
   either file's tables into its file (and removes the row and its `### <ID>` Details there), the way it moves
   Superseded rows to the archive today. That is how the conversion happens once (`tools/atomize_log.py` may simply
   call it and report counts), and how a branch made before this change, whose old `log.py` added a table row, is
   converted when it merges: the hook and `integrate.py` already run the tidy. A ruling file whose status becomes
   Superseded stays where it is (P01: never deleted); only the indexes change.
4. **`log.py`**: `add <decision letter or G>` writes the file (next number on main, a placeholder `I-new-N` on a branch,
   as today) and refreshes the indexes; `show <ID>` prints the ruling's file and then the principles it names (each
   principle's title and status line, not their whole files); `show <subject>` prints the subject's index lines and
   each of those rulings' status line and Decision text (no Details); `show --top` prints the log's top, the Subjects
   index and the principles' index lines. `note` and everything about Q, T and Tunables are unchanged. A new
   `log.py set <ID> --status S` (and `--where`, `--rel`) edits a ruling's status line without hand-editing, so
   superseding needs no hand edit (P01: the old ruling gets Superseded, the new one names it).
5. **IDs (`number_ids.py`)**: rulings files count as taken IDs; a branch's `rulings/I-new-1.md` defines the
   placeholder and is renamed to its number at merge, like a handoff file; references inside every file are
   renumbered as today.
6. **`startup.py`** reads a ruling from `main:03_Past_Decisions/rulings/<ID>.md` (falling back to the tables during
   the change, if you need it for the tests), and Tentative principles from the files or the index. Its output for a
   named ID must be no longer than today's.
7. **`integrate.py`**: `settle_log` keeps merging the tables that remain (Q, T, Tunables, indexes: the indexes can
   simply be regenerated after the merge instead of merged). Ruling files merge as ordinary files.
8. **Docs**: CLAUDE.md replaces the `grep "^| I34 " ...` advice with `python3 tools/log.py show I34` (or read
   `03_Past_Decisions/rulings/I34.md`). AGENTS.md and GEMINI.md don't repeat it today, so they stay as they are.
   docs/integrator.md: only lines that name the tables' layout.

Not in this job: moving the Process rulings and the G principles to comitatus/03_Past_Decisions (T146 step 2, on the
Work list), Q/T/Tunables files, and any change to what a ruling says.

What can fail (P42: this rewrites the project's memory, so nothing may be lost):
- A cell lost or changed in conversion: every ruling's every cell and its Details must come through word for word
  (only "(Details below.)" dropped).
- An ID in two places (a row left in a table and a file), or a file without an index line, or an index line without a
  file: `--check` refuses each.
- A branch made before this change adds a ruling row or supersedes one by editing its row: merging it must end with
  that ruling in its file and the row gone (the tidy at merge, item 3).
- Placeholders: a branch's new ruling file numbered and renamed at merge, and its ID renumbered where it's cited.
- The pre-commit hook: a commit touching only `rulings/` files still runs the tidy and the check.

Checks, each failing without the change:
- tools/test_sort_decision_log.py: "every ruling row becomes its file, word for word" (a small fixture log with an
  Active decision with Details, a Tentative principle and a Superseded archive row: files compared with expected
  text); "a ruling row added by an old branch is moved into its file by the tidy"; "the index lists each Active ruling
  under its subject, and Superseded ones in the archive's index"; "--check refuses an ID both in a table and a file".
- A conversion check on the real log, run once before committing the converted files: the set of ruling IDs before
  equals the set of files after, and for each ID every cell's text appears in its file (put it in
  tools/atomize_log.py's output and quote the counts in your response).
- tools/test_log.py: "add writes a ruling file with a placeholder on a branch", "show <ID> prints the file and its
  principles' status lines", "set --status supersedes without editing by hand".
- tools/test_number_ids.py: "a branch's rulings/I-new-1.md is renamed to its number and its citations renumbered".
- tools/test_startup.py: "a named ID's lines come from its ruling file".
- tools/test_integrate.py: "merging a branch that added a ruling file and one that edited an old row ends tidy".
- `tools/featuretest.sh` and the quick test pass (the tools' tests run in the feature tests).
