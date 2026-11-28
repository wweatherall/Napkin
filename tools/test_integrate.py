#!/usr/bin/env python3
"""Checks tools/integrate.py and tools/gate.sh on throwaway repositories (P18, P20). Summary line:
INTEGRATE TESTS: N passed, M failed."""
import atexit
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import integrate
import integrator

RESULTS = []
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    if not ok or VERBOSE:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


_TEMPLATE_REPO = None


def _template_repo():
    global _TEMPLATE_REPO
    if _TEMPLATE_REPO is None:
        root = tempfile.mkdtemp(prefix="integrate-tmpl-")
        atexit.register(shutil.rmtree, root, True)
        sh(root, "git", "init", "-q", "-b", "main")
        sh(root, "git", "config", "user.email", "t@example.invalid"); sh(root, "git", "config", "user.name", "t")
        os.makedirs(os.path.join(root, "docs", "handoff"))
        os.makedirs(os.path.join(root, "03_Past_Decisions"))
        open(os.path.join(root, "03_Past_Decisions", "decision-log.md"), "w").write("# Log\n\n## Work list\n\n| # | Item | Status |\n|---|---|---|\n| T1 | a | Open |\n")
        open(os.path.join(root, "docs", "agent-handoff.md"), "w").write("# Handoff\n\n## Open exchanges\n\n<!-- open list: built from docs/handoff/ by tools/handoff.py; don't edit by hand -->\n\n(none open)\n\n<!-- end of open list -->\n\n## Archived\n")
        open(os.path.join(root, "docs", "handoff-archive.md"), "w").write("# Archive\n")
        open(os.path.join(root, "notes.md"), "w").write("one\n")
        sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "base")
        _TEMPLATE_REPO = root
    return _TEMPLATE_REPO


def repo():
    root = tempfile.mkdtemp(prefix="integrate-test-")
    shutil.rmtree(root)
    shutil.copytree(_template_repo(), root)
    return root


# 1. A conflict in a file integrate.py doesn't settle must stop it, before anything is staged.
root = repo()
sh(root, "git", "checkout", "-qb", "agent/x")
open(os.path.join(root, "notes.md"), "w").write("agent\n"); sh(root, "git", "commit", "-qam", "agent edit")
sh(root, "git", "checkout", "-q", "main")
open(os.path.join(root, "notes.md"), "w").write("main\n"); sh(root, "git", "commit", "-qam", "main edit")
integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)
out = io.StringIO()
cwd = os.getcwd(); os.chdir(root)
try:
    with contextlib.redirect_stdout(out):
        rc = integrate.main(["agent/x", "--as", "tester", "--no-gate"])
finally:
    os.chdir(cwd)
check("a conflict in another file stops the merge", rc == 1 and "notes.md" in out.getvalue(), out.getvalue())
check("it is still unmerged afterwards (nothing staged over it)",
      "notes.md" in sh(root, "git", "diff", "--name-only", "--diff-filter=U").stdout)
check("and nothing was committed", sh(root, "git", "log", "--oneline", "-1").stdout.split()[1:3] == ["main", "edit"])
shutil.rmtree(root)

# 2. has_markers finds leftover conflict markers.
tmp = tempfile.mkdtemp(prefix="markers-")
p = os.path.join(tmp, "f.md"); open(p, "w").write("a\n<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> b\n")
q = os.path.join(tmp, "g.md"); open(q, "w").write("a line with ======= in it\n")
check("conflict markers are found", integrate.has_markers(p))
check("an ordinary ======= line isn't a marker", not integrate.has_markers(q))
shutil.rmtree(tmp)


# 3. The gate: a known UI failure never excuses a feature-test failure.
def gate(quick_out, quick_rc, known, full_rc=0, expected_full_args=""):
    root = tempfile.mkdtemp(prefix="gate-test-")
    sh(root, "git", "init", "-q")
    os.makedirs(os.path.join(root, "tools")); os.makedirs(os.path.join(root, "tests"))
    shutil.copy(os.path.join(HERE, "gate.sh"), os.path.join(root, "tools", "gate.sh"))
    open(os.path.join(root, "tools", "quicktest.sh"), "w").write(f"#!/bin/bash\ncat <<'X'\n{quick_out}\nX\nexit {quick_rc}\n")
    open(os.path.join(root, "tools", "fulltest.sh"), "w").write(
        '#!/bin/bash\nprintf "%s" "$*" > full-args\n' + f"exit {full_rc}\n")
    for f in ("quicktest.sh", "fulltest.sh"):
        os.chmod(os.path.join(root, "tools", f), 0o755)
    open(os.path.join(root, "tests", "known_failures.txt"), "w").write(known)
    r = sh(root, "bash", "tools/gate.sh")
    args = open(os.path.join(root, "full-args")).read()
    check("gate full-test mode: " + (expected_full_args or "standalone"), args == expected_full_args, args)
    shutil.rmtree(root)
    return r.returncode, r.stdout


KNOWN = "[hide] View > Hidden geometry shows it ghosted  # T85\n"
HIDE = "QUICK FAIL [hide] View > Hidden geometry shows it ghosted  <Object#null>"
OK_FEAT = "features: NATIVE TESTS: 83 passed, 0 failed | SCENARIO TESTS: 170 passed, 0 failed | viewport: QUICK 152 passed, 1 failed in 11 s"
BAD_FEAT = "features: NATIVE TESTS: 83 passed, 0 failed | SCENARIO TESTS: 169 passed, 1 failed | viewport: QUICK 152 passed, 1 failed in 11 s"
rc, out = gate(HIDE + "\n" + OK_FEAT, 1, KNOWN)
check("a listed UI failure alone passes the gate", rc == 0 and "GATE PASS" in out, out)
rc, out = gate(HIDE + "\n" + BAD_FEAT, 1, KNOWN)
check("a listed UI failure plus a feature-test failure fails the gate (Codex's case)", rc == 1 and "SCENARIO TESTS" in out, out)
rc, out = gate(HIDE + "\n" + OK_FEAT, 1, "")
check("an unlisted UI failure fails the gate", rc == 1 and "NEW FAILURE" in out, out)
rc, out = gate("QUICK 153 passed, 0 failed", 0, "", expected_full_args="")
check("no feature-test summary at all fails the gate", rc == 1 and "no feature-test summary" in out, out)
ALL_OK = OK_FEAT.replace("QUICK 152 passed, 1 failed", "QUICK 153 passed, 0 failed")
rc, out = gate(ALL_OK, 0, "", expected_full_args="--gate-ui-only")
check("a successful quick run reuses its parse and feature checks", rc == 0 and "GATE PASS" in out, out)
rc, out = gate(ALL_OK, 0, "", full_rc=1, expected_full_args="--gate-ui-only")
check("a full-test failure still fails the gate after reuse", rc == 1 and "full test FAILS" in out, out)
rc, out = gate(HIDE + "\n" + OK_FEAT.replace("NATIVE TESTS: 83 passed, 0 failed", "native did not finish"), 1, KNOWN)
check("a listed UI failure cannot excuse an unfinished feature test", rc == 1 and "didn't finish cleanly" in out, out)
rc, out = gate("SCRIPT ERROR: broken\n" + OK_FEAT, 0, "", expected_full_args="")
check("script errors fail the gate and keep full parsing enabled", rc == 1 and "didn't finish cleanly" in out, out)
rc, out = gate(ALL_OK, 1, "")
check("an unexplained quick exit still fails the gate", rc == 1 and "without a QUICK FAIL" in out, out)
check("the real known-failures list holds only failures with an open Work list item",
      all("# T" in l for l in open(os.path.join(HERE, "..", "tests", "known_failures.txt")) if l.strip() and not l.startswith("#")))


# 4. The protocol version: a branch's bump goes on top of main's (A35), and files outside the Touches list are flagged.
def write(root, rel, text):
    os.makedirs(os.path.dirname(os.path.join(root, rel)) or root, exist_ok=True)
    open(os.path.join(root, rel), "w").write(text)


root = repo()
write(root, "worker/serve.py", "PROTOCOL_VERSION = 2\n")
write(root, "viewport/main.gd", "const PROTOCOL_VERSION := 2\n")
write(root, "docs/protocol.md", "The wire protocol's own version is **2** (currently 2).\n")
sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "v2")
sh(root, "git", "checkout", "-qb", "agent/y")
write(root, "worker/serve.py", "PROTOCOL_VERSION = 3\n")
write(root, "viewport/main.gd", "const PROTOCOL_VERSION := 3\n")
write(root, "docs/protocol.md", "The wire protocol's own version is **3** (currently 3).\n")
write(root, "worker/new_op.py", "x = 1\n")
write(root, "viewport/other.gd", "# not in the job\n")
write(root, "docs/handoff/H050-y.md", "### H050 — y\n\nAuthor: Claude | Date: 2026-11-22 | Status: answered\n\n"
      "Touches: worker/serve.py, viewport/main.gd, worker/new_op.py, docs/protocol.md.\n")
sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "branch bumps to 3")
sh(root, "git", "checkout", "-q", "main")
write(root, "worker/serve.py", "PROTOCOL_VERSION = 3\n"); write(root, "viewport/main.gd", "const PROTOCOL_VERSION := 3\n")
write(root, "docs/protocol.md", "The wire protocol's own version is **3** (currently 3).\n")
sh(root, "git", "commit", "-qam", "main bumps to 3")
integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)
out = io.StringIO(); cwd = os.getcwd(); os.chdir(root)
try:
    with contextlib.redirect_stdout(out):
        rc = integrate.main(["agent/y", "--as", "tester", "--no-gate"])
finally:
    os.chdir(cwd)
said = out.getvalue()
check("both bumped 2 -> 3: the branch's lands as 4, both constants and the doc",
      open(os.path.join(root, "worker/serve.py")).read() == "PROTOCOL_VERSION = 4\n"
      and open(os.path.join(root, "viewport/main.gd")).read() == "const PROTOCOL_VERSION := 4\n"
      and "**4**" in open(os.path.join(root, "docs/protocol.md")).read() and "currently 4" in open(os.path.join(root, "docs/protocol.md")).read(), said)
check("it says so", "renumbered" in said or "is 4 on main" in said, said)
check("a file the job doesn't list is flagged, and only that one",
      "OUTSIDE ITS TOUCHES LIST: viewport/other.gd" in said and "new_op.py (" not in said.split("OUTSIDE")[-1], said)
check("the merge went in, and its message records both", rc == 0 and "renumbered to 4" in sh(root, "git", "log", "-1", "--format=%B").stdout
      and "viewport/other.gd" in sh(root, "git", "log", "-1", "--format=%B").stdout, said)
shutil.rmtree(root)

# 5. --job: a scratch branch (main merged into the job's branch first) delivers the job: it is marked merged, and
#    its worktree and its own branch go too; a job not in the queue, or one whose branch isn't in it, is refused.
import json
import job
root = repo()
sh(root, "git", "checkout", "-qb", "claude/h070-x")
write(root, "x.py", "x = 70\n"); sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "H070: x")
sh(root, "git", "checkout", "-q", "main")
write(root, "notes.md", "main moved on\n"); sh(root, "git", "commit", "-qam", "main moves")
wt = root + "-h070"
sh(root, "git", "worktree", "add", "-q", wt, "claude/h070-x")
sh(root, "git", "branch", "scratch/h070", "claude/h070-x")
sh(root, "git", "checkout", "-q", "scratch/h070"); sh(root, "git", "merge", "-q", "--no-edit", "main")
sh(root, "git", "checkout", "-q", "main")
open(job.state_path(root), "w").write(json.dumps({"jobs": {
    "H070": {"branch": "claude/h070-x", "worktree": wt, "state": "done"},
    "H071": {"branch": "other-job", "state": "done"}}, "events": []}))
integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)


def run_integrate(*args):
    out = io.StringIO(); cwd = os.getcwd(); os.chdir(root)
    try:
        with contextlib.redirect_stdout(out):
            rc = integrate.main(list(args))
    finally:
        os.chdir(cwd)
    return rc, out.getvalue()


