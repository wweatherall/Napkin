### H076 — T102: the tests refuse to run in the main checkout for a session that holds a job

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: either

References: T102, P24 (the queue), P25 (scratch/ in the worktree). From a worker's feedback, 2026-11-22: each
shell command starts back in the main checkout, and it once started the quick test there instead of in its job's
worktree.

Touches: tools/quicktest.sh, tools/gate.sh, tools/job.py (one small helper the scripts call) and tools/test_job.py.
Not BOARD.md, CLAUDE.md or AGENTS.md: if a worker should be told, say so in a "For the integrator:" line.

Request: when tools/quicktest.sh or tools/gate.sh starts, if it is running in the main checkout (the repository's
first worktree, where git's common folder lives) and the session running it (job.py's own session detection:
CLAUDE_CODE_SESSION_ID, CODEX_SESSION_ID / CODEX_THREAD_ID) holds a job in progress, stop before doing anything with
one line: "you're in the main checkout; your job H0NN is in <worktree>: cd there and run it again" and a non-zero
exit. Everything else runs as today: the integrator (no job) in the main checkout, any session in a job's
worktree, a session with no detectable ID, a missing or unreadable queue file (never block on the guard's own
failure). Keep it fast (it runs before every quick test). An override for the rare deliberate case, e.g.
SHOPSKETCH_ANY_CHECKOUT=1. Checks in test_job.py: refuses in the main checkout for a session holding a job, and
names the worktree; runs in the worktree; runs for a session with no job; runs with no session ID; runs when the
queue file is missing; the override. Quick test, then the gate. End your response with a Result line; leftovers as
Follow-up lines; anything for the merge as For the integrator lines.
