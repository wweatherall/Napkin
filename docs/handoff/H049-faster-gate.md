### H049 — T90: a faster gate

Author: Claude (integrator) | Date: 2026-11-22 | Status: queued (after H045) | For: either

References: T90, P18 (the gate), T49 (lanes side by side), T47 (own ports), T80 and T85 (timing flakes found
under load), H045 (the leftover test process, which changes quicktest.sh first).

Touches: tools/gate.sh, tools/quicktest.sh, tools/fulltest.sh, tools/featuretest.sh, tools/test_integrate.py (the
gate's checks). Not the suites or quick sections themselves unless a timing fix needs one (say so first).

Request: the gate runs the quick test, then the full test: ~3-4 minutes, and merges wait on it. Measure where the
time goes (each lane, each suite, the feature tests, which run twice: once in each). Try: the two side by side;
running the feature tests once and sharing the result; dropping what the full test repeats from the quick test.
Keep the verdict as strict as it is (tools/test_integrate.py's gate cases must still pass). Report the times and
how many of 10 runs passed before and after, with the machine otherwise idle and with other agents' tests running.
