### H054 — T92: tools/log.py add, for decision log rows

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: Claude

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
