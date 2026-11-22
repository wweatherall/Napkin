#!/usr/bin/env python3
"""Checks tools/sort_decision_log.py (run by tools/featuretest.sh). Prints PASS/FAIL per check and one summary line:
LOG SORT TESTS: N passed, M failed."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sort_decision_log as s

RESULTS = []


def check(name, ok):
    RESULTS.append(ok)
    print(("PASS " if ok else "FAIL ") + name)


TABLE = "| ID | Decision |\n|---|---|\n| A10 | ten |\n| A06a | six a |\n| A9 | nine |\n| A06 | six |\n"
out = s.sort_text(TABLE)
check("table rows sort by number, a lettered ID after its number",
      [l.split("|")[1].strip() for l in out.split("\n")[2:6]] == ["A06", "A06a", "A9", "A10"])

TUNE = "| Setting | Value |\n|---|---|\n| ZOOM | 1 |\n| HOLD | 2 |\n"
check("a table whose first column isn't an ID keeps its order", s.sort_text(TUNE) == TUNE)

DOC = ("## Decisions\n\n| ID | D |\n|---|---|\n| I3 | x (Details below.) |\n| A2 | y (Details below.) |\n\n"
       "## Details\n\n### I3\n\nDecision: three\n\n### A2\n\nDecision: two\n")
out = s.sort_text(DOC)
check("details sections sort by ID", out.index("### A2") < out.index("### I3"))
check("details sorting keeps every section's text", "Decision: three" in out and "Decision: two" in out)
check("sorting is stable (a second pass changes nothing)", s.sort_text(out) == out)
check("the trailing newline is kept", out.endswith("\n") and not out.endswith("\n\n"))
check("matched rows and sections give no problems", s.details_problems(out) == [])

MISSING = DOC.replace("### I3\n\nDecision: three\n\n", "")
check("a (Details below.) row without a section is reported",
      any("I3" in p for p in s.details_problems(MISSING)))
ORPHAN = DOC.replace("| A2 | y (Details below.) |", "| A2 | y |")
check("a section without its row marker is reported", any("A2" in p for p in s.details_problems(ORPHAN)))

AFTER = DOC + "\n## Later\n\ntext\n"
out = s.sort_text(AFTER)
check("a section after Details is left alone", out.endswith("## Later\n\ntext\n") and out.index("### A2") < out.index("### I3"))

log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "decision-log.md")
text = open(log, encoding="utf-8").read()
check("docs/decision-log.md is sorted", s.sort_text(text) == text)
check("docs/decision-log.md: every (Details below.) row has its section", s.details_problems(text) == [])


LOG = ("## Decisions\n\n| ID | D | Status |\n|---|---|---|\n| A1 | x | Active |\n| A2 | y | Maybe |\n\n"
       "## Work list\n\n| # | Item | Status |\n|---|---|---|\n| T1 | a | Done |\n| T2 | b | Open (queued: H041) |\n"
       "| T3 | c | Done (review pending) |\n| T4 | d | In progress |\n")
probs = s.status_problems(LOG)
check("a decision with a status outside Active/Tentative is reported", any(p.startswith("A2:") for p in probs))
check("a Work list status a worker invented ('Done (review pending)') is reported", any(p.startswith("T3:") for p in probs))
check("Done, In progress and 'Open (queued: H041)' are accepted", not any(p[:3] in ("T1:", "T2:", "T4:") for p in probs))
check("the real decision log uses only allowed statuses",
      s.status_problems(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "decision-log.md"), encoding="utf-8").read()) == [])

arch = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "decision-archive.md")
check("docs/decision-log.md and docs/decision-archive.md are tidy as a pair, with no problems (P23)",
      s.check_files(text, open(arch, encoding="utf-8").read()) == [])
check("a live file with no archive beside it (before P23) is only sorted",
      not any("not sorted" in p for p in s.check_files(s.sort_text(DOC))) and any("not sorted" in p for p in s.check_files(DOC)))

print(f"LOG SORT TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
