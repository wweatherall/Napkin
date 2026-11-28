#!/usr/bin/env python3
"""Checks H154's named scripts in tools/ and 02_Habits/: every script exists, reaches its library from another
directory, hooks call the habit scripts, and live guides no longer tell you to type an old command where a named
script exists. Summary line: NAMED SCRIPTS TESTS: N passed, M failed."""
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FC = "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"
VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        if VERBOSE:
            print(f"PASS {name}")
    else:
        failed += 1
        print(f"FAIL {name}  {detail}")


# (relative path, expected substring in --help output, runner)
PY_SCRIPTS = [
    ("tools/GET_A_JOB.py", "job.py", sys.executable),
    ("tools/SUBMIT_JOB.py", "job.py", sys.executable),
    ("tools/ANSWER_A_WORKERS_QUESTION.py", "job.py", sys.executable),
    ("tools/RETURN_JOB.py", "job.py", sys.executable),
    ("tools/CHECK_THE_JOB_BOARD.py", "job.py", sys.executable),
    ("tools/WAIT_FOR_THE_NEXT_JOB.py", "job.py", sys.executable),
    ("tools/RUN_THE_HOPPER.py", "job.py", sys.executable),
    ("tools/REBUILD_THE_JOB_BOARD.py", "job.py", sys.executable),
    ("tools/MERGE_JOB.py", "integrate.py", sys.executable),
    ("tools/MERGE_THE_BATCH.py", "integrate.py", sys.executable),
    ("tools/HOLD_THE_INTEGRATOR_LOCK.py", "integrator.py", sys.executable),
    ("tools/LAUNCH_A_WORKER.py", "launch.py", sys.executable),
    ("tools/RECORD_A_DECISION.py", "log.py", sys.executable),
    ("tools/PICK_UP_A_TO_DO.py", "log.py", sys.executable),
    ("tools/ADD_A_NOTE_TO_A_DECISION.py", "log.py", sys.executable),
    ("tools/NUMBER_A_NEW_ID.py", "number_ids.py", sys.executable),
    ("tools/WRITE_IN_YOUR_LOG.py", "personal_space.py", sys.executable),
    ("tools/WRITE_IN_YOUR_JOURNAL.py", "personal_space.py", sys.executable),
    ("tools/ARCHIVE_A_FINISHED_JOB.py", "handoff.py", sys.executable),
    ("tools/CHECK_JOBS_DONT_OVERLAP.py", "handoff.py", sys.executable),
    ("tools/COMPARE_TEST_SUITES.py", "compare_suites.py", sys.executable),
    ("tools/CHECK_TYPED_LENGTHS_AGAINST_FREECAD.py", "CHECK_TYPED_LENGTHS_AGAINST_FREECAD.py", sys.executable),
    ("02_Habits/REMEMBER_WHO_YOU_ARE.py", "startup.py", sys.executable),
    ("02_Habits/WHEN_THE_LOG_IS_COMMITTED_TIDY_IT.py", "sort_decision_log.py", sys.executable),
    ("02_Habits/WHEN_WATCHED_CODE_IS_COMMITTED_CHECK_THE_MAP.py", "--staged", sys.executable),
    ("02_Habits/WHEN_MAIN_CHANGES_FILL_THE_TO_DOS.py", "org_todos.py", sys.executable),
]

SH_WRAPPERS = {
    "tools/TEST_YOUR_CODE_FAST.sh": "quicktest.sh",
    "tools/TEST_YOUR_CODE_THOROUGHLY.sh": "fulltest.sh",
    "tools/TEST_WITHOUT_THE_APP.sh": "featuretest.sh",
    "tools/TEST_BEFORE_MERGING.sh": "gate.sh",
    "tools/CHECK_THE_SCRIPTS_PARSE.sh": "parsecheck.sh",
    "tools/START_A_WORKER.sh": "start_worker.sh",
    "tools/BUILD_THE_APP.sh": "build_app.sh",
}

for doc in ("tools/README.md", "02_Habits/README.md"):
    check(f"doc exists: {doc}", os.path.isfile(os.path.join(ROOT, doc)))

other_dir = tempfile.gettempdir()
for rel, needle, runner in PY_SCRIPTS:
    path = os.path.join(ROOT, rel)
    check(f"exists: {rel}", os.path.isfile(path))
    if runner == FC and not os.path.exists(FC):
        continue
    r = subprocess.run([runner, path, "--help"], cwd=other_dir, capture_output=True, text=True, timeout=30)
    out = r.stdout + r.stderr
    check(f"reaches library from another dir: {rel}", r.returncode in (0, 2) and needle in out,
          f"rc={r.returncode} out={out[:120]!r}")

