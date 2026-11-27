#!/usr/bin/env python3
"""Checks tools/comitatus_commit.py: generated files are committed in the comitatus repo, only those paths, only when
they changed, never pushed, and safely from inside another repo's hook (GIT_* variables ignored).
Throwaway repos. Summary line: COMITATUS COMMIT TESTS: N passed, M failed."""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comitatus_commit as C

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        print(f"FAIL {name}  {detail}")


def sh(cwd, *a):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, env=C.clean_env()).stdout.strip()


org = os.path.realpath(tempfile.mkdtemp(prefix="comitatus-test-"))
sh(org, "git", "init", "-q", "-b", "main"); sh(org, "git", "config", "user.email", "t@example.invalid")
sh(org, "git", "config", "user.name", "t")
os.makedirs(os.path.join(org, "05_Jobs")); os.makedirs(os.path.join(org, "04_Personal_Space"))
open(os.path.join(org, "README.md"), "w").write("x\n"); sh(org, "git", "add", "-A"); sh(org, "git", "commit", "-qm", "base")
open(os.path.join(org, "05_Jobs", "Proj.md"), "w").write("jobs\n")
open(os.path.join(org, "04_Personal_Space", "diary.md"), "w").write("mine\n")

other = os.path.realpath(tempfile.mkdtemp(prefix="comitatus-hook-"))
sh(other, "git", "init", "-q", "-b", "main")
os.environ["GIT_INDEX_FILE"] = os.path.join(other, ".git", "index")      # as inside Napkin's pre-commit hook
os.environ["GIT_DIR"] = os.path.join(other, ".git")
made = C.commit(org, [os.path.join(org, "05_Jobs", "Proj.md")], "05_Jobs: Proj (generated)")
del os.environ["GIT_INDEX_FILE"], os.environ["GIT_DIR"]
check("a generated file is committed in comitatus even from inside another repo's hook",
      made and sh(org, "git", "log", "-1", "--format=%s") == "05_Jobs: Proj (generated)")
check("only the named paths are committed: a personal file stays untracked",
      sh(org, "git", "show", "--name-only", "--format=", "HEAD") == "05_Jobs/Proj.md"
      and "?? 04_Personal_Space/" in sh(org, "git", "status", "--porcelain"), sh(org, "git", "status", "--porcelain"))
check("the other repo's index is untouched", not os.path.exists(os.path.join(other, ".git", "index"))
      or sh(other, "git", "ls-files") == "")
check("nothing changed: no commit", C.commit(org, [os.path.join(org, "05_Jobs", "Proj.md")], "again") is False)
check("a folder that isn't a repo is skipped", C.commit(tempfile.mkdtemp(), ["x"], "m") is False)

# Push tests: bare remote + push=False vs push=True + rejecting remote (fail-open).
remote = os.path.realpath(tempfile.mkdtemp(prefix="comitatus-remote-"))
sh(remote, "git", "init", "--bare", "-q", "-b", "main")
sh(org, "git", "remote", "add", "origin", remote)
sh(org, "git", "push", "-q", "-u", "origin", "main")

open(os.path.join(org, "05_Jobs", "Proj.md"), "w").write("jobs v2\n")
made_nopush = C.commit(org, [os.path.join(org, "05_Jobs", "Proj.md")], "05_Jobs: v2 (generated)")
check("push=False (default) commits locally without pushing",
      made_nopush and sh(org, "git", "rev-parse", "HEAD") != sh(remote, "git", "rev-parse", "main"))

open(os.path.join(org, "05_Jobs", "Proj.md"), "w").write("jobs v3\n")
made_push = C.commit(org, [os.path.join(org, "05_Jobs", "Proj.md")], "05_Jobs: v3 (generated)", push=True)
check("push=True pushes the commit to the remote",
      made_push and sh(org, "git", "rev-parse", "HEAD") == sh(remote, "git", "rev-parse", "main"))

hook = os.path.join(remote, "hooks", "pre-receive")
open(hook, "w").write("#!/bin/sh\nexit 1\n")
os.chmod(hook, 0o755)
open(os.path.join(org, "05_Jobs", "Proj.md"), "w").write("jobs v4\n")
msgs = []
made_rejected = C.commit(org, [os.path.join(org, "05_Jobs", "Proj.md")], "05_Jobs: v4 (generated)",
                         out=msgs.append, push=True)
check("push=True is fail-open when the remote rejects (commit stays local, returns True)",
      made_rejected and sh(org, "git", "log", "-1", "--format=%s") == "05_Jobs: v4 (generated)"
      and sh(org, "git", "rev-parse", "HEAD") != sh(remote, "git", "rev-parse", "main")
      and any("comitatus push skipped:" in m for m in msgs),
      (made_rejected, msgs))

print(f"COMITATUS COMMIT TESTS: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
