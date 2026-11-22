#!/usr/bin/env python3
"""Checks the decision log's two files (P23, T94): tidying into docs/decision-archive.md, the generated Subjects
index and principles' Explains, the checks across both files, numbering across both, startup.py's ID report,
and integrate.py settling a branch written in the layout before P23. Prints PASS/FAIL per check and one summary
line: LOG ARCHIVE TESTS: N passed, M failed."""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import integrate
import number_ids
import sort_decision_log as s
import startup

RESULTS = []


def check(name, ok):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


DH = "| ID | Decision | Status | Replaces / replaced by | Why | Principles | Where in the code | Date |\n|---|---|---|---|---|---|---|---|\n"
LIVE = ("# log\n\n## Subjects\n\n| Subject | Covers | Decisions |\n|---|---|---|\n"
        "| Snapping | Points. |  |\n| Process | How we work. |  |\n\n"
        "## Principles\n\n| ID | Principle | Status | Explains | Date |\n|---|---|---|---|---|\n"
        "| G01 | Feel first. | Tentative |  | 2026-11-22 |\n| G02 | Write it down. | Tentative |  | 2026-11-22 |\n\n"
        "## Decisions\n\nIntro.\n\n### Process\n\n" + DH +
        "| P01 | Log it. | Active |  | Why. | G02 |  | 2026-11-20 |\n\n"
        "### Snapping\n\n" + DH +
        "| I18 | Soft axes. | Active |  | Why. | G01 |  | 2026-11-20 |\n"
        "| I03b | One engine. (Details below.) | Superseded | Replaced by I18 | Why. | G01 |  | 2026-11-20 |\n\n"
        "## Open questions\n\n| # | Question | Status | Notes |\n|---|---|---|---|\n"
        "| Q1 | Third stage? | Open | Maybe. |\n| Q2 | Next tool? | Decided | Move (I14). |\n\n"
        "## Work list\n\n| # | Item | Status | Covers | Result / next step |\n|---|---|---|---|---|\n"
        "| T1 | Mirror fix. | Done | A26 | Committed. |\n| T2 | Faster. | Open | Q18 | Next. |\n\n"
        "## Tunables\n\n| Setting | Value | What it does | File | Decision |\n|---|---|---|---|---|\n"
        "| HOLD | 0.6 | Top. | main.gd | W07 |\n\n"
        "## Details\n\nFull text.\n\n### I03b\n\nThe long text.\n")
ARCH = ("# archive\n\n## Superseded decisions\n\n" + DH.replace("Principles", "Area") +
        "| A01 | Op log. | Superseded | Replaced by A21 | Why. | Architecture |  | 2026-11-20 |\n\n"
        "## Decided questions\n\n| # | Question | Status | Notes |\n|---|---|---|---|\n\n"
        "## Done work\n\n| # | Item | Status | Covers | Result / next step |\n|---|---|---|---|---|\n\n"
        "## Details\n\nArchived text.\n")

live, arch = s.tidy(LIVE, ARCH)
check("a Superseded decision moves to the archive", "| I03b " not in live and "| I03b " in arch)
check("its Principles cell keeps its subject: 'Snapping; G01'", "| Snapping; G01 |" in arch)
check("its Details section moves with it", "### I03b" in arch and "### I03b" not in live)
check("a Decided question moves to ## Decided questions",
      "| Q2 " not in live and arch.index("\n| Q2 ") > arch.index("## Decided questions"))
check("a Done item moves to ## Done work", "| T1 " not in live and arch.index("\n| T1 ") > arch.index("## Done work"))
check("Open rows stay live", "| Q1 " in live and "| T2 " in live and "| I18 " in live)
check("subject groups follow the index's order", live.index("### Snapping") < live.index("### Process"))
check("the index lists each subject's decisions", "| Snapping | Points. | I18 |" in live and "| Process | How we work. | P01 |" in live)
check("a principle's Explains lists the decisions naming it", "| G01 | Feel first. | Tentative | I18 |" in live)
check("tidying twice changes nothing", s.tidy(live, arch) == (live, arch))
check("a tidy pair has no problems", s.check_files(live, arch) == [])