for rel, target in SH_WRAPPERS.items():
    path = os.path.join(ROOT, rel)
    check(f"exists: {rel}", os.path.isfile(path) and os.access(path, os.X_OK))
    syn = subprocess.run(["bash", "-n", path], capture_output=True, text=True)
    text = open(path, encoding="utf-8").read()
    check(f"shell wrapper syntax and target: {rel}", syn.returncode == 0 and f"/{target}" in text, syn.stderr)

r_feat = subprocess.run([os.path.join(ROOT, "tools/TEST_WITHOUT_THE_APP.sh"), "--list"],
                        cwd=other_dir, capture_output=True, text=True, timeout=30)
check("TEST_WITHOUT_THE_APP.sh --list reaches featuretest.sh from another dir",
      r_feat.returncode == 0 and "tools-named_scripts" in r_feat.stdout, r_feat.stderr[:120])

env = dict(os.environ, DRY_RUN="1")
r_start = subprocess.run([os.path.join(ROOT, "tools/START_A_WORKER.sh"), "test-w"],
                         cwd=other_dir, env=env, capture_output=True, text=True, timeout=30)
check("START_A_WORKER.sh DRY_RUN=1 reaches start_worker.sh from another dir",
      r_start.returncode == 0 and "test-w" in r_start.stdout, r_start.stderr[:120])

pre_commit = open(os.path.join(ROOT, ".githooks/pre-commit"), encoding="utf-8").read()
commit_msg = open(os.path.join(ROOT, ".githooks/commit-msg"), encoding="utf-8").read()
check("pre-commit calls WHEN_THE_LOG_IS_COMMITTED_TIDY_IT.py",
      "02_Habits/WHEN_THE_LOG_IS_COMMITTED_TIDY_IT.py" in pre_commit)
check("pre-commit calls WHEN_MAIN_CHANGES_FILL_THE_TO_DOS.py",
      "02_Habits/WHEN_MAIN_CHANGES_FILL_THE_TO_DOS.py" in pre_commit)
check("commit-msg calls WHEN_WATCHED_CODE_IS_COMMITTED_CHECK_THE_MAP.py",
      "02_Habits/WHEN_WATCHED_CODE_IS_COMMITTED_CHECK_THE_MAP.py" in commit_msg)

OLD_COMMANDS = [
    r"tools/job\.py\s+(?:take|done|answer|return|status|watch|board)\b",
    r"tools/integrate\.py\b",
    r"tools/integrator\.py\s+(?:take|note)\b",
    r"tools/launch\.py\b",
    r"tools/log\.py\s+(?:add|pick|note)\b",
    r"tools/number_ids\.py\b",
    r"tools/personal_space\.py\s+(?:log|journal)\b",
    r"tools/handoff\.py\s+(?:archive|overlaps)\b",
    r"python3\s+tools/usage\.py\b",
    r"tools/compare_suites\.py\b",
    r"tools/length_cases\.py\b",
    r"tools/quicktest\.sh\b",
    r"tools/fulltest\.sh\b",
    r"tools/featuretest\.sh\b",
    r"tools/gate\.sh\b",
    r"tools/parsecheck\.sh\b",
    r"tools/start_worker\.sh\b",
    r"tools/build_app\.sh\b",
    r"tools/startup\.py\b",
    r"tools/sort_decision_log\.py\b",
    r"tools/org_todos\.py\b",
]
OLD_RE = re.compile("|".join(OLD_COMMANDS))

LIVE_GUIDES = [
    "CLAUDE.md",
    "AGENTS.md",
    "GEMINI.md",
    "BOARD.md",
    "README.txt",
    "docs/integrator.md",
    "docs/agent-handoff.md",
    "viewport/CLAUDE.md",
    "worker/CLAUDE.md",
    "docs/specs/T88-tool-interface.md",
]

for guide in LIVE_GUIDES:
    text = open(os.path.join(ROOT, guide), encoding="utf-8").read()
    if guide == "docs/agent-handoff.md":
        text = text.split("## Archived", 1)[0]
    if guide == "BOARD.md":
        text = text.split("<!-- job table:", 1)[0]
    # Strip prose references to library modules/hooks that are not commands to run.
    text = text.replace("plus `tools/build_app.sh`", "").replace("runs `tools/number_ids.py`", "")
    hits = OLD_RE.findall(text)
    check(f"live guide has no old tool commands: {guide}", not hits, f"found {hits}")

print(f"NAMED SCRIPTS TESTS: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
