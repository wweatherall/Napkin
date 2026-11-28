#!/usr/bin/env python3
"""Checks tools/org_todos.py (T134): one generated file per thing waiting on William or the integrator in
comitatus/06_To-dos, stale generated files removed, hand-written ones kept, nothing written outside comitatus.
Throwaway folders. Summary line: ORG TODOS TESTS: N passed, M failed."""
import os
import subprocess
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import org_todos

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        print(f"FAIL {name}  {detail}")


org = tempfile.mkdtemp(prefix="todos-test-")
os.makedirs(os.path.join(org, "06_To-dos"))
root = os.path.join(org, "08_Code_Bases", "Proj")
for d in ("docs/handoff", "03_Past_Decisions"):
    os.makedirs(os.path.join(root, d))
subprocess.run(["git", "init", "-q", "-b", "main", root], check=True)
open(os.path.join(root, "03_Past_Decisions", "decision-log.md"), "w").write(
    "# Log\n\n## Work list\n\n| # | Item | Status | Covers | Result / next step |\n|---|---|---|---|---|\n"
    "| T9 | Pick a wood | Open | — | Your call: oak or ash. |\n| T10 | Built | Open | — | Done soon. |\n")
os.makedirs(os.path.join(root, "03_Past_Decisions", "work"))
open(os.path.join(root, "03_Past_Decisions", "work", "T11.md"), "w").write(
    "# T11 — Choose a finish\n\nStatus: Open | Covers: —\n\nChoose a finish.\n\nResult / next step: Your call: oil or wax.\n")
open(os.path.join(root, "03_Past_Decisions", "work", "T12.md"), "w").write(
    "# T12 — Picked up item\n\nStatus: Picked up (integrator, 2026-11-26) | Covers: —\n\nPicked up.\n\nResult / next step:\n")
open(os.path.join(root, "03_Past_Decisions", "work", "T13.md"), "w").write(
    "# T13 — Ready for integrator\n\nStatus: Open | Covers: —\n\nLater.\n\nResult / next step: Later.\n")
open(os.path.join(root, "03_Past_Decisions", "work", "T14.md"), "w").write(
    "# T14 — Already on board\n\nStatus: On the board (H5) | Covers: —\n\nOn board.\n\nResult / next step:\n")
open(os.path.join(root, "03_Past_Decisions", "work", "T15.md"), "w").write(
    "# T15 — A someday idea\n\nStatus: Parked | Covers: —\n\nOne day.\n\nResult / next step:\n")
open(os.path.join(root, "docs", "handoff", "H5-review-me.md"), "w").write(
    "### H5 — Make the thing\n\nAuthor: x | Date: 2026-11-26 | Status: answered | For: either\n")
open(os.path.join(root, "docs", "follow-ups.md"), "w").write("# Follow-ups\n\n- H4 (2026-11-26): Tidy the drawer later.\n")
w, i = os.path.join(org, "06_To-dos", "waiting_on_William"), os.path.join(org, "06_To-dos", "waiting_on_integrator")
os.makedirs(w)
open(os.path.join(w, "MY_OWN_NOTE.md"), "w").write("written by William\n")
open(os.path.join(w, "Proj_T1_OLD.md"), "w").write(org_todos.MARK.format(base="Proj") + "\n\nstale\n")

run = lambda: subprocess.run([sys.executable, os.path.join(TOOLS, "org_todos.py"), "--quiet"], cwd=root,
                             capture_output=True, text=True)
r = run()
names_w, names_i = sorted(os.listdir(w)), sorted(os.listdir(i))
check("a 'your call' Work list item in its own file (H153) waits on William too",
      any(n.startswith("Proj_T11_") for n in names_w), names_w)
check("an item that isn't waiting on William gets no file", not any("T10" in n for n in names_w), names_w)
check("a job answered for review and a follow-up wait on the integrator",
      "Proj_H5_MAKE_THE_THING.md" in names_i and "Proj_H4_TIDY_THE_DRAWER_LATER.md" in names_i, names_i)
check("an Open item not waiting on William is an integrator to-do",
      any(n.startswith("Proj_T13_") for n in names_i) and not any(n.startswith("Proj_T11_") for n in names_i), names_i)
t12_files = [n for n in names_i if n.startswith("Proj_T12_")]
check("a picked-up item's to-do says picked up",
      len(t12_files) == 1 and "picked up 2026-11-26" in open(os.path.join(i, t12_files[0])).read(), names_i)
check("an item On the board has no to-do file",
      not any(n.startswith("Proj_T14_") for n in names_i), names_i)
check("a stale generated file is removed, a hand-written one kept",
      "Proj_T1_OLD.md" not in names_w and "MY_OWN_NOTE.md" in names_w, names_w)
check("each file says it is generated", open(os.path.join(i, "Proj_H5_MAKE_THE_THING.md")).read().startswith("<!-- generated"))
names_d = sorted(os.listdir(os.path.join(org, "06_To-dos", "one_day_for_William")))
check("a Parked Work list item goes in one_day_for_William, nowhere else",
      names_d == ["Proj_T15_A_SOMEDAY_IDEA.md"] and not any("T15" in n for n in names_w + names_i), (names_d, names_w, names_i))
before = {n: os.path.getmtime(os.path.join(i, n)) for n in names_i}
run()
check("a second run with nothing changed rewrites nothing",
      before == {n: os.path.getmtime(os.path.join(i, n)) for n in os.listdir(i)})
plain = tempfile.mkdtemp(prefix="todos-plain-")
subprocess.run(["git", "init", "-q", "-b", "main", plain], check=True)
check("a checkout outside comitatus writes nothing", org_todos.todos_dir(plain) is None)

print(f"ORG TODOS TESTS: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
