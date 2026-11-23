### H077 — T103: integrate.py's main() split into named steps

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: either

References: T103, P16, P18 (the gate), P20, P28 (the map pause), T74 (numbering), T91 (results), P26 (follow-ups),
H073 (the BOARD.md settling it had to fit into the order of steps). From a worker's feedback, 2026-11-22.

Touches: tools/integrate.py and tools/test_integrate.py. Nothing else: integrate.py imports job, handoff,
number_ids and others; don't change them.

Request: a pure refactor, no change in behaviour, output or exit codes. main() becomes a short list of named step
functions (for example: check the start, merge, settle conflicts, check Touches, number IDs, record results and
follow-ups, archive the handoff, rebuild the board, the map pause, gate, commit, clean up, push), each taking and
returning one small state object rather than sharing locals. The module docstring (or a comment by main) states
the order and why each constraint holds: settle before staging (staging clears git's unmerged mark), number before
archiving, the map pause before the gate, and any others you find. `--continue` re-enters at the right step using
the same functions, not a copy of them. Checks: test_integrate.py passes unchanged first (run it before you
start, keep the count); then add a check that main()'s steps run in the documented order (for example by
recording step names in a dry run), and a check that `--continue` runs only the steps after the pause. Quick test,
then the gate. End your response with a Result line; leftovers as Follow-up lines; anything for the merge as For
the integrator lines.
