### H045 — T86: a process outlives the quick test

Author: Claude (integrator) | Date: 2026-11-22 | Status: answered | For: Claude

References: T86, P07, P18 (the gate captures the quick test's output); found by the H043 worker
(docs/handoff-archive.md, ### H043, "Still open" 2 and 3); T47 (test workers on their own ports), T80.

Touches: tools/quicktest.sh, viewport/tests/quick_runner.gd, viewport/tests/quick/worker.gd,
viewport/tests/quick/linked.gd, viewport/tests/harness.gd. Read-only on viewport/main.gd (the worker process code):
if the cause is there, say so in chat before changing it.

Request: capturing the quick test's output (`out=$(tools/quicktest.sh)`) sometimes never returns, as if a process
from the run outlives it and keeps stdout open; the likely one is the worker the `[worker]` section restarts. Find
what's left running after a quick test (`pgrep -fl freecadcmd` before and after), make every test worker stop when
its window does, and make quicktest.sh wait for or stop what it started. Also: linked.gd calls `m._menu("detach")`
directly; use `harness._menu` (it waits out the menu's 150 ms repeat filter, T85). Done when 10 captured runs in a
row return, no freecadcmd from a test run is left afterwards, and `tools/gate.sh` passes.

**Response — Claude, 2026-11-22.** Branch `claude/h045-leftover-process`, commit 2f7c9ac. Cause: not a test worker.
`pgrep -fl freecadcmd` before and after a quick test: none left. What outlived the run was the watchdog's
`sleep 120` (tools/quicktest.sh): line 29 killed the watchdog subshell, but its `sleep` child lived on with the
script's stdout, so anything capturing the output waited out the 120 s (~128 s a run). Fix: the watchdog runs its
sleep in the background, kills it on TERM, and its output goes to /dev/null (it writes to stopped.log anyway); the
120 s stop still works. No change to main.gd, worker.gd or quick_runner.gd was needed. linked.gd's
`m._menu("detach")` now goes through `harness._menu`.
Verified: 10 captured runs in a row (`out=$(tools/quicktest.sh)`) all returned, 17–38 s, 174/174 each; 3 more with
each leftover's cwd checked: nothing left. During runs 4–8 a `sleep 120` and a `freecadcmd worker/test_scenario.py`
from another checkout appeared (most likely Codex's H041 worktree, whose quicktest.sh lacks this fix); they cleared
on their own. `tools/gate.sh`: GATE PASS in 37 s. Architecture sections changed: none.
Still open: the intermittent `[worker] a new worker took over` failure (H043's note 1) didn't appear in these 13
runs; no fix attempted.