head0 = sh(root, "git", "rev-parse", "HEAD").stdout
rc, said = run_integrate("scratch/h070", "--as", "tester", "--no-gate", "--job", "H099")
check("--job: a job not in the queue is refused, nothing merged",
      rc == 1 and "no such job" in said and sh(root, "git", "rev-parse", "HEAD").stdout == head0, said)
sh(root, "git", "branch", "other-job", "main")
write(root, "y.py", "y\n"); sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "main again")
sh(root, "git", "branch", "-f", "other-job", "HEAD"); sh(root, "git", "reset", "-q", "--hard", "HEAD~1")
head0 = sh(root, "git", "rev-parse", "HEAD").stdout
rc, said = run_integrate("scratch/h070", "--as", "tester", "--no-gate", "--job", "H071")
check("--job: a job whose branch isn't all in the scratch branch is refused, nothing merged",
      rc == 1 and "isn't all in" in said and sh(root, "git", "rev-parse", "HEAD").stdout == head0, said)
rc, said = run_integrate("scratch/h070", "--as", "tester", "--no-gate", "--job", "H070")
branches = sh(root, "git", "branch").stdout
check("--job: the scratch branch merges and the job is marked merged",
      rc == 0 and job.read_state(job.state_path(root))["jobs"]["H070"]["state"] == "merged", said)
check("--job: the job's worktree and its own branch are removed, and the scratch branch",
      not os.path.isdir(wt) and "claude/h070-x" not in branches and "scratch/h070" not in branches, said + branches)
shutil.rmtree(root)

# 6. A BOARD.md conflict (H073): main's Order line, job table and Notes stay; the branch's edits to the other
#    sections come with it; both changing one section stops the merge.
BOARD = ("# Work board\n\nIntro.\n\nOrder: H001\n\n## If you're not the integrator\n\n1. Take a job.\n\n"
         "## If you're the integrator\n\nSee integrator.md.\n\n## Jobs\n\n| Job |\n|---|\n| H001 |\n\n## Notes\n\n- one\n")
main_b = BOARD.replace("Order: H001", "Order: H001, H002").replace("| H001 |", "| H001 |\n| H002 |").replace("- one", "- main's note")
branch_b = BOARD.replace("1. Take a job.", "1. Take a job, then read its Notes.").replace("- one", "- branch's note")
text, clashes = integrate.settle_board(main_b, BOARD, branch_b)
check("board: the branch's instructions and main's Order, table and Notes all stay",
      clashes == [] and "1. Take a job, then read its Notes." in text and "Order: H001, H002" in text
      and "| H002 |" in text and "- main's note" in text and "branch's note" not in text, text)
added = branch_b.replace("## Jobs", "## Tips\n\nA tip.\n\n## Jobs")
text, _ = integrate.settle_board(main_b, BOARD, added)
check("board: a section the branch adds goes in where the branch put it",
      text.index("See integrator.md.") < text.index("## Tips") < text.index("## Jobs"), text)
text, _ = integrate.settle_board(main_b, BOARD, BOARD)
check("board: a branch that changed nothing leaves main's file as it is", text == main_b, text)
both = main_b.replace("1. Take a job.", "1. Take one job.")
text, clashes = integrate.settle_board(both, BOARD, branch_b)
check("board: both changing the same section is reported", clashes == ["If you're not the integrator"], clashes)

root = repo()
write(root, "BOARD.md", BOARD); sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "board")
sh(root, "git", "checkout", "-qb", "agent/b")
write(root, "BOARD.md", branch_b); sh(root, "git", "commit", "-qam", "branch edits the board")
sh(root, "git", "checkout", "-q", "main")
write(root, "BOARD.md", main_b); sh(root, "git", "commit", "-qam", "main edits the board")
integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)
rc, said = run_integrate("agent/b", "--as", "tester", "--no-gate")
board = open(os.path.join(root, "BOARD.md")).read()
check("board merge: the branch's instructions and main's Notes are both in the merge",
      rc == 0 and "1. Take a job, then read its Notes." in board and "- main's note" in board
      and "<<<<<<<" not in board and "settled BOARD.md" in said, said + board)
sh(root, "git", "checkout", "-qb", "agent/c", "HEAD~1")
write(root, "BOARD.md", main_b.replace("1. Take a job, then read its Notes.", "x").replace("1. Take a job.", "1. Take two jobs.")
      .replace("- main's note", "- c's note"))
sh(root, "git", "commit", "-qam", "c edits the same section")
sh(root, "git", "checkout", "-q", "main")
head0 = sh(root, "git", "rev-parse", "HEAD").stdout
rc, said = run_integrate("agent/c", "--as", "tester", "--no-gate")
check("board merge: both editing the same section stops it, nothing committed",
      rc == 1 and "both changed" in said and "If you're not the integrator" in said
      and sh(root, "git", "rev-parse", "HEAD").stdout == head0, said)
sh(root, "git", "merge", "--abort")
shutil.rmtree(root)

# 6b. A clean BOARD.md merge (H091): main's Order line, job table and Notes still stay when git merges without conflict.
root = repo()
write(root, "BOARD.md", BOARD); sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "board")
sh(root, "git", "checkout", "-qb", "agent/clean-notes")
write(root, "BOARD.md", BOARD.replace("- one", "- branch's note"))
sh(root, "git", "commit", "-qam", "branch edits notes cleanly")
sh(root, "git", "checkout", "-q", "main")
integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)
rc, said = run_integrate("agent/clean-notes", "--as", "tester", "--no-gate")
board = open(os.path.join(root, "BOARD.md")).read()
check("board clean merge: branch changing only Notes keeps main's Notes and names the Notes",
      rc == 0 and "- one" in board and "- branch's note" not in board and "settled BOARD.md" not in said
      and "kept main's Order line, job table and Notes in BOARD.md (the branch had changed the Notes)" in said,
      said + board)

sh(root, "git", "checkout", "-qb", "agent/clean-all")
write(root, "BOARD.md", BOARD.replace("Order: H001", "Order: H001, H099")
      .replace("| H001 |", "| H001 |\n| H099 |").replace("- one", "- branch's note"))
sh(root, "git", "commit", "-qam", "branch edits order, table and notes cleanly")
sh(root, "git", "checkout", "-q", "main")
rc, said = run_integrate("agent/clean-all", "--as", "tester", "--no-gate")
board = open(os.path.join(root, "BOARD.md")).read()
check("board clean merge: branch changing Order, job table and Notes keeps main's and names all three",
      rc == 0 and board == BOARD and "settled BOARD.md" not in said
      and "kept main's Order line, job table and Notes in BOARD.md (the branch had changed the Order line, the job table, the Notes)" in said,
      said + board)

sh(root, "git", "checkout", "-qb", "agent/order-and-step")
write(root, "BOARD.md", BOARD.replace("Order: H001", "Order: H001, H099")
      .replace("1. Take a job.", "1. Take a job, then read its Notes."))
sh(root, "git", "commit", "-qam", "branch edits order and worker step")
sh(root, "git", "checkout", "-q", "main")
write(root, "BOARD.md", BOARD.replace("- one", "- main's note"))
sh(root, "git", "commit", "-qam", "main edits notes")
rc, said = run_integrate("agent/order-and-step", "--as", "tester", "--no-gate")
board = open(os.path.join(root, "BOARD.md")).read()
check("board clean merge: branch changing Order and a worker step while main changes Notes keeps main's Order and Notes and the branch's step, naming only the Order line",
      rc == 0 and "Order: H001\n" in board and "Order: H001, H099" not in board and "- main's note" in board
      and "1. Take a job, then read its Notes." in board and "settled BOARD.md" not in said
      and "kept main's Order line, job table and Notes in BOARD.md (the branch had changed the Order line)" in said,
      said + board)

sh(root, "git", "checkout", "-qb", "agent/only-step")
write(root, "BOARD.md", board.replace("1. Take a job, then read its Notes.", "1. Take a job, read Notes, run tests."))
sh(root, "git", "commit", "-qam", "branch edits only worker step")
sh(root, "git", "checkout", "-q", "main")
rc, said = run_integrate("agent/only-step", "--as", "tester", "--no-gate")
board2 = open(os.path.join(root, "BOARD.md")).read()
check("board clean merge: branch changing only a worker step merges it with no kept-main message",
      rc == 0 and "1. Take a job, read Notes, run tests." in board2 and "kept main's" not in said
      and "settled BOARD.md" not in said, said + board2)

sh(root, "git", "checkout", "-qb", "agent/no-board")
write(root, "notes.md", "other change\n")
sh(root, "git", "commit", "-qam", "branch does not touch BOARD.md")
sh(root, "git", "checkout", "-q", "main")
rc, said = run_integrate("agent/no-board", "--as", "tester", "--no-gate")
check("board clean merge: branch not touching BOARD.md leaves it untouched and says nothing",
      rc == 0 and open(os.path.join(root, "BOARD.md")).read() == board2 and "kept main's" not in said, said)
shutil.rmtree(root)

# 7. Trace the actual steps through main(), including the map pause and --continue. The names below are
#    the documented order, independent of the production tuples. Wrappers still run each step's real work.
MERGE_ORDER = ["check_start", "prepare_log", "merge_branch", "settle_conflicts", "check_touches", "number_entries",
               "archive_entries", "update_statuses", "rebuild_and_check", "run_gate", "check_structure", "pause_for_map"]
FINISH_ORDER = ["commit_merge", "clean_up_job", "unblock_queued_jobs", "record_results", "push_main"]


@contextlib.contextmanager
def trace_steps():
    calls, states = [], []

    def wrap(step):
        def traced(state):
            calls.append(step.__name__)
            states.append(state)
            returned = step(state)
            if returned is not state:
                raise AssertionError(f"{step.__name__} didn't return its run state")
            return returned
        return traced

    with patch.object(integrate, "MERGE_STEPS", tuple(wrap(f) for f in integrate.MERGE_STEPS)), \
         patch.object(integrate, "FINISH_STEPS", tuple(wrap(f) for f in integrate.FINISH_STEPS)), \
         patch.object(integrate, "load_continuation", wrap(integrate.load_continuation)):
        yield calls, states


def ordered_repo(gate_rc=0):
    root = repo()
    write(root, "ARCHITECTURE.md", "# Map\n")
    # A real subprocess gate, with a visible verdict; no actual remote is needed for these merge checks.
    write(root, "tools/gate.sh", f"#!/bin/sh\necho GATE {'PASS' if not gate_rc else 'FAIL'}\nexit {gate_rc}\n")
    os.chmod(os.path.join(root, "tools/gate.sh"), 0o755)
    sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "map and gate")
    sh(root, "git", "checkout", "-qb", "agent/ordered")
    write(root, "notes.md", "ordered change\n")
    write(root, "docs/handoff/H080-ordered.md",
          "### H080 — T1: ordered merge\n\nAuthor: Codex | Status: answered\n\n"
          "Architecture: update the map.\nResult: abc1234; fixture checks; ordered change\n")
    sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "ordered branch")
    sh(root, "git", "checkout", "-q", "main")
    integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)
    return root


root = ordered_repo()
with trace_steps() as (calls, states):
    rc, said = run_integrate("agent/ordered", "--as", "tester", "--impact", "fixture")
check("main runs every named step in documented order", rc == 0 and calls == MERGE_ORDER + FINISH_ORDER, calls)
check("each step takes and returns the same run state", len({id(s) for s in states}) == 1)
check("the ordered run gates, commits, and records the merge result",
      "GATE PASS" in said and "Result (abc1234, merged" in open(os.path.join(root, "03_Past_Decisions/decision-log.md")).read()
      and not os.path.exists(integrate.state_file(root)), said)
shutil.rmtree(root)

root = ordered_repo()
head0 = sh(root, "git", "rev-parse", "HEAD").stdout
with trace_steps() as (calls, _):
    rc, said = run_integrate("agent/ordered", "--as", "tester")
