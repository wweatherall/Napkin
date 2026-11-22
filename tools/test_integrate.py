#!/usr/bin/env python3
"""Checks tools/integrate.py and tools/gate.sh on throwaway repositories (P18, P20). Summary line:
INTEGRATE TESTS: N passed, M failed."""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import integrate
import integrator

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def repo():
    root = tempfile.mkdtemp(prefix="integrate-test-")
    sh(root, "git", "init", "-q", "-b", "main")
    sh(root, "git", "config", "user.email", "t@example.invalid"); sh(root, "git", "config", "user.name", "t")
    os.makedirs(os.path.join(root, "docs", "handoff"))
    open(os.path.join(root, "docs", "decision-log.md"), "w").write("# Log\n\n## Work list\n\n| # | Item | Status |\n|---|---|---|\n| T1 | a | Open |\n")
    open(os.path.join(root, "docs", "agent-handoff.md"), "w").write("# Handoff\n\n## Open exchanges\n\n<!-- open list: built from docs/handoff/ by tools/handoff.py; don't edit by hand -->\n\n(none open)\n\n<!-- end of open list -->\n\n## Archived\n")
    open(os.path.join(root, "docs", "handoff-archive.md"), "w").write("# Archive\n")
    open(os.path.join(root, "notes.md"), "w").write("one\n")
    sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "base")
    return root


# 1. A conflict in a file integrate.py doesn't settle must stop it, before anything is staged.
root = repo()
sh(root, "git", "checkout", "-qb", "agent/x")
open(os.path.join(root, "notes.md"), "w").write("agent\n"); sh(root, "git", "commit", "-qam", "agent edit")
sh(root, "git", "checkout", "-q", "main")
open(os.path.join(root, "notes.md"), "w").write("main\n"); sh(root, "git", "commit", "-qam", "main edit")
integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)
out = io.StringIO()
cwd = os.getcwd(); os.chdir(root)
try:
    with contextlib.redirect_stdout(out):
        rc = integrate.main(["agent/x", "--as", "tester", "--no-gate"])
finally:
    os.chdir(cwd)
check("a conflict in another file stops the merge", rc == 1 and "notes.md" in out.getvalue(), out.getvalue())
check("it is still unmerged afterwards (nothing staged over it)",
      "notes.md" in sh(root, "git", "diff", "--name-only", "--diff-filter=U").stdout)
check("and nothing was committed", sh(root, "git", "log", "--oneline", "-1").stdout.split()[1:3] == ["main", "edit"])
shutil.rmtree(root)

# 2. has_markers finds leftover conflict markers.
tmp = tempfile.mkdtemp(prefix="markers-")
p = os.path.join(tmp, "f.md"); open(p, "w").write("a\n<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> b\n")
q = os.path.join(tmp, "g.md"); open(q, "w").write("a line with ======= in it\n")
check("conflict markers are found", integrate.has_markers(p))
check("an ordinary ======= line isn't a marker", not integrate.has_markers(q))
shutil.rmtree(tmp)


# 3. The gate: a known UI failure never excuses a feature-test failure.
def gate(quick_out, quick_rc, known):
    root = tempfile.mkdtemp(prefix="gate-test-")
    sh(root, "git", "init", "-q")
    os.makedirs(os.path.join(root, "tools")); os.makedirs(os.path.join(root, "tests"))
    shutil.copy(os.path.join(HERE, "gate.sh"), os.path.join(root, "tools", "gate.sh"))
    open(os.path.join(root, "tools", "quicktest.sh"), "w").write(f"#!/bin/bash\ncat <<'X'\n{quick_out}\nX\nexit {quick_rc}\n")
    open(os.path.join(root, "tools", "fulltest.sh"), "w").write("#!/bin/bash\nexit 0\n")
    for f in ("quicktest.sh", "fulltest.sh"):
        os.chmod(os.path.join(root, "tools", f), 0o755)
    open(os.path.join(root, "tests", "known_failures.txt"), "w").write(known)
    r = sh(root, "bash", "tools/gate.sh")
    shutil.rmtree(root)
    return r.returncode, r.stdout


