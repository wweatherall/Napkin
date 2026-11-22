#!/usr/bin/env python3
"""Checks tools/integrator.py (the integrator lock, P19). One summary line: LOCK TESTS: N passed, M failed."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integrator as g

RESULTS = []


def check(name, ok):
    RESULTS.append(ok)
    print(("PASS " if ok else "FAIL ") + name)


quiet = lambda *a: None
path = os.path.join(tempfile.mkdtemp(prefix="lock-"), "shopsketch-integrator.lock")
check("a free lock can be taken", g.take(path, "fretchup-73", out=quiet) and g.read(path)["holder"] == "fretchup-73")
check("the holder can take it again (a cleared session keeps its name)", g.take(path, "fretchup-73", out=quiet))
said = []
check("another session is refused (the e1 case)", not g.take(path, "fretchup-e1", out=said.append) and "William" in said[0])
check("only the holder can mark it in use", g.touch(path, "fretchup-73", out=quiet) and not g.touch(path, "fretchup-e1", out=quiet))
check("William can hand it over", g.take(path, "fretchup-e1", william=True, out=quiet) and g.read(path)["holder"] == "fretchup-e1")
check("the hand-over is logged", any("from fretchup-73 to fretchup-e1" in l for l in g.read(path)["log"]))
check("only the holder can release it", not g.release(path, "fretchup-73", out=quiet) and g.release(path, "fretchup-e1", out=quiet))
check("released means free", g.read(path) is None and "nobody" in g.status_line(path))
check("the lock lives in git's common folder, shared by every worktree",
      g.lock_path().endswith(os.path.join(".git", "shopsketch-integrator.lock")))
print(f"LOCK TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
