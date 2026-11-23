### H080 — T105: job.py done reuses a quick-test pass across handoff-only commits

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: either

References: T105, P24 (the queue), P18 (the gate). From a Codex worker's feedback, 2026-11-22.

Touches: tools/job.py and tools/test_job.py.

Request: today `job.py done` reruns the whole quick test whenever the latest commit has no recorded pass
(tools/job.py, `done`: `t.get("commit") == head`), so the usual last commit, the response appended to the handoff
entry, costs a full quick-test run after a gate pass. Change: if a clean pass is recorded for an earlier commit
on the job's branch, and every commit after it (that commit..HEAD) changes only files under docs/handoff/ and
docs/agent-handoff.md, accept that pass: run only tools/test_bookkeeping.py (the handoff checks; confirm by
reading it that it covers entries and the open list, and say so), and say in one line which commit's pass was
reused. Any other file changed since the pass, a pass recorded for a commit that isn't an ancestor of HEAD, or a
failed bookkeeping check: run the quick test as today. Checks in test_job.py: a handoff-only commit after a pass
reuses it and runs only the bookkeeping check; a code change after the pass reruns the quick test; a pass on a
commit not on the branch isn't reused; a failing bookkeeping check refuses. Quick test, then the gate. End your
response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.
