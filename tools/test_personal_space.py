#!/usr/bin/env python3
"""Checks T134's personal spaces (tools/personal_space.py): Log.md and Journal.md in comitatus/04_Personal_Space/<name>/,
dated lines kept whole, the brief's last ten lines of each, nothing written outside a comitatus checkout, and
integrator notes landing in the integrator's Log. Throwaway folders. Summary line: PERSONAL SPACE TESTS: N passed, M failed."""
import datetime
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integrator
import personal_space as ps
import startup

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        print(f"FAIL {name}  {detail}")


org = tempfile.mkdtemp(prefix="space-test-")
os.makedirs(os.path.join(org, "04_Personal_Space"))
root = os.path.join(org, "08_Code_Bases", "Proj")
os.makedirs(root)
subprocess.run(["git", "init", "-q", "-b", "main", root], check=True)
quiet = lambda *a: None

check("a checkout in 08_Code_Bases finds the organization's personal spaces",
      ps.spaces_dir(root) == os.path.join(org, "04_Personal_Space"))
check("a checkout elsewhere has none, and writes nothing",
      ps.spaces_dir(tempfile.mkdtemp()) is None and not ps.add("x-coder", "log", "hi", root=tempfile.mkdtemp(), out=quiet))
check("a name must be a plain lowercase slug", ps.path_of("../etc", "log", root) is None and ps.path_of("Opus", "log", root) is None)

t = datetime.datetime(2026, 11, 26, 19, 0)
for i in range(12):
    ps.add("gemini-coder", "log", f"step {i}", root=root, now=t, out=quiet)
ps.add("gemini-coder", "journal", "I  liked   this one", root=root, now=t, out=quiet)
log = open(os.path.join(org, "04_Personal_Space", "gemini-coder", "Log.md")).read()
check("the log keeps every dated line under its header (nothing cut)",
      log.startswith("# Log\n") and log.count("2026-11-26 19:00 step") == 12, log)
lines = ps.brief_lines("gemini-coder", 10, root)
check("the brief shows the last ten log lines and the journal's, each under its title",
      lines[0].startswith("Log (gemini-coder, last 10 lines") and lines[1] == "  2026-11-26 19:00 step 2"
      and lines[10] == "  2026-11-26 19:00 step 11" and lines[11].startswith("Journal (gemini-coder")
      and lines[12] == "  2026-11-26 19:00 I liked this one", lines)
check("an empty journal says so", ps.brief_lines("new-coder", 10, root)[-1] == "  (nothing yet)")
check("startup's space lines are the same lines", startup.space_lines(root, "gemini-coder") == lines)

integrator.log_note("merged H999", root=root, out=quiet)
ilog = open(os.path.join(org, "04_Personal_Space", startup.INTEGRATOR_SPACE, "Log.md")).read()
check("an integrator note lands in the integrator's Log", "merged H999" in ilog, ilog)
other = tempfile.mkdtemp(prefix="space-test-plain-")
subprocess.run(["git", "init", "-q", "-b", "main", other], check=True)
integrator.log_note("plain repo note", root=other, out=quiet)
check("without a personal space, a note goes to the old journal file in that checkout",
      "plain repo note" in open(integrator.journal_path(other)).read())

print(f"PERSONAL SPACE TESTS: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
