#!/usr/bin/env python3
"""Checks tools/sort_decision_log.py (run by tools/featuretest.sh). Prints PASS/FAIL per check and one summary line:
LOG SORT TESTS: N passed, M failed."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sort_decision_log as s

RESULTS = []
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name, ok):
    RESULTS.append(ok)
    if not ok or VERBOSE:
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

log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "03_Past_Decisions", "decision-log.md")
text = open(log, encoding="utf-8").read()
check("03_Past_Decisions/decision-log.md is sorted", s.sort_text(text) == text)
check("03_Past_Decisions/decision-log.md: every (Details below.) row has its section", s.details_problems(text) == [])


LOG = ("## Decisions\n\n| ID | D | Status |\n|---|---|---|\n| A1 | x | Active |\n| A2 | y | Maybe |\n\n"
       "## Work list\n\n| # | Item | Status |\n|---|---|---|\n| T1 | a | Done |\n| T2 | b | Open (queued: H041) |\n"
       "| T3 | c | Done (review pending) |\n| T4 | d | In progress |\n")
probs = s.status_problems(LOG)
check("a decision with a status outside Active/Tentative is reported", any(p.startswith("A2:") for p in probs))
check("a Work list status a worker invented ('Done (review pending)') is reported", any(p.startswith("T3:") for p in probs))
check("Done, In progress and 'Open (queued: H041)' are accepted", not any(p[:3] in ("T1:", "T2:", "T4:") for p in probs))
check("the real decision log uses only allowed statuses",
      s.status_problems(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "03_Past_Decisions", "decision-log.md"), encoding="utf-8").read()) == [])

arch = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "03_Past_Decisions", "decision-archive.md")
rdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "03_Past_Decisions", "rulings")
wdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "03_Past_Decisions", "work")
qdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "03_Past_Decisions", "questions")
check("03_Past_Decisions/decision-log.md, archive, rulings/, work/ and questions/ are tidy with no problems (P23, P65)",
      s.check_files(text, open(arch, encoding="utf-8").read(), rulings_dir=rdir, work_dir=wdir, questions_dir=qdir) == [])
check("a live file with no archive beside it (before P23) is only sorted",
      not any("not sorted" in p for p in s.check_files(s.sort_text(DOC))) and any("not sorted" in p for p in s.check_files(DOC)))

import shutil
import tempfile

FIX_LIVE = (
    "# Log\n\n## Subjects\n\n| Subject | Covers | Decisions |\n|---|---|---|\n| Snapping | Snap. | — |\n\n"
    "## Principles\n\n| ID | Principle | Status | Explains | Date |\n|---|---|---|---|---|\n"
    "| G01 | Keep it simple. | Tentative | — | 2026-11-22 |\n\n"
    "## Decisions\n\n### Snapping\n\n"
    "| ID | Decision | Status | Replaces / replaced by | Why | Principles | Where in the code | Date |\n"
    "|---|---|---|---|---|---|---|---|\n"
    "| I10 | Snap to corners. (Details below.) | Active |  | Fast. | G01 | snap.gd | 2026-11-21 |\n\n"
    "## Details\n\n### I10\n\nCorner snap details here.\n"
)
FIX_ARCH = (
    "# Archive\n\n## Superseded decisions\n\n"
    "| ID | Decision | Status | Replaces / replaced by | Why | Area | Where in the code | Date |\n"
    "|---|---|---|---|---|---|---|---|\n"
    "| I03 | Old snap. | Superseded | Replaced by I10 | Old way. | Snapping; G01 |  | 2026-11-20 |\n\n"
    "## Details\n"
)

tmp = tempfile.mkdtemp(prefix="sortlog-")
trdir = os.path.join(tmp, "rulings")
l2, a2 = s.tidy(FIX_LIVE, FIX_ARCH, rulings_dir=trdir)

exp_i10 = (
    "# I10 — Snap to corners.\n\n"
    "Status: Active | Subject: Snapping | Principles: G01 | Date: 2026-11-21\n"
    "Replaces / replaced by: —\n"
    "Where in the code: snap.gd\n\n"
    "Snap to corners.\n\n"
    "Why: Fast.\n\n"
    "## Details\n\n"
    "Corner snap details here.\n"
)
exp_g01 = (
    "# G01 — Keep it simple.\n\n"
    "Status: Tentative | Date: 2026-11-22\n\n"
    "Keep it simple.\n"
)
exp_i03 = (
    "# I03 — Old snap.\n\n"
    "Status: Superseded | Subject: Snapping | Principles: G01 | Date: 2026-11-20\n"
    "Replaces / replaced by: Replaced by I10\n"
    "Where in the code: —\n\n"
    "Old snap.\n\n"
    "Why: Old way.\n"
)
check("every ruling row becomes its file, word for word",
      open(os.path.join(trdir, "I10.md"), encoding="utf-8").read() == exp_i10
      and open(os.path.join(trdir, "G01.md"), encoding="utf-8").read() == exp_g01
      and open(os.path.join(trdir, "I03.md"), encoding="utf-8").read() == exp_i03)

check("the index lists each Active ruling under its subject, and Superseded ones in the archive's index",
      "| I10 | Snap to corners. | Active |" in l2
      and "| G01 | Keep it simple. | Tentative |" in l2
      and "| I03 | Old snap. | Superseded |" in a2
      and "| Snapping | Snap. | I10 |" in l2)

old_branch_live = l2.replace(
    "| I10 | Snap to corners. | Active |",
    "| I10 | Snap to corners. | Active |\n"
    "| I11 | Snap to edges. | Active |  | Helpful. | G01 | edge.gd | 2026-11-22 |",
)
# Simulate an old branch adding a full 8-column row into the table
old_branch_live = s.insert_row(
    l2,
    "| I11 | Snap to edges. | Active |  | Helpful. | G01 | edge.gd | 2026-11-22 |",
    "## Decisions", "Snapping",
)
# Wait: insert_row puts it into the 3-column index table; test with an 8-column table row in ## Decisions
old_branch_live2 = l2.replace(
    "| I10 | Snap to corners. | Active |",
    "| I10 | Snap to corners. | Active |\n\n"
    "| ID | Decision | Status | Replaces / replaced by | Why | Principles | Where in the code | Date |\n"
    "|---|---|---|---|---|---|---|---|\n"
    "| I11 | Snap to edges. | Active |  | Helpful. | G01 | edge.gd | 2026-11-22 |",
)
l3, a3 = s.tidy(old_branch_live2, a2, rulings_dir=trdir)
check("a ruling row added by an old branch is moved into its file by the tidy",
      os.path.isfile(os.path.join(trdir, "I11.md"))
      and "| I11 | Snap to edges. | Active |" in l3
      and "Helpful." not in l3)

both_bad = l3.replace(
    "| I10 | Snap to corners. | Active |",
    "| I10 | Snap to corners. | Active |\n\n"
    "| ID | Decision | Status | Replaces / replaced by | Why | Principles | Where in the code | Date |\n"
    "|---|---|---|---|---|---|---|---|\n"
    "| I10 | Snap to corners. | Active |  | Fast. | G01 | snap.gd | 2026-11-21 |",
)
check("--check refuses an ID both in a table and a file",
      any("I10 is in both" in p for p in s.check_files(both_bad, a3, rulings_dir=trdir)))

twdir = os.path.join(tmp, "work")
tqdir = os.path.join(tmp, "questions")
QT_LIVE = (
    "# Log\n\n## Open questions\n\n| # | Question | Status | Notes |\n|---|---|---|---|\n"
    "| Q1 | Third stage? (Details below.) | Open | Maybe. |\n\n"
    "## Work list\n\n| # | Item | Status | Covers | Result / next step |\n|---|---|---|---|---|\n"
    "| T2 | Faster cuts. | Open | Q1 | Next step here. |\n\n"
    "## Details\n\n### Q1\n\nExtra question context.\n"
)
QT_ARCH = (
    "# Archive\n\n## Decided questions\n\n| # | Question | Status | Notes |\n|---|---|---|---|\n"
    "| Q2 | Next tool? | Decided | Move (I14). |\n\n"
    "## Done work\n\n| # | Item | Status | Covers | Result / next step |\n|---|---|---|---|---|\n"
    "| T1 | Mirror fix. | Done | A26 | Committed. |\n\n"
    "## Details\n"
)
ql2, qa2 = s.tidy(QT_LIVE, QT_ARCH, work_dir=twdir, questions_dir=tqdir)
exp_q1 = (
    "# Q1 — Third stage?\n\n"
    "Status: Open\n\n"
    "Third stage?\n\n"
    "Notes: Maybe.\n\n"
    "## Details\n\n"
    "Extra question context.\n"
)
exp_t2 = (
    "# T2 — Faster cuts.\n\n"
    "Status: Open | Covers: Q1\n\n"
    "Faster cuts.\n\n"
    "Result / next step: Next step here.\n"
)
exp_t1 = (
    "# T1 — Mirror fix.\n\n"
    "Status: Done | Covers: A26\n\n"
    "Mirror fix.\n\n"
    "Result / next step: Committed.\n"
)
check("every Work list and question row becomes its file, word for word",
      open(os.path.join(tqdir, "Q1.md"), encoding="utf-8").read() == exp_q1
      and open(os.path.join(twdir, "T2.md"), encoding="utf-8").read() == exp_t2
      and open(os.path.join(twdir, "T1.md"), encoding="utf-8").read() == exp_t1)

# Mark T2 Done in its file and re-tidy: file stays in work/, index line moves to archive
s.write_entry(twdir, "T2", exp_t2.replace("Status: Open", "Status: Done"))
ql3, qa3 = s.tidy(ql2, qa2, work_dir=twdir, questions_dir=tqdir)
check("a Done item's index line is in the archive's index, its file unmoved",
      os.path.isfile(os.path.join(twdir, "T2.md"))
      and "| T2 | Faster cuts. | Done |" not in ql3
      and "| T2 | Faster cuts. | Done |" in qa3)

old_t_live = ql3.replace(
    "## Work list\n\n| # | Item | Status |\n|---|---|---|\n",
    "## Work list\n\n| # | Item | Status |\n|---|---|---|\n\n"
    "| # | Item | Status | Covers | Result / next step |\n|---|---|---|---|---|\n"
    "| T3 | Old branch item. | Open | T2 | From branch. |\n",
)
ql4, qa4 = s.tidy(old_t_live, qa3, work_dir=twdir, questions_dir=tqdir)
check("an old branch's T row is moved into its file by the tidy",
      os.path.isfile(os.path.join(twdir, "T3.md"))
      and "| T3 | Old branch item. | Open |" in ql4
      and "From branch." not in ql4)

shutil.rmtree(tmp)

print(f"LOG SORT TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
raise SystemExit(0 if all(RESULTS) else 1)   # a failed check fails the run, not only its summary
