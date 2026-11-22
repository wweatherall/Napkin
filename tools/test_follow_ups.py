#!/usr/bin/env python3
"""Checks P26's follow-ups (T97): a response's "Follow-up:" lines reach docs/follow-ups.md at merge, once each, and
its "For the integrator:" lines are printed after the merge. Throwaway repositories.
Summary line: FOLLOW-UP TESTS: N passed, M failed."""
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
FU = integrate.FOLLOW_UPS


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def write(root, rel, text):
    os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
    open(os.path.join(root, rel), "w").write(text)


def read(root, rel):
    p = os.path.join(root, rel)
    return open(p).read() if os.path.isfile(p) else None


ENTRY = ("### H{n} — T7: a tool\n\nAuthor: Claude | Date: 2026-11-22 | Status: {status} | For: Claude\n\n"
         "Touches: tools/x.py.\n\nRequest: use `Follow-up: <what>` lines for anything you leave.\n")


def repo(n="060"):
    root = tempfile.mkdtemp(prefix="follow-ups-test-")
    sh(root, "git", "init", "-q", "-b", "main")
    sh(root, "git", "config", "user.email", "t@example.invalid"); sh(root, "git", "config", "user.name", "t")
    write(root, "docs/decision-log.md", "# Log\n\n## Work list\n\n| # | Item | Status | Covers | Notes |\n"
          "|---|---|---|---|---|\n| T7 | a tool | Open | P20 | |\n")
    write(root, "docs/agent-handoff.md", "# Handoff\n\n## Open exchanges\n\n<!-- open list: built from docs/handoff/ by "
          "tools/handoff.py; don't edit by hand -->\n\n(none open)\n\n<!-- end of open list -->\n\n## Archived\n")
    write(root, "docs/handoff-archive.md", "# Archive\n")
    write(root, f"docs/handoff/H{n}-tool.md", ENTRY.format(n=n, status="open"))
    write(root, "tools/x.py", "x = 1\n")
    sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "base")
    return root


def branch(root, response, n="060"):
    b = f"claude/h{n}-tool"
    sh(root, "git", "checkout", "-qb", b)
    write(root, "tools/x.py", f"x = {n}\n")
    write(root, f"docs/handoff/H{n}-tool.md", ENTRY.format(n=n, status="answered") + response)
    sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", f"H{n}: the tool")
    sh(root, "git", "checkout", "-q", "main")
    integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)
    out = io.StringIO(); cwd = os.getcwd(); os.chdir(root)
    try:
        with contextlib.redirect_stdout(out):
            rc = integrate.main([b, "--as", "tester", "--no-gate"])
    finally:
        os.chdir(cwd)
    return rc, out.getvalue()


# 1. Parsing: with and without "- ", the request's own mention mid-line isn't one.
text = ENTRY.format(n="060", status="answered") + ("\nResponse: done.\n\nFollow-up: retire the old flag\n"
                                                   "- Follow-up: say which key Paint takes  \n"
                                                   "For the integrator: add the feature-test line\n"
                                                   "- For the integrator: run number_ids.py\n")
check("Follow-up lines parse with and without '- '; a mention mid-line isn't one",
      integrate.follow_ups(text) == ["retire the old flag", "say which key Paint takes"], integrate.follow_ups(text))
check("For the integrator lines parse with and without '- '",
      integrate.for_integrator(text) == ["add the feature-test line", "run number_ids.py"], integrate.for_integrator(text))
check("a response with neither gives none of either",
      integrate.follow_ups(ENTRY) == [] and integrate.for_integrator(ENTRY) == [])

# 2. add_follow_ups: the file made with its header, a line already there not added twice (whatever its date).
tmp = tempfile.mkdtemp(prefix="follow-ups-add-")
got = integrate.add_follow_ups(tmp, [("H060", "retire the old flag")], date="2026-11-22")
body = read(tmp, FU)
check("a missing file is made with its header, and the line added in place of (none)",
      got == ["- H060 (2026-11-22): retire the old flag"] and body.startswith("# Follow-ups")
      and "(none)" not in body and body.endswith("## Open\n\n- H060 (2026-11-22): retire the old flag\n"), body)
got = integrate.add_follow_ups(tmp, [("H060", "retire the  old flag"), ("H061", "retire the old flag")], date="2026-11-23")
check("the same entry and text isn't added twice (spacing and date aside); another entry's is",
      got == ["- H061 (2026-11-23): retire the old flag"]
      and integrate.open_follow_ups(read(tmp, FU)) == ["- H060 (2026-11-22): retire the old flag",
                                                        "- H061 (2026-11-23): retire the old flag"], read(tmp, FU))
shutil.rmtree(tmp)

# 3. A merge with both kinds: follow-ups in the merge commit, instructions printed after it, before "left for you".
root = repo()
rc, said = branch(root, "\nResponse: done.\n\nFollow-up: retire the old flag\n- Follow-up: say which key Paint takes\n"
                        "For the integrator: add the feature-test line to featuretest.sh\n")
merge_files = sh(root, "git", "show", "--name-only", "--format=", "HEAD").stdout.split()
check("the merge went in, with docs/follow-ups.md in the merge commit",
      rc == 0 and FU in merge_files and sh(root, "git", "log", "-1", "--format=%s").stdout.startswith("Merge claude/h060"), said)
check("both follow-ups are in the file, under the entry's ID",
      [l.split(": ", 1)[1] for l in integrate.open_follow_ups(read(root, FU))] == ["retire the old flag", "say which key Paint takes"]
      and all(l.startswith("- H060 (") for l in integrate.open_follow_ups(read(root, FU))), read(root, FU))
check("it says how many it added", "follow-ups: 2 added to docs/follow-ups.md" in said, said)
i = said.find("for you now:")
check("the instruction is printed under 'for you now:', after the merge commit and before 'left for you'",
      i > said.find("committed ") >= 0 and "  H060: add the feature-test line to featuretest.sh" in said[i:]
      and (said.find("left for you") == -1 or said.find("left for you") > i), said)
shutil.rmtree(root)

# 4. A merge whose response has neither: no file made, nothing printed.
root = repo()
rc, said = branch(root, "\nResponse: done, nothing left.\n")
check("a response with neither: no docs/follow-ups.md, no 'for you now:'",
      rc == 0 and read(root, FU) is None and "for you now:" not in said and "follow-ups:" not in said, said)
shutil.rmtree(root)

# 5. A follow-up already on main (a returned job's earlier response) isn't copied twice.
root = repo("061")
write(root, FU, integrate.FOLLOW_UPS_HEADER + "- H061 (2026-11-20): retire the old flag\n")
sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "an earlier follow-up")
rc, said = branch(root, "\nResponse: done.\n\nFollow-up: retire the old flag\nFollow-up: a new one\n", n="061")
check("a line already on main isn't added twice; the new one is",
      rc == 0 and integrate.open_follow_ups(read(root, FU)) == ["- H061 (2026-11-20): retire the old flag",
                                                               integrate.open_follow_ups(read(root, FU))[-1]]
      and integrate.open_follow_ups(read(root, FU))[-1].endswith(": a new one") and "1 added" in said, read(root, FU) + said)
shutil.rmtree(root)

print(f"FOLLOW-UP TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
sys.exit(1 if not all(RESULTS) else 0)
