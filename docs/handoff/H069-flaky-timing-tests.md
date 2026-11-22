### H069 — Two timing-sensitive worker tests that fail under load

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: queued (after H066) | For: either

References: P18 (the gate), H057's and the integrator's follow-ups in docs/follow-ups.md, A36 (outside saves), W13.
William chose this job, 2026-11-22 (review: re-running the gate on a flake must not become a habit).

Touches: worker/test_serve.py, worker/test_outside_save.py, docs/follow-ups.md (remove the two lines this clears).
Not worker/serve.py or worker/session.py unless the cause is a real bug there: then stop and say so in your response
first (that would be a behaviour fix, its own job).

Request: make both deterministic without weakening what they check. (1) test_serve.py fails 4 of 20 (saved / focus /
save_failed replies in another order) when featuretest.sh writes inside the repo under full load. (2)
test_outside_save.py "an outside save with actions unsaved says so" once got `unsaved: False` in the gate's quick
test. Find whether each waits on time instead of on the event it means (a sleep, a fixed timeout, a reply order it
assumes) and wait on the event. Checks: each test passes 20 runs in a row under load (all feature tests side by side:
`tools/featuretest.sh`, run through `python3 tools/job.py run -- ...`, P40); say how you loaded it. Quick test.