check("an untidy pair is reported", any("not tidy" in p for p in s.check_files(LIVE, ARCH)))
both = arch.replace("## Decided questions", "## Decided questions", 1)
both = s.insert_row(both, "| Q1 | Third stage? | Decided | Copy. |", "## Decided questions")
check("an ID in both files is reported", any("Q1 is in both" in p for p in s.check_files(live, s.sort_text(both))))
stray = live.replace("### Process", "### Procedure")
check("a subject heading missing from the index is reported",
      any("### Procedure" in p for p in s.layout_problems(stray, arch)))
check("an index subject without a heading is reported",
      any("names Process" in p for p in s.layout_problems(stray, arch)))
ghost = live.replace("| G02 |  | 2026-11-20 |", "| G09 |  | 2026-11-20 |")
check("a decision naming a principle that doesn't exist is reported",
      any("G09" in p for p in s.layout_problems(ghost, arch)))
blank = live.replace("| G02 |  | 2026-11-20 |", "|  |  | 2026-11-20 |")
check("a decision with an empty Principles cell is reported", any("P01: no principle" in p for p in s.layout_problems(blank, arch)))

# the real files
root = os.path.join(HERE, "..")
rl = open(os.path.join(root, s.LIVE), encoding="utf-8").read()
ra = open(os.path.join(root, s.ARCHIVE), encoding="utf-8").read()
check("docs/decision-log.md and docs/decision-archive.md have no problems", s.check_files(rl, ra) == [])
check("the live file holds no Superseded, Decided or Done row",
      not any(c[2] in ("Superseded", "Decided", "Done") for c in (s.cells(l) for l in rl.split("\n") if s.row_id(l))))

# numbering counts both files; startup finds rows in either
tmp = tempfile.mkdtemp()
try:
    os.makedirs(os.path.join(tmp, "docs"))
    open(os.path.join(tmp, s.LIVE), "w").write(live)
    a2 = s.insert_row(arch, "| T7 | Old item. | Done | Q1 | Done. |", "## Done work")
    open(os.path.join(tmp, s.ARCHIVE), "w").write(s.sort_text(a2))
    open(os.path.join(tmp, "note.md"), "w").write("See T-new-1 and G-new-1.\n")
    got = number_ids.apply(tmp, files=["note.md", s.LIVE, s.ARCHIVE], out=lambda x: None)
    check("number_ids takes the next free number across both files (T7 is archived: T8)", got.get("T-new-1") == "T8")
    check("a new principle placeholder gets the next G number", got.get("G-new-1") == "G03")
finally:
    shutil.rmtree(tmp)
lines, unknown = startup.report_ids(live, ["T1", "I18"], arch)
check("startup finds an archived row and says so", "== T1" + startup.ARCHIVE_NOTE in lines and not unknown)
check("a live row is reported without the archive note", "== I18" in lines)
lines, unknown = startup.report_ids(live, ["Z9"], arch)
check("an ID in neither file is unknown", unknown == ["Z9"] and "or docs/decision-archive.md" in lines[0])

# integrate.py: a branch in the old layout settles into the new one
OLD_DH = DH.replace("Principles", "Area")
BASE_OLD = ("# log\n\n## Decisions\n\n" + OLD_DH +
            "| I18 | Soft axes. | Active |  | Why. | Interaction |  | 2026-11-20 |\n"
            "| P01 | Log it. | Active |  | Why. | Process |  | 2026-11-20 |\n\n"
            "## Superseded decisions\n\n" + OLD_DH + "\n"
            "## Open questions\n\n| # | Question | Status | Notes |\n|---|---|---|---|\n| Q1 | Third stage? | Open | Maybe. |\n\n"
            "## Work list\n\n| # | Item | Status | Covers | Result / next step |\n|---|---|---|---|---|\n"
            "| T2 | Faster. | Open | Q18 | Next. |\n\n"
            "## Tunables\n\n| Setting | Value | What it does | File | Decision |\n|---|---|---|---|---|\n"
            "| HOLD | 0.6 | Top. | main.gd | W07 |\n\n## Details\n\nFull text.\n")
