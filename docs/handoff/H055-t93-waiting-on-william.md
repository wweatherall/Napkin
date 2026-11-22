### H055 — T93: startup.py shows what waits on William

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: queued (after H056) | For: Claude

References: T93, P16, P19, tools/startup.py, H050 (the integrator's note, kept by hand today).

Touches: tools/startup.py, tools/test_startup.py.

Request: add a "Waiting on William" section to startup.py's report, from main: Work list rows that are Open and whose
last column says "your call" (or "William:") with no I/A/... decision ID after it; open or queued handoffs with an
"Ask William" sentence and no "William's answers" / logged ID in their response; BOARD.md notes addressed to
William. One line each with the ID and a short reason. When the integrator lock is held, a line reminding it to
check CronList for the check-ins after a clear. Checks: samples for each source, including a row that was answered
(not listed). Then shorten H050's "Waiting on William" to point at startup.py. Quick test after.
