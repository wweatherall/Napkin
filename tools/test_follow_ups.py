#!/usr/bin/env python3
"""Checks P26's follow-ups (T97): a response's "Follow-up:" lines reach docs/follow-ups.md at merge, once each, and
its "For the integrator:" lines are printed after the merge. Throwaway repositories.
Summary line: FOLLOW-UP TESTS: N passed, M failed."""
import contextlib
import io
import os
import re
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

text = ENTRY.format(n="060", status="answered") + ("\nResponse: done.\n\nArchitecture: session.py saves generations\n"
                                                   "- Architecture: the open reply gains recovered  \n\n"
                                                   "A mention mid-line, `Architecture: <what>`, isn't one.\n")
check("Architecture lines (P28) parse with and without '- '; a mention mid-line isn't one",
      integrate.architecture(text) == ["session.py saves generations", "the open reply gains recovered"],
      integrate.architecture(text))

# 1b. H123: brief lines above a Response heading (and fenced examples) are ignored; entries without a Response
#     heading still fall back to the full text so no worker's leftovers are lost.
scoped = (
    "### H099 — T7: brief quoting response fields\n\nAuthor: Claude | Status: answered\n\n"
    "Request: write lines like:\n"
    "Follow-up: brief example follow-up\n"
    "For the integrator: brief example instruction\n"
    "Architecture: brief example map note\n\n"
    "Response — Gemini, 2026-11-23:\n"
    "Done.\n\n"
    "```\n"
    "Follow-up: fenced follow-up\n"
    "For the integrator: fenced instruction\n"
    "Architecture: fenced map note\n"
    "```\n\n"
    "Follow-up: real leftover\n"
    "For the integrator: real merge step\n"
    "Architecture: real map change\n"
)
check("Follow-up ignores brief lines above Response heading and fenced blocks",
      integrate.follow_ups(scoped) == ["real leftover"], integrate.follow_ups(scoped))
check("For the integrator ignores brief lines above Response heading and fenced blocks",
      integrate.for_integrator(scoped) == ["real merge step"], integrate.for_integrator(scoped))
check("Architecture ignores brief lines above Response heading and fenced blocks",
      integrate.architecture(scoped) == ["real map change"], integrate.architecture(scoped))

no_heading = (
    "### H099 — T7: no heading\n\nAuthor: Claude | Status: answered\n\n"
    "Request: do it.\n\nDone.\n\n"
    "Follow-up: kept without heading\n"
    "For the integrator: step without heading\n"
    "Architecture: map without heading\n"
)
check("entry with no Response heading still reads Follow-up, For the integrator and Architecture",
      integrate.follow_ups(no_heading) == ["kept without heading"]
      and integrate.for_integrator(no_heading) == ["step without heading"]
      and integrate.architecture(no_heading) == ["map without heading"],
      (integrate.follow_ups(no_heading), integrate.for_integrator(no_heading), integrate.architecture(no_heading)))

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

# 4a. An entry still named H-new-N at merge (H060): numbered first, so its follow-ups and Result carry its number.
NEW = "-" + "new-"      # in two halves, so number_ids.py never numbers this file's own example
root = repo(n=NEW + "1")
rc, said = branch(root, "\nResponse: done.\n\nFollow-up: a leftover\n\nResult: abc1234; quick test passes; the tool.\n",
                  n=NEW + "1")
fu = integrate.open_follow_ups(read(root, FU) or "")
check("a placeholder entry's follow-up is recorded under its number, not 'H'",
      rc == 0 and len(fu) == 1 and re.match(r"- H\d+ \(", fu[0]) and fu[0].endswith(": a leftover"), (read(root, FU) or "") + said)
num = fu[0].split()[1] if fu else "?"
check("... its Result goes into its item's row, committed under that number",
      "Result (abc1234" in read(root, "docs/decision-log.md") and f"T7 ({num})" in sh(root, "git", "log", "-1", "--format=%s").stdout, said)
