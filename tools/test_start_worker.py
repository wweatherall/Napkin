#!/usr/bin/env python3
"""tools/start_worker.sh (F005): the command it would run in the new Terminal window, checked with DRY_RUN=1."""
import os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    passed, failed = passed + bool(ok), failed + (not ok)
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))


def dry(*args):
    env = dict(os.environ, DRY_RUN="1")
    return subprocess.run([os.path.join(HERE, "start_worker.sh"), *args], env=env, capture_output=True, text=True)


r = dry("worker-a")
check("it starts claude in the repository with Remote Control, named, told to check the board",
      r.returncode == 0 and r.stdout.strip() == f"cd {REPO} && claude --remote-control worker-a Check\\ the\\ board",
      r.stdout + r.stderr)
r = dry()
check("without a name it makes one (worker-HHMM)", r.returncode == 0 and "--remote-control worker-" in r.stdout, r.stdout)
r = dry("a name; rm -rf x")
check("a name can't run anything (it's quoted)", r.returncode == 0 and r"a\ name\;\ rm\ -rf\ x" in r.stdout, r.stdout)
print(f"START WORKER TESTS: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
