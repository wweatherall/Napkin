### H088 — integrate.py and job.py show the tests' progress as it happens

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: gemini

References: T106 / H081 (the test scripts print a line as each stage starts and ends), P40 (a slow run must be
told from a hung one), the H081 follow-up in docs/follow-ups.md ("integrate.py and job.py test capture the
scripts' output until exit"; clear that line in your last commit).

Touches: tools/integrate.py (`run_gate`), tools/job.py (`run_quick`), tools/test_integrate.py, tools/test_job.py.
Not the test scripts themselves (gate.sh, quicktest.sh, fulltest.sh) or ARCHITECTURE.md.

Today: integrate.py `run_gate` runs tools/gate.sh with `subprocess.run(..., capture_output=True)`, then prints
only the last line (the verdict) and, on a failure, the last 2000 characters. job.py `run_quick` runs
`QUICKTEST` the same way and keeps the last line. So nothing shows until the run ends (80 s for the gate).

Request: run them with `subprocess.Popen` (stdout piped, stderr merged into it, text, line-buffered) and, as each
line arrives, print it at once when it is a progress line: it starts with `gate: `, `quick: ` or `full: ` (the
forms H081's `run_stage` prints: "<label> started", "<label> passed in N s", "<label> failed in N s"); keep
every line. When it ends, everything after stays as today: `run_gate` says the verdict (the last line), and on
a failure prints the last 2000 characters of the whole output; `run_quick` returns the same `(ok, last line)`.
Print with flush, so a caller reading this script's output sees each line as it comes. job.py's `QUICKTEST` stays
a list its tests can replace.

Checks: in test_integrate.py and test_job.py, a stub in place of the gate / quick test (a small shell script
that prints "quick: parse started", sleeps 1 s, prints "quick: parse passed in 1 s", then a verdict line):
the first progress line reaches the caller before the stub ends (read the output while it runs, as
tools/test_featuretest.py's "gate stages arrive live and in order" check does); lines that aren't progress
lines are not printed live; the verdict and the failure tail are as before (a failing stub); `run_quick`'s
return value is unchanged.

Reading path: integrate.py `run_gate` (and the `say` it uses), job.py `run_quick` and `test` (who reads its
result), then tools/test_featuretest.py around its live-arrival check (how H081 tested the same thing for the
shell scripts). Who owns what: the shell scripts own what they print; these two only relay it.

Run `python3 tools/test_integrate.py` and `python3 tools/test_job.py` while building, then
`python3 tools/job.py test`. End your response with a Result line; leftovers as Follow-up lines; anything for the
merge as For the integrator lines.
