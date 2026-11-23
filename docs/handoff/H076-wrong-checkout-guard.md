### H076 — T102: the tests refuse to run in the main checkout for a session that holds a job

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: either

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

Response — Codex, 2026-11-22:

Branch: `codex/h076-wrong-checkout-guard`. Implementation commit: `753ec27`.
Both test entry points call `job.py guard-checkout` before starting tests or creating output folders.
It uses existing session detection and reads the shared queue without locking it; in the main checkout,
a session holding an in-progress or waiting job gets the requested one-line refusal and worktree path.
`SHOPSKETCH_ANY_CHECKOUT=1` permits a deliberate run. Missing session IDs, queue read/schema failures,
and worktree runs pass through. Main was merged before this response (already up to date).

Verification: `python3 tools/job.py run -- python3 tools/test_job.py`: 96 passed, 0 failed.
Quick test: all feature suites pass, viewport 240 passed, 0 failed.
Gate: PASS, full test passes, quick 240 passed, 0 failed, 0 known failures (84 s).
Logs: `scratch/h076-job.log`, `scratch/h076-quick.log`, `scratch/h076-gate.log`.
The shell guard checks use each entry point's actual startup prefix, ending at a test-start marker,
to verify that a refusal precedes any test execution. All three session environment keys are covered,
along with the worktree, no-job/no-ID cases, override, and missing/malformed/unreadable queue data.

Decisions: T102 implements the already approved request; no new decisions or placeholder IDs.
Architecture: Test orchestration adds a read-only job-queue guard to quicktest.sh and gate.sh via
job.py; model state, saving, protocol and application module boundaries are unchanged.
For the integrator: H076 is ready for review; no worker-guide edits are needed. The override is in job.py's help.

Result: 753ec27; job tests 96/0, quick 240/0 with all feature suites passing, gate PASS; refused worker tests in the main checkout and named the assigned worktree.