check("the map pause stops after the gate, before commit or cleanup",
      rc == 0 and calls == MERGE_ORDER and "GATE PASS" in said and "staged, not committed" in said
      and sh(root, "git", "rev-parse", "HEAD").stdout == head0 and os.path.isfile(integrate.state_file(root)), said + str(calls))
with trace_steps() as (calls, _):
    rc, said = run_integrate("--continue", "--as", "tester")
check("continue without a map edit stops at continuation validation",
      rc == 1 and calls == ["load_continuation"] and "aren't changed yet" in said, said + str(calls))
write(root, "ARCHITECTURE.md", "# Map\n\nUpdated after review.\n")
sh(root, "git", "add", "ARCHITECTURE.md")
with trace_steps() as (calls, states):
    rc, said = run_integrate("--continue", "--as", "tester")
check("continue runs only validation and the shared steps after the pause",
      rc == 0 and calls == ["load_continuation"] + FINISH_ORDER and "GATE PASS" not in said
      and len({id(s) for s in states}) == 1 and not os.path.exists(integrate.state_file(root)), said + str(calls))
check("continue includes the reviewed map and records the merge result",
      "Updated after review." in sh(root, "git", "show", "HEAD:ARCHITECTURE.md").stdout
      and "Result (abc1234, merged" in open(os.path.join(root, "03_Past_Decisions/decision-log.md")).read(), said)
shutil.rmtree(root)

root = ordered_repo(gate_rc=1)
head0 = sh(root, "git", "rev-parse", "HEAD").stdout
with trace_steps() as (calls, _):
    rc, said = run_integrate("agent/ordered", "--as", "tester")
check("a failed gate stops before the map pause and every finishing step",
      rc == 1 and calls == MERGE_ORDER[:MERGE_ORDER.index("run_gate") + 1] and "GATE FAIL" in said
      and sh(root, "git", "rev-parse", "HEAD").stdout == head0
      and os.path.exists(integrate.state_file(root)), said + str(calls))
shutil.rmtree(root)

# 8. Live gate progress streaming (H088): progress lines arrive before the gate ends; non-progress lines are held
#    until the failure tail; verdict and the 2000-char failure tail stay as before.
def run_integrate_live(repo_root, args, release_on, release_path):
    env = dict(os.environ, RELEASE=release_path)
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "integrate.py"), *args],
                         cwd=repo_root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    lines, before_release, alive = [], None, False
    for raw in p.stdout:
        line = raw.rstrip("\r\n")
        lines.append(line)
        if before_release is None and line == release_on:
            alive = p.poll() is None
            before_release = list(lines)
            open(release_path, "w").close()
    rc = p.wait(timeout=15)
    return rc, lines, before_release, alive


root = ordered_repo()
release = os.path.join(root, ".release-pass")
write(root, "tools/gate.sh", """#!/bin/bash
echo "noise before"
echo "gate: quick test started"
echo "quick: parse started"
for ((i=0; i<100; i++)); do [ -f "$RELEASE" ] && break; sleep 0.05; done
if [ ! -f "$RELEASE" ]; then echo "STUB TIMED OUT"; exit 2; fi
echo "noise middle"
echo "quick: parse passed in 1 s"
echo "gate: quick test passed in 1 s"
echo "gate: full test started"
echo "full: viewport suites started"
echo "full: viewport suites passed in 1 s"
echo "gate: full test passed in 1 s"
echo "GATE PASS: stub passed"
""")
os.chmod(os.path.join(root, "tools/gate.sh"), 0o755)
sh(root, "git", "add", "tools/gate.sh"); sh(root, "git", "commit", "-qm", "live gate stub")
rc, lines, before_release, alive = run_integrate_live(
    root, ["agent/ordered", "--as", "tester", "--impact", "fixture"], "quick: parse started", release)
expected_progress = [
    "gate: quick test started",
    "quick: parse started",
    "quick: parse passed in 1 s",
    "gate: quick test passed in 1 s",
    "gate: full test started",
    "full: viewport suites started",
    "full: viewport suites passed in 1 s",
    "gate: full test passed in 1 s",
]
got_progress = [l for l in lines if l.startswith(("gate: ", "quick: ", "full: "))]
check("run_gate relays the first progress line before the gate ends",
      rc == 0 and alive and before_release is not None and "gate: quick test started" in before_release,
      (rc, alive, before_release, lines))
check("run_gate relays gate:, quick: and full: progress lines in order, then says the verdict",
      got_progress == expected_progress and "integrate: GATE PASS: stub passed" in lines
      and lines.index(expected_progress[-1]) < lines.index("integrate: GATE PASS: stub passed"), lines)
check("run_gate does not print non-progress lines live on a passing gate",
      "noise before" not in lines and "noise middle" not in lines, lines)
shutil.rmtree(root)

root = ordered_repo()
release = os.path.join(root, ".release-fail")
write(root, "tools/gate.sh", f"""#!/bin/bash
echo "early-marker-trimmed"
"{sys.executable}" -c 'print("x" * 2100)'
echo "noise before fail"
echo "quick: parse started"
for ((i=0; i<100; i++)); do [ -f "$RELEASE" ] && break; sleep 0.05; done
if [ ! -f "$RELEASE" ]; then echo "STUB TIMED OUT"; exit 2; fi
echo "stderr-detail-line" >&2
echo "quick: parse failed in 1 s"
echo "GATE FAIL: stub failed"
exit 1
""")
os.chmod(os.path.join(root, "tools/gate.sh"), 0o755)
sh(root, "git", "add", "tools/gate.sh"); sh(root, "git", "commit", "-qm", "failing live gate stub")
head0 = sh(root, "git", "rev-parse", "HEAD").stdout
rc, lines, before_release, alive = run_integrate_live(
    root, ["agent/ordered", "--as", "tester", "--impact", "fixture"], "quick: parse started", release)
verdict_idx = lines.index("integrate: GATE FAIL: stub failed") if "integrate: GATE FAIL: stub failed" in lines else -1
tail_text = "\n".join(lines[verdict_idx + 1:]) if verdict_idx >= 0 else ""
check("a failing gate streams progress live without leaking non-progress lines first",
      rc == 1 and alive and before_release is not None
      and "noise before fail" not in before_release and "early-marker-trimmed" not in before_release,
      (rc, alive, before_release, lines))
check("a failing gate says the verdict, prints the last 2000 chars of output, and leaves the merge uncommitted",
      verdict_idx >= 0 and "noise before fail" in tail_text and "stderr-detail-line" in tail_text
      and "early-marker-trimmed" not in tail_text and lines[-1].startswith("integrate: the merge is left uncommitted")
      and sh(root, "git", "rev-parse", "HEAD").stdout == head0, (verdict_idx, lines[-10:]))
shutil.rmtree(root)

# 9. Result step prints one short line per item (cut to 160 chars with … if longer), then the commit's oneline,
#    instead of the word diff of the whole Work list row (H104).
root = repo()
old_history = "Long pre-existing T1 history paragraph that should not be reprinted at merge."
write(root, "03_Past_Decisions/decision-log.md",
      f"# Log\n\n## Work list\n\n| # | Item | Status | Notes |\n|---|---|---|---|\n"
      f"| T1 | a | Open | {old_history} |\n"
      f"| T2 | b | Open | |\n")
sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "long history row")
sh(root, "git", "checkout", "-qb", "agent/long-result")
long_text = "tests 50/50; " + ("detailed summary of many changes " * 7).strip()
short_text = "tests 3/3; short fix"
assert len(long_text) > 160
write(root, "docs/handoff/H081-long.md",
      f"### H081 — T1: long result\n\nAuthor: Gemini | Status: answered\n\n"
      f"Result: 1111aaa; {long_text}\n")
write(root, "docs/handoff/H082-short.md",
      f"### H082 — T2: short result\n\nAuthor: Gemini | Status: answered\n\n"
      f"Result: 2222bbb; {short_text}\n")
sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "H081 + H082 results")
sh(root, "git", "checkout", "-q", "main")
integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)
rc, said = run_integrate("agent/long-result", "--as", "tester", "--no-gate")
merge_sha = sh(root, "git", "rev-parse", "--short", "HEAD~1").stdout.strip()
result_oneline = sh(root, "git", "log", "--oneline", "-1").stdout.strip()
expected_long_cut = (long_text + ".")[:159] + "…"
expected_long_line = f"T1 (H081): Result (1111aaa, merged {merge_sha}): {expected_long_cut}"
expected_short_line = f"T2 (H082): Result (2222bbb, merged {merge_sha}): {short_text}."
out_lines = said.splitlines()
check("result step prints a long Result cut to 160 chars with … and a short Result intact",
      rc == 0 and expected_long_line in out_lines and expected_short_line in out_lines
      and len(expected_long_cut) == 160, (said, expected_long_line, expected_short_line))
check("result step prints the commit's oneline after the summary lines, with no word diff or old row text",
      f"integrate: committed {result_oneline}" in out_lines
      and out_lines.index(expected_long_line) < out_lines.index(f"integrate: committed {result_oneline}")
      and "{+" not in said and old_history not in said, said)
log_now = open(os.path.join(root, "03_Past_Decisions/decision-log.md")).read()
check("the result commit itself still writes the full uncut Result text to the Work list row",
      f"Result (1111aaa, merged {merge_sha}, step merged (H081)): {long_text}." in log_now
      and f"Result (2222bbb, merged {merge_sha}, step merged (H082)): {short_text}." in log_now, log_now)
shutil.rmtree(root)

# 10. Changed from the brief (P44): scoped to the response (outside code blocks), stops staged before commit
#     (even with --yes), combines with the map pause into one stop, and records each change in the merge commit.
brief_with_quote = (
    "### H083 — T1: brief quoting the phrase\n\nAuthor: Claude | Status: answered\n\n"
    "Request: add a `Changed from the brief:` line per departure:\n"
    "Response: a table of what changed.\n"
    "Changed from the brief: example in the brief itself\n"
    "- Changed from the brief: bulleted example in the brief\n"
)
check("changed_from_brief ignores lines in the brief before the Response heading",
      integrate.changed_from_brief(brief_with_quote) == []
      and integrate.changed_from_brief(brief_with_quote + "\nResponse — Gemini, 2026-11-23:\nDone.\n") == [],
      integrate.changed_from_brief(brief_with_quote))
code_block_resp = (
    brief_with_quote
    + "\n**Response — Gemini, 2026-11-23**\n\n"
    "```markdown\nChanged from the brief: inside backtick fence\n```\n"
    "~~~\n- Changed from the brief: inside tilde fence\n~~~\n"
    "> Changed from the brief: quoted line\n"
    "Changed from the brief: kept line one  \n"
    "- Changed from the brief: kept line two\n"
)
check("changed_from_brief parses plain and bulleted lines in the response and ignores fenced code blocks and quotes",
      integrate.changed_from_brief(code_block_resp) == ["kept line one", "kept line two"],
      integrate.changed_from_brief(code_block_resp))


wrapped_response = (
    "#### Response — Codex\n\n"
    "Changed from the brief: brief said A;\n"
    "  did B;\n"
    "  A broke C\n"
    "- Architecture: the new owner is\n"
    "  notes.md\n\n"
    "Changed from the brief: kept on one line\n \t\n"
    "This prose is outside the field.\n\n"
    "Follow-up: revisit the\n"
    "  remaining checks\n"
    "For the integrator: update the map\n"
    "  on merge\n"
    "Result: abc1234; tests pass; checks added"
)
check("wrapped Changed stops at Architecture; single-line Changed stops at blank line",
      integrate.changed_from_brief(wrapped_response) == ["brief said A; did B; A broke C", "kept on one line"])
check("wrapped Architecture is joined",
      integrate.architecture(wrapped_response) == ["the new owner is notes.md"])
check("wrapped Follow-up stops at For the integrator",
      integrate.follow_ups(wrapped_response) == ["revisit the remaining checks"])
check("wrapped For the integrator stops at Result",
      integrate.for_integrator(wrapped_response) == ["update the map on merge"])
