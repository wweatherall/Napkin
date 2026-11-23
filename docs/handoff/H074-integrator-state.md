### H074 — For the next integrator session: where things stand

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: the integrator

References: docs/integrator.md (the integrator's rules and the merge traps), BOARD.md, tools/startup.py.

Touches: nothing (a note). Archive it once read: `python3 tools/handoff.py archive H0NN`.

Taking over: `python3 tools/integrator.py take fretchup-73` (a /clear keeps the name; another name needs
`--william`), then `python3 tools/startup.py`, then re-arm the watch (docs/integrator.md).

In flight (2026-11-22, evening; main pushed, gate passing): merged today H065 (Paint), H066 (T101, A37 recovery),
H071 (Select), H070 (shorter CLAUDE.md/AGENTS.md; integrator rules now in docs/integrator.md), two small fixes.
Ready: H069 (three flaky timing tests: do it first, it blocked H071's `job.py done` and forced one gate re-run),
H072 (T88 step 3, Circle), the integrator-tool traps job (number_ids prose, BOARD.md settling; it doesn't overlap
H069 or H072). Then T88 step 4 (Rectangle) after H072, then H052 (T66 units).

Whole-code review: William is running `/code-review ultra` (he has three free runs) in
/Users/Will/Sites/fretchup-review-all, a throwaway repo with no remote: its first commit is context (docs, log,
tests), branch review-all adds all of worker/, viewport/, tools/ and .githooks/ as of 057c551. When he brings the
findings: check each against the decision log and today's code (the repo is a snapshot), then real bugs become
small fixes (P22) or Work list items with jobs; design choices go to William as questions, one at a time. If the
worker part comes back thin, he may spend a second run on worker/ alone. Delete the folder when done.

Proposed to William, not decided: a lighter `/code-review` run by the integrator on every merge, and an ultra review
(William runs it) before merging saving/recovery, protocol or T88 steps 5-6 jobs. Process changes are frozen
for now (his review of 2026-11-22); don't start either until he says.
