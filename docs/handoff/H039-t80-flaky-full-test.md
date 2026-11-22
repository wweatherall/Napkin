### H039 — T80: make the full test reliable (suites that sometimes differ, a startup crash)

Author: Claude (integrator) | Date: 2026-11-22 | Status: open | For: Claude

References: T80, P07, P13 (the full test is the merge gate), T45 (an earlier timing race fixed the same way:
watch for the state, don't assume how fast it comes); the H036 worker's notes in docs/handoff-archive.md (### H036).

Touches: viewport/tests/suites/*.gd, viewport/tests/harness.gd, tools/fulltest.sh, tools/compare_suites.py,
tests/reference/ only if a recording itself is wrong (say why). Not viewport/tools/* (H040 owns them) and not
viewport/main.gd unless a test hook there is the cause (say so first).

Request: on main, `tools/fulltest.sh` fails now and then: one recorded suite differs, a different one each run
(movetest, holetest, infertest, mirrortest seen), and once Godot crashed at startup (signal 11 in macOS
file-open handling, before our scripts ran). Reproduce first: run it 10 times and count, and note the load (other
agents run tests at the same time). Find each cause; make the suites wait on state (a confirmed mesh, a reply)
rather than on time; retry a run that crashes before any script starts, and say so in the output. Done when 10
runs in a row pass, also with a quick test running beside them. Report the before/after counts.
