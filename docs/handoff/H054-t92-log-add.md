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
note T66 "<text>"` appends to a Work list row's last column. Print the row it wrote. Checks: numbering on main and on a
branch, each table kind, a note appended, the file still passes sort_decision_log.py --check. Quick test after.