THEIRS = (BASE_OLD
          .replace("| P01 | Log it. | Active |  | Why. | Process |  | 2026-11-20 |\n",
                   "| P01 | Log it. | Active |  | Why. | Process |  | 2026-11-20 |\n"
                   "| P-new-1 | Gate faster. (Details below.) | Active |  | Your call. | Process | gate.sh | 2026-11-22 |\n"
                   "| I-new-1 | Snap to circles. | Active |  | Your call. | Interaction |  | 2026-11-22 |\n")
          .replace("| I18 | Soft axes. | Active |  | Why. | Interaction |  | 2026-11-20 |\n", "")
          .replace("## Superseded decisions\n\n" + OLD_DH,
                   "## Superseded decisions\n\n" + OLD_DH + "| I18 | Soft axes. | Superseded | Replaced by I-new-1 | Why. | Interaction |  | 2026-11-20 |\n")
          .replace("| T2 | Faster. | Open | Q18 | Next. |\n", "| T2 | Faster. | Open | Q18 | Next. |\n| T-new-1 | Measure. | Open | P-new-1 | Assigned. |\n")
          .replace("| HOLD | 0.6 |", "| HOLD | 0.7 |")
          .replace("Full text.\n", "Full text.\n\n### P-new-1\n\nRun the halves side by side.\n"))
ours = (live, arch)
res, asks = integrate.settle_log(ours, (BASE_OLD, ""), (THEIRS, ""))
check("a new old-layout decision whose Area is 'Interaction' stops and asks", res is None and [a[0] for a in asks] == ["I-new-1"])
(nl, na), asks = integrate.settle_log(ours, (BASE_OLD, ""), (THEIRS, ""), {"I-new-1": "Snapping"})
check("with --subject it goes under that subject, principle —",
      not asks and nl.index("\n| I-new-1 ") > nl.index("### Snapping") and "| I-new-1 | Snap to circles. | Active |  | Your call. | — |" in nl)
check("an Area that names one subject places the row by itself (Process)",
      nl.index("\n| P-new-1 ") > nl.index("### Process") and nl.index("\n| P-new-1 ") < nl.index("## Open questions"))
check("a live decision the branch superseded moves to the archive with main's subject and principles",
      "| I18 " not in nl and "| I18 | Soft axes. | Superseded | Replaced by I-new-1 | Why. | Snapping; G01 |" in na)
check("the branch's new Work list row lands in the live Work list", nl.index("\n| T-new-1 ") > nl.index("## Work list"))
check("the branch's Details section comes along", "### P-new-1\n\nRun the halves side by side." in nl)
check("a changed Tunables row is carried", "| HOLD | 0.7 |" in nl and "| HOLD | 0.6 |" not in nl)
check("main's rows the branch didn't touch are kept", "| Q1 " in nl and "| T1 " in na and "| A01 " in na)
check("the settled pair is tidy (no problems apart from the placeholders' own)", s.check_files(nl, na) == [])
NEW_THEIRS = s.insert_row(live, "| I-new-2 | Snap to arcs. | Active |  | Why. | G01 |  | 2026-11-22 |", "## Decisions", "Snapping")
(nl, na), asks = integrate.settle_log(ours, ours, (NEW_THEIRS, arch))
check("a new-layout branch's row keeps the subject it was written under", not asks and nl.index("\n| I-new-2 ") > nl.index("### Snapping"))
check("the integrator asked about no subject for it", asks == [])

# integrate.py --status T2=Done moves the item to the archive
tmp = tempfile.mkdtemp()
try:
    os.makedirs(os.path.join(tmp, "docs"))
    open(os.path.join(tmp, s.LIVE), "w").write(live)
    open(os.path.join(tmp, s.ARCHIVE), "w").write(arch)
    msg = integrate.set_status(tmp, "T2", "Done")
    l2, a2 = (open(os.path.join(tmp, p)).read() for p in (s.LIVE, s.ARCHIVE))
    check("--status T2=Done moves it to the archive and says so", "moved to docs/decision-archive.md" in msg
          and "| T2 " not in l2 and "| T2 | Faster. | Done |" in a2)
    msg = integrate.set_status(tmp, "T2", "In progress")
    check("--status on an archived item changes it there, nothing moves", "moved" not in msg
          and "| T2 | Faster. | In progress |" in open(os.path.join(tmp, s.ARCHIVE)).read())
finally:
    shutil.rmtree(tmp)

print(f"LOG ARCHIVE TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
sys.exit(0 if all(RESULTS) else 1)
