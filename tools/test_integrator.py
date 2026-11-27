#!/usr/bin/env python3
"""Checks tools/integrator.py (the integrator lock, P19). One summary line: LOCK TESTS: N passed, M failed."""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integrator as g

RESULTS = []
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name, ok):
    RESULTS.append(ok)
    if not ok or VERBOSE:
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

check("parse_take_args parses --william, --archive and --push together",
      g.parse_take_args(["--william", "--archive", "H134", "--push"]) == (True, ["H134"], True, True, None))
check("parse_take_args rejects --push without --archive, missing ID, and unknown flags",
      g.parse_take_args(["--push"])[4] is not None
      and g.parse_take_args(["--archive"])[4] is not None
      and g.parse_take_args(["--bogus"])[4] is not None)

# Temp git repo to verify take_and_archive only archives after the lock is granted.
repo = tempfile.mkdtemp(prefix="lock-archive-")
subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
os.makedirs(os.path.join(repo, "docs", "handoff"), exist_ok=True)
open(os.path.join(repo, "docs", "agent-handoff.md"), "w", encoding="utf-8").write(
    "# Handoff\n\n## Open exchanges\n\n"
    "<!-- open list: built from docs/handoff/ by tools/handoff.py; don't edit by hand -->\n\n"
    "- [H134 — State](handoff/H134-integrator-state.md) — status: open; for: the integrator\n\n"
    "<!-- end of open list -->\n\n## Archived\n\n- H133 — Old. Resolved: ok\n"
)
open(os.path.join(repo, "docs", "handoff-archive.md"), "w", encoding="utf-8").write(
    "# Archive\n\n### H133 — Old\n\nResolution: ok\n"
)
note_path = os.path.join(repo, "docs", "handoff", "H134-integrator-state.md")
open(note_path, "w", encoding="utf-8").write(
    "### H134 — State\n\nAuthor: x | Date: 2026-11-24 | Status: open | For: the integrator\n\n"
    "Resolution: read by next session.\n"
)
subprocess.run(["git", "add", "."], cwd=repo, check=True)
subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
repo_lock = g.lock_path(repo)
g.take(repo_lock, "other-session", out=quiet)
check("take_and_archive does not archive if lock is refused",
      not g.take_and_archive(repo_lock, "me", william=False, archives=["H134"], commit=True, root=repo, out=quiet)
      and os.path.exists(note_path))
lines = []
ok = g.take_and_archive(repo_lock, "me", william=True, archives=["H134"], commit=True, root=repo, out=lines.append)
head_msg = subprocess.run(["git", "log", "-1", "--format=%s"], cwd=repo, capture_output=True, text=True).stdout.strip()
check("take_and_archive takes the lock and archives+commits the note in one step",
      ok and g.read(repo_lock)["holder"] == "me" and not os.path.exists(note_path)
      and head_msg == "Archive H134 — State" and any("committed " in l for l in lines))

print(f"LOCK TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
raise SystemExit(0 if all(RESULTS) else 1)   # a failed check fails the run, not only its summary
