#!/usr/bin/env python3
"""Checks tools/startup.py (run by tools/featuretest.sh) on small inline samples, plus one smoke run of the real
script. Prints PASS/FAIL per check and one summary line: STARTUP TESTS: N passed, M failed."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import startup as s

RESULTS = []


def check(name, ok):
    RESULTS.append(ok)
    print(("PASS " if ok else "FAIL ") + name)


WT = ("worktree /repo\nHEAD abc\nbranch refs/heads/main\n\n"
      "worktree /tmp/x\nHEAD def\nbranch refs/heads/codex/h037-fit\n\n"
      "worktree /tmp/y\nHEAD 123\ndetached\n")
check("worktrees parse to path and branch, a detached one marked",
      s.parse_worktrees(WT) == [("/repo", "main"), ("/tmp/x", "codex/h037-fit"), ("/tmp/y", "(detached)")])

REFS = ("main|0 0|2026-11-22\nsmall-fixes|0 19|2026-11-21\ncodex/old|0 40|2026-11-20\n"
        "codex/plane|10 100|2026-11-21\nclaude/h036-keys|0 0|2026-11-22\nfeature|3 0|2026-11-22\n"
        "origin|0 16|2026-11-21\norigin/main|0 16|2026-11-21\norigin/codex/plane|10 100|2026-11-21\n"
        "origin/claude/cloud|2 5|2026-11-22\norigin/other|4 0|2026-11-22\n")
refs = s.parse_refs(REFS)
check("ref lines parse to name, ahead, behind, date", refs[3] == ("codex/plane", 10, 100, "2026-11-21"))
shown, hidden = s.agent_branches(refs)
names = [n for n, *_ in shown]
check("branches ahead of main are shown with count and date", ("codex/plane", 10, "2026-11-21") in shown)
check("main, small-fixes and origin/main are never shown", not {"main", "small-fixes", "origin/main"} & set(names))
check("a local branch other than main counts as an agent branch", "feature" in names)
check("a remote copy of a local branch is not shown twice", "origin/codex/plane" not in names)
check("a remote claude/* branch is shown; other remote branches aren't",
      "origin/claude/cloud" in names and "origin/other" not in names)
check("branches with nothing ahead are hidden and counted", hidden == 2 and "codex/old" not in names)

BOARD = ("# Work board\n\n## Jobs\n\n| Job | For | Status | Item | Handoff | Waits for |\n|---|---|---|---|---|---|\n"
         "| H036 | Claude | **Ready** | T75: keys | [H036](x) | |\n"
         "| H037 | Codex | **Ready** | T54: fits | [H037](y) | |\n"
         "| next | either | Queued | T33: small | later | H036 |\n\n"
         "## Notes\n\n- Codex: take H037.\n- Second note.\n\n## After\n\n- not a note\n")
jobs = s.ready_jobs(BOARD, ["main", "codex/h037-fits"])
check("only Ready jobs are listed", [j[0] for j in jobs] == ["H036", "H037"])
check("a branch containing the job ID in lower case claims it", jobs[1][3] == "codex/h037-fits" and jobs[0][3] is None)
check("a job's For and Item are kept", jobs[0][1:3] == ("Claude", "T75: keys"))
check("notes are the Notes section's lines, not the next section's", s.notes(BOARD) == ["- Codex: take H037.", "- Second note."])
check("an empty board gives no jobs and no notes", s.ready_jobs("", []) == [] and s.notes("") == [])

LOG = ("## Decisions\n\n| ID | Decision | Status |\n|---|---|---|\n"
       "| I40 | A push stays tied to a face. " + "x" * 300 + " (Details below.) | Active |\n"
       "| A23 | sync keeps the prefix | Active |\n\n"
       "## Work list\n\n| # | Item | Status | Covers | Result |\n|---|---|---|---|---|\n"
       "| T53 | Plane fits | Done | I40 | ok |\n"
       "| T54 | Refit only changed | In progress | T53, I40, A23, Q99 | assigned |\n\n"
       "## Details\n\n### I40\n\ntext\n")
check("a row is found by its first cell", s.find_row(LOG, "A23").startswith("| A23 |"))
check("an ID that is only a prefix of another doesn't match", s.find_row(LOG, "T5") is None)
check("Covers IDs are read from a Work list row", s.cited_ids(s.find_row(LOG, "T54")) == ["T53", "I40", "A23", "Q99"])
lines, unknown = s.report_ids(LOG, ["T54"])
out = "\n".join(lines)
check("an asked-for row is printed whole", "| T54 | Refit only changed |" in out)
check("each cited row is printed, shortened to ~200 characters",
      "  A23: | A23 |" in out and all(len(l) <= s.SHORT + 60 for l in lines[2:]))
check("a cited (Details below.) row says it has a ### section",
      any(l.startswith("  I40:") and "### section" in l for l in lines))
check("a cited ID missing from the log says so", "  Q99: not found" in out and unknown == [])
lines, unknown = s.report_ids(LOG, ["A23"])
check("a decision row is printed without following citations", len(lines) == 2)
lines, unknown = s.report_ids(LOG, ["T54", "T999"])
check("an unknown ID asked for is reported", unknown == ["T999"] and any("T999: not found" in l for l in lines))

r = subprocess.run([sys.executable, os.path.join(HERE, "startup.py")], capture_output=True, text=True, timeout=10)
check("smoke: the real report runs and has every section",
      r.returncode == 0 and all(h in r.stdout for h in ("This checkout:", "Worktrees", "Recent main:",
                                                         "Branches with commits", "Ready on the board")))
r = subprocess.run([sys.executable, os.path.join(HERE, "startup.py"), "T1"], capture_output=True, text=True, timeout=10)
check("smoke: asking for T1 prints its row", r.returncode == 0 and "| T1 |" in r.stdout)
r = subprocess.run([sys.executable, os.path.join(HERE, "startup.py"), "T99999"], capture_output=True, text=True, timeout=10)
check("smoke: an unknown ID exits 1", r.returncode == 1 and "T99999: not found" in r.stdout)

print(f"STARTUP TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
sys.exit(0 if all(RESULTS) else 1)
