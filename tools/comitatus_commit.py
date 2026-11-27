#!/usr/bin/env python3
"""Commit generated files in the comitatus repo (William, 2026-11-26: "commit the generated files automatically").

commit(org, paths, message) stages and commits only `paths` (05_Jobs/<code base>.md, 06_To-dos/, 01_Principles'
ranking files) in the comitatus repo, and only when they changed; anything else in that repo (personal spaces,
William's own edits) is left alone. It never pushes. It is called from inside Napkin's own git hook, where git sets
GIT_DIR, GIT_INDEX_FILE and friends for Napkin: those are removed first, or the commit would land in Napkin's index.
Fail-open: a problem here never stops the caller."""
import os
import subprocess

def clean_env():
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(org, *args):
    return subprocess.run(["git", "-C", org, *args], capture_output=True, text=True, env=clean_env())


def commit(org, paths, message, out=lambda *a: None):
    """True if a commit was made."""
    try:
        if not org or git(org, "rev-parse", "--show-toplevel").stdout.strip() != os.path.realpath(org):
            return False
        rel = [os.path.relpath(p, org) if os.path.isabs(p) else p for p in paths]
        rel = [p for p in rel if os.path.exists(os.path.join(org, p)) or git(org, "ls-files", "--", p).stdout.strip()]
        if not rel:
            return False
        git(org, "add", "-A", "--", *rel)
        if not git(org, "diff", "--cached", "--name-only", "--", *rel).stdout.strip():
            return False
        r = git(org, "commit", "-q", "-m", message, "--", *rel)
        if r.returncode != 0:
            out("comitatus commit refused: " + (r.stdout + r.stderr).strip()[:200])
            return False
        out("committed in comitatus: " + message)
        return True
    except Exception as e:        # fail-open
        out(f"comitatus commit skipped: {e}")
        return False
