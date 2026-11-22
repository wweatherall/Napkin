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
check("a branch an open handoff names but that's gone is reported; a live one (local or origin/) isn't",
      s.gone_branches({"H1.md": "on claude/h043-hide-check and codex/plane, claude/cloud.", "H2.md": "no branch"},
                      ["codex/plane", "origin/claude/cloud"]) == [("H1.md", "claude/h043-hide-check")])

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

WLOG = ("## Principles\n\n| ID | Principle | Status | Covers | Date |\n|---|---|---|---|---|\n"
        "| G01 | Feel first. | Active | A02 | 2026-11-22 |\n| G14 | Measure twice. | Tentative | I01 | 2026-11-22 |\n\n"
        "## Work list\n\n| # | Item | Status | Covers | Result / next step |\n|---|---|---|---|---|\n"
        "| T65 | Ask on a dropped save | Open | Q19 | After T64; the question's wording is your call. |\n"
        "| T66 | Units | Open | T32 | Units preference: your call. Decided 2026-11-22: I57. |\n"
        "| T25 | AppKit | Parked | I31 | Your call, 2026-11-21: wait for a prototype. |\n"
        "| T67 | Paint key | Open | Q14 | Your call, 2026-11-21: P. |\n"
        "| T68 | Done one | Done | Q1 | your call |\n"
        "| T69 | Plain | Open | Q2 | After T68. |\n")
rows = s.waiting_rows(WLOG)
check("an Open Work list row left as 'your call' is waiting, with its sentence",
      rows[:1] == [("T65", "After T64; the question's wording is your call.")])
check("a 'your call' row with a decision ID after it was answered and isn't listed", "T66" not in [r[0] for r in rows])
check("'Your call, <date>:' records an answer; Parked and Done rows aren't listed", [r[0] for r in rows] == ["T65"])
check("a Tentative principle is waiting; an Active one isn't", s.tentative_principles(WLOG) == [("G14", "Measure twice.")])

HO = {"H060-a.md": "### H060\n\nAuthor: x | Date: d | Status: open | For: Claude\n\nAsk William which key. Then build.\n",
      "H061-b.md": "### H061\n\nAuthor: x | Date: d | Status: open | For: Claude\n\nAsk William which key.\n\n"
                   "Response — Claude: logged as I70 (Option).\n",
      "H062-c.md": "### H062\n\nAuthor: x | Date: d | Status: queued (after H060) | For: Codex\n\nFirst, ask William two"
                   " things.\n\n- William's answers, logged: yes.\n",
      "H063-d.md": "### H063\n\nAuthor: x | Date: d | Status: answered | For: Codex\n\nAsk William.\n",
      "H064-e.md": "### H064\n\nAuthor: x | Date: d | Status: queued (after H060) | For: Codex\n\nNo question.\n"}
check("an open handoff with an unanswered 'Ask William' is waiting, with its sentence",
      s.waiting_handoffs(HO) == [("H060", "Ask William which key.")])
check("a Response naming a logged decision, or a 'William's answers' line, answers it; an answered entry isn't open",
      [h for h, _ in s.waiting_handoffs(HO)] == ["H060"])
WBOARD = "## Notes\n\n- William: say whether to clear the old worktrees.\n- For William: T38's key.\n- Codex: take H046.\n"
check("board notes addressed to William are listed; others aren't",
      s.william_notes(WBOARD) == ["William: say whether to clear the old worktrees.", "For William: T38's key."])
out = s.waiting_on_william(WLOG, HO, WBOARD, True)
check("the section has one line per source, with IDs, and the CronList reminder when the lock is held",
      any(l.startswith("  T65 (Work list):") for l in out) and any(l.startswith("  G14 (principle") for l in out)
      and any(l.startswith("  H060 (handoff):") for l in out) and sum("Board note:" in l for l in out) == 2
      and "CronList" in out[-1])
check("nothing waiting says so; no lock, no reminder", s.waiting_on_william("", {}, "", False) == ["  (nothing)"])

r = subprocess.run([sys.executable, os.path.join(HERE, "startup.py")], capture_output=True, text=True, timeout=10)
check("smoke: the real report runs and has every section",
      r.returncode == 0 and all(h in r.stdout for h in ("This checkout:", "Worktrees", "Recent main:",
                                                         "Branches with commits", "Ready on the board",
                                                         "Waiting on William")))
r = subprocess.run([sys.executable, os.path.join(HERE, "startup.py"), "T1"], capture_output=True, text=True, timeout=10)
check("smoke: asking for T1 prints its row", r.returncode == 0 and "| T1 |" in r.stdout)
r = subprocess.run([sys.executable, os.path.join(HERE, "startup.py"), "T99999"], capture_output=True, text=True, timeout=10)
check("smoke: an unknown ID exits 1", r.returncode == 1 and "T99999: not found" in r.stdout)

ARCHIVED = "## Done work\n\n| # | Item | Status | Covers | Result |\n|---|---|---|---|---|\n| T50 | Old item | Done | A23 | ok |\n"
lines, unknown = s.report_ids(LOG, ["T50"], ARCHIVED)
check("an ID only in docs/decision-archive.md is found and marked (P23)", not unknown and lines[0] == "== T50" + s.ARCHIVE_NOTE)
check("an archived Work list item's Covers IDs are looked up in the live file", any(l.startswith("  A23: | A23 |") for l in lines))
lines, unknown = s.report_ids(LOG, ["T51"], ARCHIVED)
check("an ID in neither file is unknown", unknown == ["T51"])

print(f"STARTUP TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
sys.exit(0 if all(RESULTS) else 1)
