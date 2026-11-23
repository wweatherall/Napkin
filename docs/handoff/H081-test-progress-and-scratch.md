### H081 — T106: the test scripts show progress and keep their output in the job's scratch/

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: either

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

### Response — Codex, 2026-11-22

Branch `codex/h081-test-progress-and-scratch`, implementation `8c4ab15`. The gate, quick test and full test report stage starts and timed outcomes, including concurrent feature and viewport runs. The gate forwards child progress live and keeps complete quick and full logs. The existing final summary formats still pass their consumer checks.

Reproduced the misplaced output on this Mac. With an exported TMPDIR pointing at the job's scratch folder, `/usr/bin/mktemp -u -t shopsketch-probe` picked Darwin's per-user temporary folder. Four scripts used that form. All five now pass an explicit path. Linked worktrees use scratch and honour a TMPDIR inside it. The main checkout honours TMPDIR and keeps each script's previous default when it is unset.

Verified 43/43 harness checks, including live output during stubbed runs, all five folder destinations, and final summaries. The quick test passed all features and 240 viewport checks. The gate passed in 83 s with zero known failures. Logs are in `scratch/shopsketch-gate.v8vnKT`. No decision IDs or open questions.

Architecture: Only the test harness and its fixture changed.
Follow-up: worker/test_length_protocol.py creates its temporary folder through TMPDIR instead of its assigned TESTDIR. In a job it now lands in scratch and is removed on exit.
Follow-up: integrate.py and job.py test capture the scripts' output until exit. Live progress is visible when running the scripts directly or through job.py run.
Result: 8c4ab15; 43/43 harness checks, quick 240/240, gate passed in 83 s; the test scripts report live stage timings and keep job output in the worktree's scratch folder.
