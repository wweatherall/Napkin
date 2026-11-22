### H070 — Trim CLAUDE.md and AGENTS.md to what a session needs

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: Claude

References: P23 (the log's live/archive split, same idea), P37-P40, G11. William chose this job, 2026-11-22: every
session reads these at the start, so their length is paid on every job (usage).

Touches: CLAUDE.md, AGENTS.md, BOARD.md (its instructions part only, not the job table). Not the folder guides,
ARCHITECTURE.md or docs/protocol.md.

Request: shorten CLAUDE.md (145 lines) and AGENTS.md (63) by moving what only the integrator needs (merging,
numbering, the map, the lock) into one integrator page (a new docs/integrator.md; H050 points to it) and cutting
repetition (rules said in CLAUDE.md, AGENTS.md and BOARD.md alike: say each once, point to it). Keep every rule
(nothing is dropped, only moved or said once); keep William's "Working with William" section in his words. Say in
your response the line counts before and after and where each moved section went. Check: tools/test_startup.py and
anything that greps these files still pass; quick test. A worker's start (CLAUDE.md, then BOARD.md) must still
be enough to take and finish a job.
