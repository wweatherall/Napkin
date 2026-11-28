#!/usr/bin/env python3
"""Unit tests for tools/test_scope.py (T151).
Summary line: TEST SCOPE TESTS: N passed, M failed."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_scope

RESULTS = []
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    if not ok or VERBOSE:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {detail}"))


def run_cli(cwd):
    p = subprocess.run(
        [sys.executable, os.path.join(HERE, "test_scope.py")],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    lines = [l for l in p.stdout.splitlines() if l.strip()]
    return p.returncode, lines[0] if lines else "", lines[1:]


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


# 1. File classification: every `full` entry must return False (full).
FULL_FILES = [
    # App and data folders
    "viewport/x.gd",
    "worker/x.py",
    "tests/x.txt",
    "models/x.FCStd",
    "materials/x.json",
    "examples/x.FCStd",
    "sim/x.py",
    "dist/x.app",
    # Top-level app scripts and unknown files/folders
    "Start Napkin.command",
    "common.sh",
    "newfolder/x.py",
    "unknown_top_file.py",
    # Test runners and app tools
    "tools/gate.sh",
    "tools/quicktest.sh",
    "tools/fulltest.sh",
    "tools/featuretest.sh",
    "tools/parsecheck.sh",
    "tools/build_app.sh",
    "tools/start_worker.sh",
    "tools/compare_suites.py",
    "tools/length_cases.py",
    "tools/test_scope.py",
    # Named runner/app scripts
    "tools/TEST_BEFORE_MERGING.sh",
    "tools/TEST_WITHOUT_THE_APP.sh",
    "tools/TEST_YOUR_CODE_FAST.sh",
    "tools/TEST_YOUR_CODE_THOROUGHLY.sh",
    "tools/TEST_CUSTOM.sh",
    "tools/CHECK_THE_SCRIPTS_PARSE.sh",
    "tools/BUILD_THE_APP.sh",
    "tools/START_A_WORKER.sh",
    "tools/COMPARE_TEST_SUITES.py",
    "tools/CHECK_TYPED_LENGTHS_AGAINST_FREECAD.py",
]

for path in FULL_FILES:
    check(f"full file: {path}", not test_scope.is_tools_file(path), f"classified as tools: {path}")

TOOLS_FILES = [
    "tools/job.py",
    "tools/test_job.py",
    "tools/GET_A_JOB.py",
    ".githooks/pre-commit",
    "02_Habits/REMEMBER_WHO_YOU_ARE.py",
    "01_Principles/P01.md",
    "03_Past_Decisions/work/T151.md",
    "docs/integrator.md",
    "BOARD.md",
    "CLAUDE.md",
    "AGENTS.md",
    "GEMINI.md",
    "ARCHITECTURE.md",
    "README.txt",
]

for path in TOOLS_FILES:
    check(f"tools file: {path}", test_scope.is_tools_file(path), f"classified as full: {path}")


# 2. Temp git repo: staged merge in main, worktree branch, widening, detached HEAD, no base, non-git.
with tempfile.TemporaryDirectory(prefix="test-scope-", dir=os.environ.get("TESTDIR")) as tmp:
    base = Path(tmp).resolve()
    main = base / "main"
    wt = base / "wt"
    nongit = base / "nongit"
    main.mkdir()
    nongit.mkdir()

    # Non-git / broken-git directory -> full (write corrupt .git so parent repo isn't inherited)
    (nongit / ".git").write_text("not a git repo\n")
    rc, scope, files = run_cli(nongit)
    check("git failing / non-git -> full", rc == 0 and scope == "full" and files == [], (rc, scope, files))

    git(main, "init", "-q", "-b", "main")
    (main / "tools").mkdir()
    (main / "viewport").mkdir()
    (main / "worker").mkdir()
    (main / "docs").mkdir()
    (main / "tools" / "job.py").write_text("# v1\n")
    (main / "viewport" / "x.gd").write_text("# v1\n")
    (main / "worker" / "foo.py").write_text("# v1\n")
    (main / "docs" / "guide.md").write_text("# v1\n")
    git(main, "add", ".")
    git(main, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "init")

    # Clean main -> no changed files -> full
    rc, scope, files = run_cli(main)
    check("main clean (no changed files) -> full", rc == 0 and scope == "full" and files == [], (rc, scope, files))

    # Main staged change to tools/job.py only -> tools
    (main / "tools" / "job.py").write_text("# v2\n")
    git(main, "add", "tools/job.py")
    rc, scope, files = run_cli(main)
    check("main staged tools/job.py only -> tools", rc == 0 and scope == "tools" and files == ["tools/job.py"], (rc, scope, files))

    # Main staged change to viewport/x.gd -> full
    (main / "viewport" / "x.gd").write_text("# v2\n")
    git(main, "add", "viewport/x.gd")
    rc, scope, files = run_cli(main)
    check("main staged viewport/x.gd -> full", rc == 0 and scope == "full" and files == ["viewport/x.gd"], (rc, scope, files))

    # Reset main clean before worktree tests
    git(main, "reset", "-q", "--hard", "HEAD")

    # Linked worktree on a job branch
    git(main, "worktree", "add", "-q", "-b", "gemini/h999-test", str(wt), "main")
    (wt / "tools" / "job.py").write_text("# wt v1\n")
    git(wt, "add", "tools/job.py")
    git(wt, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "tools commit")
    (wt / "docs" / "guide.md").write_text("# wt doc\n")
    rc, scope, files = run_cli(wt)
    check(
        "worktree committed tools + uncommitted docs -> tools",
        rc == 0 and scope == "tools" and set(files) == {"tools/job.py", "docs/guide.md"},
        (rc, scope, files),
    )

    # Uncommitted app change widens scope to full
    (wt / "worker" / "foo.py").write_text("# wt worker\n")
    rc, scope, files = run_cli(wt)
    check(
        "worktree uncommitted worker/foo.py widens -> full",
        rc == 0 and scope == "full" and files == ["worker/foo.py"],
        (rc, scope, files),
    )
    git(wt, "checkout", "--", "worker/foo.py")

    # Detached HEAD in worktree -> full
    git(wt, "checkout", "-q", "--detach", "HEAD")
    rc, scope, files = run_cli(wt)
    check("worktree detached HEAD -> full", rc == 0 and scope == "full" and files == [], (rc, scope, files))

    # No main branch -> full
    git(wt, "checkout", "-q", "gemini/h999-test")
    git(main, "branch", "-M", "main", "other")
    rc, scope, files = run_cli(wt)
    check("worktree missing main base -> full", rc == 0 and scope == "full" and files == [], (rc, scope, files))


print(f"TEST SCOPE TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
raise SystemExit(0 if all(RESULTS) else 1)