KNOWN = "[hide] View > Hidden geometry shows it ghosted  # T85\n"
HIDE = "QUICK FAIL [hide] View > Hidden geometry shows it ghosted  <Object#null>"
OK_FEAT = "features: NATIVE TESTS: 83 passed, 0 failed | SCENARIO TESTS: 170 passed, 0 failed | viewport: QUICK 152 passed, 1 failed in 11 s"
BAD_FEAT = "features: NATIVE TESTS: 83 passed, 0 failed | SCENARIO TESTS: 169 passed, 1 failed | viewport: QUICK 152 passed, 1 failed in 11 s"
rc, out = gate(HIDE + "\n" + OK_FEAT, 1, KNOWN)
check("a listed UI failure alone passes the gate", rc == 0 and "GATE PASS" in out, out)
rc, out = gate(HIDE + "\n" + BAD_FEAT, 1, KNOWN)
check("a listed UI failure plus a feature-test failure fails the gate (Codex's case)", rc == 1 and "SCENARIO TESTS" in out, out)
rc, out = gate(HIDE + "\n" + OK_FEAT, 1, "")
check("an unlisted UI failure fails the gate", rc == 1 and "NEW FAILURE" in out, out)
rc, out = gate("QUICK 153 passed, 0 failed", 0, "")
check("no feature-test summary at all fails the gate", rc == 1 and "no feature-test summary" in out, out)
check("the real known-failures list holds only failures with an open Work list item",
      all("# T" in l for l in open(os.path.join(HERE, "..", "tests", "known_failures.txt")) if l.strip() and not l.startswith("#")))


# 4. The protocol version: a branch's bump goes on top of main's (A35), and files outside the Touches list are flagged.
def write(root, rel, text):
    os.makedirs(os.path.dirname(os.path.join(root, rel)) or root, exist_ok=True)
    open(os.path.join(root, rel), "w").write(text)


root = repo()
write(root, "worker/serve.py", "PROTOCOL_VERSION = 2\n")
write(root, "viewport/main.gd", "const PROTOCOL_VERSION := 2\n")
write(root, "docs/protocol.md", "The wire protocol's own version is **2** (currently 2).\n")
sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "v2")
sh(root, "git", "checkout", "-qb", "agent/y")
write(root, "worker/serve.py", "PROTOCOL_VERSION = 3\n")
write(root, "viewport/main.gd", "const PROTOCOL_VERSION := 3\n")
write(root, "docs/protocol.md", "The wire protocol's own version is **3** (currently 3).\n")
write(root, "worker/new_op.py", "x = 1\n")
write(root, "viewport/other.gd", "# not in the job\n")
write(root, "docs/handoff/H050-y.md", "### H050 — y\n\nAuthor: Claude | Date: 2026-11-22 | Status: answered\n\n"
      "Touches: worker/serve.py, viewport/main.gd, worker/new_op.py, docs/protocol.md.\n")
sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "branch bumps to 3")
sh(root, "git", "checkout", "-q", "main")
write(root, "worker/serve.py", "PROTOCOL_VERSION = 3\n"); write(root, "viewport/main.gd", "const PROTOCOL_VERSION := 3\n")
write(root, "docs/protocol.md", "The wire protocol's own version is **3** (currently 3).\n")
sh(root, "git", "commit", "-qam", "main bumps to 3")
integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)
out = io.StringIO(); cwd = os.getcwd(); os.chdir(root)
try:
    with contextlib.redirect_stdout(out):
        rc = integrate.main(["agent/y", "--as", "tester", "--no-gate"])
finally:
    os.chdir(cwd)
said = out.getvalue()
check("both bumped 2 -> 3: the branch's lands as 4, both constants and the doc",
      open(os.path.join(root, "worker/serve.py")).read() == "PROTOCOL_VERSION = 4\n"
      and open(os.path.join(root, "viewport/main.gd")).read() == "const PROTOCOL_VERSION := 4\n"
      and "**4**" in open(os.path.join(root, "docs/protocol.md")).read() and "currently 4" in open(os.path.join(root, "docs/protocol.md")).read(), said)
check("it says so", "renumbered" in said or "is 4 on main" in said, said)
check("a file the job doesn't list is flagged, and only that one",
      "OUTSIDE ITS TOUCHES LIST: viewport/other.gd" in said and "new_op.py (" not in said.split("OUTSIDE")[-1], said)
check("the merge went in, and its message records both", rc == 0 and "renumbered to 4" in sh(root, "git", "log", "-1", "--format=%B").stdout
      and "viewport/other.gd" in sh(root, "git", "log", "-1", "--format=%B").stdout, said)
shutil.rmtree(root)

print(f"INTEGRATE TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
