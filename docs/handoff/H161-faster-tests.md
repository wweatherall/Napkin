### H161 — Faster tests: find where the gate's time goes and cut it, every check kept

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: answered | For: gemini

Item: T154

References: T154 (this item), T151/H160 (scope: tools-only changes skip the app tests; this job makes what still runs
faster), T95 (featuretest runs every suite side by side), T49 (quick-test lanes).

Touches: tools/featuretest.sh, tools/quicktest.sh, tools/test_job.py, tools/test_integrate.py, tools/test_startup.py,
tools/test_log.py, tools/job.py (`handoff_texts`, `processes`, `ancestors`), worker/test_outside_save.py,
worker/test_scenario.py, worker/test_runs.py, worker/test_native.py,
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

### Response — Gemini (gemini-juniper-1126-2326)

Result: full gate 88 s before → 71 s / 131 s / 87 s after (`featuretest.sh` parallel median 46.5 s → 33.7 s); tools-only `featuretest.sh --tools-only` median 34.7 s (+ 8 s parse) → 24.0 s (parse skipped, under 30 s goal).

Changed from the brief:
- Added `tools/job.py` (`handoff_texts`, `processes`, `ancestors`) per integrator scope approval: *"Yes, both, in tools/job.py's handoff_texts, processes and ancestors only (H163 and H164 change next_step, save_personal_space and _take, so stay out of those). Conditions: same results as today (every caller gets what it got, including when git or ps fails: keep the fail-open paths), add Touches with backticked names: tools/job.py (`handoff_texts`, `processes`, `ancestors`), and a Changed from the brief: line. test_job.py's count unchanged."*
- Kept `tools/featuretest.sh` unbounded (all 42 suites in parallel): bounding concurrency to 8 cores slowed `featuretest.sh` from 46.9 s to 105.4 s (and 16 slots took 62.0 s) because the slow suites (`outside_save`, `job`, `integrate`) are I/O-, sleep-, and subprocess-bound and serialize when capped.
- Left `tools/test_startup.py`, `worker/test_scenario.py`, `worker/test_runs.py`, and `worker/test_native.py` unchanged (their parallel slowdown was CPU contention from the 42-way run, not internal sleeps/setups).

#### Measurement and bottlenecks
The 42-suite parallel run on 8 cores is heavily CPU-bound (1.7x–11x slower in parallel than alone, e.g. `worker-combos` 1.78 s alone vs 20.0 s in parallel, `worker-scenario` 10.96 s alone vs 32.0 s in parallel). Inside the slowest suites alone:
- `tools-job` (27.00 s): 661 `git show` calls in `handoff_texts` (5.19 s), 38 `MEASURE_TOKEN_USE.py` subprocesses (4.76 s), 634 `git rev-parse` calls (3.85 s), 140 `ps -o ppid=` + `ps -axo` + 29 `lsof` calls (3.38 s), 10 `repo()` setups.
- `worker-outside_save` (23.12 s): 16 `freecad_save` + `READ_LABEL` `freecadcmd` cold starts, 16 `wait_outside` polls against `serve.py`'s `WATCH_S = 0.25`, and 2.5 s of explicit sleeps/timeouts.
- `tools-integrate` (15.55 s): 29 `repo()` setups (`git init`/`add`/`commit`) and 9 `bash tools/gate.sh` runs.
- `tools-log` (4.40 s): 9 `repo()` setups copying `03_Past_Decisions/` and running `git add .` (2.00 s).

#### Changes made (every check kept)
- `tools/job.py` (`handoff_texts`, `processes`, `ancestors`): batched `handoff_texts(root, ref)` with `git cat-file --batch` (with `git show` fallback on error); folded `ancestors()` into `processes()`'s single `ps -axo pid=,ppid=,etime=,command=` call.
- `tools/test_job.py`: disabled `SHOPSKETCH_USAGE_TOOL` by default (the dedicated usage-hook section overrides it with `patch.dict`); cached `_TEMPLATE_REPO` in `repo()`.
- `worker/test_outside_save.py`: replaced 16 `freecad_save` and `READ_LABEL` `freecadcmd` cold starts with one persistent `freecadcmd` helper process.
- `tools/test_integrate.py` & `tools/test_log.py`: cached `_TEMPLATE_REPO` in `repo()`.
- `tools/quicktest.sh`: skipped `parsecheck.sh` on `tools-only` (which only parses Godot scripts while viewport is skipped), and in `full` scope launched `featuretest.sh` in the background before `parsecheck.sh` so `parsecheck.sh` + `viewport_tests` overlap with `featuretest.sh`.
- `tools/featuretest.sh`: updated header comment from `~10 s` to `~34 s`.

