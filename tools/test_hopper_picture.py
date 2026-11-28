#!/usr/bin/env python3
"""Tests for tools/hopper_picture.py and tools/SHOW_THE_HOPPER.py (H203)."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import hopper_picture
import job

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(("PASS: " if ok else "FAIL: ") + name + (f" ({detail})" if detail and not ok else ""))


# 1. Golden picture for a fixed queue state
now = 10_000
golden_st = {
    "jobs": {
        "H196": {"state": "merged", "merged": 9_000},
        "H197": {"state": "done", "agent": "gemini", "branch": "gemini/h197-wake"},
        "H198": {"state": "done", "agent": "codex", "branch": "codex/h198-split", "base": "gemini/h197-wake"},
        "H199": {"state": "in progress", "agent": "gemini", "session": "gemini-larch", "taken": now - 15 * 60},
        "H200": {"state": "waiting", "agent": "codex", "session": "codex-pine", "taken": now - 75 * 60, "question": "q?"},
    },
    "launched": {"H201": {"at": now - 30, "agent": "gemini"}},
    "events": [],
}
golden_jobs = [
    {"id": "H197", "kind": "answered", "item": "Wake or start integrator", "waits": ""},
    {"id": "H198", "kind": "answered", "item": "Split push pull step 1", "waits": ""},
    {"id": "H199", "kind": "ready", "item": "Split push pull step 2", "waits": ""},
    {"id": "H200", "kind": "ready", "item": "Split push pull step 3", "waits": ""},
    {"id": "H201", "kind": "ready", "item": "Fit names target face", "waits": ""},
    {"id": "H202", "kind": "ready", "item": "Draw the hopper", "waits": ""},
    {"id": "H203", "kind": "queued", "item": "Follow-up polish", "waits": "H202"},
]
golden_order = ["H197", "H198", "H199", "H200", "H201", "H202", "H203"]
# Put H198 before H197 in order to verify batch order puts base H197 before stacked H198
desk_order = ["H198", "H197", "H199", "H200", "H201", "H202", "H203"]

expected_golden = "\n".join([
    "+---------------------------------- HOPPER ----------------------------------+",
    "| H202 Draw the hopper                                                       |",
    "| H203 Follow-up polish                                        [waits: H202] |",
    "\\____________________________________________________________________________/",
    "                                    \\    /                                    ",
    "                                    |H201|                                    ",
    "                                      v                                       ",
    "+-------------------------------- WORKBENCH ---------------------------------+",
    "| ? H200 Split push pull step 3                            codex-pine  1h15m |",
    "|   H199 Split push pull step 2                            gemini-larch  15m |",
    "+----------------------------------------------------------------------------+",
    "+---------------------------- INTEGRATOR'S DESK -----------------------------+",
    "| [=] H197 Wake or start integrator                                 (gemini) |",
    "| [=] H198 Split push pull step 1                                    (codex) |",
    "| last merged: H196                                                          |",
    "+----------------------------------------------------------------------------+",
])

actual_golden = hopper_picture.render(golden_st, golden_jobs, desk_order, now=now)
check("fixed queue state draws exact golden picture", actual_golden == expected_golden,
      f"\n--- expected ---\n{expected_golden}\n--- actual ---\n{actual_golden}")
check("every line in golden picture fits within 78 columns",
      all(len(line) <= 78 for line in actual_golden.splitlines()),
      [len(line) for line in actual_golden.splitlines()])

# 2. All three empty cases still draw
empty_pic = hopper_picture.render({"jobs": {}, "events": []}, [], [], now=now)
check("empty hopper still draws (empty)", "(empty)" in empty_pic.split("+-------------------------------- WORKBENCH ---------------------------------+")[0], empty_pic)
check("empty workbench still draws (empty)", "(empty)" in empty_pic.split("+-------------------------------- WORKBENCH ---------------------------------+")[1].split("+---------------------------- INTEGRATOR'S DESK -----------------------------+")[0], empty_pic)
desk_part = empty_pic.split("+---------------------------- INTEGRATOR'S DESK -----------------------------+")[1]
check("empty desk still draws (empty) and last merged: (none)",
      "(empty)" in desk_part and "last merged: (none)" in desk_part, desk_part)

# 3. Long titles are cut to fit with …
long_title = "A very long job title that definitely exceeds seventy-eight columns when rendered inside the hopper funnel"
long_st = {
    "jobs": {
        "H301": {"state": "in progress", "agent": "gemini", "session": "gemini-larch", "taken": now - 60},
        "H302": {"state": "done", "agent": "codex", "branch": "codex/h302-long"},
    },
    "events": [],
}
long_jobs = [
    {"id": "H300", "kind": "ready", "item": long_title, "waits": ""},
    {"id": "H301", "kind": "ready", "item": long_title, "waits": ""},
    {"id": "H302", "kind": "answered", "item": long_title, "waits": ""},
]
long_pic = hopper_picture.render(long_st, long_jobs, ["H300", "H301", "H302"], now=now)
check("long titles are clipped with … and stay within 78 columns",
      long_pic.count("…") >= 3 and all(len(l) <= 78 for l in long_pic.splitlines()),
      long_pic)

# 4. Question mark on a waiting job (and not on non-waiting job)
wait_lines = [l for l in actual_golden.splitlines() if "H200" in l]
work_lines = [l for l in actual_golden.splitlines() if "H199" in l]
check("waiting job shows ? and non-waiting job does not",
      len(wait_lines) == 1 and wait_lines[0].startswith("| ? H200")
      and len(work_lines) == 1 and work_lines[0].startswith("|   H199"),
      (wait_lines, work_lines))

# 5. SHOW_THE_HOPPER.py --help and single run work
root = os.path.dirname(HERE)
help_r = subprocess.run([sys.executable, os.path.join(HERE, "SHOW_THE_HOPPER.py"), "--help"],
                        cwd=root, capture_output=True, text=True)
run_r = subprocess.run([sys.executable, os.path.join(HERE, "SHOW_THE_HOPPER.py")],
                       cwd=root, capture_output=True, text=True)
check("SHOW_THE_HOPPER.py --help and single run succeed",
      help_r.returncode == 0 and "--watch" in help_r.stdout
      and run_r.returncode == 0 and "HOPPER" in run_r.stdout and "INTEGRATOR'S DESK" in run_r.stdout,
      (help_r.returncode, run_r.returncode, run_r.stderr))

# 6. watch() clamps poll >= WATCH_POLL and redraws once when state doesn't change
sleeps = []
outs = []
hopper_picture.watch(root, poll=1, out=outs.append, sleep=sleeps.append, clock=lambda: now, clear=False, max_iterations=2)
check("watch() polls no faster than WATCH_POLL and skips duplicate redraws",
      sleeps == [job.WATCH_POLL] and len(outs) == 1,
      (sleeps, len(outs)))

print(f"HOPPER PICTURE TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
sys.exit(0 if all(RESULTS) else 1)
