#!/usr/bin/env python3
"""Checks integrate.py's merge bookkeeping (T91): a handoff response's Result line becomes the Work list result,
in its own commit, shown before the push. Throwaway repositories. Summary line: BOOKKEEPING TESTS: N passed, M failed."""
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
LOG = "docs/decision-log.md"
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    if not ok or VERBOSE:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def write(root, rel, text):
    os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
    open(os.path.join(root, rel), "w").write(text)


def read(root, rel):
    return open(os.path.join(root, rel)).read()


ENTRY = ("### H060 — T7: a tool\n\nAuthor: Claude | Date: 2026-11-22 | Status: {status} | For: Claude\n\n"
         "Touches: tools/x.py.\n\nRequest: give a \"Result: <commit>; <tests>; <what changed>\" line.\n")


def repo():
    root = tempfile.mkdtemp(prefix="bookkeeping-test-")
    sh(root, "git", "init", "-q", "-b", "main")
    sh(root, "git", "config", "user.email", "t@example.invalid"); sh(root, "git", "config", "user.name", "t")
    write(root, LOG, "# Log\n\n## Work list\n\n| # | Item | Status | Covers | Notes |\n|---|---|---|---|---|\n"
          "| T6 | other | Open | - | |\n| T7 | a tool | Open | P20 | From a review. |\n")
    write(root, "docs/agent-handoff.md", "# Handoff\n\n## Open exchanges\n\n<!-- open list: built from docs/handoff/ by "
          "tools/handoff.py; don't edit by hand -->\n\n(none open)\n\n<!-- end of open list -->\n\n## Archived\n")
    write(root, "docs/handoff-archive.md", "# Archive\n")
    write(root, "docs/handoff/H060-tool.md", ENTRY.format(status="open"))
    write(root, "tools/x.py", "x = 1\n")
    sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "base")
    sh(root, "git", "checkout", "-qb", "claude/h060-tool")
    write(root, "tools/x.py", "x = 2\n")
    sh(root, "git", "commit", "-qam", "H060 (T7): the tool")
    return root


def respond(root, response):
    write(root, "docs/handoff/H060-tool.md", ENTRY.format(status="answered") + response)
    sh(root, "git", "commit", "-qam", "H060: response")
    sh(root, "git", "checkout", "-q", "main")
    integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)


def run(root, *args):
    out = io.StringIO(); cwd = os.getcwd(); os.chdir(root)
    try:
        with contextlib.redirect_stdout(out):
            rc = integrate.main(["claude/h060-tool", "--as", "tester", "--no-gate"] + list(args))
    finally:
        os.chdir(cwd)
    return rc, out.getvalue()


def row(root, tid):
    return next(l for l in read(root, LOG).split("\n") if l.startswith(f"| {tid} "))


# 1. The Result line parsed: the newest one, commit shortened; an example in quotes mid-line isn't one.
text = "Result: <commit>; ...\n\nResponse 1\nResult: 1111111; old; old\n\nResponse 2\n- Result: abcdef0123456; tests 3/3; did it\n"
check("the newest Result line is the one read", integrate.result_line(text) == ("abcdef0", "tests 3/3; did it"),
      integrate.result_line(text))
check("no Result line: None", integrate.result_line(ENTRY.format(status="answered")) is None)
check("the item: the --status one the heading names, else the only one, else the heading's",
      integrate.entry_item(ENTRY, ["T3", "T7"]) == "T7" and integrate.entry_item(ENTRY, ["T3"]) == "T3"
      and integrate.entry_item(ENTRY, []) == "T7")

# 2. A merge with a Result line: the row gets it, in its own commit after the merge, and --push stops before pushing.
root = repo()
bare = tempfile.mkdtemp(prefix="bookkeeping-remote-"); sh(bare, "git", "init", "-q", "--bare")
sh(root, "git", "remote", "add", "origin", bare); sh(root, "git", "push", "-q", "origin", "main")
respond(root, "\nResponse (Claude, 2026-11-22): done.\n\nResult: 0123abc; tools/test_x.py 4/4, quick test passed; "
        "tools/x.py sets x | y to 2\n")
rc, said = run(root, "--status", "T7=In progress", "--push")
merge = sh(root, "git", "rev-parse", "--short", "HEAD~1").stdout.strip()
r = row(root, "T7")
check("the row gets the result, with the merge commit", rc == 0 and r.endswith(
      f"From a review. Result (0123abc, merged {merge}): tools/test_x.py 4/4, quick test passed; tools/x.py sets x / y to 2. |"),
      r + "\n" + said)
check("other rows are untouched", row(root, "T6") == "| T6 | other | Open | - | |")
check("in its own commit on top of the merge", sh(root, "git", "log", "-1", "--format=%s").stdout.startswith("T7 (H060): Work list result")
      and sh(root, "git", "log", "-1", "--format=%P").stdout.strip() == sh(root, "git", "rev-parse", "HEAD~1").stdout.strip()
      and len(sh(root, "git", "log", "-1", "--format=%P", "HEAD~1").stdout.split()) == 2, said)
check("the change is shown", f"T7 (H060): Result (0123abc, merged {merge}):" in said and "{+" not in said, said)
check("--push without --yes stops before the push", "git push origin main" in said
      and sh(bare, "git", "rev-parse", "main").stdout.strip() == sh(root, "git", "rev-parse", "HEAD~2").stdout.strip(), said)

# 3. Recorded already: not added twice.
_, what = integrate.record_result(root, "T7", "0123abc", "again", "fffffff")
check("an already-recorded result isn't added twice", row(root, "T7") == r and "already" in what, what)
_, what = integrate.record_result(root, "T99", "0123abc", "x", "fffffff")
check("an item the log hasn't got is said, not guessed", "not in the decision log" in what, what)
shutil.rmtree(root); shutil.rmtree(bare)

# 4. Done moves the row to the archive: the result goes with it.
root = repo()
write(root, "docs/decision-archive.md", "# Archive\n\n## Done work\n\n| # | Item | Status | Covers | Notes |\n|---|---|---|---|---|\n")
sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "archive")
respond(root, "\nResult: 0123abc; 4/4; the tool.\n")
rc, said = run(root, "--status", "T7=Done")
arch = read(root, "docs/decision-archive.md")
check("a Done item's result lands in the archive, where its row went",
      rc == 0 and "| T7 " in arch and "Result (0123abc, merged" in arch and "| T7 " not in read(root, LOG), said + arch)
shutil.rmtree(root)

# 5. No Result line: nothing drafted, it says so, and --push pushes as before.
root = repo()
bare = tempfile.mkdtemp(prefix="bookkeeping-remote-"); sh(bare, "git", "init", "-q", "--bare")
sh(root, "git", "remote", "add", "origin", bare); sh(root, "git", "push", "-q", "origin", "main")
respond(root, "\nResponse: done, commit 0123abc, tests pass.\n")
before = row(root, "T7")
rc, said = run(root, "--push")
check("no Result line: the row is left alone", rc == 0 and row(root, "T7") == before, said)
check("and it says what's left", "left for you: the Work list result of H060 (no Result line" in said, said)
check("the merge is the last commit, and it was pushed", sh(root, "git", "log", "-1", "--format=%s").stdout.startswith("Merge claude/h060-tool")
      and "pushed main" in said, said)
shutil.rmtree(root); shutil.rmtree(bare)

print(f"BOOKKEEPING TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
sys.exit(1 if not all(RESULTS) else 0)
