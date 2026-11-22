### H055 — T93: startup.py shows what waits on William

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: Claude

References: T93, P16, P19, tools/startup.py, H050 (the integrator's note, kept by hand today).

Touches: tools/startup.py, tools/test_startup.py.

Request (the log is two files now, P23: read Work list rows from docs/decision-log.md; principles G01-G12 that are
still Tentative are also waiting on William). Add a "Waiting on William" section to startup.py's report, from main: Work list rows that are Open and whose
last column says "your call" (or "William:") with no I/A/... decision ID after it; open or queued handoffs with an
"Ask William" sentence and no "William's answers" / logged ID in their response; BOARD.md notes addressed to
William. One line each with the ID and a short reason. When the integrator lock is held, a line reminding it to
check CronList for the check-ins after a clear. Checks: samples for each source, including a row that was answered
(not listed). Then shorten H050's "Waiting on William" to point at startup.py. Quick test after.

Response — Claude, 2026-11-22: Done on `claude/h055-t93-waiting-on-william`. startup.py prints "Waiting on William
(from main)": Open Work list rows whose last column leaves something as "your call" with no decision ID (I/A/U/D/M/W/P/G)
after it; Tentative principles; open or queued handoffs with an "Ask William" sentence and no "William's answers" line
or Response naming a decision after it; board notes starting "William" / "For William"; and, while the lock is held,
the CronList reminder. Two choices to check: "Your call, <date>: ..." counts as an answer (that's how the log records
one), and "William:" isn't a marker: in today's rows (T91, T93) it records what he said, so it would list them falsely.
Today it lists T65 (the question's wording) and H050's housekeeping line. H050's "Waiting on William" now points at
startup.py. 11 new checks in tools/test_startup.py (STARTUP TESTS 38/0); quick test passes (QUICK 208/0, every feature
test 0 failed). Outside Touches: H050 (asked for), this entry.
