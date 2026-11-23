### H081 — T106: the test scripts show progress and keep their output in the job's scratch/

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: either

References: T106, P25 (scratch/ in the worktree), P40 (hung tests are the worker's). From a Codex worker's
feedback, 2026-11-22.

Touches: tools/gate.sh, tools/quicktest.sh, tools/fulltest.sh, tools/featuretest.sh, tools/parsecheck.sh, and
tools/test_featuretest.py (or a new tools/test_scripts.py) for the checks. Not tools/job.py (another job has it)
or the worker/ and viewport/ tests themselves: if one of them writes outside the folder it is given, list it as
a Follow-up line.

Request: (1) Progress: gate.sh, quicktest.sh and fulltest.sh print one line as each stage starts and one as it
ends, with its time ("gate: quick test started", "gate: quick test passed in 18 s", ...), unbuffered, so a
watcher can tell a slow run from a hung one; their final summary lines keep their present form (integrate.py
and job.py read them: check what they parse and keep it working). (2) Scratch: when a script runs in a job's
worktree (not the main checkout), its temporary output (the mktemp folders: shopsketch-gate, -quick, -full,
-feature, -parse) goes under that worktree's scratch/; elsewhere as today. Today some scripts use
`mktemp -d -t` and one `${TMPDIR:-/tmp}`: make them consistent and honour TMPDIR when it is set. Find out why
output landed in the system temporary folder despite TMPDIR (a worker saw it) and say what it was. Checks: the
progress lines appear in order for a stubbed quick and full test; in a worktree the folders go under scratch/;
in the main checkout and with TMPDIR set they go where they do today; the summary lines unchanged. Quick test,
then the gate. End your response with a Result line; leftovers as Follow-up lines; anything for the merge as For
the integrator lines.
