### H161 — Faster tests: find where the gate's time goes and cut it, every check kept

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: open | For: gemini

Item: T154

References: T154 (this item), T151/H160 (scope: tools-only changes skip the app tests; this job makes what still runs
faster), T95 (featuretest runs every suite side by side), T49 (quick-test lanes).

Touches: tools/featuretest.sh, tools/quicktest.sh, tools/test_job.py, tools/test_integrate.py, tools/test_startup.py,
tools/test_log.py, worker/test_outside_save.py, worker/test_scenario.py, worker/test_runs.py, worker/test_native.py,
and any other test file the measurement shows is a long pole (add it with a `Changed from the brief:` line).

Reading path:
1. `tools/featuretest.sh`: how suites are found and started (all at once today).
2. The gate's per-suite `TIMING feature <name>: N s` lines (in `quick.log` under the gate's log folder).
3. The slowest suites' setup: temp git repos, subprocess starts (python3, freecadcmd, Godot), sleeps and timeouts.

Today (measured 2026-11-26, the H158 merge gate, 8 cores, all 42 suites at once): `tools-job` 71 s, `worker-outside_save`
62 s, `worker-scenario` 57 s, `tools-integrate` 55 s, `worker-runs` 48 s, `worker-native` 47 s, `tools-startup` 44 s;
quick lanes 30-41 s; the full test 19 s; the gate ~100 s. featuretest.sh's own comment says "~10 s". The long poles are
tools suites as much as app suites, so H160's tools scope still waits ~70 s.

Request (William, 2026-11-26: "it throws me when we have these long things; I sometimes lose focus"):
1. **Measure first.** Time each of the ten slowest suites alone and inside the parallel run (three runs each, quote
   the medians). Say for each where its time goes (git repo setup, process starts, sleeps/polls, real work) and
   whether the parallel run is CPU-bound (42 suites on 8 cores).
2. **Cut, keeping every check.** Make the changes that keep every check and its meaning, e.g.: shared or cached
   fixtures (one temp git repo copied, not rebuilt per check); fewer process starts (one freecadcmd for many cases);
   sleeps replaced by waiting on the event; limiting featuretest's concurrency to the cores if that's faster; starting
   the longest suites first. Every check that ran before still runs and can still fail: quote each changed suite's
   pass count before and after (equal).
3. **Goal, not rule:** the tools-only gate (H160's scope) under 30 s and the full gate under 60 s. Say how close it
   got; what would need a check dropped or changed goes in the response as a proposal for William (T152 covers
   thinning), not in the code.
4. Fix featuretest.sh's "~10 s" comment to the measured figure.

What can fail:
- A check silently stops running (a shared fixture skips a case). Check: pass counts before/after equal per suite.
- Shared fixtures leak state between checks, so a check passes only because of order. Check: run each changed suite
  three times, and once with its checks in a different order if it has an order you can change; quote.
- Lower concurrency that is faster on this Mac but slower elsewhere: say the setting and how it's chosen (cores).
- A timing flake made more likely (H096, H109, H154's movetest): run the gate three times at the end; quote all three.

Checks:
- The before/after table in the response (suite, alone, in parallel, pass count).
- `tools/TEST_BEFORE_MERGING.sh` passes three times running; quote the totals.
- Result: line gives the gate's total before and after.
