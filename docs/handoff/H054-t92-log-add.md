### H054 — T92: tools/log.py add, for decision log rows

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: Claude

References: T92, P09 (the log's format, in its header), P01, T74 (placeholders on a branch, numbers on main),
tools/sort_decision_log.py (its parsing), tools/number_ids.py.

Touches: tools/log.py (new), a new tools/test_log.py (don't add it to the feature-test script: H049 owns it; give
the line in your response), docs/decision-log.md (its header: one line on the command). Not the instruction files: H053 has them; give the
line for them in your response and the integrator adds it.

Request: `python3 tools/log.py add <I|A|P|M|Q|T|...> "<decision or item>" [--rel "Refines I35"] [--area X] [--where
"..."] [--why "..."] [--status Active]` adds a row to the right table: the next free number when run on main (by the
integrator), else the kind's next placeholder (I-new-N, T74); dated today; sorted by sort_decision_log.py. Also `log.py
note T66 "<text>"` appends to a Work list row's last column. Print the row it wrote. The log is now two files (P23, merged 6c1f65d): a decision goes under its subject's ###
group (--subject, required for decisions) with a Principles cell (--principles G01,G04, or —); use
sort_decision_log.py's functions (insert_row, sort_text) rather than new parsing; numbering counts both files. Also `log.py show <subject|ID>` (William, 2026-11-22), so an agent reads only what it needs: a subject name prints
the log's top (header, Subjects, Principles) only with --top, otherwise just that subject's ### group; an ID prints
its row from whichever file holds it, plus its `### <ID>` details if it has them, plus the principles it names;
`log.py show --top` prints the file down to `## Decisions`. Give the instruction lines for CLAUDE.md and AGENTS.md
("read the top, then `log.py show <subject>`") in your response; the integrator adds them.
Checks: show by subject, by ID in the live file and in the archive, an ID with details, an unknown subject or ID;
numbering on main and on a
branch, each table kind, a note appended, the file still passes sort_decision_log.py --check. Quick test after.

Response — Claude (worker), 2026-11-22: Done on `claude/h054-t92-log-add`.
- `tools/log.py add <kind> "<text>"`: G goes to Principles, Q to Open questions, T to the Work list, any other
  letter is a decision (needs `--subject`, alias `--area`, a unique start of the name is enough, and
  `--principles G01,G04` or `—`; unknown principles are refused). `--rel` (Replaces / or a T's Covers), `--why`
  (or a Q's Notes), `--where`, `--covers`, `--result`, `--status` (checked against the table's allowed statuses).
  On main: the next free number from `number_ids.taken` (both files and the handoff); elsewhere: the kind's next
  placeholder after those already cited on the branch (`number_ids.plan`). Dated today; inserted with
  `insert_row`, then `tidy`, so the Subjects index and Explains are regenerated. A `|` in any text is refused.
  Prints the row as written.
- `log.py note T66 "<text>"`: appends to a Work list row's last column (space-separated); a non-Work-list ID says
  where it is instead.
- `log.py show <subject|ID> [--top]`, `log.py show --top`: as asked; an ID's output starts with
  `<file>: <section> / <subject>` and its table header, then the row, its `### <ID>` Details, and the principles
  it names. An unknown subject lists the subjects; an unknown ID or subject exits 1.
- docs/decision-log.md header: a three-line paragraph on the command (after the New IDs paragraph).
- Tests: `tools/test_log.py`, LOG TESTS 50 passed, 0 failed (~0.7 s), on copies of the real log in temp git repos:
  show by subject (exact, prefix, ambiguous, unknown), --top, by ID in the live file, in the archive, with
  details, with principles, unknown; add of I, A, G, Q, T on main (next numbers) and on a branch (placeholders,
  the second counting the first); the row in the right table/group and the index; seven refusals leaving the log
  unchanged; notes (empty cell, after a result, twice, wrong table, unknown); sort_decision_log --check after;
  the command line. Quick test: QUICK 208 passed, every feature suite passes.

For the integrator at merge:
- tools/featuretest.sh (H057's, unless its discovery finds `tools/test_*.py`): `"log|python3 tools/test_log.py|LOG TESTS"`
- CLAUDE.md, in the "Before changing behaviour" paragraph, replacing "then read only your subject's group
  (`### <subject>`). Grep both files by ID": `then python3 tools/log.py show <subject> for your subject's group, and
  log.py show <ID> for one row (its Details and principles come with it). Add rows with log.py add, never by hand.`
- AGENTS.md, the same line in its decision-log step: `Read the log's top (python3 tools/log.py show --top), then
  python3 tools/log.py show <subject> or <ID>; add rows with python3 tools/log.py add <kind> "<text>" (see its --help
  text at the top of tools/log.py).`
- ARCHITECTURE.md: not changed (it doesn't map the process tools).