check("response headings accept ATX, bold, em dash and Response from",
      all(integrate.changed_from_brief(f"{heading}\nChanged from the brief: a change at EOF") == ["a change at EOF"]
          for heading in ("#### Response", "**Response**", "Response — Codex", "Response from Codex:")))


def brief_repo(entry_text, branch_name="agent/p44", with_map=False, with_remote=False):
    root = repo()
    if with_map:
        write(root, "ARCHITECTURE.md", "# Map\n")
        sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "add map")
    bare = None
    if with_remote:
        bare = tempfile.mkdtemp(prefix="p44-remote-")
        sh(bare, "git", "init", "-q", "--bare")
        sh(root, "git", "remote", "add", "origin", bare)
        sh(root, "git", "push", "-q", "origin", "main")
    sh(root, "git", "checkout", "-qb", branch_name)
    write(root, "notes.md", f"change on {branch_name}\n")
    write(root, "docs/handoff/H083-p44.md", entry_text)
    sh(root, "git", "add", "-A"); sh(root, "git", "commit", "-qm", "H083 work")
    sh(root, "git", "checkout", "-q", "main")
    integrator.take(integrator.lock_path(root), "tester", out=lambda *a: None)
    return root, bare


# 10a. Brief quotes the phrase and response has it only inside a code block: no stop, merges cleanly.
root, _ = brief_repo(
    brief_with_quote
    + "\nResponse — Gemini, 2026-11-23:\nDone.\n\n```text\nChanged from the brief: sample in code block\n```\n"
)
rc, said = run_integrate("agent/p44", "--as", "tester", "--no-gate")
merge_body = sh(root, "git", "log", "-1", "--format=%B").stdout
check("brief quoting the phrase and response with only a fenced example merges with no stop",
      rc == 0 and "staged, not committed" not in said and "Changed from the brief (" not in merge_body
      and not os.path.exists(integrate.state_file(root)), said + merge_body)
shutil.rmtree(root)

# 10b. Branch with no Changed from the brief line at all merges with no stop.
root, _ = brief_repo(
    "### H083 — T1: plain job\n\nAuthor: Claude | Status: answered\n\n"
    "Request: ordinary task.\n\nResponse — Gemini, 2026-11-23:\nDone.\n"
)
rc, said = run_integrate("agent/p44", "--as", "tester", "--no-gate")
check("branch with no Changed from the brief line merges with no stop",
      rc == 0 and "staged, not committed" not in said and "changed:" not in said
      and not os.path.exists(integrate.state_file(root)), said)
shutil.rmtree(root)