check("... and it is archived under that number", f"### {num} — T7" in read(root, "docs/handoff-archive.md")
      and not os.listdir(os.path.join(root, "docs/handoff")), said)
shutil.rmtree(root)

# 4b. Architecture lines (P28): the merge stops staged, before its commit, with the lines and the reminder;
#     --continue refuses until the map is changed, then commits and finishes (the job merged, the Result drafted).
root = repo()
head0 = sh(root, "git", "rev-parse", "HEAD").stdout.strip()
rc, said = branch(root, "\nResponse: done.\n\nArchitecture: tools/x.py joins the map\n"
                        "For the integrator: add the feature-test line\n")
i = said.find("for you now:")
check("Architecture lines: printed under 'for you now:', marked map:, with the instruction",
      rc == 0 and i >= 0 and "  H060: map: tools/x.py joins the map" in said[i:]
      and "  H060: add the feature-test line" in said[i:], said)
check("... the merge is staged, not committed, with the reminder and how to continue",
      sh(root, "git", "rev-parse", "HEAD").stdout.strip() == head0
      and sh(root, "git", "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0
      and "write these into ARCHITECTURE.md / docs/protocol.md" in said and "--continue --as tester" in said, said)


def resume(*extra):
    out = io.StringIO(); cwd = os.getcwd(); os.chdir(root)
    try:
        with contextlib.redirect_stdout(out):
            rc = integrate.main(["--continue", "--as", "tester", *extra])
    finally:
        os.chdir(cwd)
    return rc, out.getvalue()


rc, said = resume()
check("--continue refuses while the map is unchanged, and shows the lines again",
      rc == 1 and "aren't changed yet" in said and "map: tools/x.py joins the map" in said
      and sh(root, "git", "rev-parse", "HEAD").stdout.strip() == head0, said)
x_before = read(root, "tools/x.py")
write(root, "tools/x.py", x_before + "# changed while paused\n")
sh(root, "git", "add", "tools/x.py")
write(root, "ARCHITECTURE.md", "# Map\n\ntools/x.py: the tool.\n")
sh(root, "git", "add", "ARCHITECTURE.md")
rc, said = resume()
check("--continue refuses when code changed while paused (the gate passed on other code)",
      rc == 1 and "changed outside the map since the gate passed (tools/x.py)" in said
      and sh(root, "git", "rev-parse", "HEAD").stdout.strip() == head0, said)
write(root, "tools/x.py", x_before)
sh(root, "git", "add", "tools/x.py")
sh(root, "git", "add", "ARCHITECTURE.md")
rc, said = resume()
files = sh(root, "git", "show", "--name-only", "--format=", "HEAD^").stdout.split() + \
    sh(root, "git", "show", "--name-only", "--format=", "HEAD").stdout.split()
merge_msg = sh(root, "git", "log", "-1", "--format=%s", "--merges").stdout
check("--continue commits the merge with the map in it",
      rc == 0 and "committed " in said and merge_msg.startswith("Merge claude/h060")
      and "ARCHITECTURE.md" in sh(root, "git", "show", "--name-only", "--format=", "--first-parent", "-m",
                                  sh(root, "git", "log", "-1", "--format=%H", "--merges").stdout.strip()).stdout, said)
check("... and finishes: the branch removed (job merged), the instruction printed, nothing left to continue",
      "claude/h060-tool" not in sh(root, "git", "branch").stdout and "  H060: add the feature-test line" in said
      and not os.path.exists(integrate.state_file(root)), said)
rc, said = resume()
check("--continue with nothing stopped says so", rc == 1 and "nothing to continue" in said, said)
shutil.rmtree(root)
root = repo()
rc, said = branch(root, "\nResponse: done, nothing left.\n")
check("no Architecture lines: no reminder", rc == 0 and "ARCHITECTURE.md / docs/protocol.md" not in said
      and "map:" not in said, said)
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
