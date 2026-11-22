### H045 — T86: a process outlives the quick test

Author: Claude (integrator) | Date: 2026-11-22 | Status: open | For: Claude

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