# 10c. Branch with Changed from the brief lines stops staged even with --push --yes; --continue with nothing else
#      changed commits with each line in the merge commit message.
root, bare = brief_repo(
    "### H083 — T1: departed job\n\nAuthor: Claude | Status: answered\n\n"
    "Request: do X.\n\nResponse — Gemini, 2026-11-23:\nDone.\n\n"
    "Changed from the brief: brief said A;\n  did B;\n  A broke C\n"
    "- Changed from the brief: updated test_foo.py; asserted old text; P46\n"
    "Result: abc1234; test_integrate passes; departed cleanly\n",
    with_remote=True,
)
head0 = sh(root, "git", "rev-parse", "HEAD").stdout.strip()
rc, said = run_integrate("agent/p44", "--as", "tester", "--no-gate", "--push", "--yes")
idx = said.find("for you now:")
expected_p44_msg = (
    'the merge is staged, not committed (P44): check each change from the brief above; accept with '
    'python3 tools/MERGE_JOB.py --continue --as tester --push --yes, or put the job back with '
    'python3 tools/RETURN_JOB.py H083 "<notes>"'
)
check("Changed from the brief stops staged even with --yes, prints under 'for you now:' and gives P44 message",
      rc == 0 and idx >= 0
      and "  H083: changed: brief said A; did B; A broke C" in said[idx:]
      and "  H083: changed: updated test_foo.py; asserted old text; P46" in said[idx:]
      and expected_p44_msg in said
      and sh(root, "git", "rev-parse", "HEAD").stdout.strip() == head0
      and sh(root, "git", "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0
      and sh(bare, "git", "rev-parse", "main").stdout.strip() == head0, said)
rc, said = run_integrate("--continue", "--as", "tester")
merge_sha = sh(root, "git", "log", "-1", "--format=%H", "--merges").stdout.strip()
merge_body = sh(root, "git", "log", "-1", "--format=%B", merge_sha).stdout
check("--continue after P44 stop with nothing else changed commits with the changes in the merge commit message",
      rc == 0 and "Changed from the brief (H083): brief said A; did B; A broke C" in merge_body
      and "Changed from the brief (H083): updated test_foo.py; asserted old text; P46" in merge_body
      and not os.path.exists(integrate.state_file(root))
      and "agent/p44" not in sh(root, "git", "branch").stdout, said + merge_body)
shutil.rmtree(root); shutil.rmtree(bare)

# 10d. Both Architecture and Changed from the brief: one stop listing both; --continue after map edit commits both.
root, _ = brief_repo(
    "### H083 — T1: map and brief change\n\nAuthor: Claude | Status: answered\n\n"
    "Request: do X.\n\nResponse — Gemini, 2026-11-23:\nDone.\n\n"
    "Architecture: notes.md owns the note\n"
    "Changed from the brief: brief said X; did Y; Y serves the purpose\n"
    "Result: def5678; tests pass; map and departure\n",
    with_map=True,
)
head0 = sh(root, "git", "rev-parse", "HEAD").stdout.strip()
rc, said = run_integrate("agent/p44", "--as", "tester", "--no-gate")
idx = said.find("for you now:")
check("both map and brief changes produce one stop listing both under 'for you now:'",
      rc == 0 and idx >= 0
      and "  H083: map: notes.md owns the note" in said[idx:]
      and "  H083: changed: brief said X; did Y; Y serves the purpose" in said[idx:]
      and "(P28)" in said and "(P44)" in said
      and sh(root, "git", "rev-parse", "HEAD").stdout.strip() == head0, said)
rc, said = run_integrate("--continue", "--as", "tester")
check("with both map and brief changes, --continue still requires the map edit",
      rc == 1 and "aren't changed yet" in said, said)
write(root, "ARCHITECTURE.md", "# Map\n\nnotes.md owns the note.\n")
sh(root, "git", "add", "ARCHITECTURE.md")
rc, said = run_integrate("--continue", "--as", "tester")
merge_sha = sh(root, "git", "log", "-1", "--format=%H", "--merges").stdout.strip()
merge_body = sh(root, "git", "log", "-1", "--format=%B", merge_sha).stdout
check("after map edit, one --continue commits both the map and the Changed from the brief line",
      rc == 0 and "notes.md owns the note." in sh(root, "git", "show", f"{merge_sha}:ARCHITECTURE.md").stdout
      and "Changed from the brief (H083): brief said X; did Y; Y serves the purpose" in merge_body
      and not os.path.exists(integrate.state_file(root)), said + merge_body)
shutil.rmtree(root)

# 10e. Architecture + Changed from the brief with --impact: stops once for P44 only, --continue keeps --impact.
root, _ = brief_repo(
    "### H083 — T1: impact plus brief change\n\nAuthor: Claude | Status: answered\n\n"
    "Request: do X.\n\nResponse — Gemini, 2026-11-23:\nDone.\n\n"
    "Architecture: notes.md owns the note\n"
    "Changed from the brief: brief said X; did Y; Y serves the purpose\n",
    with_map=True,
)
rc, said = run_integrate("agent/p44", "--as", "tester", "--no-gate", "--impact", "no architecture change needed")
check("with --impact and brief changes, stops for P44 only (not P28)",
      rc == 0 and "(P44)" in said and "(P28)" not in said and "  H083: changed:" in said, said)
rc, said = run_integrate("--continue", "--as", "tester")
merge_body = sh(root, "git", "log", "-1", "--format=%B").stdout
check("--continue without repeating --impact commits with both the brief change and Architecture-Impact",
      rc == 0 and "Changed from the brief (H083): brief said X; did Y; Y serves the purpose" in merge_body
      and "Architecture-Impact: none - no architecture change needed" in merge_body, said + merge_body)
shutil.rmtree(root)

# 11. Passive job-usage merge hook in clean_up_job (H124 / T117).
usage_tmp = tempfile.mkdtemp(prefix="integrate-usage-")
usage_log = os.path.join(usage_tmp, "usage.log")
usage_stub = os.path.join(usage_tmp, "usage_stub.py")
open(usage_stub, "w").write(
    f"import json, sys\n"
    f"with open({usage_log!r}, 'a', encoding='utf-8') as f:\n"
    f"    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
)
usage_fail = os.path.join(usage_tmp, "usage_fail.py")
open(usage_fail, "w").write("import sys\nsys.exit(1)\n")
usage_missing = os.path.join(usage_tmp, "no_such_usage_tool.py")


def usage_merge_repo(jid, branch, with_scratch=False):
    r = repo()
    sh(r, "git", "checkout", "-qb", branch)
    write(r, f"{jid.lower()}.py", f"x = '{jid}'\n")
    sh(r, "git", "add", "-A"); sh(r, "git", "commit", "-qm", f"{jid}: work")
    sh(r, "git", "checkout", "-q", "main")
    if with_scratch:
        write(r, "notes.md", "main moved\n"); sh(r, "git", "commit", "-qam", "main moves")
        scratch = f"scratch/{jid.lower()}"
        sh(r, "git", "branch", scratch, branch)
        sh(r, "git", "checkout", "-q", scratch); sh(r, "git", "merge", "-q", "--no-edit", "main")
        sh(r, "git", "checkout", "-q", "main")
    open(job.state_path(r), "w").write(json.dumps({"jobs": {jid: {"branch": branch, "state": "done"}}, "events": []}))
    integrator.take(integrator.lock_path(r), "tester", out=lambda *a: None)
    return r


root = usage_merge_repo("H090", "claude/h090-u")
with patch.dict(os.environ, {"NAPKIN_USAGE_TOOL": usage_stub}):
    rc, said = run_integrate("claude/h090-u", "--as", "tester", "--no-gate")
u_calls = [json.loads(l) for l in open(usage_log, encoding="utf-8").read().splitlines()] if os.path.isfile(usage_log) else []
check("usage hook: merge calls NAPKIN_USAGE_TOOL with --repo <tmp_root>, --event merge, --job, and no --quiet",
      rc == 0 and len(u_calls) == 1
      and u_calls[0] == ["--repo", os.path.realpath(root), "snapshot", "--event", "merge", "--job", "H090"]
      and "--quiet" not in u_calls[0] and u_calls[0][1] != job.main_root(HERE), (rc, u_calls, said))
shutil.rmtree(root)

open(usage_log, "w").close()
root = usage_merge_repo("H091", "claude/h091-u", with_scratch=True)
with patch.dict(os.environ, {"NAPKIN_USAGE_TOOL": usage_stub}):
    rc, said = run_integrate("scratch/h091", "--as", "tester", "--no-gate", "--job", "H091")
u_calls = [json.loads(l) for l in open(usage_log, encoding="utf-8").read().splitlines()] if os.path.isfile(usage_log) else []
check("usage hook: --job scratch merge calls NAPKIN_USAGE_TOOL once for the merged job without --quiet",
      rc == 0 and len(u_calls) == 1
      and u_calls[0] == ["--repo", os.path.realpath(root), "snapshot", "--event", "merge", "--job", "H091"],
      (rc, u_calls, said))
shutil.rmtree(root)

root = usage_merge_repo("H092", "claude/h092-u")
with patch.dict(os.environ, {"NAPKIN_USAGE_TOOL": usage_missing}):
    rc, said = run_integrate("claude/h092-u", "--as", "tester", "--no-gate")
check("usage hook: merge succeeds with a missing NAPKIN_USAGE_TOOL path",
      rc == 0 and job.read_state(job.state_path(root))["jobs"]["H092"]["state"] == "merged", (rc, said))
shutil.rmtree(root)

root = usage_merge_repo("H093", "claude/h093-u")
with patch.dict(os.environ, {"NAPKIN_USAGE_TOOL": usage_fail}):
    rc, said = run_integrate("claude/h093-u", "--as", "tester", "--no-gate")
check("usage hook: merge succeeds when NAPKIN_USAGE_TOOL exits 1 (fail-open)",
      rc == 0 and job.read_state(job.state_path(root))["jobs"]["H093"]["state"] == "merged", (rc, said))
shutil.rmtree(root)

root = usage_merge_repo("H094", "claude/h094-u")
orig_sub_run = job.subprocess.run


def fail_usage_run(cmd, *a, **k):
    if isinstance(cmd, (list, tuple)) and usage_stub in cmd:
        raise OSError("usage boom")
    return orig_sub_run(cmd, *a, **k)


with patch.dict(os.environ, {"NAPKIN_USAGE_TOOL": usage_stub}), \
     patch.object(job.subprocess, "run", side_effect=fail_usage_run):
    rc, said = run_integrate("claude/h094-u", "--as", "tester", "--no-gate")
check("usage hook: merge succeeds when NAPKIN_USAGE_TOOL raises (fail-open)",
      rc == 0 and job.read_state(job.state_path(root))["jobs"]["H094"]["state"] == "merged", (rc, said))
shutil.rmtree(root)
shutil.rmtree(usage_tmp)

# --- Auto-unblock queued jobs on merge and push (H146 / T130) ---
ub_base = tempfile.mkdtemp(prefix="integrate-unblock-")
ub_bare = os.path.join(ub_base, "origin.git")
sh(ub_base, "git", "init", "--bare", "-q", "-b", "main", ub_bare)
ub_root = os.path.join(ub_base, "repo")
sh(ub_base, "git", "clone", "-q", ub_bare, ub_root)
sh(ub_root, "git", "config", "user.email", "t@example.invalid"); sh(ub_root, "git", "config", "user.name", "t")
sh(ub_root, "git", "checkout", "-qb", "main")
os.makedirs(os.path.join(ub_root, "docs", "handoff"))
write(ub_root, "03_Past_Decisions/decision-log.md", "# Log\n\n## Work list\n\n| # | Item | Status |\n|---|---|---|\n| T126 | a | Open |\n")
write(ub_root, "docs/handoff-archive.md", "# Archive\n")
write(ub_root, "docs/handoff/H126-blocker.md",
      "### H126 — T126: blocker\n\nAuthor: Codex | Date: 2026-11-24 | Status: open | For: either\n\nTouches: notes.md.\n")
write(ub_root, "docs/handoff/H127-dep.md",
      "### H127 — T127: dependent\n\nAuthor: Codex | Date: 2026-11-24 | Status: queued (after H126) | For: either\n\nTouches: other.md.\n")
write(ub_root, "docs/handoff/H128-other.md",
      "### H128 — T128: second blocker\n\nAuthor: Codex | Date: 2026-11-24 | Status: open | For: either\n\nTouches: z.md.\n")
write(ub_root, "docs/handoff/H129-multi.md",
      "### H129 — T129: multi dep\n\nAuthor: Codex | Date: 2026-11-24 | Status: queued (after H126, H128) | For: either\n\nTouches: m.md.\n")
write(ub_root, "BOARD.md",
      f"# Work board\n\nOrder: H126, H128, H127, H129\n\n## Jobs\n\n{job.START}\n\n(none)\n\n{job.END}\n")
write(ub_root, "docs/agent-handoff.md",
      "# Handoff\n\n## Open exchanges\n\n<!-- open list: built from docs/handoff/ by tools/handoff.py; don't edit by "
      "hand -->\n\n(none open)\n\n<!-- end of open list -->\n\n## Archived\n")
write(ub_root, "notes.md", "one\n")
sh(ub_root, "git", "add", "-A"); sh(ub_root, "git", "commit", "-qm", "base")
sh(ub_root, "git", "push", "-q", "-u", "origin", "main")

# Branch for H126 (no Result line so --push without --yes pushes immediately).
sh(ub_root, "git", "checkout", "-qb", "claude/h126-blocker")
write(ub_root, "notes.md", "two\n")
write(ub_root, "docs/handoff/H126-blocker.md",
      "### H126 — T126: blocker\n\nAuthor: Codex | Date: 2026-11-24 | Status: answered | For: either\n\nTouches: notes.md.\n\nResponse: done.\n")
sh(ub_root, "git", "add", "-A"); sh(ub_root, "git", "commit", "-qm", "H126 done")
sh(ub_root, "git", "checkout", "-q", "main")
open(job.state_path(ub_root), "w").write(json.dumps({"jobs": {"H126": {"branch": "claude/h126-blocker", "state": "done"}}, "events": []}))
integrator.take(integrator.lock_path(ub_root), "tester", out=lambda *a: None)

cwd = os.getcwd(); os.chdir(ub_root)
out_ub = io.StringIO()
try:
    with contextlib.redirect_stdout(out_ub):
        rc_ub = integrate.main(["claude/h126-blocker", "--as", "tester", "--no-gate", "--push"])
finally:
    os.chdir(cwd)
said_ub = out_ub.getvalue()
h127_main = open(os.path.join(ub_root, "docs/handoff/H127-dep.md"), encoding="utf-8").read()
h129_main = open(os.path.join(ub_root, "docs/handoff/H129-multi.md"), encoding="utf-8").read()
board_main = open(os.path.join(ub_root, "BOARD.md"), encoding="utf-8").read()
h127_origin = sh(ub_root, "git", "show", "origin/main:docs/handoff/H127-dep.md").stdout
board_origin = sh(ub_root, "git", "show", "origin/main:BOARD.md").stdout
check("integrate --push unblocks H127 to Status: open on main and origin/main",
      rc_ub == 0 and "| Status: open |" in h127_main and "| Status: open |" in h127_origin
      and "unblocked H127 (after H126)" in said_ub, (rc_ub, h127_main, said_ub))
check("integrate --push rebuilds BOARD.md with H127 Ready on main and origin/main",
      "| H127 | either | **Ready** |" in board_main and "| H127 | either | **Ready** |" in board_origin, board_main)
check("partial dep resolution rewrites H129 to queued (after H128) and keeps it Queued",
      "| Status: queued (after H128) |" in h129_main and "| H129 | either | Queued |" in board_main,
      (h129_main, board_main))
shutil.rmtree(ub_base)

# Merging a branch that added a ruling file and one that edited an old row ends tidy
r_tmp = tempfile.mkdtemp(prefix="int-ruling-")
r_dir = os.path.join(r_tmp, "rulings")
r_base_live = (
    "# Log\n\n## Subjects\n\n| Subject | Covers | Decisions |\n|---|---|---|\n| Snapping | Snap. | I10 |\n\n"
    "## Principles\n\n| ID | Principle | Status |\n|---|---|---|\n| G01 | Keep it simple. | Active |\n\n"
    "## Decisions\n\n### Snapping\n\n| ID | Decision | Status |\n|---|---|---|\n| I10 | Snap corners. | Active |\n\n"
    "## Details\n"
)
r_base_arch = "# Archive\n\n## Superseded decisions\n\n| ID | Decision | Status |\n|---|---|---|\n\n## Details\n"
import integrate
import sort_decision_log
sort_decision_log.write_entry(r_dir, "G01", sort_decision_log.format_ruling("G01", "Keep it simple.", "Active", "2026-11-22"))
sort_decision_log.write_entry(r_dir, "I10", sort_decision_log.format_ruling("I10", "Snap corners.", "Active", "2026-11-21", subject="Snapping", principles="G01"))
sort_decision_log.write_entry(r_dir, "I11", sort_decision_log.format_ruling("I11", "Snap edges.", "Active", "2026-11-26", subject="Snapping", principles="G01"))
theirs_old_row = r_base_live.replace(
    "| I10 | Snap corners. | Active |",
    "| I10 | Snap corners. | Active |\n\n"
    "| ID | Decision | Status | Replaces / replaced by | Why | Principles | Where in the code | Date |\n"
    "|---|---|---|---|---|---|---|---|\n"
    "| I12 | Snap midpoints. | Active |  | Helpful. | G01 | snap.gd | 2026-11-22 |",
)
settled_pair, asks_r = integrate.settle_log((r_base_live, r_base_arch), (r_base_live, r_base_arch), (theirs_old_row, r_base_arch), rulings_dir=r_dir)
check("merging a branch that added a ruling file and one that edited an old row ends tidy",
      not asks_r
      and sort_decision_log.check_files(*settled_pair, rulings_dir=r_dir) == []
      and os.path.isfile(os.path.join(r_dir, "I12.md"))
      and "| I11 | Snap edges. | Active |" in settled_pair[0]
      and "| I12 | Snap midpoints. | Active |" in settled_pair[0]
      and "Helpful." not in settled_pair[0])
shutil.rmtree(r_tmp)

w_tmp = tempfile.mkdtemp(prefix="int-work-")
w_dir = os.path.join(w_tmp, "03_Past_Decisions", "work")
w_log = "# Log\n\n## Work list\n\n| # | Item | Status |\n|---|---|---|\n| T7 | Mirror fix. | Open |\n"
w_arch = "# Archive\n\n## Done work\n\n| # | Item | Status |\n|---|---|---|\n"
os.makedirs(os.path.join(w_tmp, "03_Past_Decisions"), exist_ok=True)
open(os.path.join(w_tmp, "03_Past_Decisions", "decision-log.md"), "w", encoding="utf-8").write(w_log)
open(os.path.join(w_tmp, "03_Past_Decisions", "decision-archive.md"), "w", encoding="utf-8").write(w_arch)
sort_decision_log.write_entry(w_dir, "T7", sort_decision_log.format_work("T7", "Mirror fix.", "Open", covers="A26"))
rel_res, msg_res = integrate.record_result(w_tmp, "T7", "abc1234", "quicktest passed.", "def5678")
check("a job's Result line is appended to its Work list file",
      rel_res == "03_Past_Decisions/work/T7.md"
      and "Result (abc1234, merged def5678): quicktest passed." in open(os.path.join(w_dir, "T7.md"), encoding="utf-8").read())
msg_done = integrate.set_status(w_tmp, "T7", "Done")
check("--status Done keeps the file and moves its index line",
      "moved to 03_Past_Decisions/decision-archive.md" in msg_done
      and os.path.isfile(os.path.join(w_dir, "T7.md"))
      and "Status: Done" in open(os.path.join(w_dir, "T7.md"), encoding="utf-8").read()
      and "| T7 |" not in open(os.path.join(w_tmp, "03_Past_Decisions", "decision-log.md"), encoding="utf-8").read()
      and "| T7 | Mirror fix. | Done |" in open(os.path.join(w_tmp, "03_Past_Decisions", "decision-archive.md"), encoding="utf-8").read())
shutil.rmtree(w_tmp)

# Completes: marks item Done at merge after recording Result; without it, board_statuses leaves On the board or Open
c_root = repo()
write(c_root, "03_Past_Decisions/decision-log.md",
      "# Log\n\n## Work list\n\n| # | Item | Status |\n|---|---|---|\n"
      "| T1 | First. | On the board (H090) |\n| T2 | Second. | On the board (H091, H092) |\n| T3 | Third. | On the board (H093) |\n")
write(c_root, "03_Past_Decisions/decision-archive.md",
      "# Archive\n\n## Done work\n\n| # | Item | Status |\n|---|---|---|\n")
c_wdir = os.path.join(c_root, "03_Past_Decisions", "work")
sort_decision_log.write_entry(c_wdir, "T1", sort_decision_log.format_work("T1", "First.", "On the board (H090)"))
sort_decision_log.write_entry(c_wdir, "T2", sort_decision_log.format_work("T2", "Second.", "On the board (H091, H092)"))
sort_decision_log.write_entry(c_wdir, "T3", sort_decision_log.format_work("T3", "Third.", "On the board (H093)"))
write(c_root, "docs/handoff/H092-t2-other.md",
      "### H092 — T2: other job\n\nAuthor: Claude | Date: 2026-11-26 | Status: open | For: either\n")
sh(c_root, "git", "add", "-A"); sh(c_root, "git", "commit", "-qm", "setup work items")

sh(c_root, "git", "checkout", "-qb", "agent/completes-t1")
write(c_root, "docs/handoff/H090-t1.md",
      "### H090 — T1: finish it\n\nAuthor: Gemini | Date: 2026-11-26 | Status: answered | For: either\n\n"
      "Completes: T1\n\nResult: 1111aaa; tests 1/1; done T1\n")
sh(c_root, "git", "add", "-A"); sh(c_root, "git", "commit", "-qm", "H090 answered")
sh(c_root, "git", "checkout", "-q", "main")
integrator.take(integrator.lock_path(c_root), "tester", out=lambda *a: None)
cwd = os.getcwd(); os.chdir(c_root)
try:
    with contextlib.redirect_stdout(io.StringIO()):
        rc_c1 = integrate.main(["agent/completes-t1", "--as", "tester", "--no-gate"])
finally:
    os.chdir(cwd)
t1_final = open(os.path.join(c_wdir, "T1.md"), encoding="utf-8").read()
check("a job with Completes: marks its item Done at merge",
      rc_c1 == 0 and "Status: Done" in t1_final and "Result (1111aaa" in t1_final
      and "| T1 | First. | Done |" in open(os.path.join(c_root, "03_Past_Decisions/decision-archive.md"), encoding="utf-8").read(),
      t1_final)

sh(c_root, "git", "checkout", "-qb", "agent/partial-t2-t3")
write(c_root, "docs/handoff/H091-t2.md",
      "### H091 — T2: step 1\n\nAuthor: Gemini | Date: 2026-11-26 | Status: answered | For: either\n\n"
      "Result: 2222bbb; tests 1/1; step 1 T2\n")
write(c_root, "docs/handoff/H093-t3.md",
      "### H093 — T3: step 1\n\nAuthor: Gemini | Date: 2026-11-26 | Status: answered | For: either\n\n"
      "Result: 3333ccc; tests 1/1; step 1 T3\n")
sh(c_root, "git", "add", "-A"); sh(c_root, "git", "commit", "-qm", "H091 and H093 answered")
sh(c_root, "git", "checkout", "-q", "main")
cwd = os.getcwd(); os.chdir(c_root)
try:
    with contextlib.redirect_stdout(io.StringIO()):
        rc_c2 = integrate.main(["agent/partial-t2-t3", "--as", "tester", "--no-gate"])
finally:
    os.chdir(cwd)
t2_final = open(os.path.join(c_wdir, "T2.md"), encoding="utf-8").read()
t3_final = open(os.path.join(c_wdir, "T3.md"), encoding="utf-8").read()
check("a merged job without it leaves the item On the board while another job remains, else Open with the Result",
      rc_c2 == 0 and "Status: On the board (H092)" in t2_final and "Result (2222bbb" in t2_final
      and "step merged (H091)" in t2_final
      and "Status: Open" in t3_final and "Result (3333ccc" in t3_final
      and "step merged (H093)" in t3_final,
      (t2_final, t3_final))
shutil.rmtree(c_root)

# Merging a branch made before Process rulings moved to comitatus: keeps its edit to P16 and moves P-new-1 -> comitatus
m_org = os.path.realpath(tempfile.mkdtemp(prefix="int-comitatus-"))
m_proj = os.path.join(m_org, "08_Code_Bases", "Proj")
m_org_rdir = os.path.join(m_org, "03_Past_Decisions", "rulings")
m_proj_rdir = os.path.join(m_proj, "03_Past_Decisions", "rulings")
os.makedirs(m_org_rdir)
os.makedirs(m_proj_rdir)
os.makedirs(os.path.join(m_proj, "03_Past_Decisions", "work"))
os.makedirs(os.path.join(m_proj, "03_Past_Decisions", "questions"))
os.makedirs(os.path.join(m_proj, "docs", "handoff"))
for r in (m_org, m_proj):
    for c in (["init", "-q", "-b", "main"], ["config", "user.email", "t@example.invalid"], ["config", "user.name", "t"],
              ["commit", "-q", "--allow-empty", "-m", "base"]):
        sh(r, "git", *c)
write(m_proj, "03_Past_Decisions/decision-log.md",
      "# Log\n\n## Subjects\n\n| Subject | Covers | Decisions |\n|---|---|---|\n"
      "| Process | Agents. | P16 |\n\n"
      "## Principles\n\n| ID | Principle | Status | Explains | Date |\n|---|---|---|---|---|\n"
      "| G01 | Simple. | Active | — | 2026-11-22 |\n\n"
      "## Decisions\n\n### Process\n\n| ID | Decision | Status |\n|---|---|---|\n| P16 | Integrator merges. | Active |\n\n"
      "## Open questions\n\n| ID | Question | Status | Notes |\n|---|---|---|---|\n\n"
      "## Work list\n\n| ID | Item | Status | Covers | Result / next step |\n|---|---|---|---|---|\n"
      "| T1 | Move rulings. | Open |  |  |\n\n"
      "## Tunables\n\n| Setting | Value | What it does | File | Decision |\n|---|---|---|---|---|\n")
write(m_proj, "03_Past_Decisions/decision-archive.md",
      "# Archive\n\n## Superseded decisions\n\n| ID | Decision | Status | Principles | Where | Date |\n|---|---|---|---|---|---|\n\n"
      "## Decided questions\n\n| ID | Question | Status | Notes |\n|---|---|---|---|\n\n"
      "## Done work\n\n| ID | Item | Status | Covers | Result / next step |\n|---|---|---|---|---|\n")
write(m_proj, "03_Past_Decisions/work/T1.md", "# T1 — Move rulings.\n\nStatus: Open\n\nMove rulings.\n")
write(m_proj, "03_Past_Decisions/rulings/G01.md", "# G01 — Simple.\n\nStatus: Active | Date: 2026-11-22\n\nSimple.\n")
write(m_proj, "03_Past_Decisions/rulings/P16.md",
      "# P16 — Integrator merges.\n\nStatus: Active | Subject: Process | Principles: G01 | Date: 2026-11-22\n\nIntegrator merges.\n")
write(m_proj, "docs/agent-handoff.md",
      "# Agent handoff\n\n## Open\n\n<!-- open list: built from docs/handoff/ by tools/handoff.py; don't edit by hand -->\n"
      "<!-- end of open list -->\n\n## Archived\n\n")
write(m_proj, "docs/handoff-archive.md", "# Handoff archive\n\n## Archived\n\n")
sh(m_proj, "git", "add", "-A"); sh(m_proj, "git", "commit", "-qm", "before move")

# Old branch created before P16 moved: edits P16 and adds P-new-1
sh(m_proj, "git", "checkout", "-qb", "agent/old-branch")
write(m_proj, "03_Past_Decisions/rulings/P16.md",
      "# P16 — Integrator merges.\n\nStatus: Active | Subject: Process | Principles: G01 | Date: 2026-11-22\n\n"
      "Integrator merges (updated on old branch).\n")
write(m_proj, "03_Past_Decisions/rulings/P-new-1.md",
      "# P-new-1 — New process rule.\n\nStatus: Active | Subject: Process | Principles: G01 | Date: 2026-11-27\n\n"
      "New process rule.\n")
write(m_proj, "docs/handoff/H099-t1.md",
      "### H099 — T1: work\n\nAuthor: Gemini | Date: 2026-11-27 | Status: answered | For: either\n\n"
      "Result: abc1234; tests 1/1; updated P16 and added P-new-1\n")
sh(m_proj, "git", "add", "-A"); sh(m_proj, "git", "commit", "-qm", "old branch changes")

# Main moves P16 to comitatus
sh(m_proj, "git", "checkout", "-q", "main")
shutil.move(os.path.join(m_proj_rdir, "P16.md"), os.path.join(m_org_rdir, "P16.md"))
sh(m_org, "git", "add", "-A"); sh(m_org, "git", "commit", "-qm", "move P16")
sh(m_proj, "git", "add", "-A"); sh(m_proj, "git", "commit", "-qm", "remove P16 from napkin")
integrate.integrator.take(integrate.integrator.lock_path(m_proj), "tester")

old_env = os.environ.get("NAPKIN_COMITATUS")
os.environ.pop("NAPKIN_COMITATUS", None)
cwd = os.getcwd(); os.chdir(m_proj)
try:
    with contextlib.redirect_stdout(io.StringIO()):
        rc_m = integrate.main(["agent/old-branch", "--as", "tester", "--no-gate", "--status", "T1=Done"])
finally:
    os.chdir(cwd)
    if old_env is not None:
        os.environ["NAPKIN_COMITATUS"] = old_env

p16_after = open(os.path.join(m_org_rdir, "P16.md"), encoding="utf-8").read() if os.path.isfile(os.path.join(m_org_rdir, "P16.md")) else ""
p17_after = open(os.path.join(m_org_rdir, "P17.md"), encoding="utf-8").read() if os.path.isfile(os.path.join(m_org_rdir, "P17.md")) else ""
check("merging pre-move branch moves P-new-1 and P16 edit to comitatus only, keeping the edit",
      rc_m == 0
      and not os.path.exists(os.path.join(m_proj_rdir, "P16.md"))
      and not os.path.exists(os.path.join(m_proj_rdir, "P17.md"))
      and "updated on old branch" in p16_after
      and "New process rule." in p17_after,
      (rc_m, os.listdir(m_proj_rdir), os.listdir(m_org_rdir)))
shutil.rmtree(m_org)

# H175 item 1: settle_handoff three-way on hand-written text, rebuilt generated lists, conflict stops when both change
h_root = repo()
write(h_root, "docs/agent-handoff.md",
      f"# Agent handoff\n\n## How to\n\nOriginal rule.\n\n## Open exchanges\n\n{integrate.handoff.START}\n\n(none open)\n\n{integrate.handoff.END}\n\n"
      "## Archived\n\nFull entries in [handoff-archive.md](handoff-archive.md).\n\nOlder: docs/handoff-archive.md (0 entries; find one with grep \"^### H0NN\" docs/handoff-archive.md)\n")
write(h_root, "docs/handoff-archive.md", "# Archive\n")
write(h_root, "docs/handoff/H010-one.md", "### H010 — One\n\nAuthor: Gemini | Date: 2026-11-27 | Status: open | For: gemini\n")
sh(h_root, "git", "add", "-A"); sh(h_root, "git", "commit", "-qm", "handoff base")

sh(h_root, "git", "checkout", "-qb", "agent/handoff-rewrite")
write(h_root, "docs/agent-handoff.md",
      f"# Agent handoff\n\n## How to\n\nUpdated rule on branch.\n\n## Open exchanges\n\n{integrate.handoff.START}\n\n- old\n\n{integrate.handoff.END}\n\n"
      "## Archived\n\nFull entries in [handoff-archive.md](handoff-archive.md).\n")
write(h_root, "docs/handoff/H010-one.md",
      "### H010 — One\n\nAuthor: Gemini | Date: 2026-11-27 | Status: answered | For: gemini\n\nResult: aaa1111; tests 1/1; ok\n")
sh(h_root, "git", "add", "-A"); sh(h_root, "git", "commit", "-qm", "branch rewrites how-to")

sh(h_root, "git", "checkout", "-q", "main")
write(h_root, "docs/handoff/H011-two.md", "### H011 — Two\n\nAuthor: Gemini | Date: 2026-11-27 | Status: open | For: gemini\n")
integrate.handoff.tidy(h_root)
sh(h_root, "git", "add", "-A"); sh(h_root, "git", "commit", "-qm", "main adds H011")
integrate.integrator.take(integrate.integrator.lock_path(h_root), "tester")
cwd = os.getcwd(); os.chdir(h_root)
try:
    with contextlib.redirect_stdout(io.StringIO()):
        rc_h1 = integrate.main(["agent/handoff-rewrite", "--as", "tester", "--no-gate"])
finally:
    os.chdir(cwd)
h_after = open(os.path.join(h_root, "docs/agent-handoff.md"), encoding="utf-8").read()
check("settle_handoff takes branch's hand-written text when main only changed generated lists, and tidies lists",
      rc_h1 == 0 and "Updated rule on branch." in h_after and "H011" in h_after and "H010 — One. Resolved:" in h_after,
      (rc_h1, h_after))

sh(h_root, "git", "checkout", "-qb", "agent/handoff-clash")
write(h_root, "docs/agent-handoff.md", h_after.replace("Updated rule on branch.", "Branch clash edit."))
sh(h_root, "git", "add", "-A"); sh(h_root, "git", "commit", "-qm", "branch clash")
sh(h_root, "git", "checkout", "-q", "main")
write(h_root, "docs/agent-handoff.md", h_after.replace("Updated rule on branch.", "Main clash edit."))
sh(h_root, "git", "add", "-A"); sh(h_root, "git", "commit", "-qm", "main clash")
cwd = os.getcwd(); os.chdir(h_root)
buf_hc = io.StringIO()
try:
    with contextlib.redirect_stdout(buf_hc):
        rc_hc = integrate.main(["agent/handoff-clash", "--as", "tester", "--no-gate"])
finally:
    os.chdir(cwd)
check("settle_handoff stops with a conflict when both main and branch changed hand-written text",
      rc_hc == 1 and "both changed" in buf_hc.getvalue(), (rc_hc, buf_hc.getvalue()))
sh(h_root, "git", "merge", "--abort")
shutil.rmtree(h_root)

# H175 item 3: --continue --regate after gate failure (fails if gate still fails, finishes on pass, removes state file)
g_root = repo()
write(g_root, "tools/gate.sh", "#!/bin/sh\ntest -f ok.txt\n")
os.chmod(os.path.join(g_root, "tools/gate.sh"), 0o755)
write(g_root, "ok.txt", "ok\n")
write(g_root, "docs/handoff/H050-gate.md", "### H050 — T1: gate test\n\nAuthor: Gemini | Date: 2026-11-27 | Status: open | For: gemini\n")
write(g_root, "03_Past_Decisions/decision-log.md", "# Log\n\n## Work list\n\n| # | Item | Status |\n|---|---|---|\n| T1 | Gate. | On the board (H050) |\n")
write(g_root, "03_Past_Decisions/decision-archive.md", "# Archive\n\n## Done work\n\n| # | Item | Status |\n|---|---|---|\n")
sh(g_root, "git", "add", "-A"); sh(g_root, "git", "commit", "-qm", "gate base")

sh(g_root, "git", "checkout", "-qb", "agent/gate-fail")
os.remove(os.path.join(g_root, "ok.txt"))
write(g_root, "docs/handoff/H050-gate.md",
      "### H050 — T1: gate test\n\nAuthor: Gemini | Date: 2026-11-27 | Status: answered | For: gemini\n\n"
      "Completes: T1\n\nResult: bbb2222; tests 1/1; fixed\n")
sh(g_root, "git", "add", "-A"); sh(g_root, "git", "commit", "-qm", "breaks gate")
sh(g_root, "git", "checkout", "-q", "main")
integrate.integrator.take(integrate.integrator.lock_path(g_root), "tester")
cwd = os.getcwd(); os.chdir(g_root)
try:
    with contextlib.redirect_stdout(io.StringIO()):
        rc_gf = integrate.main(["agent/gate-fail", "--as", "tester"])
    sf = integrate.state_file(g_root)
    has_state_after_fail = os.path.isfile(sf)
    with contextlib.redirect_stdout(io.StringIO()) as b_noreg:
        rc_noreg = integrate.main(["--continue", "--as", "tester"])
    with contextlib.redirect_stdout(io.StringIO()) as b_stillfail:
        rc_stillfail = integrate.main(["--continue", "--regate", "--as", "tester"])
    still_paused = os.path.isfile(sf) and sh(g_root, "git", "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0
    write(g_root, "ok.txt", "fixed\n")
    with contextlib.redirect_stdout(io.StringIO()) as b_pass:
        rc_pass = integrate.main(["--continue", "--regate", "--as", "tester"])
finally:
    os.chdir(cwd)
check("gate failure saves state; --continue without --regate or with still-failing gate refuses; --continue --regate finishes on pass and removes state",
      rc_gf == 1 and has_state_after_fail
      and rc_noreg == 1 and "--regate" in b_noreg.getvalue()
      and rc_stillfail == 1 and still_paused
      and rc_pass == 0 and not os.path.isfile(integrate.state_file(g_root))
      and "| T1 | Gate. | Done |" in open(os.path.join(g_root, "03_Past_Decisions/decision-archive.md"), encoding="utf-8").read(),
      (rc_gf, has_state_after_fail, rc_noreg, rc_stillfail, still_paused, rc_pass, b_pass.getvalue()))
shutil.rmtree(g_root)

# H175 item 2: merged log is tidied with both rulings folders before the gate runs
l_org = os.path.realpath(tempfile.mkdtemp(prefix="log-tidy-gate-"))
l_proj = os.path.join(l_org, "08_Code_Bases", "Proj")
l_org_r = os.path.join(l_org, "03_Past_Decisions", "rulings")
l_proj_r = os.path.join(l_proj, "03_Past_Decisions", "rulings")
os.makedirs(l_org_r); os.makedirs(l_proj_r)
sh(l_org, "git", "init", "-q", "-b", "main")
sh(l_org, "git", "config", "user.email", "t@example.invalid"); sh(l_org, "git", "config", "user.name", "T")
open(os.path.join(l_org_r, "P01.md"), "w").write("# P01 — Org.\n\nStatus: Active | Subject: Process | Principles: — | Date: 2026-11-22\n\nOrg.\n")
sh(l_org, "git", "add", "-A"); sh(l_org, "git", "commit", "-qm", "org")
sh(l_proj, "git", "init", "-q", "-b", "main")
sh(l_proj, "git", "config", "user.email", "t@example.invalid"); sh(l_proj, "git", "config", "user.name", "T")
write(l_proj, "03_Past_Decisions/decision-log.md",
      "# Log\n\n## Subjects\n\n| Subject | Purpose |\n|---|---|\n| Process | Process. |\n\n"
      "## Decisions\n\n### Process\n\n| ID | Decision | Status | Date | Summary |\n|---|---|---|---|---|\n"
      "| P01 | Org. | Active | 2026-11-22 | Org. |\n\n## Work list\n\n| # | Item | Status |\n|---|---|---|\n")
write(l_proj, "03_Past_Decisions/decision-archive.md", "# Archive\n\n## Superseded decisions\n\n| ID | Decision | Status | Date | Summary |\n|---|---|---|---|---|\n\n## Done work\n\n| # | Item | Status |\n|---|---|---|\n")
write(l_proj, "docs/handoff-archive.md", "# Archive\n")
write(l_proj, "docs/agent-handoff.md", f"# Handoff\n\n{integrate.handoff.START}\n\n{integrate.handoff.END}\n")
write(l_proj, "tools/gate.sh", "#!/bin/sh\ngrep -q '| P02 |' 03_Past_Decisions/decision-log.md && grep -q '| P01 |' 03_Past_Decisions/decision-log.md\n")
os.chmod(os.path.join(l_proj, "tools/gate.sh"), 0o755)
sh(l_proj, "git", "add", "-A"); sh(l_proj, "git", "commit", "-qm", "base")
sh(l_proj, "git", "checkout", "-qb", "agent/new-p")
write(l_proj, "03_Past_Decisions/rulings/P-new-1.md", "# P-new-1 — New.\n\nStatus: Active | Subject: Process | Principles: — | Date: 2026-11-27\n\nNew.\n")
write(l_proj, "docs/handoff/H060-p.md", "### H060 — P\n\nAuthor: Gemini | Date: 2026-11-27 | Status: answered | For: gemini\n\nResult: ccc3333; tests 1/1; ok\n")
sh(l_proj, "git", "add", "-A"); sh(l_proj, "git", "commit", "-qm", "new process ruling")
sh(l_proj, "git", "checkout", "-q", "main")
integrate.integrator.take(integrate.integrator.lock_path(l_proj), "tester")
old_env_l = os.environ.get("NAPKIN_COMITATUS")
os.environ.pop("NAPKIN_COMITATUS", None)
cwd = os.getcwd(); os.chdir(l_proj)
buf_lt = io.StringIO()
try:
    with contextlib.redirect_stdout(buf_lt):
        rc_lt = integrate.main(["agent/new-p", "--as", "tester"])
finally:
    os.chdir(cwd)
    if old_env_l is not None:
        os.environ["NAPKIN_COMITATUS"] = old_env_l
check("merged log is tidied with both rulings folders before gate.sh runs", rc_lt == 0, (rc_lt, buf_lt.getvalue()))
shutil.rmtree(l_org)

# 15. Structure step (H180 / P31): added files need `owns`, added deps need `uses`; header-only & no-change pass.
def structure_repo(setup_branch):
    r = repo()
    os.makedirs(os.path.join(r, "worker"), exist_ok=True)
    write(r, "worker/common.py", '"""Common helpers."""\n\ndef helper():\n    return 1\n')
    write(r, "worker/app.py", '"""Main app."""\n\ndef run():\n    return 0\n')
    body, _ = integrate.architecture_map.build_map(integrate.Path(r))
    write(r, "ARCHITECTURE.md", f"# Arch\n\n{integrate.architecture_map.START}\n\n{body}\n\n{integrate.architecture_map.END}\n")
    write(r, "docs/dependency-map.md", integrate.dependency_map.render_map(integrate.Path(r)))
    sh(r, "git", "add", "-A"); sh(r, "git", "commit", "-qm", "base with maps")
    sh(r, "git", "checkout", "-qb", "agent/struct")
    setup_branch(r)
    sh(r, "git", "add", "-A"); sh(r, "git", "commit", "-qm", "branch change")
    sh(r, "git", "checkout", "-q", "main")
    integrator.take(integrator.lock_path(r), "tester", out=lambda *a: None)
    return r


def run_struct(r, *extra_args):
    buf = io.StringIO()
    cwd = os.getcwd(); os.chdir(r)
    try:
        with contextlib.redirect_stdout(buf):
            rc_s = integrate.main([*extra_args, "--as", "tester", "--no-gate"])
    finally:
        os.chdir(cwd)
    return rc_s, buf.getvalue()


# 15a. Added file without `owns` stops staged; --continue accepts it.
r_s = structure_repo(lambda r: (
    write(r, "worker/extra.py", '"""Extra module."""\n'),
    write(r, "docs/handoff/H090-extra.md", "### H090 — T1: add extra\n\nAuthor: Gemini | Status: answered\n\nResult: aaa1111; tests pass; added extra\n"),
))
rc_s, out_s = run_struct(r_s, "agent/struct")
check("added file without owns stops staged with structure explanation",
      rc_s == 0 and "added file: extra.py" in out_s and "structure: extra.py added, not explained" in out_s
      and sh(r_s, "git", "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0, out_s)
rc_c, out_c = run_struct(r_s, "--continue")
check("--continue after unexplained structure accepts and commits",
      rc_c == 0 and not os.path.exists(integrate.state_file(r_s)), out_c)
shutil.rmtree(r_s)

# 15b. Added file WITH `owns` (short name) and --impact merges without structure stop.
r_s = structure_repo(lambda r: (
    write(r, "worker/extra.py", '"""Extra module."""\n'),
    write(r, "docs/handoff/H090-extra.md",
          "### H090 — T1: add extra\n\nAuthor: Gemini | Status: answered\n\n"
          "Architecture: extra.py owns extra state\n"
          "Result: aaa1111; tests pass; added extra\n"),
))
rc_s, out_s = run_struct(r_s, "agent/struct", "--impact", "auto-generated map")
check("added file with owns merges without structure stop",
      rc_s == 0 and "added file: extra.py" in out_s and "not explained" not in out_s
      and sh(r_s, "git", "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode != 0, out_s)
shutil.rmtree(r_s)

# 15c. Added dependency without `uses` stops staged; with `uses` (short names) merges cleanly.
r_s = structure_repo(lambda r: (
    write(r, "worker/app.py", '"""Main app."""\nimport common\n\ndef run():\n    return common.helper()\n'),
    write(r, "docs/handoff/H090-dep.md", "### H090 — T1: use common\n\nAuthor: Gemini | Status: answered\n\nResult: bbb2222; tests pass; use common\n"),
))
rc_s, out_s = run_struct(r_s, "agent/struct")
check("added dependency without uses stops staged",
      rc_s == 0 and "added dep: app.py uses common.py" in out_s
      and "structure: app.py now uses common.py, not explained" in out_s
      and sh(r_s, "git", "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0, out_s)
shutil.rmtree(r_s)

r_s = structure_repo(lambda r: (
    write(r, "worker/app.py", '"""Main app."""\nimport common\n\ndef run():\n    return common.helper()\n'),
    write(r, "docs/handoff/H090-dep.md",
          "### H090 — T1: use common\n\nAuthor: Gemini | Status: answered\n\n"
          "Architecture: app.py uses common.py: needs helper()\n"
          "Result: bbb2222; tests pass; use common\n"),
))
rc_s, out_s = run_struct(r_s, "agent/struct", "--impact", "auto-generated map")
check("added dependency with uses (short names) merges without stop",
      rc_s == 0 and "added dep: app.py uses common.py" in out_s and "not explained" not in out_s
      and sh(r_s, "git", "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode != 0, out_s)
shutil.rmtree(r_s)

# 15d. Header-only change prints change and merges without stopping.
r_s = structure_repo(lambda r: (
    write(r, "worker/app.py", '"""Updated main app."""\n\ndef run():\n    return 0\n'),
    write(r, "docs/handoff/H090-hdr.md", "### H090 — T1: header only\n\nAuthor: Gemini | Status: answered\n\nResult: ccc3333; tests pass; header only\n"),
))
rc_s, out_s = run_struct(r_s, "agent/struct")
check("header-only change prints change and merges without stopping",
      rc_s == 0 and "changed header: app.py: Main app -> Updated main app" in out_s and "not explained" not in out_s, out_s)
shutil.rmtree(r_s)

# 15e. No structural change prints nothing about structure and merges cleanly.
r_s = structure_repo(lambda r: (
    write(r, "worker/app.py", '"""Main app."""\n\ndef run():\n    return 42\n'),
    write(r, "docs/handoff/H090-none.md", "### H090 — T1: body only\n\nAuthor: Gemini | Status: answered\n\nResult: ddd4444; tests pass; body only\n"),
))
rc_s, out_s = run_struct(r_s, "agent/struct")
check("no structural change prints nothing about structure",
      rc_s == 0 and "structure:" not in out_s, out_s)
shutil.rmtree(r_s)

# 16. H185: MERGE_THE_BATCH.py / integrate.main(["--batch", ...])
# 16a. Stacking order: job 2 based on job 1 listed FIRST in Order still merges job 1 first;
#      job 3 built on a branch not in the batch is left out with a reason.
b_base = tempfile.mkdtemp(prefix="int-batch-")
b_origin = os.path.join(b_base, "origin.git")
b_root = os.path.join(b_base, "repo")
sh(b_base, "git", "init", "--bare", "-q", b_origin)
sh(b_base, "git", "clone", "-q", b_origin, b_root)
sh(b_root, "git", "config", "user.email", "t@example.invalid")
sh(b_root, "git", "config", "user.name", "T")
sh(b_root, "git", "checkout", "-qb", "main")
os.makedirs(os.path.join(b_root, "docs", "handoff"))
write(b_root, "03_Past_Decisions/decision-log.md", "# Log\n\n## Work list\n\n| # | Item | Status |\n|---|---|---|\n| T1 | a | Open |\n| T2 | b | Open |\n")
write(b_root, "docs/handoff-archive.md", "# Archive\n")
write(b_root, "docs/agent-handoff.md",
      "# Handoff\n\n## Open exchanges\n\n<!-- open list: built from docs/handoff/ by tools/handoff.py; don't edit by hand -->\n\n(none open)\n\n<!-- end of open list -->\n\n## Archived\n")
write(b_root, "docs/handoff/H201-first.md", "### H201 — T1: first\n\nAuthor: Gemini | Date: 2026-11-27 | Status: open | For: gemini\n\nTouches: app.txt.\n")
write(b_root, "docs/handoff/H202-second.md", "### H202 — T2: second\n\nAuthor: Gemini | Date: 2026-11-27 | Status: open | For: gemini\n\nTouches: app.txt.\n")
write(b_root, "docs/handoff/H203-orphan.md", "### H203 — orphan\n\nAuthor: Gemini | Date: 2026-11-27 | Status: open | For: gemini\n\nTouches: other.txt.\n")
write(b_root, "BOARD.md", f"# Work board\n\nOrder: H202, H201, H203\nPace: one at a time\n\n## Jobs\n\n{job.START}\n\n(none)\n\n{job.END}\n")
write(b_root, "app.txt", "v0\n")
write(b_root, "tools/gate.sh", "#!/bin/sh\necho 'gate: PASS'\nexit 0\n")
os.chmod(os.path.join(b_root, "tools/gate.sh"), 0o755)
sh(b_root, "git", "add", "-A"); sh(b_root, "git", "commit", "-qm", "base"); sh(b_root, "git", "push", "-q", "-u", "origin", "main")

# Create H201 branch from main
sh(b_root, "git", "checkout", "-qb", "gemini/h201-first")
write(b_root, "app.txt", "v1\n")
write(b_root, "docs/handoff/H201-first.md",
      "### H201 — T1: first\n\nAuthor: Gemini | Date: 2026-11-27 | Status: answered | For: gemini\n\nTouches: app.txt.\n\n## Response\n\nChanged from the brief: kept v1 short.\nResult: 1111111; tests pass; v1\n")
sh(b_root, "git", "add", "-A"); sh(b_root, "git", "commit", "-qm", "H201 done")

# Create H202 branch stacked on H201
sh(b_root, "git", "checkout", "-qb", "gemini/h202-second")
write(b_root, "app.txt", "v1\nv2\n")
write(b_root, "docs/handoff/H202-second.md",
      "### H202 — T2: second\n\nAuthor: Gemini | Date: 2026-11-27 | Status: answered | For: gemini\n\nTouches: app.txt.\n\nResponse: done.\nResult: 2222222; tests pass; v2\n")
sh(b_root, "git", "add", "-A"); sh(b_root, "git", "commit", "-qm", "H202 done")

# Create H203 branch stacked on a returned branch not in the batch
sh(b_root, "git", "checkout", "-q", "main")
sh(b_root, "git", "checkout", "-qb", "gemini/h203-orphan")
write(b_root, "other.txt", "x\n")
sh(b_root, "git", "add", "-A"); sh(b_root, "git", "commit", "-qm", "H203 done")
sh(b_root, "git", "checkout", "-q", "main")

open(job.state_path(b_root), "w").write(json.dumps({
    "jobs": {
        "H201": {"branch": "gemini/h201-first", "state": "done"},
        "H202": {"branch": "gemini/h202-second", "state": "done", "base": "gemini/h201-first"},
        "H203": {"branch": "gemini/h203-orphan", "state": "done", "base": "gemini/h200-returned"},
    },
    "events": [],
}))
integrator.take(integrator.lock_path(b_root), "tester", out=lambda *a: None)

# Dry-run checks order and left-out reason
cwd = os.getcwd(); os.chdir(b_root)
buf_dry = io.StringIO()
try:
    with contextlib.redirect_stdout(buf_dry):
        rc_dry = integrate.main(["--batch", "--dry-run"])
finally:
    os.chdir(cwd)
dry_s = buf_dry.getvalue()
check("batch --dry-run orders H201 before H202 (even with H202 first in Order) and leaves out H203",
      rc_dry == 0 and "would merge in order: H201 (gemini/h201-first), H202 (gemini/h202-second)" in dry_s
      and "left out H203 (gemini/h203-orphan): built on gemini/h200-returned" in dry_s, dry_s)

# 16b. Failing gate resets main back to pre_batch and pushes nothing
write(b_root, "tools/gate.sh", "#!/bin/sh\necho 'gate: FAIL'\nexit 1\n")
os.chmod(os.path.join(b_root, "tools/gate.sh"), 0o755)
sh(b_root, "git", "add", "tools/gate.sh"); sh(b_root, "git", "commit", "-qm", "failing gate")
sh(b_root, "git", "push", "-q", "origin", "main")
pre_fail_sha = sh(b_root, "git", "rev-parse", "HEAD").stdout.strip()
cwd = os.getcwd(); os.chdir(b_root)
buf_fail1, buf_fail2 = io.StringIO(), io.StringIO()
try:
    with contextlib.redirect_stdout(buf_fail1):
        rc_f1 = integrate.main(["--batch", "--push", "--yes"])
    with contextlib.redirect_stdout(buf_fail2):
        rc_f2 = integrate.main(["--batch", "--continue", "--push", "--yes"])
finally:
    os.chdir(cwd)
fail2_s = buf_fail2.getvalue()
check("batch gate failure resets main to pre-batch commit, pushes nothing, and lists MERGE_JOB.py commands",
      rc_f1 == 0 and "H201: changed: kept v1 short." in buf_fail1.getvalue()
      and rc_f2 == 1 and sh(b_root, "git", "rev-parse", "HEAD").stdout.strip() == pre_fail_sha
      and sh(b_root, "git", "rev-parse", "origin/main").stdout.strip() == pre_fail_sha
      and "MERGE_JOB.py gemini/h201-first" in fail2_s and "MERGE_JOB.py gemini/h202-second" in fail2_s,
      (rc_f1, rc_f2, sh(b_root, "git", "rev-parse", "HEAD").stdout.strip(), pre_fail_sha, fail2_s))

# 16c. Passing gate merges both, pauses once for review, then --continue runs gate once and pushes once
write(b_root, "tools/gate.sh", "#!/bin/sh\necho 'gate: PASS'\nexit 0\n")
os.chmod(os.path.join(b_root, "tools/gate.sh"), 0o755)
sh(b_root, "git", "add", "tools/gate.sh"); sh(b_root, "git", "commit", "-qm", "passing gate")
sh(b_root, "git", "push", "-q", "origin", "main")
cwd = os.getcwd(); os.chdir(b_root)
buf_ok1, buf_ok2 = io.StringIO(), io.StringIO()
try:
    with contextlib.redirect_stdout(buf_ok1):
        rc_ok1 = integrate.main(["--batch", "--push", "--yes"])
    with contextlib.redirect_stdout(buf_ok2):
        rc_ok2 = integrate.main(["--batch", "--continue", "--push", "--yes"])
finally:
    os.chdir(cwd)
st_after_batch = job.read_state(job.state_path(b_root))
check("batch merge with --continue runs gate once, marks H201/H202 merged, leaves H203 done, and pushes",
      rc_ok1 == 0 and rc_ok2 == 0
      and open(os.path.join(b_root, "app.txt")).read() == "v1\nv2\n"
      and st_after_batch["jobs"]["H201"]["state"] == "merged"
      and st_after_batch["jobs"]["H202"]["state"] == "merged"
      and st_after_batch["jobs"]["H203"]["state"] == "done"
      and sh(b_root, "git", "rev-parse", "HEAD").stdout.strip() == sh(b_root, "git", "rev-parse", "origin/main").stdout.strip(),
      (rc_ok1, rc_ok2, buf_ok1.getvalue(), buf_ok2.getvalue(), st_after_batch))
shutil.rmtree(b_base)

print(f"INTEGRATE TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
raise SystemExit(0 if all(RESULTS) else 1)   # a failed check fails the run, not only its summary
