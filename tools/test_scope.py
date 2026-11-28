#!/usr/bin/env python3
# runner: none
"""Classify whether a change needs full app tests or only tools tests (T151).

Prints `tools` or `full` on the first line, followed by the files that decided it
(one per line). Falls back to `full` whenever unsure (no base, detached HEAD,
git failure, or no changed files).
"""
import fnmatch
import os
import subprocess
import sys

EXCLUDED_TOOLS = {
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
    "tools/CHECK_THE_SCRIPTS_PARSE.sh",
    "tools/BUILD_THE_APP.sh",
    "tools/START_A_WORKER.sh",
    "tools/COMPARE_TEST_SUITES.py",
    "tools/CHECK_TYPED_LENGTHS_AGAINST_FREECAD.py",
}

TOOLS_DIRS = (
    ".githooks/",
    "02_Habits/",
    "01_Principles/",
    "03_Past_Decisions/",
    "docs/",
    "viewport/demos/",   # stand-alone scenes nothing in the app loads; the parse check still covers their scripts (H202)
)


def is_tools_file(path):
    """Return True only if path is strictly in the tools/docs allowlist."""
    p = path.replace("\\", "/").removeprefix("./")
    if not p:
        return False
    if p.startswith("tools/"):
        if p in EXCLUDED_TOOLS:
            return False
        base = p[len("tools/"):]
        if "/" not in base and fnmatch.fnmatch(base, "TEST_*.sh"):
            return False
        return True
    if any(p.startswith(d) for d in TOOLS_DIRS):
        return True
    if "/" not in p and (p.endswith(".md") or p == "README.txt"):
        return True
    return False


def _git(root, *args):
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
    )


def _is_worktree(root):
    p_dir = _git(root, "rev-parse", "--git-dir")
    p_common = _git(root, "rev-parse", "--git-common-dir")
    if p_dir.returncode != 0 or p_common.returncode != 0:
        return None
    d = os.path.realpath(os.path.join(root, p_dir.stdout.strip()))
    c = os.path.realpath(os.path.join(root, p_common.stdout.strip()))
    return d != c


def changed_files(root):
    """Return list of changed file paths, or None if git state cannot be determined."""
    wt = _is_worktree(root)
    if wt is None:
        return None
    if wt:
        head_ref = _git(root, "symbolic-ref", "-q", "HEAD")
        if head_ref.returncode != 0:
            return None
        base = _git(root, "merge-base", "HEAD", "main")
        if base.returncode != 0 or not base.stdout.strip():
            return None
        diff = _git(root, "diff", "--name-only", base.stdout.strip())
    else:
        diff = _git(root, "diff", "--name-only", "HEAD")
    if diff.returncode != 0:
        return None
    return [line.strip() for line in diff.stdout.splitlines() if line.strip()]


def classify(root):
    """Return (scope, deciding_files) where scope is 'tools' or 'full'."""
    files = changed_files(root)
    if not files:
        return "full", []
    non_tools = [f for f in files if not is_tools_file(f)]
    if non_tools:
        return "full", non_tools
    return "tools", files


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    root = args[0] if args else os.getcwd()
    scope, files = classify(root)
    print(scope)
    for f in files:
        print(f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