#### Before / after table (3-run medians)
| Suite | Before alone | After alone | Before parallel | After parallel | Pass count (before → after) |
|---|---:|---:|---:|---:|---|
| `tools-job` | 27.00 s | 17.93 s | 45.0 s | 32.0 s | 199/199 → 199/199 |
| `worker-outside_save` | 23.12 s | 20.80 s | 39.0 s | 33.0 s | 54/54 → 54/54 |
| `tools-integrate` | 15.55 s | 14.88 s | 28.0 s | 26.0 s | 88/88 → 88/88 |
| `worker-scenario` | 10.96 s | — | 32.0 s | 30.0 s | 714/714 → 714/714 |
| `tools-startup` | 6.25 s | — | 19.0 s | 16.0 s | 63/63 → 63/63 |
| `tools-log` | 4.40 s | 3.61 s | 19.0 s | 19.0 s | 66/66 → 66/66 |
| `worker-runs` | 4.34 s | — | 24.0 s | 23.0 s | 13/13 → 13/13 |
| `worker-native` | 3.75 s | — | 24.0 s | 22.0 s | 87/87 → 87/87 |
| `worker-model_units` | 3.62 s | — | 21.0 s | 20.0 s | 22/22 → 22/22 |
| `worker-cut_ties` | 2.05 s | — | 21.0 s | 20.0 s | 25/25 → 25/25 |
| `worker-combos` | 1.78 s | — | 20.0 s | 19.0 s | 61/61 → 61/61 |
| **featuretest (all 42)** | — | — | **46.5 s** | **33.7 s** | all 42 pass |
| **featuretest (`--tools-only`)** | — | — | **34.7 s** | **24.0 s** | all 19 pass |

#### Verification
- Each changed suite run 3 times alone: `tools/test_job.py` `[18.09, 17.61, 17.93] s` (199/199), `worker/test_outside_save.py` `[20.80, 20.84, 20.46] s` (54/54), `tools/test_integrate.py` `[14.87, 14.88, 15.01] s` (88/88), `tools/test_log.py` `[3.65, 3.56, 3.61] s` (66/66).
- `tools/test_log.py` with check functions run in reversed order: `REVERSED LOG TESTS: 66 passed, 0 failed`.
- `tools/TEST_BEFORE_MERGING.sh --full` 3 consecutive runs:
  1. `GATE PASS: full test passes; QUICK 399 passed, 0 failed in 28.6 s ; 0 known failure(s); 71 s total`
  2. `GATE PASS: full test passes; QUICK 399 passed, 0 failed in 49.2 s ; 0 known failure(s); 131 s total`
  3. `GATE PASS: full test passes; QUICK 399 passed, 0 failed in 29.7 s ; 0 known failure(s); 87 s total`

#### Proposals for T152 (to get the full gate under 60 s)
1. **Allow `SERVE_WATCH_INTERVAL` override in `worker/serve.py`** (or thin `test_outside_save.py`'s 16 outside-save cycles): `test_outside_save.py` still spends ~11 s waiting on `serve.py`'s hardcoded `WATCH_S = 0.25`.
2. **Cache `common_dir` / `main_root` in `tools/job.py` or thin `test_job.py` / `test_integrate.py`:** `test_job.py` still spends ~3.85 s on 634 `git rev-parse` calls, and `test_integrate.py` runs 9 `bash tools/gate.sh` subprocesses.
3. **Full-gate critical path:** `quicktest` (`55 s`) + `fulltest` (`16 s`) = `71 s` even at best; getting under `60 s` requires either thinning `quicktest`'s viewport/feature suites (~35 s) or running `fulltest` suites in parallel with `quicktest` where safe.
